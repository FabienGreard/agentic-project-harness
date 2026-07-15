#!/usr/bin/env python3
"""Build and validate deterministic Baton stable-release payloads."""

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


MANIFEST_NAME = "baton-manifest.json"
NEW_PROJECT_ARCHIVE = "baton-new-project.tar.gz"
ADOPTION_ARCHIVE = "baton-adoption.tar.gz"
CHECKSUMS_NAME = "SHA256SUMS"
INSTALLER_NAME = "install.sh"
INSTALLER_SOURCE = "scripts/install.sh"
CLASSIFICATION_NAME = "release/source-classification.json"
MANIFEST_SCHEMA = "baton.release-bundle/v1"
CLASSIFICATION_SCHEMA = "baton.source-classification/v1"
CHANNEL = "stable"
SOURCE_CLASSES = {"source-only", "template-only", "adoption-runtime", "shared"}
PAYLOADS = {
    "new-project": NEW_PROJECT_ARCHIVE,
    "adoption": ADOPTION_ARCHIVE,
}
REQUIRED_ARTIFACTS = (
    INSTALLER_NAME,
    NEW_PROJECT_ARCHIVE,
    ADOPTION_ARCHIVE,
    MANIFEST_NAME,
    CHECKSUMS_NAME,
)


class BundleError(RuntimeError):
    """A release input or artifact violated the Baton safety contract."""


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
        fail(completed.stderr.strip() or completed.stdout.strip() or "git command failed")
    return completed.stdout


def tracked_paths(source: Path) -> list[str]:
    paths = [item for item in run_git(source, "ls-files", "-z").split("\0") if item]
    if not paths:
        fail("source repository has no tracked files")
    return sorted(paths)


def checked_source(source: Path) -> tuple[str, list[str]]:
    if not source.is_dir():
        fail(f"source directory does not exist: {source}")
    if run_git(source, "status", "--porcelain=v1").strip():
        fail("source worktree is dirty")
    commit = run_git(source, "rev-parse", "--verify", "HEAD^{commit}").strip()
    if not re.fullmatch(r"[0-9a-f]{40}", commit):
        fail("source commit is not a full immutable SHA")
    return commit, tracked_paths(source)


def safe_path(raw: str) -> PurePosixPath:
    path = PurePosixPath(raw)
    if (
        not raw
        or raw != path.as_posix()
        or path.is_absolute()
        or "\\" in raw
        or any(part in {"", ".", ".."} for part in path.parts)
    ):
        fail(f"unsafe path: {raw!r}")
    return path


def source_entry(source: Path, relative: str) -> dict[str, Any]:
    safe_path(relative)
    path = source / relative
    try:
        path.lstat()
    except FileNotFoundError:
        fail(f"tracked source path is missing: {relative}")
    if path.is_symlink():
        target = os.readlink(path)
        if not target or os.path.isabs(target):
            fail(f"unsafe source symlink: {relative}")
        resolved = (path.parent / target).resolve(strict=False)
        root = source.resolve()
        if resolved != root and root not in resolved.parents:
            fail(f"source symlink escapes the repository: {relative}")
        return {
            "kind": "symlink",
            "data": target.encode("utf-8"),
            "link_target": target,
            "mode": 0o777,
        }
    if not path.is_file():
        fail(f"unsupported source path type: {relative}")
    return {
        "kind": "file",
        "data": path.read_bytes(),
        "link_target": None,
        "mode": 0o755 if path.stat().st_mode & 0o111 else 0o644,
    }


def inferred_class(relative: str) -> str:
    if relative == "template/.baton/integration/README.md":
        return "adoption-runtime"
    if relative.startswith("template/.baton/"):
        payload_relative = relative.removeprefix("template/")
        template_prefixes = (
            ".baton/state/",
            ".baton/dashboard/",
            ".baton/docs/",
            ".baton/decisions/",
            ".baton/implementation-reports/",
            ".baton/prds/",
            ".baton/review-packets/",
            ".baton/tickets/",
        )
        if payload_relative == ".baton/thread-registry.md" or payload_relative.startswith(template_prefixes):
            return "template-only"
        return "shared"
    return "source-only"


def classification_document(paths: list[str]) -> dict[str, Any]:
    return {
        "schema": CLASSIFICATION_SCHEMA,
        "files": {path: inferred_class(path) for path in paths},
    }


def load_classification(source: Path, paths: list[str]) -> dict[str, str]:
    path = source / CLASSIFICATION_NAME
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        fail(f"invalid source classification: {error}")
    if not isinstance(raw, dict) or set(raw) != {"schema", "files"}:
        fail("source classification keys do not match the contract")
    if raw["schema"] != CLASSIFICATION_SCHEMA or not isinstance(raw["files"], dict):
        fail("source classification schema is invalid")
    records = raw["files"]
    if set(records) != set(paths):
        missing = sorted(set(paths) - set(records))
        stale = sorted(set(records) - set(paths))
        fail(f"source classification drift; missing={missing}, stale={stale}")
    for relative, value in records.items():
        safe_path(relative)
        if value not in SOURCE_CLASSES:
            fail(f"unsupported source classification for {relative}: {value!r}")
        expected = inferred_class(relative)
        if value != expected:
            fail(f"source classification policy mismatch for {relative}: expected {expected}, got {value}")
    return dict(sorted(records.items()))


def classify(args: argparse.Namespace) -> None:
    source = Path(args.source).resolve()
    paths = tracked_paths(source)
    document = classification_document(paths)
    destination = source / CLASSIFICATION_NAME
    if args.write:
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(json.dumps(document, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    else:
        existing = load_classification(source, paths)
        document = {"schema": CLASSIFICATION_SCHEMA, "files": existing}
    counts = {name: list(document["files"].values()).count(name) for name in sorted(SOURCE_CLASSES)}
    print(json.dumps({"ok": True, "path": str(destination), "files": len(paths), "counts": counts}, sort_keys=True))


def payload_path(source_path: str, classification: str, payload: str) -> str | None:
    prefix = "template/"
    if not source_path.startswith(prefix) or classification == "source-only":
        return None
    relative = source_path.removeprefix(prefix)
    if payload == "new-project":
        if classification == "adoption-runtime":
            return None
        return relative
    if classification == "shared" or classification == "adoption-runtime":
        return relative
    if classification == "template-only":
        if not relative.startswith(".baton/"):
            fail(f"template-only source is outside .baton: {source_path}")
        return ".baton/integration/starter/" + relative.removeprefix(".baton/")
    return None


def payload_entries(source: Path, classifications: dict[str, str], payload: str) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    seen: set[str] = set()
    for source_path, classification in classifications.items():
        destination = payload_path(source_path, classification, payload)
        if destination is None:
            continue
        safe_path(destination)
        if destination in seen:
            fail(f"duplicate {payload} payload path: {destination}")
        seen.add(destination)
        entry = source_entry(source, source_path)
        entries.append(
            {
                "path": destination,
                "source_path": source_path,
                "classification": classification,
                "kind": entry["kind"],
                "data": entry["data"],
                "link_target": entry["link_target"],
                "mode": entry["mode"],
                "sha256": sha256_bytes(entry["data"]),
            }
        )
    entries.sort(key=lambda item: item["path"])
    if not entries or entries[0]["path"] == "":
        fail(f"{payload} payload is empty")
    forbidden = {
        "install.sh", "README.md", "VERSION", "LICENSE", "CHANGELOG.md",
        "CONTRIBUTING.md", "SECURITY.md", "CODE_OF_CONDUCT.md",
    }
    bad = [entry["path"] for entry in entries if entry["path"] in forbidden or not entry["path"].startswith(".baton/")]
    if bad:
        fail(f"{payload} payload contains forbidden consumer paths: {bad}")
    return entries


def archive_bytes(entries: list[dict[str, Any]]) -> bytes:
    buffer = io.BytesIO()
    with gzip.GzipFile(fileobj=buffer, mode="wb", mtime=0, filename="") as compressed:
        with tarfile.open(fileobj=compressed, mode="w", format=tarfile.PAX_FORMAT) as archive:
            for entry in entries:
                info = tarfile.TarInfo(entry["path"])
                info.uid = info.gid = 0
                info.uname = info.gname = ""
                info.mtime = 0
                info.mode = entry["mode"]
                if entry["kind"] == "symlink":
                    info.type = tarfile.SYMTYPE
                    info.linkname = entry["link_target"]
                    info.size = 0
                    archive.addfile(info)
                else:
                    info.size = len(entry["data"])
                    archive.addfile(info, io.BytesIO(entry["data"]))
    return buffer.getvalue()


def parse_origins(values: list[str]) -> dict[str, dict[str, str]]:
    result: dict[str, dict[str, str]] = {}
    for raw in values:
        match = re.fullmatch(r"(v[0-9]+\.[0-9]+\.[0-9]+)=([0-9a-f]{40}),([0-9a-f]{64})", raw)
        if match is None:
            fail("upgrade origins must use TAG=FULL_COMMIT,MANIFEST_SHA256")
        tag, commit, manifest_sha = match.groups()
        if tag in result:
            fail(f"duplicate upgrade origin: {tag}")
        result[tag] = {"sourceCommit": commit, "manifestSha256": manifest_sha}
    return dict(sorted(result.items()))


def version_from_source(source: Path) -> str:
    try:
        version = (source / "VERSION").read_text(encoding="utf-8").strip()
    except OSError as error:
        fail(f"cannot read source VERSION: {error}")
    if re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+", version) is None:
        fail("VERSION must contain one stable semantic version")
    return version


def write_bytes(path: Path, data: bytes, mode: int = 0o644) -> None:
    path.write_bytes(data)
    path.chmod(mode)


def manifest_payload(entries: list[dict[str, Any]], artifact: str, artifact_sha: str) -> dict[str, Any]:
    return {
        "artifact": artifact,
        "sha256": artifact_sha,
        "files": [
            {
                "path": item["path"],
                "sourcePath": item["source_path"],
                "classification": item["classification"],
                "kind": item["kind"],
                "sha256": item["sha256"],
            }
            for item in entries
        ],
    }


def build(args: argparse.Namespace) -> None:
    source = Path(args.source).resolve()
    output = Path(args.output).resolve()
    commit, paths = checked_source(source)
    classifications = load_classification(source, paths)
    version = version_from_source(source)
    tag = f"v{version}"
    if args.tag != tag:
        fail(f"stable tag {args.tag!r} does not match VERSION {version!r}")
    origins = parse_origins(args.supported_upgrade_origin)
    if args.tag in origins:
        fail("target release cannot list itself as an upgrade origin")
    if output.exists() and (not output.is_dir() or any(output.iterdir())):
        fail("output directory must be absent or empty")
    if output == source or source in output.parents:
        fail("output directory must stay outside the source repository")

    new_entries = payload_entries(source, classifications, "new-project")
    adoption_entries = payload_entries(source, classifications, "adoption")
    new_archive = archive_bytes(new_entries)
    adoption_archive = archive_bytes(adoption_entries)
    installer = source_entry(source, INSTALLER_SOURCE)
    classification_bytes = (source / CLASSIFICATION_NAME).read_bytes()
    manifest = {
        "schema": MANIFEST_SCHEMA,
        "channel": CHANNEL,
        "version": version,
        "stableTag": args.tag,
        "source": {
            "repository": args.repository,
            "commit": commit,
        },
        "stateSchemaVersion": args.state_schema_version,
        "supportedUpgradeOrigins": origins,
        "sourceClassificationSha256": sha256_bytes(classification_bytes),
        "payloads": {
            "new-project": manifest_payload(new_entries, NEW_PROJECT_ARCHIVE, sha256_bytes(new_archive)),
            "adoption": manifest_payload(adoption_entries, ADOPTION_ARCHIVE, sha256_bytes(adoption_archive)),
        },
        "artifacts": {
            INSTALLER_NAME: sha256_bytes(installer["data"]),
            NEW_PROJECT_ARCHIVE: sha256_bytes(new_archive),
            ADOPTION_ARCHIVE: sha256_bytes(adoption_archive),
        },
    }
    manifest_bytes = (json.dumps(manifest, indent=2, sort_keys=True) + "\n").encode("utf-8")
    checksums = dict(manifest["artifacts"])
    checksums[MANIFEST_NAME] = sha256_bytes(manifest_bytes)
    checksum_bytes = "".join(f"{checksums[name]}  {name}\n" for name in sorted(checksums)).encode("utf-8")

    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=output.parent, prefix=f".{output.name}.tmp-") as raw:
        staging = Path(raw)
        write_bytes(staging / INSTALLER_NAME, installer["data"], 0o755)
        write_bytes(staging / NEW_PROJECT_ARCHIVE, new_archive)
        write_bytes(staging / ADOPTION_ARCHIVE, adoption_archive)
        write_bytes(staging / MANIFEST_NAME, manifest_bytes)
        write_bytes(staging / CHECKSUMS_NAME, checksum_bytes)
        validate_bundle(staging)
        output.mkdir(exist_ok=True)
        for name in REQUIRED_ARTIFACTS:
            os.replace(staging / name, output / name)
    print(json.dumps({"ok": True, "output": str(output), "version": version, "tag": args.tag}, sort_keys=True))


def is_sha256(value: Any) -> bool:
    return isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value) is not None


def validate_payload_record(name: str, record: Any) -> dict[str, dict[str, Any]]:
    if not isinstance(record, dict) or set(record) != {"artifact", "sha256", "files"}:
        fail(f"invalid payload record: {name}")
    if record["artifact"] != PAYLOADS[name] or not is_sha256(record["sha256"]):
        fail(f"invalid payload artifact record: {name}")
    if not isinstance(record["files"], list) or not record["files"]:
        fail(f"payload has no files: {name}")
    indexed: dict[str, dict[str, Any]] = {}
    for item in record["files"]:
        if not isinstance(item, dict) or set(item) != {"path", "sourcePath", "classification", "kind", "sha256"}:
            fail(f"invalid payload file record: {name}")
        path = item["path"]
        safe_path(path)
        if path in indexed or not path.startswith(".baton/"):
            fail(f"invalid or duplicate payload path: {path}")
        if item["classification"] not in SOURCE_CLASSES - {"source-only"} or item["kind"] not in {"file", "symlink"} or not is_sha256(item["sha256"]):
            fail(f"invalid payload metadata: {path}")
        indexed[path] = item
    if list(indexed) != sorted(indexed):
        fail(f"payload files are not sorted: {name}")
    return indexed


def load_manifest(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        fail(f"invalid manifest: {error}")
    if not isinstance(value, dict):
        fail("manifest must be an object")
    required = {
        "schema", "channel", "version", "stableTag", "source",
        "stateSchemaVersion", "supportedUpgradeOrigins",
        "sourceClassificationSha256", "payloads", "artifacts",
    }
    if set(value) != required or value["schema"] != MANIFEST_SCHEMA or value["channel"] != CHANNEL:
        fail("manifest keys or schema do not match the stable contract")
    if not isinstance(value["version"], str) or value["stableTag"] != f"v{value['version']}":
        fail("manifest version and stable tag do not match")
    source = value["source"]
    if not isinstance(source, dict) or set(source) != {"repository", "commit"} or not re.fullmatch(r"[0-9a-f]{40}", str(source.get("commit"))):
        fail("manifest source is not immutable")
    if type(value["stateSchemaVersion"]) is not int or value["stateSchemaVersion"] < 1:
        fail("manifest state schema version is invalid")
    if not is_sha256(value["sourceClassificationSha256"]):
        fail("manifest source classification checksum is invalid")
    if not isinstance(value["supportedUpgradeOrigins"], dict):
        fail("manifest upgrade origins are invalid")
    for tag, origin in value["supportedUpgradeOrigins"].items():
        if (
            re.fullmatch(r"v[0-9]+\.[0-9]+\.[0-9]+", str(tag)) is None
            or not isinstance(origin, dict)
            or set(origin) != {"sourceCommit", "manifestSha256"}
            or re.fullmatch(r"[0-9a-f]{40}", str(origin.get("sourceCommit"))) is None
            or not is_sha256(origin.get("manifestSha256"))
        ):
            fail(f"invalid immutable upgrade origin: {tag}")
    if not isinstance(value["payloads"], dict) or set(value["payloads"]) != set(PAYLOADS):
        fail("manifest payload set is invalid")
    for name in PAYLOADS:
        validate_payload_record(name, value["payloads"][name])
    if not isinstance(value["artifacts"], dict) or set(value["artifacts"]) != {INSTALLER_NAME, NEW_PROJECT_ARCHIVE, ADOPTION_ARCHIVE} or not all(is_sha256(item) for item in value["artifacts"].values()):
        fail("manifest artifact contract is invalid")
    return value


def validate_archive(path: Path, expected: dict[str, dict[str, Any]]) -> None:
    try:
        archive = tarfile.open(path, "r:gz")
    except (OSError, tarfile.TarError) as error:
        fail(f"invalid archive {path.name}: {error}")
    seen: set[str] = set()
    symlinks: set[PurePosixPath] = set()
    with archive:
        members = archive.getmembers()
        for member in members:
            raw = safe_path(member.name)
            if member.name in seen or member.isdir() or member.islnk() or member.isdev() or member.isfifo() or not (member.isfile() or member.issym()):
                fail(f"unsafe archive entry: {member.name}")
            if any(parent in symlinks for parent in raw.parents):
                fail(f"archive path passes through a symlink: {member.name}")
            seen.add(member.name)
            if member.issym():
                symlinks.add(raw)
                target = member.linkname
                if not target or os.path.isabs(target) or "\\" in target:
                    fail(f"unsafe archive symlink: {member.name}")
                stack: list[str] = list(raw.parent.parts)
                for part in PurePosixPath(target).parts:
                    if part in {"", "."}:
                        continue
                    if part == "..":
                        if not stack:
                            fail(f"archive symlink escapes: {member.name}")
                        stack.pop()
                    else:
                        stack.append(part)
                data = target.encode("utf-8")
                kind = "symlink"
            else:
                handle = archive.extractfile(member)
                if handle is None:
                    fail(f"cannot read archive entry: {member.name}")
                data = handle.read()
                kind = "file"
            record = expected.get(member.name)
            if record is None or record["kind"] != kind or record["sha256"] != sha256_bytes(data):
                fail(f"archive entry does not match manifest: {member.name}")
    if seen != set(expected):
        fail(f"archive file set does not match manifest: {path.name}")


def parse_checksums(path: Path) -> dict[str, str]:
    expected = {INSTALLER_NAME, NEW_PROJECT_ARCHIVE, ADOPTION_ARCHIVE, MANIFEST_NAME}
    result: dict[str, str] = {}
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as error:
        fail(f"cannot read checksums: {error}")
    for line in lines:
        parts = line.split("  ")
        if len(parts) != 2 or parts[1] not in expected or not is_sha256(parts[0]) or parts[1] in result:
            fail("invalid SHA256SUMS")
        result[parts[1]] = parts[0]
    if set(result) != expected:
        fail("SHA256SUMS file set is incomplete")
    return result


def validate_bundle(bundle: Path) -> None:
    if not bundle.is_dir():
        fail("release bundle is not a directory")
    actual = {path.name for path in bundle.iterdir()}
    if actual != set(REQUIRED_ARTIFACTS) or any(not (bundle / name).is_file() for name in REQUIRED_ARTIFACTS):
        fail(
            "release bundle artifact set is not exact; "
            f"missing={sorted(set(REQUIRED_ARTIFACTS) - actual)}, "
            f"unexpected={sorted(actual - set(REQUIRED_ARTIFACTS))}"
        )
    manifest = load_manifest(bundle / MANIFEST_NAME)
    checksums = parse_checksums(bundle / CHECKSUMS_NAME)
    for name, digest in checksums.items():
        if sha256_file(bundle / name) != digest:
            fail(f"checksum mismatch: {name}")
    for name, digest in manifest["artifacts"].items():
        if sha256_file(bundle / name) != digest:
            fail(f"manifest artifact checksum mismatch: {name}")
    for payload, archive_name in PAYLOADS.items():
        expected = validate_payload_record(payload, manifest["payloads"][payload])
        validate_archive(bundle / archive_name, expected)


def validate(args: argparse.Namespace) -> None:
    bundle = Path(args.bundle).resolve()
    validate_bundle(bundle)
    print(json.dumps({"ok": True, "bundle": str(bundle)}, sort_keys=True))


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    commands = result.add_subparsers(dest="command", required=True)
    classify_parser = commands.add_parser("classify", help="validate or regenerate the exact source-file classification")
    classify_parser.add_argument("--source", required=True)
    classify_parser.add_argument("--write", action="store_true")
    classify_parser.set_defaults(handler=classify)
    build_parser = commands.add_parser("build", help="build two fail-closed stable payloads")
    build_parser.add_argument("--source", required=True)
    build_parser.add_argument("--output", required=True)
    build_parser.add_argument("--tag", required=True)
    build_parser.add_argument("--repository", default="FabienGreard/baton")
    build_parser.add_argument("--supported-upgrade-origin", action="append", default=[])
    build_parser.add_argument("--state-schema-version", type=int, default=1)
    build_parser.set_defaults(handler=build)
    validate_parser = commands.add_parser("validate", help="validate exact bundle checksums and payloads")
    validate_parser.add_argument("--bundle", required=True)
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
