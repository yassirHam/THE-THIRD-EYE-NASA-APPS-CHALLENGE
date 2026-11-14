#!/usr/bin/env python3
"""Clean-environment replay verifier for P4's PUBLIC evidence bundle.

Designed for a fresh Linux InstaBox (team-kit/INSTABOX.md) or any clean local
machine. It only reads the public manifest and the files it lists. It refuses to
read sealed holdout locations and never uploads anything.

For every partition in the manifest it checks:
  - the path stays inside the bundle (no absolute paths, '..' or escaping links)
  - the path is not a sealed/holdout location
  - the file exists, its byte size matches, and its SHA256 matches
  - the partition's cache key digest matches the five identity fields
Then it checks that partition sizes sum to the manifest total and, if given,
that the manifest itself matches a pinned SHA256.

Verified partitions are copied into --out through temp file + fsync + rename,
so an interrupted run never leaves a partial artifact. A checkpoint (also
written atomically) lets a rerun resume; resumed entries are re-hashed when the
source file's size or mtime changed.

The report says "reproduced" only when every check passes. Any failure makes the
exit status 1 and is listed in the report.

Usage:
    python tests/e2e/replay_bundle.py --manifest M.json --bundle-dir DIR --out OUT
        [--expected-manifest-sha256 HEX]
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import re
import shutil
import sys
import tempfile
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Callable

CONTRACT_VERSION = "1.1.0"
CACHE_KEY_FIELDS = ("artifact_version", "geometry_id", "period_spec", "method_id", "policy_id")
CACHE_KEY_PREFIX = "tte-cache-v1:"
CHECKPOINT_NAME = ".replay_checkpoint.json"
REPORT_NAME = "replay_report.json"
TMP_SUFFIX = ".replay-tmp"
SEALED_PATTERN = re.compile(r"(?:^|[/\\_.-])(?:sealed|holdouts?)(?:$|[/\\_.-])", re.IGNORECASE)
HEX64 = re.compile(r"^[0-9a-f]{64}$")


class SealedDataRefused(RuntimeError):
    """Raised before any read of a sealed holdout location."""


@dataclass
class ReplayResult:
    reproduced: bool
    checks: list[dict] = field(default_factory=list)
    failures: list[str] = field(default_factory=list)
    resumed_partitions: list[str] = field(default_factory=list)
    report_path: str | None = None


# --------------------------------------------------------------- primitives


def sha256_file(path: Path, chunk: int = 1 << 20) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for block in iter(lambda: fh.read(chunk), b""):
            h.update(block)
    return h.hexdigest()


def cache_key_digest(identity: dict) -> str:
    """Written definition (contract 1.1.0): JSON array of the five fields in fixed
    order, compact separators, ASCII; SHA256 of its UTF-8 bytes, with prefix."""
    values = [identity[name] for name in CACHE_KEY_FIELDS]
    canonical = json.dumps(values, ensure_ascii=True, separators=(",", ":"))
    return CACHE_KEY_PREFIX + hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def atomic_write_bytes(dest: Path, data: bytes) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=dest.name + ".", suffix=TMP_SUFFIX, dir=dest.parent)
    try:
        with os.fdopen(fd, "wb") as fh:
            fh.write(data)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, dest)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise


def atomic_write_json(dest: Path, obj) -> None:
    atomic_write_bytes(dest, (json.dumps(obj, indent=2, sort_keys=True) + "\n").encode("utf-8"))


def atomic_copy(src: Path, dest: Path, expected_sha256: str) -> None:
    """Copy via temp file, verify the copy's hash, then rename into place."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=dest.name + ".", suffix=TMP_SUFFIX, dir=dest.parent)
    try:
        h = hashlib.sha256()
        with os.fdopen(fd, "wb") as out, src.open("rb") as inp:
            for block in iter(lambda: inp.read(1 << 20), b""):
                h.update(block)
                out.write(block)
            out.flush()
            os.fsync(out.fileno())
        if h.hexdigest() != expected_sha256:
            raise OSError(f"copy of {src.name} changed during transfer")
        os.replace(tmp, dest)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise


def clean_stale_temp_files(root: Path) -> list[str]:
    removed = []
    if root.exists():
        for p in root.rglob(f"*{TMP_SUFFIX}"):
            p.unlink(missing_ok=True)
            removed.append(p.name)
    return removed


# --------------------------------------------------------------- firewall


def assert_public_location(path: Path, label: str) -> None:
    resolved = path.resolve()
    if SEALED_PATTERN.search(resolved.as_posix()):
        raise SealedDataRefused(f"{label} looks like a sealed/holdout location: {resolved}")
    sealed_env = os.environ.get("SEALED_EVAL_DIR")
    if sealed_env:
        sealed = Path(sealed_env).resolve()
        if resolved == sealed or sealed in resolved.parents or resolved in sealed.parents:
            raise SealedDataRefused(f"{label} overlaps SEALED_EVAL_DIR")


def safe_partition_path(bundle_dir: Path, file_path: str) -> Path:
    pure = PurePosixPath(file_path.replace("\\", "/"))
    if pure.is_absolute() or re.match(r"^[A-Za-z]:", file_path) or ".." in pure.parts or not pure.parts:
        raise ValueError(f"unsafe partition path: {file_path!r}")
    if SEALED_PATTERN.search(pure.as_posix()):
        raise SealedDataRefused(f"partition path names a sealed/holdout location: {file_path!r}")
    candidate = (bundle_dir / Path(*pure.parts)).resolve()
    root = bundle_dir.resolve()
    if root not in candidate.parents:
        raise ValueError(f"partition path escapes the bundle: {file_path!r}")
    return candidate


# --------------------------------------------------------------- replay


def environment_record() -> dict:
    return {
        "python": sys.version.split()[0],
        "implementation": platform.python_implementation(),
        "platform": platform.platform(),
        "machine": platform.machine(),
    }


def replay(
    manifest_path: Path,
    bundle_dir: Path,
    out_dir: Path,
    expected_manifest_sha256: str | None = None,
    after_partition: Callable[[int, dict], None] | None = None,
) -> ReplayResult:
    """Verify and materialize the bundle. ``after_partition`` is a test hook that
    runs after each partition is committed (used to simulate interruption)."""
    assert_public_location(manifest_path, "manifest")
    assert_public_location(bundle_dir, "bundle directory")
    assert_public_location(out_dir, "output directory")

    result = ReplayResult(reproduced=False)

    def record(name: str, ok: bool, detail: str = "") -> None:
        result.checks.append({"check": name, "ok": ok, "detail": detail})
        if not ok:
            result.failures.append(f"{name}: {detail}")

    out_dir.mkdir(parents=True, exist_ok=True)
    stale = clean_stale_temp_files(out_dir)
    if stale:
        record("stale temp files removed", True, f"{len(stale)} removed from an interrupted run")

    manifest_bytes = manifest_path.read_bytes()
    manifest_sha = hashlib.sha256(manifest_bytes).hexdigest()
    if expected_manifest_sha256:
        record("manifest sha256 pinned", manifest_sha == expected_manifest_sha256.lower(),
               f"actual {manifest_sha}")
    manifest = json.loads(manifest_bytes)

    record("contract version", manifest.get("contract_version") == CONTRACT_VERSION,
           f"manifest declares {manifest.get('contract_version')!r}")
    if manifest.get("data_classification") == "synthetic_dev_fixture":
        record("synthetic label visible", manifest.get("fixture_label") == "[SYNTHETIC DEV FIXTURE]",
               "synthetic bundles must carry the visible label")

    checkpoint_path = out_dir / CHECKPOINT_NAME
    checkpoint = {}
    if checkpoint_path.exists():
        try:
            saved = json.loads(checkpoint_path.read_text(encoding="utf-8"))
            if saved.get("manifest_sha256") == manifest_sha:
                checkpoint = saved.get("partitions", {})
        except json.JSONDecodeError:
            checkpoint = {}  # a torn checkpoint cannot happen with atomic writes; ignore if it does

    partitions = manifest.get("partitions") or []
    record("manifest lists partitions", bool(partitions), f"{len(partitions)} listed")
    total = 0
    seen: set[str] = set()
    for index, part in enumerate(partitions):
        fp = part.get("file_path", "")
        label = f"partition {fp!r}"
        if fp in seen:
            record(f"{label} unique", False, "listed twice")
            continue
        seen.add(fp)
        try:
            src = safe_partition_path(bundle_dir, fp)
        except SealedDataRefused:
            raise
        except ValueError as exc:
            record(f"{label} path safe", False, str(exc))
            continue

        identity = {"artifact_version": manifest.get("artifact_version"), **part}
        try:
            digest = cache_key_digest(identity)
            record(f"{label} cache key", digest == part.get("cache_key_sha256"),
                   f"expected {digest}, manifest {part.get('cache_key_sha256')}")
        except KeyError as exc:
            record(f"{label} cache key", False, f"missing identity field {exc}")

        expected_sha = str(part.get("sha256_checksum", "")).lower()
        if not HEX64.match(expected_sha):
            record(f"{label} sha256 declared", False, "not a 64-hex SHA256")
            continue
        if not src.is_file():
            record(f"{label} present", False, "file missing from bundle")
            continue
        stat = src.stat()
        total += stat.st_size
        record(f"{label} size", stat.st_size == part.get("file_size_bytes"),
               f"actual {stat.st_size}, manifest {part.get('file_size_bytes')}")

        dest = out_dir / "bundle" / Path(*PurePosixPath(fp.replace("\\", "/")).parts)
        prior = checkpoint.get(fp)
        if (
            prior
            and prior.get("sha256") == expected_sha
            and prior.get("size") == stat.st_size
            and prior.get("mtime_ns") == stat.st_mtime_ns
            and dest.is_file()
            and sha256_file(dest) == expected_sha
        ):
            record(f"{label} sha256", True, "resumed from checkpoint; materialized copy re-hashed")
            result.resumed_partitions.append(fp)
            continue

        actual_sha = sha256_file(src)
        ok = actual_sha == expected_sha
        record(f"{label} sha256", ok, f"actual {actual_sha}")
        if not ok:
            continue
        atomic_copy(src, dest, expected_sha)
        checkpoint[fp] = {"sha256": expected_sha, "size": stat.st_size, "mtime_ns": stat.st_mtime_ns}
        atomic_write_json(checkpoint_path, {"manifest_sha256": manifest_sha, "partitions": checkpoint})
        if after_partition:
            after_partition(index, part)

    if partitions:
        record("total size reconciles", total == manifest.get("total_file_size_bytes"),
               f"partitions sum {total}, manifest {manifest.get('total_file_size_bytes')}")

    result.reproduced = not result.failures
    report = {
        "reproduced": result.reproduced,
        "verified_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "manifest_path": manifest_path.name,
        "manifest_sha256": manifest_sha,
        "artifact_version": manifest.get("artifact_version"),
        "geometry_id": manifest.get("geometry_id"),
        "data_classification": manifest.get("data_classification"),
        "environment": environment_record(),
        "checks": result.checks,
        "failures": result.failures,
        "resumed_partitions": result.resumed_partitions,
    }
    report_path = out_dir / REPORT_NAME
    atomic_write_json(report_path, report)
    result.report_path = str(report_path)
    if result.reproduced:
        checkpoint_path.unlink(missing_ok=True)  # a completed run needs no resume state
    return result


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Replay and verify a public evidence bundle.")
    ap.add_argument("--manifest", required=True, type=Path)
    ap.add_argument("--bundle-dir", required=True, type=Path)
    ap.add_argument("--out", required=True, type=Path)
    ap.add_argument("--expected-manifest-sha256")
    args = ap.parse_args(argv)
    try:
        res = replay(args.manifest, args.bundle_dir, args.out, args.expected_manifest_sha256)
    except SealedDataRefused as exc:
        print(f"REFUSED: {exc}", file=sys.stderr)
        return 2
    for c in res.checks:
        print(("PASS  " if c["ok"] else "FAIL  ") + c["check"] + (f"  ({c['detail']})" if not c["ok"] else ""))
    print(f"\nreproduced: {res.reproduced}   report: {res.report_path}")
    return 0 if res.reproduced else 1


if __name__ == "__main__":
    sys.exit(main())
