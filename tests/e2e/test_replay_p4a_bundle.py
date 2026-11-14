"""End-to-end replay of a bundle BUILT BY P4-A, using this lane's own replay verifier.

Synthetic fixtures only ([SYNTHETIC DEV FIXTURE]). This proves the formats connect; it is not
a scientific result and, when written or run by the implementation agent, not a P5 verdict.

Source of P4-A's builder, in order:
1. $env:E2E_PIPELINE_DIR: a directory containing artifact_pipeline/ and contracts/.
2. This repository, if both directories are present (after integration).
3. A read-only `git archive` of $env:E2E_PIPELINE_REF (default: the pinned P4-A commit).
The builder runs in a subprocess; this suite imports none of P4-A's code.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import tarfile
from pathlib import Path

import pytest

from tests.e2e import replay_bundle as rb

REPO_ROOT = Path(__file__).resolve().parents[2]
# origin/task/P4-A-001 0edd7d3 "emit one replayable ProvenanceManifest per bundle file".
PINNED_PIPELINE_COMMIT = "0edd7d304a1ba0f40161e7f059394b42a0fb4bc5"


def _pipeline_root(tmp: Path) -> Path:
    override = os.environ.get("E2E_PIPELINE_DIR")
    if override:
        return Path(override).resolve()
    if (REPO_ROOT / "artifact_pipeline" / "bundle.py").is_file() and (REPO_ROOT / "contracts").is_dir():
        return REPO_ROOT
    ref = os.environ.get("E2E_PIPELINE_REF", PINNED_PIPELINE_COMMIT)
    dest = tmp / "pipeline_src"
    dest.mkdir(parents=True, exist_ok=True)
    archive = dest / "src.tar"
    try:
        subprocess.run(["git", "-C", str(REPO_ROOT), "archive", "-o", str(archive), ref,
                        "artifact_pipeline", "contracts"], check=True, capture_output=True, timeout=60)
    except (OSError, subprocess.SubprocessError) as exc:
        pytest.skip(f"P4-A builder not available locally (ref {ref[:12]}): {exc}")
    with tarfile.open(archive) as tar:
        tar.extractall(dest, filter="data")
    archive.unlink()
    return dest


@pytest.fixture(scope="module")
def built(tmp_path_factory) -> Path:
    tmp = tmp_path_factory.mktemp("p4a")
    root = _pipeline_root(tmp)
    out = tmp / "public_bundle"
    proc = subprocess.run(
        [sys.executable, "-m", "artifact_pipeline.build", "--src", str(root / "contracts" / "fixtures"),
         "--out", str(out), "--bundle-version", "synthetic-replay-e2e", "--classification", "synthetic_dev_fixture"],
        cwd=root, capture_output=True, text=True, timeout=120)
    assert proc.returncode == 0, proc.stderr[-1500:]
    return out


@pytest.fixture()
def short_out():
    """Short output root: P4-A paths are ~120 characters, and pytest's tmp_path plus them can pass
    the 260-character Windows path limit during the verifier's temp-file writes."""
    import tempfile
    d = Path(tempfile.mkdtemp(prefix="rp"))
    yield d
    shutil.rmtree(d, ignore_errors=True)


def _index(bundle: Path) -> dict:
    return json.loads((bundle / "bundle_index.json").read_text(encoding="utf-8"))


def _independent_key(m: dict) -> str:
    """P5's own restatement of the cache key (five fields, fixed order)."""
    values = [m["artifact_version"]] + [m["partitions"][0][f] for f in ("geometry_id", "period_spec", "method_id",
                                                                        "policy_id")]
    return "tte-cache-v1:" + hashlib.sha256(json.dumps(values, separators=(",", ":")).encode("ascii")).hexdigest()


def test_p4a_bundle_lists_a_replay_manifest_for_every_file(built: Path) -> None:
    idx = _index(built)
    assert idx["contract_version"] == rb.CONTRACT_VERSION
    assert idx["replay_manifests_missing"] == []
    assert {m["describes"] for m in idx["replay_manifests"]} == {e["path"] for e in idx["entries"]}


def test_every_p4a_manifest_replays_end_to_end(built: Path, short_out: Path) -> None:
    tmp_path = short_out
    idx = _index(built)
    for i, m in enumerate(idx["replay_manifests"]):
        res = rb.replay(built / m["path"], built, tmp_path / f"out{i}", expected_manifest_sha256=m["sha256"])
        assert res.reproduced, res.failures
        manifest = json.loads((built / m["path"]).read_text(encoding="utf-8"))
        assert manifest["partitions"][0]["cache_key_sha256"] == _independent_key(manifest)
        assert manifest["fixture_label"] == "[SYNTHETIC DEV FIXTURE]"
        replayed = tmp_path / f"out{i}" / "bundle" / m["describes"]
        assert replayed.read_bytes() == (built / m["describes"]).read_bytes()


def test_replayed_calendar_keeps_missing_states_null(built: Path, short_out: Path) -> None:
    tmp_path = short_out
    idx = _index(built)
    m = next(x for x in idx["replay_manifests"] if x["family"] == "calendar")
    assert rb.replay(built / m["path"], built, tmp_path / "cal").reproduced
    cal = json.loads((tmp_path / "cal" / "bundle" / m["describes"]).read_text(encoding="utf-8"))
    recs = [r for s in cal["monthly_series"] + cal["weekly_series"] for r in s["records"]]
    unavailable = [r for r in recs if r["availability"] == "unavailable"]
    assert unavailable, "fixture should contain unavailable periods"
    assert all(r["fire_activity_index"] is None for r in unavailable)
    no_file = [r for r in recs if r["days_with_file"] == 0]
    assert no_file and all(r["detected_fire_cell_days"] is None for r in no_file)  # missing is never zero


def test_tampered_p4a_file_is_not_reproduced(built: Path, tmp_path: Path) -> None:
    copy = tmp_path / "bundle"
    shutil.copytree(built, copy)
    m = _index(copy)["replay_manifests"][0]
    target = copy / m["describes"]
    target.write_bytes(target.read_bytes() + b" ")
    res = rb.replay(copy / m["path"], copy, tmp_path / "out")
    assert not res.reproduced and any("size" in f or "sha256" in f for f in res.failures)


def test_p4a_manifest_pointing_into_a_sealed_location_is_refused(built: Path, tmp_path: Path) -> None:
    copy = tmp_path / "bundle"
    shutil.copytree(built, copy)
    m = _index(copy)["replay_manifests"][0]
    path = copy / m["path"]
    data = json.loads(path.read_text(encoding="utf-8"))
    data["partitions"][0]["file_path"] = "sealed/" + data["partitions"][0]["file_path"]
    path.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(rb.SealedDataRefused):
        rb.replay(path, copy, tmp_path / "out")


def test_p4a_manifest_identity_change_breaks_the_cache_key(built: Path, tmp_path: Path) -> None:
    copy = tmp_path / "bundle"
    shutil.copytree(built, copy)
    m = _index(copy)["replay_manifests"][0]
    path = copy / m["path"]
    data = json.loads(path.read_text(encoding="utf-8"))
    data["partitions"][0]["geometry_id"] = "geo-synthetic-sub-a"  # another area
    path.write_text(json.dumps(data), encoding="utf-8")
    res = rb.replay(path, copy, tmp_path / "out")
    assert not res.reproduced and any("cache key" in f for f in res.failures)
