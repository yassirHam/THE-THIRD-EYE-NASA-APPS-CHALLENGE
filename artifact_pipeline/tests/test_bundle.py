"""P4-A static bundle tests on contract 1.4.0 synthetic fixtures only."""
from __future__ import annotations

import copy
import gzip
import json
from pathlib import Path

import pytest

from artifact_pipeline.build import P0_SYNTHETIC_SET, family_for, load_files, main
from artifact_pipeline.bundle import (
    INDEX_NAME,
    MODEL_BY_FAMILY,
    Bundle,
    BundleError,
    canonical_json,
    verify_bundle,
)
from contracts.schemas import CacheKey, CalendarArtifact, ComparisonResult, RegionSelectorArtifact

FIXTURES = Path(__file__).resolve().parents[2] / "contracts" / "fixtures"
SYN = "synthetic_dev_fixture"


def model(name: str, **changes):
    data = json.loads((FIXTURES / name).read_text(encoding="utf-8"))
    data.update(changes)
    return MODEL_BY_FAMILY[family_for(FIXTURES / name)].model_validate_json(json.dumps(data))


def p0_bundle() -> Bundle:
    b = Bundle(bundle_version="synthetic-dev-1", data_classification=SYN)
    load_files(FIXTURES, P0_SYNTHETIC_SET, b)
    return b


def test_build_write_and_verify_round_trip(tmp_path: Path) -> None:
    index = p0_bundle().write(tmp_path / "b")
    again = verify_bundle(tmp_path / "b")
    assert index == again
    assert len(index["entries"]) == len(P0_SYNTHETIC_SET)
    assert index["label"].startswith("[SYNTHETIC DEV FIXTURE]")
    size = index["size_report"]
    assert size["total_gzip_bytes"] == sum(e["gzip_bytes"] for e in index["entries"])
    assert size["within_p0_target"] is True
    assert size["measurement_basis"].startswith("synthetic")  # never reported as real P0 evidence


def test_output_is_deterministic(tmp_path: Path) -> None:
    p0_bundle().write(tmp_path / "a")
    p0_bundle().write(tmp_path / "b")
    files_a = {p.relative_to(tmp_path / "a"): p.read_bytes() for p in (tmp_path / "a").rglob("*") if p.is_file()}
    files_b = {p.relative_to(tmp_path / "b"): p.read_bytes() for p in (tmp_path / "b").rglob("*") if p.is_file()}
    assert files_a == files_b


def test_written_bytes_preserve_missing_states_exactly(tmp_path: Path) -> None:
    index = p0_bundle().write(tmp_path / "b")
    cal = next(e for e in index["entries"] if e["family"] == "calendar")
    data = json.loads((tmp_path / "b" / cal["path"]).read_text(encoding="utf-8"))
    src = json.loads((FIXTURES / "sample_calendar.json").read_text(encoding="utf-8"))
    by_key = lambda d: {(r["sensor"], r["year"], r["month"]): r for s in d["monthly_series"] for r in s["records"]}
    for key, rec in by_key(src).items():
        out = by_key(data)[key]
        for f in ("detected_fire_cell_days", "usable_land_cell_days", "fire_activity_index",
                  "availability", "unavailable_reason", "coverage_state", "coverage_reasons", "unusual_status"):
            assert out[f] == rec[f], (key, f)
    # a no-file month stays null, never 0
    nofile = by_key(data)[("VIIRS_SNPP", 2023, 9)]
    assert nofile["detected_fire_cell_days"] is None and nofile["fire_activity_index"] is None


def test_paths_are_addressed_by_the_full_identity_and_content(tmp_path: Path) -> None:
    index = p0_bundle().write(tmp_path / "b")
    for e in index["entries"]:
        k = e["cache_key"]
        parts = Path(e["path"]).parts
        assert parts[1:6] == (k["artifact_version"], k["geometry_id"], k["method_id"], k["policy_id"],
                              k["period_spec"])
        assert e["sha256"][:16] in parts[-1]
        assert e["cache_key_digest"] == CacheKey(**k).digest()


def test_firms_points_live_in_a_separate_subtree(tmp_path: Path) -> None:
    index = p0_bundle().write(tmp_path / "b")
    assert index["firms_separate"] is True
    firms = [e for e in index["entries"] if e["family"] == "firms_hotspots"]
    assert firms and all(e["path"].startswith("firms/") for e in firms)
    assert all(e["path"].startswith("artifacts/") for e in index["entries"] if e["family"] != "firms_hotspots")


# ------------------------------------------------------------- identity guards


def test_lookup_requires_all_five_fields() -> None:
    b = p0_bundle()
    comp = model("sample_comparison_normal.json")
    assert b.get("comparison", comp.cache_key()) == comp
    for field in ("artifact_version", "geometry_id", "period_spec", "method_id", "policy_id"):
        other = CacheKey(**{**comp.cache_key().model_dump(), field: "other"})
        with pytest.raises(BundleError, match="nothing is inherited"):
            b.get("comparison", other)


def test_same_identity_with_different_content_is_refused() -> None:
    b = p0_bundle()
    with pytest.raises(BundleError, match="immutable"):
        b.add(model("sample_comparison_sensitive.json"))
    b.add(model("sample_comparison_normal.json"))  # identical content is idempotent


def test_raw_only_area_cannot_be_served_a_comparison() -> None:
    b = p0_bundle()
    b.add(model("sample_comparison_normal.json", geometry_id="geo-synthetic-sub-a"))
    with pytest.raises(BundleError, match="raw_only"):
        b.check()


def test_comparison_must_match_the_areas_evaluated_identity() -> None:
    b = Bundle(bundle_version="v", data_classification=SYN)
    b.add(model("sample_region_selector.json"))
    b.add(model("sample_comparison_normal.json", method_id="another_method"))
    with pytest.raises(BundleError, match="evaluated"):
        b.check()


def test_comparison_without_a_region_option_is_refused() -> None:
    b = Bundle(bundle_version="v", data_classification=SYN)
    b.add(model("sample_comparison_normal.json"))
    with pytest.raises(BundleError, match="no region option"):
        b.check()


def test_manifest_must_describe_an_artifact_in_the_bundle() -> None:
    b = Bundle(bundle_version="v", data_classification=SYN)
    b.add(model("sample_manifest.json"))
    with pytest.raises(BundleError, match="not in the bundle"):
        b.check()
    b.add(model("sample_calendar.json"))
    b.check()


# ------------------------------------------------------- classification guards


def test_production_bundle_refuses_synthetic_artifacts() -> None:
    b = Bundle(bundle_version="v", data_classification="production")
    with pytest.raises(BundleError, match="cannot hold"):
        b.add(model("sample_calendar.json"))


def production_calendar(**record_changes) -> CalendarArtifact:
    data = json.loads((FIXTURES / "sample_calendar.json").read_text(encoding="utf-8"))
    data.update(data_classification="production", fixture_label=None, sealed_window={
        "start": "2011-01-01", "end": "2011-11-30", "registration_status": "registered",
        "registration_ref": "test-only-ref", "decision_date": "2026-11-15"})
    data["footprint_certification"]["certification_ref"] = "p2-cert-test-only-ref"
    return CalendarArtifact.model_validate_json(json.dumps(data))


def test_production_calendar_passes_the_sealed_record_guard() -> None:
    b = Bundle(bundle_version="v", data_classification="production")
    b.add(production_calendar())


def test_sealed_record_guard_refuses_data_inside_the_window() -> None:
    from artifact_pipeline.bundle import _refuse_sealed_records
    cal = production_calendar()
    data = json.loads(canonical_json(cal))
    data["sealed_window"].update(start="2023-06-01", end="2023-06-30")  # covers an available month
    # Bypass validation on purpose: the guard must still refuse if a malformed artifact slipped past.
    window = type(cal.sealed_window).model_validate_json(json.dumps(data["sealed_window"]))
    leaked = CalendarArtifact.model_construct(**{**cal.__dict__, "sealed_window": window})
    with pytest.raises(BundleError, match="sealed window carries data"):
        _refuse_sealed_records(leaked)


# ------------------------------------------------------------------ writing


def test_write_refuses_a_non_empty_directory(tmp_path: Path) -> None:
    (tmp_path / "b").mkdir()
    (tmp_path / "b" / "stale.json").write_text("{}")
    with pytest.raises(BundleError, match="not empty"):
        p0_bundle().write(tmp_path / "b")


def test_verify_detects_tampering(tmp_path: Path) -> None:
    index = p0_bundle().write(tmp_path / "b")
    path = tmp_path / "b" / index["entries"][0]["path"]
    path.write_bytes(path.read_bytes().replace(b'"', b"'", 1))
    with pytest.raises(BundleError, match="mismatch"):
        verify_bundle(tmp_path / "b")


def test_gzip_copies_decompress_to_the_json(tmp_path: Path) -> None:
    index = p0_bundle().write(tmp_path / "b")
    for e in index["entries"]:
        assert gzip.decompress((tmp_path / "b" / e["gzip_path"]).read_bytes()) == \
            (tmp_path / "b" / e["path"]).read_bytes()


def test_cli_builds_and_reports(tmp_path: Path, capsys) -> None:
    code = main(["--src", str(FIXTURES), "--out", str(tmp_path / "cli"), "--bundle-version", "synthetic-dev-1",
                 "--classification", SYN])
    assert code == 0
    report = json.loads(capsys.readouterr().out)
    assert report["entries"] == len(P0_SYNTHETIC_SET) and report["within_p0_target"] is True
    assert (tmp_path / "cli" / INDEX_NAME).exists()


def test_cli_refuses_conflicting_fixture_variants(tmp_path: Path) -> None:
    code = main(["--src", str(FIXTURES), "--out", str(tmp_path / "x"), "--bundle-version", "v",
                 "--classification", SYN, "--files", "sample_comparison_normal.json",
                 "sample_comparison_sensitive.json"])
    assert code == 2


def test_bundle_refuses_an_artifact_from_another_contract_version() -> None:
    comp = model("sample_comparison_normal.json")
    old = comp.model_construct(**{**comp.__dict__, "contract_version": "1.3.0"})
    with pytest.raises(BundleError, match="contract"):
        Bundle(bundle_version="v", data_classification=SYN).add(old)
