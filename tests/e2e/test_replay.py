"""Tests for the clean-environment bundle replay verifier.

Each test builds its own isolated synthetic bundle under pytest's tmp_path, so
`pytest tests/e2e/test_replay.py -v` passes on a fresh clone with no network,
no P4 bundle and no sealed data. Expected hashes are computed here from the
bytes written, not copied from any implementation output.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

import pytest

IDENTITY = {
    "artifact_version": "synthetic-replay-v1",
    "geometry_id": "geo-synthetic-primary",
    "period_spec": "synthetic-2020-2021",
    "method_id": "artifact_manifest",
    "policy_id": "own_support_eligible",
}


def expected_cache_key(identity: dict) -> str:
    """Independent restatement of the contract 1.1.0 definition."""
    fields = ["artifact_version", "geometry_id", "period_spec", "method_id", "policy_id"]
    canonical = "[" + ",".join(json.dumps(identity[f]) for f in fields) + "]"
    return "tte-cache-v1:" + hashlib.sha256(canonical.encode("ascii")).hexdigest()


def build_bundle(root: Path, files: dict[str, bytes]) -> tuple[Path, Path]:
    bundle = root / "bundle"
    partitions = []
    for rel, data in files.items():
        p = bundle / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(data)
        partitions.append({
            "file_path": rel,
            "geometry_id": IDENTITY["geometry_id"],
            "period_spec": IDENTITY["period_spec"],
            "method_id": IDENTITY["method_id"],
            "policy_id": IDENTITY["policy_id"],
            "sensor": "MODIS_Aqua",
            "row_count": data.count(b"\n"),
            "file_size_bytes": len(data),
            "cache_key_sha256": expected_cache_key(IDENTITY),
            "sha256_checksum": hashlib.sha256(data).hexdigest(),
            "coverage_status": "complete",
        })
    manifest = {
        "contract_version": "1.1.0",
        **IDENTITY,
        "data_classification": "synthetic_dev_fixture",
        "fixture_label": "[SYNTHETIC DEV FIXTURE]",
        "manifest_version": "synthetic-replay-manifest-1",
        "generated_at": "2026-11-14T00:00:00Z",
        "snpp_cessation_date": "2026-11-02",
        "canonical_boundary": {"type": "Polygon", "coordinates": [[[0.0, 0.0], [1.0, 0.0], [1.0, 1.0], [0.0, 1.0], [0.0, 0.0]]]},
        "boundary_source": "synthetic",
        "boundary_version": "1",
        "crs": "EPSG:4326",
        "grid_inclusion_rule": "cell centroid inside boundary",
        "source_collections": [{"collection_id": "MODIS/061/MYD14A1", "sensor": "MODIS_Aqua", "source_version": "061", "record_end_date": None}],
        "total_file_size_bytes": sum(len(d) for d in files.values()),
        "compressed_bundle_size_bytes": sum(len(d) for d in files.values()),
        "partitions": partitions,
    }
    manifest_path = root / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest_path, bundle


FILES = {
    "calendar/monthly.json": b'{"rows": [1, 2, 3]}\n',
    "comparison/case.json": b'{"case": "synthetic"}\n',
    "evidence/record.json": b'{"record": "synthetic"}\n',
}


@pytest.fixture
def bundle(tmp_path):
    return build_bundle(tmp_path, FILES)


def edit_manifest(path: Path, fn) -> None:
    m = json.loads(path.read_text(encoding="utf-8"))
    fn(m)
    path.write_text(json.dumps(m), encoding="utf-8")


def failures_matching(result, text: str) -> list[str]:
    return [f for f in result.failures if text in f]


# ---------------------------------------------------------------- happy path


def test_clean_replay_reproduces(replay, bundle, tmp_path):
    manifest, bdir = bundle
    out = tmp_path / "out"
    res = replay.replay(manifest, bdir, out)
    assert res.reproduced, res.failures
    for rel, data in FILES.items():
        assert (out / "bundle" / rel).read_bytes() == data
    report = json.loads(Path(res.report_path).read_text(encoding="utf-8"))
    assert report["reproduced"] is True
    assert report["manifest_sha256"] == hashlib.sha256(manifest.read_bytes()).hexdigest()
    assert report["environment"]["python"]
    assert not list(out.rglob("*.replay-tmp")), "no temp files after success"
    assert not (out / ".replay_checkpoint.json").exists()


def test_cache_key_matches_written_definition(replay):
    assert replay.cache_key_digest(IDENTITY) == expected_cache_key(IDENTITY)


def test_cache_key_matches_p4_published_fixture(replay, fixtures):
    m = fixtures["sample_manifest"]
    part = m["partitions"][0]
    identity = {"artifact_version": m["artifact_version"], **part}
    assert replay.cache_key_digest(identity) == part["cache_key_sha256"]
    assert expected_cache_key(identity) == part["cache_key_sha256"]


def test_pinned_manifest_hash(replay, bundle, tmp_path):
    manifest, bdir = bundle
    good = hashlib.sha256(manifest.read_bytes()).hexdigest()
    assert replay.replay(manifest, bdir, tmp_path / "a", expected_manifest_sha256=good).reproduced
    res = replay.replay(manifest, bdir, tmp_path / "b", expected_manifest_sha256="0" * 64)
    assert not res.reproduced and failures_matching(res, "manifest sha256 pinned")


def test_cli_exit_codes(replay, bundle, tmp_path):
    manifest, bdir = bundle
    assert replay.main(["--manifest", str(manifest), "--bundle-dir", str(bdir), "--out", str(tmp_path / "ok")]) == 0
    (bdir / "calendar/monthly.json").write_bytes(b"tampered\n")
    assert replay.main(["--manifest", str(manifest), "--bundle-dir", str(bdir), "--out", str(tmp_path / "bad")]) == 1


# ---------------------------------------------------------------- detection


def test_detects_tampered_bytes_same_size(replay, bundle, tmp_path):
    manifest, bdir = bundle
    target = bdir / "comparison/case.json"
    data = bytearray(target.read_bytes())
    data[3] ^= 0x01
    target.write_bytes(bytes(data))
    res = replay.replay(manifest, bdir, tmp_path / "out")
    assert not res.reproduced
    assert failures_matching(res, "comparison/case.json' sha256")
    assert not (tmp_path / "out/bundle/comparison/case.json").exists(), "a bad file must not be materialized"


def test_detects_size_mismatch(replay, bundle, tmp_path):
    manifest, bdir = bundle
    edit_manifest(manifest, lambda m: m["partitions"][0].update(file_size_bytes=1))
    res = replay.replay(manifest, bdir, tmp_path / "out")
    assert failures_matching(res, "size")


def test_detects_missing_file(replay, bundle, tmp_path):
    manifest, bdir = bundle
    (bdir / "evidence/record.json").unlink()
    res = replay.replay(manifest, bdir, tmp_path / "out")
    assert failures_matching(res, "file missing from bundle")
    assert failures_matching(res, "total size reconciles")


def test_detects_cache_key_mismatch(replay, bundle, tmp_path):
    manifest, bdir = bundle
    edit_manifest(manifest, lambda m: m["partitions"][1].update(geometry_id="geo-other-region"))
    res = replay.replay(manifest, bdir, tmp_path / "out")
    assert failures_matching(res, "cache key")


def test_detects_wrong_contract_version(replay, bundle, tmp_path):
    manifest, bdir = bundle
    edit_manifest(manifest, lambda m: m.update(contract_version="1.0.0"))
    assert failures_matching(replay.replay(manifest, bdir, tmp_path / "out"), "contract version")


def test_detects_duplicate_partition(replay, bundle, tmp_path):
    manifest, bdir = bundle
    edit_manifest(manifest, lambda m: m["partitions"].append(dict(m["partitions"][0])))
    assert failures_matching(replay.replay(manifest, bdir, tmp_path / "out"), "listed twice")


def test_empty_manifest_is_not_reproduced(replay, bundle, tmp_path):
    manifest, bdir = bundle
    edit_manifest(manifest, lambda m: m.update(partitions=[]))
    res = replay.replay(manifest, bdir, tmp_path / "out")
    assert not res.reproduced and failures_matching(res, "manifest lists partitions")


def test_p4_sample_manifest_without_its_files_fails_honestly(replay, contracts, tmp_path):
    empty = tmp_path / "empty_bundle"
    empty.mkdir()
    res = replay.replay(contracts.fixtures / "sample_manifest.json", empty, tmp_path / "out")
    assert not res.reproduced
    assert failures_matching(res, "file missing from bundle")


# ---------------------------------------------------------------- path safety and firewall


@pytest.mark.parametrize("bad", ["../outside.json", "/etc/passwd", "C:/Windows/win.ini", "a/../../x.json", ""])
def test_rejects_unsafe_paths(replay, bundle, tmp_path, bad):
    manifest, bdir = bundle
    edit_manifest(manifest, lambda m: m["partitions"][0].update(file_path=bad))
    res = replay.replay(manifest, bdir, tmp_path / "out")
    assert not res.reproduced and failures_matching(res, "path safe")


def test_rejects_symlink_escaping_bundle(replay, bundle, tmp_path):
    manifest, bdir = bundle
    outside = tmp_path / "outside.json"
    outside.write_bytes(FILES["calendar/monthly.json"])
    link = bdir / "calendar/monthly.json"
    link.unlink()
    try:
        os.symlink(outside, link)
    except (OSError, NotImplementedError):
        pytest.skip("symlinks not permitted on this machine")
    res = replay.replay(manifest, bdir, tmp_path / "out")
    assert failures_matching(res, "escapes the bundle")


@pytest.mark.parametrize("name", ["sealed/eval_2020.json", "holdout/part.json", "data/sealed_holdouts/x.json"])
def test_refuses_sealed_partition_paths(replay, bundle, tmp_path, name):
    manifest, bdir = bundle
    edit_manifest(manifest, lambda m: m["partitions"][0].update(file_path=name))
    with pytest.raises(replay.SealedDataRefused):
        replay.replay(manifest, bdir, tmp_path / "out")


def test_refuses_bundle_inside_sealed_eval_dir(replay, tmp_path, monkeypatch):
    sealed = tmp_path / "p5_private"
    manifest, bdir = build_bundle(sealed, FILES)
    monkeypatch.setenv("SEALED_EVAL_DIR", str(sealed))
    with pytest.raises(replay.SealedDataRefused):
        replay.replay(manifest, bdir, tmp_path / "out")


def test_cli_returns_2_when_refused(replay, tmp_path):
    manifest, bdir = build_bundle(tmp_path / "sealed", FILES)
    assert replay.main(["--manifest", str(manifest), "--bundle-dir", str(bdir), "--out", str(tmp_path / "o")]) == 2


# ---------------------------------------------------------------- atomic writes and recovery


def test_atomic_write_leaves_no_partial_file_on_error(replay, tmp_path, monkeypatch):
    dest = tmp_path / "report.json"
    dest.write_text("previous", encoding="utf-8")

    def boom(*_):
        raise OSError("disk full (simulated)")

    monkeypatch.setattr(replay.os, "fsync", boom)
    with pytest.raises(OSError):
        replay.atomic_write_bytes(dest, b"new content")
    assert dest.read_text(encoding="utf-8") == "previous", "old file must survive a failed write"
    assert not list(tmp_path.glob("*.replay-tmp"))


class Interrupted(Exception):
    pass


def test_recovers_after_interruption(replay, bundle, tmp_path):
    manifest, bdir = bundle
    out = tmp_path / "out"

    def crash_after_first(index, _part):
        if index == 0:
            raise Interrupted

    with pytest.raises(Interrupted):
        replay.replay(manifest, bdir, out, after_partition=crash_after_first)
    assert (out / ".replay_checkpoint.json").exists()
    assert not (out / "replay_report.json").exists(), "no report may claim success after a crash"
    (out / "bundle" / "stale.json.abc.replay-tmp").write_bytes(b"half-written")  # leftover from a hard kill

    res = replay.replay(manifest, bdir, out)
    assert res.reproduced, res.failures
    assert res.resumed_partitions == ["calendar/monthly.json"]
    assert not list(out.rglob("*.replay-tmp"))
    for rel, data in FILES.items():
        assert (out / "bundle" / rel).read_bytes() == data


def test_resume_rehashes_changed_source(replay, bundle, tmp_path):
    manifest, bdir = bundle
    out = tmp_path / "out"

    def crash(index, _part):
        raise Interrupted

    with pytest.raises(Interrupted):
        replay.replay(manifest, bdir, out, after_partition=crash)
    src = bdir / "calendar/monthly.json"
    src.write_bytes(b'{"rows": [9, 9, 9]}\n')  # same size, different content
    res = replay.replay(manifest, bdir, out)
    assert not res.reproduced
    assert "calendar/monthly.json" not in res.resumed_partitions
    assert failures_matching(res, "calendar/monthly.json' sha256")


def test_resume_detects_corrupted_materialized_copy(replay, bundle, tmp_path):
    manifest, bdir = bundle
    out = tmp_path / "out"

    def crash(index, _part):
        raise Interrupted

    with pytest.raises(Interrupted):
        replay.replay(manifest, bdir, out, after_partition=crash)
    (out / "bundle/calendar/monthly.json").write_bytes(b"corrupted copy\n")
    res = replay.replay(manifest, bdir, out)
    assert res.reproduced, res.failures
    assert res.resumed_partitions == [], "a corrupted copy must be re-verified, not resumed"
    assert (out / "bundle/calendar/monthly.json").read_bytes() == FILES["calendar/monthly.json"]


def test_synthetic_manifest_is_valid_contract_1_1_0(contracts, bundle):
    """The replay fixture uses P4's real manifest shape, checked by P4's own schema."""
    pytest.importorskip("pydantic")
    import subprocess
    import sys

    manifest, _ = bundle
    code = (
        "import json,sys; sys.path.insert(0, sys.argv[1]); import contracts.schemas as s; "
        "s.ProvenanceManifest.model_validate_json(open(sys.argv[2], encoding='utf-8').read())"
    )
    proc = subprocess.run([sys.executable, "-c", code, str(contracts.root), str(manifest)],
                          capture_output=True, text=True, timeout=60, cwd=contracts.root)
    assert proc.returncode == 0, proc.stderr[-1500:]
