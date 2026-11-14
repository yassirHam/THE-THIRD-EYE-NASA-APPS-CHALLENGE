"""Contract 1.4.0: P2 r9 coverage states, required-year baselines, footprint evidence,
manifest binding and the proposed P1-A status mapping.

All values are fabricated [SYNTHETIC DEV FIXTURE] data. No sealed observation is read.
These tests validate RAW dicts (no coverage recomputation), unlike the older shims.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import get_args

import pytest
from pydantic import ValidationError

from contracts import build_fixtures as bf
from contracts.schemas import comparison as comparison_module
from contracts.schemas.calendar import (
    PARTIAL_REASON_TO_P2,
    CalendarArtifact,
    CoverageReason,
    FootprintCertification,
    PartialReason,
)
from contracts.schemas.manifest import ManifestBindingError, ProvenanceManifest, assert_manifest_describes
from contracts.schemas.status_mapping import (
    UnmappedStatusError,
    UnregisteredMappingError,
    load_mapping,
    map_p1a_statuses,
)

FIXTURES = Path(bf.FIXTURE_DIR)
CALENDARS = ["sample_calendar.json", "sample_calendar_sealed_boundary.json",
             "sample_calendar_unverified_footprint.json"]


def load(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def ok(data: dict) -> bool:
    try:
        CalendarArtifact.model_validate_json(json.dumps(data))
    except ValidationError:
        return False
    return True


def month(data: dict, sensor: str, year: int, m: int) -> dict:
    for s in data["monthly_series"]:
        for r in s["records"]:
            if (r["sensor"], r["year"], r["month"]) == (sensor, year, m):
                return r
    raise KeyError((sensor, year, m))


def week(data: dict, sensor: str, year: int, n: int) -> dict:
    for s in data["weekly_series"]:
        for r in s["records"]:
            if (r["sensor"], r["year"], r["week_number"]) == (sensor, year, n):
                return r
    raise KeyError((sensor, year, n))


# ------------------------------------------------------------------ fixtures, raw


@pytest.mark.parametrize("name", CALENDARS)
def test_committed_calendar_fixtures_validate_without_recomputation(name: str) -> None:
    assert ok(load(name))


@pytest.mark.parametrize("name", CALENDARS)
def test_fixture_coverage_fields_equal_an_independent_recomputation(name: str) -> None:
    data = load(name)
    assert bf.fill_coverage(copy.deepcopy(data)) == data


# ------------------------------------------------ P2 r9 required change 1: missing files


def test_mid_record_missing_files_month_is_partial_ineligible_with_null_labels() -> None:
    data = load("sample_calendar.json")
    rec = month(data, "VIIRS_SNPP", 2023, 11)
    assert rec["days_with_file"] < rec["days_in_period"]
    assert rec["is_partial_period"] and rec["partial_period_reason"] == "missing_days_or_tiles"
    assert rec["coverage_state"] == "partial" and rec["coverage_reasons"] == ["missing_days_or_tiles"]
    assert rec["unusual_status"] is None and rec["baseline_p90"] is None and not rec["comparison_eligible"]
    assert ok(data)


@pytest.mark.parametrize("change", [
    {"is_partial_period": False, "partial_period_reason": None, "coverage_state": "complete",
     "coverage_reasons": [], "unusual_status": "insufficient_baseline"},  # hidden gap
    {"unusual_status": "not_unusual"},  # a label on a partial period
    {"unusual_status": "insufficient_baseline"},  # still a non-null label
    {"coverage_reasons": []},  # reason dropped
    {"coverage_state": "complete"},
    {"comparison_eligible": True},
])
def test_mid_record_missing_files_cannot_be_hidden_labelled_or_compared(change: dict) -> None:
    data = load("sample_calendar.json")
    month(data, "VIIRS_SNPP", 2023, 11).update(change)
    assert not ok(data)


def test_missing_days_on_an_otherwise_complete_week_must_be_flagged() -> None:
    data = load("sample_calendar.json")
    rec = week(data, "MODIS_Aqua", 2023, 28)
    rec["days_with_file"] = 6
    rec.update(comparison_eligible=False, paired_comparison_eligible=False)
    week(data, "VIIRS_SNPP", 2023, 28)["paired_comparison_eligible"] = False
    assert not ok(data)  # not flagged
    rec.update(is_partial_period=True, partial_period_reason="missing_days_or_tiles", critical_status=None,
               unusual_status=None, coverage_state="partial", coverage_reasons=["missing_days_or_tiles"])
    assert ok(data)


def test_no_file_period_is_unavailable_and_never_zero() -> None:
    data = load("sample_calendar.json")
    rec = month(data, "VIIRS_SNPP", 2023, 9)
    assert rec["days_with_file"] == 0 and rec["coverage_state"] == "unavailable"
    assert rec["coverage_reasons"] == ["no_file"] and rec["detected_fire_cell_days"] is None
    rec.update(unavailable_reason="zero_usable_support", detected_fire_cell_days=0.0, usable_land_cell_days=0.0)
    assert not ok(data)  # a period with no file is not an observed zero


# ------------------------------------------- P2 r9 required change 3: reasons and scope


def test_every_partial_reason_has_an_explicit_p2_mapping() -> None:
    assert set(PARTIAL_REASON_TO_P2) == set(get_args(PartialReason))
    assert set(PARTIAL_REASON_TO_P2.values()) <= set(get_args(CoverageReason))
    assert set(get_args(CoverageReason)) == {
        "period_clipped", "sensor_not_operating", "partition_boundary",
        "missing_days_or_tiles", "low_processed_coverage", "no_file"}


def test_record_boundary_partials_list_period_clipped() -> None:
    data = load("sample_calendar.json")
    rec = week(data, "VIIRS_SNPP", 2012, 3)
    assert rec["coverage_reasons"] == ["period_clipped"] and rec["coverage_state"] == "partial"
    rec["coverage_reasons"] = []
    assert not ok(data)


def test_record_boundary_partial_with_missing_permitted_days_lists_both_reasons() -> None:
    data = load("sample_calendar.json")
    rec = week(data, "VIIRS_SNPP", 2012, 3)  # 4 days inside the record
    rec["days_with_file"] = 3
    assert not ok(data)
    rec["coverage_reasons"] = ["period_clipped", "missing_days_or_tiles"]
    assert ok(data)


def test_pre_record_start_period_is_unavailable_not_rejected() -> None:
    data = load("sample_calendar.json")
    rec = month(data, "VIIRS_SNPP", 2011, 12)
    assert rec["unavailable_reason"] == "sensor_not_operating"
    assert rec["coverage_reasons"] == ["sensor_not_operating"] and rec["coverage_state"] == "unavailable"
    assert ok(data)


@pytest.mark.parametrize("change", [
    {"unusual_status": "insufficient_baseline"},
    {"days_with_file": 3},
    {"unavailable_reason": "source_not_available", "coverage_reasons": ["no_file"]},
])
def test_pre_record_start_period_carries_no_files_labels_or_other_reason(change: dict) -> None:
    data = load("sample_calendar.json")
    month(data, "VIIRS_SNPP", 2011, 12).update(change)
    assert not ok(data)


def test_sensor_not_operating_is_rejected_inside_the_record() -> None:
    data = load("sample_calendar.json")
    month(data, "VIIRS_SNPP", 2023, 9).update(unavailable_reason="sensor_not_operating",
                                              coverage_reasons=["sensor_not_operating"])
    assert not ok(data)


def test_sealed_boundary_partials_list_partition_boundary() -> None:
    data = load("sample_calendar_sealed_boundary.json")
    rec = week(data, "MODIS_Aqua", 2020, 1)
    assert rec["coverage_reasons"] == ["partition_boundary"]
    rec["coverage_reasons"] = ["period_clipped"]
    assert not ok(data)


def test_low_processed_coverage_makes_the_period_partial() -> None:
    data = load("sample_calendar.json")
    rec = month(data, "VIIRS_SNPP", 2023, 6)
    for r in (rec, month(data, "MODIS_Aqua", 2023, 6)):
        r["paired_comparison_eligible"] = False
    rec["processed_coverage"] = 0.995  # below 1.0: C_MIN is unregistered, so any shortfall is low
    assert not ok(data)
    rec.update(is_partial_period=True, partial_period_reason="low_processed_coverage", unusual_status=None,
               baseline_median=None, baseline_p90=None, comparison_eligible=False,
               coverage_state="partial", coverage_reasons=["low_processed_coverage"])
    assert ok(data)
    rec["processed_coverage"] = 1.0
    assert not ok(data)  # reason without a shortfall


# --------------------------------------- P2 r9 required change 2: required-year baselines


def test_required_year_invalid_makes_the_baseline_unavailable() -> None:
    data = load("sample_calendar_unverified_footprint.json")
    b = data["seasonal_baselines"][1]
    assert b["status"] == "unavailable" and b["unavailable_reason"] == "required_year_invalid"
    assert [e["year"] for e in b["excluded_years"]] == [2017]
    assert ok(data)


@pytest.mark.parametrize("change", [
    # silently shortened: the invalid year simply disappears
    {"excluded_years": [], "status": "insufficient_baseline", "unavailable_reason": None},
    # invalid year still used
    {"eligible_prior_years": [2016, 2017, 2018, 2019], "excluded_years": [], "status": "insufficient_baseline",
     "unavailable_reason": None},
    # invalid year excluded, but the baseline keeps going with the rest
    {"status": "available", "unavailable_reason": None, "normal_season_start_month": 6,
     "normal_season_end_month": 9, "peak_median_month": 7},
    {"unavailable_reason": None},
])
def test_required_year_baseline_cannot_be_shortened_or_replaced(change: dict) -> None:
    data = load("sample_calendar_unverified_footprint.json")
    data["seasonal_baselines"][1].update(change)
    assert not ok(data)


def test_replacement_year_cannot_fill_an_invalid_required_year() -> None:
    data = load("sample_calendar_unverified_footprint.json")
    b = data["seasonal_baselines"][1]
    data["annual_coverage"].append(bf.annual(data["sensor_coverage"], "MODIS_Aqua", 2015))
    b.update(reference_start_year=2015, eligible_prior_years=[2015, 2016, 2018, 2019])
    assert ok(data)  # widening the span is visible, but the baseline stays unavailable
    b.update(status="available", unavailable_reason=None, normal_season_start_month=6,
             normal_season_end_month=9, peak_median_month=7)
    assert not ok(data)


def test_exclusion_reasons_must_be_backed_by_the_artifact() -> None:
    data = load("sample_calendar.json")
    b = data["seasonal_baselines"][0]
    b.update(reference_end_year=2020, excluded_years=[{"year": 2020, "reason": "sealed_evaluation_window",
                                                       "detail": None}])
    assert not ok(data)  # no sealed window declared
    b.update(excluded_years=[{"year": 2020, "reason": "partial_record_year", "detail": None}])
    assert not ok(data)  # 2020 is not a declared partial year


# --------------------------------------------------------- footprint certification (Q3)


def test_day_level_evidence_never_certifies_a_complete_footprint() -> None:
    base = {"geometry_id": "g", "certification_ref": "test-only-p2-doc", "certified_at": "2026-11-15T10:00:00Z"}
    for status, extra in (("complete", {}), ("partial", {"coverage_fraction": 0.9})):
        for evidence in ("day_level", "none"):
            with pytest.raises(ValidationError):
                FootprintCertification.model_validate_json(json.dumps(
                    {**base, "status": status, "footprint_evidence": evidence, **extra}))
    FootprintCertification.model_validate_json(json.dumps(
        {"geometry_id": "g", "status": "unverified", "footprint_evidence": "day_level"}))


def test_unverified_fixture_reflects_p2_r9_no_eligible_periods() -> None:
    data = load("sample_calendar_unverified_footprint.json")
    assert data["footprint_certification"]["status"] == "unverified"
    assert data["footprint_certification"]["footprint_evidence"] == "day_level"
    recs = [r for s in data["monthly_series"] + data["weekly_series"] for r in s["records"]]
    assert not any(r["comparison_eligible"] or r["paired_comparison_eligible"] for r in recs)


@pytest.mark.parametrize("classification", ["synthetic_dev_fixture", "production"])
def test_eligible_periods_without_any_certification_fail_closed(classification: str) -> None:
    data = load("sample_calendar.json")
    data["footprint_certification"] = None
    if classification == "production":
        data.update(data_classification="production", fixture_label=None, sealed_window={
            "start": "2011-01-01", "end": "2011-11-30", "registration_status": "registered",
            "registration_ref": "test-only-ref", "decision_date": "2026-11-15"})
    assert not ok(data)


def test_production_cannot_reuse_the_synthetic_certification() -> None:
    data = load("sample_calendar.json")
    data.update(data_classification="production", fixture_label=None, sealed_window={
        "start": "2011-01-01", "end": "2011-11-30", "registration_status": "registered",
        "registration_ref": "test-only-ref", "decision_date": "2026-11-15"})
    assert not ok(data)
    data["footprint_certification"]["certification_ref"] = "p2-cert-test-only-ref"
    assert ok(data)


# -------------------------------------------- manifest binding (P3 method_id concern)


def test_manifest_fixture_describes_the_calendar_fixture() -> None:
    man = ProvenanceManifest.model_validate_json((FIXTURES / "sample_manifest.json").read_text(encoding="utf-8"))
    cal = CalendarArtifact.model_validate_json((FIXTURES / "sample_calendar.json").read_text(encoding="utf-8"))
    assert man.method_id == cal.method_id == "same_sensor_calendar"
    assert_manifest_describes(man, cal, "calendar")


def test_manifest_binding_rejects_other_methods_and_families() -> None:
    raw = load("sample_manifest.json")
    cal = CalendarArtifact.model_validate_json((FIXTURES / "sample_calendar.json").read_text(encoding="utf-8"))
    man = ProvenanceManifest.model_validate_json(json.dumps(raw))
    with pytest.raises(ManifestBindingError):
        assert_manifest_describes(man, cal, "comparison")
    other = copy.deepcopy(raw)
    other["method_id"] = "artifact_manifest"  # the 1.3.0 self-describing identity
    other["partitions"][0]["method_id"] = "artifact_manifest"
    other["partitions"][0]["cache_key_sha256"] = bf.CacheKey(
        artifact_version="synthetic-v1", geometry_id=bf.GEO, period_spec=bf.PERIOD,
        method_id="artifact_manifest", policy_id=bf.POLICY).digest()
    man2 = ProvenanceManifest.model_validate_json(json.dumps(other))
    with pytest.raises(ManifestBindingError, match="method_id"):
        assert_manifest_describes(man2, cal, "calendar")


def test_manifest_requires_described_artifact_type() -> None:
    raw = load("sample_manifest.json")
    del raw["described_artifact_type"]
    with pytest.raises(ValidationError):
        ProvenanceManifest.model_validate_json(json.dumps(raw))


# ------------------------------------------------- P1-A vocabulary mapping (PROPOSED)

GOOD = dict(sensitivity="sensitive", applicability="evaluated_for_conditions", applicability_passed=True,
            headline="unresolved", practical_change="unspecified")


def test_mapping_is_unregistered_and_refuses_production_use() -> None:
    table = load_mapping()
    assert table["registered"] is False and table["decision_at"] is None and table["reference"] is None
    with pytest.raises(UnregisteredMappingError):
        map_p1a_statuses(**GOOD)


def test_mapping_targets_are_contract_enums() -> None:
    m = map_p1a_statuses(**GOOD, allow_unregistered=True)
    assert m.sensitivity_status == "sensitive_to_assumptions"
    assert m.applicability_status == "applicable"
    assert m.headline_direction == "unavailable"
    table = load_mapping()
    enums = {
        "sensitivity": comparison_module.SensitivityStatus,
        "applicability": comparison_module.ApplicabilityStatus,
        "headline": comparison_module.HeadlineDirection,
        "practical_change": comparison_module.PracticalChangeCategory,
        "inference": comparison_module.InferenceStatus,
    }
    for dim, enum in enums.items():
        for target in table[dim].values():
            assert target is None or target in get_args(enum), (dim, target)


def test_evaluated_is_not_passed_and_both_failed_spellings_agree() -> None:
    with pytest.raises(UnmappedStatusError):
        map_p1a_statuses(**{**GOOD, "applicability_passed": None}, allow_unregistered=True)
    a = map_p1a_statuses(**{**GOOD, "applicability_passed": False}, allow_unregistered=True)
    b = map_p1a_statuses(**{**GOOD, "applicability": "failed_applicability", "applicability_passed": None},
                         allow_unregistered=True)
    assert a.applicability_status == b.applicability_status == "failed_applicability"


@pytest.mark.parametrize("override", [
    {"applicability": "insufficient_evidence", "applicability_passed": None},  # awaiting P1 decision
    {"sensitivity": "stable"},  # unknown name
    {"headline": "no_change_detected"},
])
def test_unagreed_or_unknown_names_raise(override: dict) -> None:
    with pytest.raises(UnmappedStatusError):
        map_p1a_statuses(**{**GOOD, **override}, allow_unregistered=True)


def test_registered_mapping_needs_decision_time_and_reference() -> None:
    table = load_mapping()
    table["registered"] = True
    with pytest.raises(UnregisteredMappingError):
        map_p1a_statuses(**GOOD, mapping=table)


# ------------------------------------------ versioning and cross-identity reuse (1.4.0)

ALL_FIXTURES = sorted(p.name for p in FIXTURES.glob("*.json"))


@pytest.mark.parametrize("name", ALL_FIXTURES)
def test_artifact_without_or_with_an_older_version_is_rejected(name: str) -> None:
    from contracts.build_fixtures import all_fixtures
    model = all_fixtures()[name][0]
    raw = load(name)
    for bad in ("1.4.0", "1.3.0", "1.1.0"):
        with pytest.raises(ValidationError):
            model.model_validate_json(json.dumps({**raw, "contract_version": bad}))
    del raw["contract_version"]
    with pytest.raises(ValidationError):
        model.model_validate_json(json.dumps(raw))


@pytest.mark.parametrize("field,value", [("geometry_id", "geo-synthetic-sub-a"),
                                         ("period_spec", "synthetic-2024"),
                                         ("policy_id", "common_support_eligible"),
                                         ("method_id", "stage_a_finite_factors")])
def test_manifest_partition_cannot_describe_another_identity(field: str, value: str) -> None:
    raw = load("sample_manifest.json")
    raw["partitions"][0][field] = value
    with pytest.raises(ValidationError, match="partition identity"):
        ProvenanceManifest.model_validate_json(json.dumps(raw))


@pytest.mark.parametrize("field,value", [("geometry_id", "geo-synthetic-sub-a"),
                                         ("period_spec", "synthetic-2024"),
                                         ("policy_id", "common_support_eligible"),
                                         ("artifact_version", "synthetic-v2")])
def test_manifest_cannot_be_bound_to_a_calendar_with_another_identity(field: str, value: str) -> None:
    man = ProvenanceManifest.model_validate_json((FIXTURES / "sample_manifest.json").read_text(encoding="utf-8"))
    cal_raw = load("sample_calendar.json")
    cal_raw[field] = value
    if field == "geometry_id":
        cal_raw["footprint_certification"]["geometry_id"] = value
    if field == "policy_id":
        for s in cal_raw["monthly_series"] + cal_raw["weekly_series"]:
            s["policy_id"] = value
        for b in cal_raw["seasonal_baselines"]:
            b["policy_id"] = value
    cal = CalendarArtifact.model_validate_json(json.dumps(cal_raw))
    with pytest.raises(ManifestBindingError, match=field):
        assert_manifest_describes(man, cal, "calendar")


def test_partition_cache_key_must_be_the_manifest_identity_digest() -> None:
    raw = load("sample_manifest.json")
    raw["partitions"][0]["cache_key_sha256"] = bf.CacheKey(
        artifact_version="synthetic-v1", geometry_id="geo-synthetic-sub-a", period_spec=bf.PERIOD,
        method_id="same_sensor_calendar", policy_id=bf.POLICY).digest()
    with pytest.raises(ValidationError, match="digest"):
        ProvenanceManifest.model_validate_json(json.dumps(raw))


# ------------------------------------- 1.5.0: replayable manifest partitions (P4-A / P5-B)


def test_calendar_partition_may_name_no_single_sensor() -> None:
    raw = load("sample_manifest.json")
    assert raw["partitions"][0]["sensor"] is None
    ProvenanceManifest.model_validate_json(json.dumps(raw))
    del raw["partitions"][0]["sensor"]
    with pytest.raises(ValidationError):  # required key: null must be explicit
        ProvenanceManifest.model_validate_json(json.dumps(raw))


def _cal(name: str) -> CalendarArtifact:
    return CalendarArtifact.model_validate_json((FIXTURES / name).read_text(encoding="utf-8"))


@pytest.mark.parametrize("claimed,ok_for_certified,ok_for_unverified", [
    ("complete", True, False), ("partial", False, False), ("unverified", False, True), ("unavailable", False, False)])
def test_manifest_coverage_cannot_exceed_the_calendar_certification(claimed, ok_for_certified, ok_for_unverified) -> None:
    raw = load("sample_manifest.json")
    raw["partitions"][0]["coverage_status"] = claimed
    man = ProvenanceManifest.model_validate_json(json.dumps(raw))
    for cal, ok_ in ((_cal("sample_calendar.json"), ok_for_certified),
                     (_cal("sample_calendar_unverified_footprint.json"), ok_for_unverified)):
        if ok_:
            assert_manifest_describes(man, cal, "calendar")
        else:
            with pytest.raises(ManifestBindingError, match="certification"):
                assert_manifest_describes(man, cal, "calendar")


def test_manifest_and_artifact_must_share_data_classification() -> None:
    man = ProvenanceManifest.model_validate_json((FIXTURES / "sample_manifest.json").read_text(encoding="utf-8"))
    cal = _cal("sample_calendar.json")
    prod = cal.model_construct(**{**cal.__dict__, "data_classification": "production", "fixture_label": None})
    with pytest.raises(ManifestBindingError, match="classification"):
        assert_manifest_describes(man, prod, "calendar")
