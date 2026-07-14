#!/usr/bin/env python3
"""Build and validate deterministic stable release bundles without network access."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import re
import subprocess
import sys
import tarfile
import tempfile
from typing import Any


MANIFEST_NAME = "harness-manifest.json"
ARCHIVE_NAME = "agentic-project-harness-template.tar.gz"
CHECKSUMS_NAME = "SHA256SUMS"
INSTALLER_NAME = "install.sh"
MANIFEST_SCHEMA = "agentic-project-harness.release-bundle/v1"
CHANNEL = "stable"
OWNERSHIP_CLASSES = {"harness-managed", "generated-config", "project-owned"}
REQUIRED_ARTIFACTS = (INSTALLER_NAME, ARCHIVE_NAME, MANIFEST_NAME, CHECKSUMS_NAME)


class BundleError(Exception):
    """A release bundle violated a stable-contract safety invariant."""


def fail(message: str) -> None:
    raise BundleError(message)


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def run_git(source: Path, *args: str) -> str:
    completed = subprocess.run(
        ["git", "-C", str(source), *args],
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    if completed.returncode:
        detail = completed.stderr.strip() or completed.stdout.strip()
        fail(f"git {' '.join(args)} failed: {detail}")
    return completed.stdout


def checked_source(source: Path) -> tuple[str, list[str]]:
    if not source.is_dir():
        fail(f"source directory does not exist: {source}")
    if run_git(source, "status", "--porcelain=v1").strip():
        fail("source worktree is dirty")
    commit = run_git(source, "rev-parse", "--verify", "HEAD^{commit}").strip()
    if len(commit) != 40 or any(character not in "0123456789abcdef" for character in commit):
        fail("source commit is not a full SHA-1 object id")
    paths = run_git(source, "ls-files", "-z").split("\0")
    paths = [path for path in paths if path]
    if not paths:
        fail("source has no tracked files")
    return commit, sorted(paths)


def safe_relative_path(value: str) -> PurePosixPath:
    path = PurePosixPath(value)
    if (
        not value
        or not path.parts
        or value != path.as_posix()
        or path.is_absolute()
        or "\\" in value
        or any(part in ("", ".", "..") for part in path.parts)
    ):
        fail(f"unsafe archive path: {value!r}")
    return path


def safe_archive_symlink(member_name: str, target: str) -> None:
    if not target or target.startswith("/") or "\\" in target:
        fail(f"symlink escapes archive: {member_name}")
    components: list[str] = []
    for part in (*PurePosixPath(member_name).parent.parts, *PurePosixPath(target).parts):
        if part in ("", "."):
            continue
        if part == "..":
            if not components:
                fail(f"symlink escapes archive: {member_name}")
            components.pop()
        else:
            components.append(part)


def source_entry(source: Path, relative: str) -> tuple[Path, str, bytes]:
    safe_relative_path(relative)
    path = source / relative
    try:
        path.lstat()
    except FileNotFoundError:
        fail(f"tracked file is missing from source: {relative}")
    if os.path.islink(path):
        target = os.readlink(path)
        if os.path.isabs(target) or not target:
            fail(f"symlink escapes source: {relative}")
        resolved = (path.parent / target).resolve()
        try:
            resolved.relative_to(source.resolve())
        except ValueError:
            fail(f"symlink escapes source: {relative}")
        if not resolved.exists():
            fail(f"symlink target is missing: {relative}")
        return path, "symlink", target.encode("utf-8")
    if not os.path.isfile(path):
        fail(f"tracked path is not a regular file or symlink: {relative}")
    return path, "file", path.read_bytes()


def ownership_for(relative: str) -> str:
    """Classify shipped files for baseline-aware adoption and update policy."""
    project_owned_exact = {
        "README.md",
        "docs/active-work.md",
        "docs/backlog.md",
        "docs/direction.md",
        "docs/overview.md",
        "docs/project-state.json",
        "docs/thread-registry.md",
    }
    project_owned_prefixes = (
        "docs/decisions/",
        "docs/implementation-reports/",
        "docs/prds/",
        "docs/requirements/",
        "docs/review-packets/",
        "docs/state/",
        "docs/tickets/",
    )
    generated_exact = {".agent-harness.json", "docs/index.html"}
    generated_prefixes = (".codex/agents/",)
    if relative in project_owned_exact or relative.startswith(project_owned_prefixes):
        return "project-owned"
    if relative in generated_exact or relative == ".codex/config.toml" or relative.startswith(generated_prefixes):
        return "generated-config"
    return "harness-managed"


def version_from_source(source: Path) -> str:
    version_path = source / "VERSION"
    if not version_path.is_file():
        fail("source is missing VERSION")
    version = version_path.read_text(encoding="utf-8").strip()
    if re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+", version) is None:
        fail("VERSION must contain one stable semantic version")
    return version


def validate_tag(version: str, tag: str) -> None:
    if not tag.startswith("v"):
        fail("stable tag must be v-prefixed")
    if tag != f"v{version}":
        fail(f"stable tag {tag!r} does not match VERSION {version!r}")


def parse_upgrade_origins(values: list[str]) -> dict[str, dict[str, str | None]]:
    """Parse TAG=COMMIT[,MANIFEST_SHA256] immutable upgrade anchors."""
    origins: dict[str, dict[str, str | None]] = {}
    for value in values:
        match = re.fullmatch(
            r"(v[0-9]+\.[0-9]+\.[0-9]+)=([0-9a-f]{40})(?:,([0-9a-f]{64}))?",
            value,
        )
        if match is None:
            fail(
                "upgrade origins must use TAG=FULL_COMMIT[,MANIFEST_SHA256]"
            )
        tag, commit, manifest_sha256 = match.groups()
        if tag in origins:
            fail(f"duplicate supported upgrade origin: {tag}")
        origins[tag] = {
            "source_commit": commit,
            "manifest_sha256": manifest_sha256,
        }
    if not origins:
        fail("at least one immutable stable upgrade origin is required")
    return dict(sorted(origins.items()))


def archive_bytes(entries: list[dict[str, Any]]) -> bytes:
    buffer = io.BytesIO()
    with gzip.GzipFile(fileobj=buffer, mode="wb", mtime=0, filename="") as compressed:
        with tarfile.open(fileobj=compressed, mode="w", format=tarfile.PAX_FORMAT) as archive:
            for entry in entries:
                info = tarfile.TarInfo(entry["path"])
                info.uid = 0
                info.gid = 0
                info.uname = ""
                info.gname = ""
                info.mtime = 0
                info.mode = entry["mode"]
                if entry["kind"] == "symlink":
                    info.type = tarfile.SYMTYPE
                    info.linkname = entry["link_target"]
                    info.size = 0
                    archive.addfile(info)
                else:
                    data = entry["data"]
                    info.size = len(data)
                    archive.addfile(info, io.BytesIO(data))
    return buffer.getvalue()


def write_bytes(path: Path, data: bytes, mode: int = 0o644) -> None:
    path.write_bytes(data)
    path.chmod(mode)


def build(args: argparse.Namespace) -> None:
    source = Path(args.source).resolve()
    output = Path(args.output).resolve()
    commit, paths = checked_source(source)
    version = version_from_source(source)
    validate_tag(version, args.tag)
    origins = parse_upgrade_origins(args.supported_upgrade_origin)
    if args.tag in origins:
        fail("the target release cannot list itself as an upgrade origin")
    if output.exists() and (not output.is_dir() or any(output.iterdir())):
        fail("output directory must be absent or empty")
    if output == source or source in output.parents:
        fail("output directory must not be inside the source directory")

    entries: list[dict[str, Any]] = []
    for relative in paths:
        path, kind, data = source_entry(source, relative)
        entries.append(
            {
                "path": relative,
                "kind": kind,
                "data": data,
                "link_target": data.decode("utf-8") if kind == "symlink" else None,
                "mode": 0o755 if kind == "file" and path.stat().st_mode & 0o111 else 0o644,
                "ownership": ownership_for(relative),
                "sha256": sha256_bytes(data),
            }
        )
    if INSTALLER_NAME not in {entry["path"] for entry in entries}:
        fail("source is missing required install.sh")

    archive = archive_bytes(entries)
    installer = next(entry for entry in entries if entry["path"] == INSTALLER_NAME)
    manifest = {
        "schema": MANIFEST_SCHEMA,
        "version": version,
        "source_commit": commit,
        "stable_tag": args.tag,
        "supported_upgrade_origins": list(origins),
        "upgrade_origins": origins,
        "state_schema_version": args.state_schema_version,
        "channel": CHANNEL,
        "files": [
            {
                "path": entry["path"],
                "kind": entry["kind"],
                "ownership": entry["ownership"],
                "sha256": entry["sha256"],
            }
            for entry in entries
        ],
        "artifacts": {
            INSTALLER_NAME: installer["sha256"],
            ARCHIVE_NAME: sha256_bytes(archive),
        },
    }
    manifest_bytes = (json.dumps(manifest, indent=2, sort_keys=True) + "\n").encode("utf-8")
    checksums = {
        INSTALLER_NAME: installer["sha256"],
        ARCHIVE_NAME: sha256_bytes(archive),
        MANIFEST_NAME: sha256_bytes(manifest_bytes),
    }
    checksum_bytes = "".join(f"{checksums[name]}  {name}\n" for name in sorted(checksums)).encode("utf-8")

    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=output.parent, prefix=f".{output.name}.tmp-") as temporary:
        staging = Path(temporary)
        write_bytes(staging / INSTALLER_NAME, installer["data"], installer["mode"])
        write_bytes(staging / ARCHIVE_NAME, archive)
        write_bytes(staging / MANIFEST_NAME, manifest_bytes)
        write_bytes(staging / CHECKSUMS_NAME, checksum_bytes)
        validate_bundle(staging)
        output.mkdir(exist_ok=True)
        for name in REQUIRED_ARTIFACTS:
            os.replace(staging / name, output / name)
    print(json.dumps({"output": str(output), "tag": args.tag, "version": version}, sort_keys=True))


def load_manifest(path: Path) -> dict[str, Any]:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        fail(f"invalid manifest: {error}")
    if not isinstance(raw, dict):
        fail("manifest must be an object")
    return raw


def is_sha256(value: Any) -> bool:
    return isinstance(value, str) and len(value) == 64 and all(char in "0123456789abcdef" for char in value)


def is_git_commit(value: Any) -> bool:
    return isinstance(value, str) and len(value) == 40 and all(char in "0123456789abcdef" for char in value)


def validate_manifest(manifest: dict[str, Any]) -> dict[str, dict[str, Any]]:
    required = {
        "schema", "version", "source_commit", "stable_tag", "supported_upgrade_origins", "upgrade_origins",
        "state_schema_version", "channel", "files", "artifacts",
    }
    if set(manifest) != required:
        fail("manifest keys do not match the stable contract")
    if manifest["schema"] != MANIFEST_SCHEMA or manifest["channel"] != CHANNEL:
        fail("manifest is not a stable release-bundle manifest")
    if not isinstance(manifest["version"], str) or re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+", manifest["version"]) is None:
        fail("manifest version is invalid")
    validate_tag(manifest["version"], manifest["stable_tag"])
    if not is_git_commit(manifest["source_commit"]):
        fail("manifest source_commit must be a full immutable commit hash")
    if type(manifest["state_schema_version"]) is not int or manifest["state_schema_version"] < 1:
        fail("manifest state_schema_version must be a positive integer")
    origins = manifest["supported_upgrade_origins"]
    if not isinstance(origins, list) or not origins or origins != sorted(set(origins)) or any(not isinstance(origin, str) or re.fullmatch(r"v[0-9]+\.[0-9]+\.[0-9]+", origin) is None for origin in origins):
        fail("manifest supported_upgrade_origins must be sorted unique v-prefixed tags")
    origin_records = manifest["upgrade_origins"]
    if not isinstance(origin_records, dict) or list(origin_records) != origins:
        fail("manifest upgrade_origins must exactly anchor every supported origin")
    for tag, record in origin_records.items():
        if (
            not isinstance(record, dict)
            or set(record) != {"source_commit", "manifest_sha256"}
            or not is_git_commit(record.get("source_commit"))
            or (
                record.get("manifest_sha256") is not None
                and not is_sha256(record.get("manifest_sha256"))
            )
        ):
            fail(f"manifest upgrade origin is invalid: {tag}")
    artifacts = manifest["artifacts"]
    if set(artifacts) != {INSTALLER_NAME, ARCHIVE_NAME} or any(not is_sha256(value) for value in artifacts.values()):
        fail("manifest artifact checksums are invalid")
    files = manifest["files"]
    if not isinstance(files, list) or not files:
        fail("manifest files must be a non-empty list")
    indexed: dict[str, dict[str, Any]] = {}
    for entry in files:
        if not isinstance(entry, dict) or set(entry) != {"path", "kind", "ownership", "sha256"}:
            fail("manifest file entry is invalid")
        path = entry["path"]
        safe_relative_path(path)
        if entry["kind"] not in ("file", "symlink") or entry["ownership"] not in OWNERSHIP_CLASSES or not is_sha256(entry["sha256"]):
            fail(f"manifest file metadata is invalid: {path}")
        if path in indexed:
            fail(f"duplicate manifest path: {path}")
        indexed[path] = entry
    if list(indexed) != sorted(indexed):
        fail("manifest files must be sorted by path")
    if INSTALLER_NAME not in indexed or indexed[INSTALLER_NAME]["kind"] != "file":
        fail("manifest is missing regular install.sh")
    return indexed


def parse_checksums(path: Path) -> dict[str, str]:
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as error:
        fail(f"cannot read SHA256SUMS: {error}")
    parsed: dict[str, str] = {}
    for line in lines:
        parts = line.split("  ")
        if len(parts) != 2 or not is_sha256(parts[0]) or parts[1] not in (INSTALLER_NAME, ARCHIVE_NAME, MANIFEST_NAME):
            fail("SHA256SUMS contains an invalid entry")
        if parts[1] in parsed:
            fail(f"SHA256SUMS contains duplicate entry: {parts[1]}")
        parsed[parts[1]] = parts[0]
    if set(parsed) != {INSTALLER_NAME, ARCHIVE_NAME, MANIFEST_NAME}:
        fail("SHA256SUMS is missing a required artifact")
    return parsed


def validate_archive(path: Path, files: dict[str, dict[str, Any]]) -> None:
    try:
        archive = tarfile.open(path, mode="r:gz")
    except (OSError, tarfile.TarError) as error:
        fail(f"invalid archive: {error}")
    with archive:
        members = archive.getmembers()
        names: set[str] = set()
        for member in members:
            safe_relative_path(member.name)
            if member.name in names:
                fail(f"duplicate archive path: {member.name}")
            names.add(member.name)
            if member.isdir() or member.islnk() or member.isdev() or member.isfifo() or not (member.isfile() or member.issym()):
                fail(f"unsafe archive entry type: {member.name}")
            if member.issym():
                target = member.linkname
                safe_archive_symlink(member.name, target)
                data = target.encode("utf-8")
                kind = "symlink"
            else:
                extracted = archive.extractfile(member)
                if extracted is None:
                    fail(f"cannot read archive member: {member.name}")
                data = extracted.read()
                kind = "file"
            expected = files.get(member.name)
            if expected is None or expected["kind"] != kind or expected["sha256"] != sha256_bytes(data):
                fail(f"archive member does not match manifest: {member.name}")
        if names != set(files):
            fail("archive paths do not exactly match manifest files")


def validate_bundle(bundle: Path) -> None:
    if not bundle.is_dir():
        fail(f"bundle directory does not exist: {bundle}")
    for name in REQUIRED_ARTIFACTS:
        if not (bundle / name).is_file():
            fail(f"missing required artifact: {name}")
    manifest = load_manifest(bundle / MANIFEST_NAME)
    files = validate_manifest(manifest)
    checksums = parse_checksums(bundle / CHECKSUMS_NAME)
    for name, expected in checksums.items():
        actual = sha256_file(bundle / name)
        if actual != expected:
            fail(f"checksum mismatch: {name}")
    for name, expected in manifest["artifacts"].items():
        if sha256_file(bundle / name) != expected:
            fail(f"manifest artifact checksum mismatch: {name}")
    if sha256_file(bundle / INSTALLER_NAME) != files[INSTALLER_NAME]["sha256"]:
        fail("install.sh does not match manifest file checksum")
    validate_archive(bundle / ARCHIVE_NAME, files)


def validate(args: argparse.Namespace) -> None:
    bundle = Path(args.bundle).resolve()
    validate_bundle(bundle)
    print(json.dumps({"bundle": str(bundle), "valid": True}, sort_keys=True))


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    commands = result.add_subparsers(dest="command", required=True)
    build_parser = commands.add_parser("build", help="build a stable bundle from a clean Git source")
    build_parser.add_argument("--source", required=True, help="clean Git checkout to package")
    build_parser.add_argument("--output", required=True, help="absent or empty artifact directory")
    build_parser.add_argument("--tag", required=True, help="stable v-prefixed tag matching VERSION")
    build_parser.add_argument(
        "--supported-upgrade-origin",
        action="append",
        default=[],
        metavar="TAG=COMMIT[,MANIFEST_SHA256]",
        help="immutable prior stable anchor; repeatable",
    )
    build_parser.add_argument("--state-schema-version", type=int, default=1, help="positive operational state schema version")
    build_parser.set_defaults(handler=build)
    validate_parser = commands.add_parser("validate", help="fail closed on an invalid stable bundle")
    validate_parser.add_argument("--bundle", required=True, help="artifact directory to validate")
    validate_parser.set_defaults(handler=validate)
    return result


def main() -> int:
    try:
        args = parser().parse_args()
        args.handler(args)
    except BundleError as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
