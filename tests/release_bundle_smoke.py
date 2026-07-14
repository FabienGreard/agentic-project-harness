#!/usr/bin/env python3
"""Focused disposable-Git smoke coverage for tools/release_bundle.py."""

from __future__ import annotations

import gzip
import hashlib
import io
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile
import tempfile


ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / "tools" / "release_bundle.py"


def run(*args: str, expected: int = 0) -> subprocess.CompletedProcess[str]:
    completed = subprocess.run(args, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if completed.returncode != expected:
        raise AssertionError(
            f"expected {expected}, got {completed.returncode}: {' '.join(args)}\nstdout: {completed.stdout}\nstderr: {completed.stderr}"
        )
    return completed


def build(source: Path, output: Path, tag: str = "v0.5.0", expected: int = 0) -> subprocess.CompletedProcess[str]:
    origin_commit = run("git", "-C", str(source), "rev-parse", "HEAD").stdout.strip()
    return run(
        sys.executable, str(TOOL), "build", "--source", str(source), "--output", str(output),
        "--tag", tag, "--supported-upgrade-origin", f"v0.4.0={origin_commit}", "--state-schema-version", "1", expected=expected,
    )


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def make_fixture(root: Path) -> Path:
    source = root / "source"
    source.mkdir()
    (source / "VERSION").write_text("0.5.0\n", encoding="utf-8")
    (source / "install.sh").write_text("#!/usr/bin/env bash\necho installer\n", encoding="utf-8")
    (source / "install.sh").chmod(0o755)
    (source / "docs").mkdir()
    (source / "docs" / "state.txt").write_text("state\n", encoding="utf-8")
    (source / ".codex").mkdir()
    (source / ".codex" / "skills").symlink_to("../docs")
    run("git", "init", "-q", str(source))
    run("git", "-C", str(source), "config", "user.email", "smoke@example.test")
    run("git", "-C", str(source), "config", "user.name", "Release Smoke")
    run("git", "-C", str(source), "add", ".")
    run("git", "-C", str(source), "commit", "-qm", "fixture")
    return source


def assert_failure(completed: subprocess.CompletedProcess[str], message: str) -> None:
    if message not in completed.stderr:
        raise AssertionError(f"expected {message!r} in {completed.stderr!r}")


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="release-bundle-smoke-") as temporary:
        root = Path(temporary)
        source = make_fixture(root)
        output = root / "bundle"

        build(source, output)
        repeated = root / "bundle-repeat"
        build(source, repeated)
        expected = {"install.sh", "agentic-project-harness-template.tar.gz", "harness-manifest.json", "SHA256SUMS"}
        if {path.name for path in output.iterdir()} != expected:
            raise AssertionError("bundle artifact set is incomplete")
        if {path.name: sha256(path) for path in output.iterdir()} != {path.name: sha256(path) for path in repeated.iterdir()}:
            raise AssertionError("clean source builds are not deterministic")
        validated = run(sys.executable, str(TOOL), "validate", "--bundle", str(output))
        if json.loads(validated.stdout) != {"bundle": str(output.resolve()), "valid": True}:
            raise AssertionError("validator did not return the stable success result")

        boolean_state_schema = root / "boolean-state-schema"
        shutil.copytree(output, boolean_state_schema)
        boolean_manifest_path = boolean_state_schema / "harness-manifest.json"
        boolean_manifest = json.loads(boolean_manifest_path.read_text(encoding="utf-8"))
        boolean_manifest["state_schema_version"] = True
        boolean_manifest_path.write_text(
            json.dumps(boolean_manifest, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        checksum_names = [
            line.split("  ")[1]
            for line in (boolean_state_schema / "SHA256SUMS")
            .read_text(encoding="utf-8")
            .splitlines()
        ]
        (boolean_state_schema / "SHA256SUMS").write_text(
            "\n".join(
                f"{sha256(boolean_state_schema / name)}  {name}"
                for name in checksum_names
            )
            + "\n",
            encoding="utf-8",
        )
        assert_failure(
            run(
                sys.executable,
                str(TOOL),
                "validate",
                "--bundle",
                str(boolean_state_schema),
                expected=1,
            ),
            "state_schema_version must be a positive integer",
        )

        manifest = json.loads((output / "harness-manifest.json").read_text(encoding="utf-8"))
        if manifest["schema"] != "agentic-project-harness.release-bundle/v1" or manifest["channel"] != "stable":
            raise AssertionError("manifest lacks stable contract metadata")
        if manifest["stable_tag"] != "v0.5.0" or manifest["supported_upgrade_origins"] != ["v0.4.0"]:
            raise AssertionError("manifest release provenance is wrong")
        if manifest["upgrade_origins"]["v0.4.0"]["source_commit"] != run(
            "git", "-C", str(source), "rev-parse", "HEAD"
        ).stdout.strip():
            raise AssertionError("manifest upgrade origin is not commit-anchored")
        if manifest["artifacts"]["install.sh"] != sha256(output / "install.sh"):
            raise AssertionError("manifest installer checksum is wrong")
        with tarfile.open(output / "agentic-project-harness-template.tar.gz", "r:gz") as archive:
            names = archive.getnames()
            if names != [entry["path"] for entry in manifest["files"]]:
                raise AssertionError("archive order does not match manifest order")
            link = archive.getmember(".codex/skills")
            if not link.issym() or link.linkname != "../docs":
                raise AssertionError("internal symlink was not preserved safely")

        dirty = root / "dirty"
        shutil.copytree(source, dirty, symlinks=True)
        (dirty / "docs" / "state.txt").write_text("dirty\n", encoding="utf-8")
        assert_failure(build(dirty, root / "dirty-bundle", expected=1), "source worktree is dirty")
        assert_failure(build(source, root / "bad-tag", tag="0.5.0", expected=1), "v-prefixed")
        assert_failure(build(source, root / "mismatch-tag", tag="v9.9.9", expected=1), "does not match VERSION")

        escaped = root / "escaped"
        shutil.copytree(source, escaped, symlinks=True)
        (escaped / ".codex" / "skills").unlink()
        (escaped / ".codex" / "skills").symlink_to("../../etc")
        run("git", "-C", str(escaped), "add", ".codex/skills")
        run("git", "-C", str(escaped), "commit", "-qm", "escape")
        assert_failure(build(escaped, root / "escaped-bundle", expected=1), "symlink escapes source")

        tampered = root / "tampered"
        shutil.copytree(output, tampered)
        (tampered / "install.sh").write_text("tampered\n", encoding="utf-8")
        assert_failure(run(sys.executable, str(TOOL), "validate", "--bundle", str(tampered), expected=1), "checksum mismatch: install.sh")

        unsafe = root / "unsafe"
        shutil.copytree(output, unsafe)
        with gzip.GzipFile(filename="", mode="wb", fileobj=(unsafe / "agentic-project-harness-template.tar.gz").open("wb"), mtime=0) as compressed:
            with tarfile.open(fileobj=compressed, mode="w") as archive:
                info = tarfile.TarInfo("../escape")
                info.size = 1
                archive.addfile(info, fileobj=io.BytesIO(b"x"))
        unsafe_manifest = json.loads((unsafe / "harness-manifest.json").read_text(encoding="utf-8"))
        unsafe_manifest["artifacts"]["agentic-project-harness-template.tar.gz"] = sha256(unsafe / "agentic-project-harness-template.tar.gz")
        manifest_bytes = (json.dumps(unsafe_manifest, indent=2, sort_keys=True) + "\n").encode("utf-8")
        (unsafe / "harness-manifest.json").write_bytes(manifest_bytes)
        sums = (unsafe / "SHA256SUMS").read_text(encoding="utf-8").splitlines()
        (unsafe / "SHA256SUMS").write_text(
            "\n".join(
                f"{sha256(unsafe / line.split('  ')[1])}  {line.split('  ')[1]}" for line in sums
            ) + "\n", encoding="utf-8"
        )
        assert_failure(run(sys.executable, str(TOOL), "validate", "--bundle", str(unsafe), expected=1), "unsafe archive path")
    print("release bundle smoke passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
