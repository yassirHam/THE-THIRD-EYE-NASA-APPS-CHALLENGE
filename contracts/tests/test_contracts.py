"""Contract tests: fixtures validate and forbidden states are rejected."""

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from contracts import build_fixtures as bf
from contracts import generate_ts
from contracts.schemas import (
    CacheKey,
    CacheKeyMismatch,
    ClaimAuditRecord,
    ComparisonResult,
    assert_cache_key_match,
)

FIXTURES = Path(bf.FIXTURE_DIR)
MODELS = {name: model for name, (model, _) in bf.all_fixtures().items()}


def load(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def fails(model, data: dict) -> None:
    with pytest.raises(ValidationError):
        model.model_validate_json(json.dumps(data))


@pytest.mark.parametrize("name", sorted(MODELS))
def test_committed_fixture_validates_and_is_labelled(name: str) -> None:
    text = (FIXTURES / name).read_text(encoding="utf-8")
    obj = MODELS[name].model_validate_json(text)
    assert obj.fixture_label == "[SYNTHETIC DEV FIXTURE]"
    assert obj.data_classification == "synthetic_dev_fixture"


def test_fixture_files_match_builder_and_no_strays() -> None:
    expected = {name: data for name, (_, data) in bf.all_fixtures().items()}
    assert {p.name for p in FIXTURES.glob("*.json")} == set(expected)
    for name, data in expected.items():
        assert load(name) == json.loads(json.dumps(data))


def test_generated_types_are_current() -> None:
    assert generate_ts.OUTPUT.read_text(encoding="utf-8") == generate_ts.build()


def test_no_legacy_unresolved_enum_anywhere() -> None:
    sources = [generate_ts.build()] + [
        p.read_text(encoding="utf-8") for p in (Path(bf.__file__).parent / "schemas").glob("*.py")
    ]
    assert not any("unresolved" in s.lower() for s in sources)

@pytest.mark.parametrize("model_name", sorted(MODELS))
def test_unknown_fields_rejected(model_name: str) -> None:
    data = load(model_name)
    data["surprise"] = 1
    fails(MODELS[model_name], data)


def test_status_dimensions_cover_required_edge_cases() -> None:
    cases = {p.name: load(p.name) for p in FIXTURES.glob("sample_comparison_*.json")}
    pairs = {(c["sensitivity_status"], c["applicability_status"]) for c in cases.values()}
    assert ("stable_across_displayed_settings", "failed_applicability") in pairs
    assert ("unavailable", "missing_required_support") in pairs
    assert ("stable_across_displayed_settings", "out_of_domain") in pairs
    assert ("sensitive_to_assumptions", "applicable") in pairs
    within = load("sample_comparison_within_margin_opposite_sign.json")
    signs = {v["direction"] for v in within["registered_variants"]}
    assert {"increase", "decrease"} <= signs
    assert within["practical_change"]["category"] == "within_practical_margin"
    assert all(c["inference_status"] == "not_established" for c in cases.values())


def test_inference_cannot_be_upgraded() -> None:
    data = load("sample_comparison_normal.json")
    data["inference_status"] = "statistically_supported"
    fails(ComparisonResult, data)


def test_legacy_unresolved_rejected() -> None:
    data = load("sample_comparison_normal.json")
    data["sensitivity_status"] = "unresolved"
    fails(ComparisonResult, data)


def test_stable_but_failed_cannot_publish_direction_or_eligibility() -> None:
    data = load("sample_comparison_stable_failed_applicability.json")
    data["headline_direction"] = "increase"
    fails(ComparisonResult, data)
    data = load("sample_comparison_stable_failed_applicability.json")
    data["conclusion_eligible"] = True
    fails(ComparisonResult, data)


def test_applicable_requires_all_checks_passed() -> None:
    data = load("sample_comparison_normal.json")
    data["applicability_checks"][1]["status"] = "failed"
    fails(ComparisonResult, data)


def test_summary_must_preserve_failed_vs_missing_vs_out_of_domain() -> None:
    data = load("sample_comparison_stable_failed_applicability.json")
    data["reviewed_summary"]["output_category"] = "outside_evaluated_calibration"
    data["reviewed_summary"]["status_label"] = "Outside evaluated calibration"
    fails(ComparisonResult, data)


def test_missing_required_variant_cannot_be_called_stable() -> None:
    data = load("sample_comparison_normal.json")
    data["registered_variants"].pop()
    fails(ComparisonResult, data)


def test_within_margin_rejects_variant_outside_tau() -> None:
    data = load("sample_comparison_within_margin_opposite_sign.json")
    data["registered_variants"][0]["effect_delta"] = 0.9
    fails(ComparisonResult, data)


def test_practical_category_requires_preregistered_margin() -> None:
    data = load("sample_comparison_normal.json")
    data["practical_change"]["practical_margin_tau"] = None
    fails(ComparisonResult, data)


def test_zero_support_is_null_not_zero() -> None:
    cal = load("sample_calendar.json")
    aug = cal["monthly_series"][0]["records"][2]
    assert aug["fire_activity_index"] is None and aug["availability"] == "unavailable"
    aug["fire_activity_index"] = 0.0
    fails(MODELS["sample_calendar.json"], cal)


def test_valid_zero_rate_with_positive_support_is_available() -> None:
    cal = load("sample_calendar.json")
    june = cal["monthly_series"][0]["records"][0]
    assert june["fire_activity_index"] == 0.0 and june["availability"] == "available"
    june["availability"] = "unavailable"
    fails(MODELS["sample_calendar.json"], cal)


def test_rate_must_equal_sum_ratio() -> None:
    cal = load("sample_calendar.json")
    cal["monthly_series"][0]["records"][1]["fire_activity_index"] = 1.0
    fails(MODELS["sample_calendar.json"], cal)


def test_threshold_tie_is_not_unusual() -> None:
    cal = load("sample_calendar.json")
    rec = cal["monthly_series"][0]["records"][1]  # R = 150
    rec["baseline_p90"] = rec["fire_activity_index"]
    fails(MODELS["sample_calendar.json"], cal)  # still labelled unusual
    rec["unusual_status"] = "not_unusual"
    MODELS["sample_calendar.json"].model_validate_json(json.dumps(cal))


def test_snpp_partial_november_and_no_extension() -> None:
    cal = load("sample_calendar.json")
    nov = cal["monthly_series"][0]["records"][5]
    assert nov["is_partial_period"] and not nov["comparison_eligible"]
    nov["comparison_eligible"] = True
    fails(MODELS["sample_calendar.json"], cal)
    cal = load("sample_calendar.json")
    cal["monthly_series"][0]["records"][5]["month"] = 12
    fails(MODELS["sample_calendar.json"], cal)


def test_series_cannot_mix_sensors() -> None:
    cal = load("sample_calendar.json")
    cal["monthly_series"][0]["records"][0]["sensor"] = "MODIS_Aqua"
    fails(MODELS["sample_calendar.json"], cal)


def test_insufficient_baseline_publishes_no_season() -> None:
    cal = load("sample_calendar.json")
    cal["seasonal_baselines"][1]["peak_median_month"] = 7
    fails(MODELS["sample_calendar.json"], cal)


def test_raw_only_cannot_reference_evaluated_identity() -> None:
    sel = load("sample_region_selector.json")
    sel["options"][1]["evaluated_method_id"] = "stage_a_finite_factors"
    fails(MODELS["sample_region_selector.json"], sel)


def test_unavailable_geometry_needs_reason_and_no_comparison() -> None:
    sel = load("sample_region_selector.json")
    sel["options"][2]["unavailable_reason"] = None
    fails(MODELS["sample_region_selector.json"], sel)
    sel = load("sample_region_selector.json")
    sel["options"][2]["comparison_access_status"] = "raw_only"
    fails(MODELS["sample_region_selector.json"], sel)


def test_selector_has_raw_only_unavailable_and_evaluated() -> None:
    sel = load("sample_region_selector.json")
    states = {o["comparison_access_status"] for o in sel["options"]}
    assert {"raw_only", "unavailable", "evaluated_comparison"} <= states


def test_firms_isolation_flags_cannot_be_flipped() -> None:
    for flag in ("feeds_grid_math", "inherits_grid_calibration", "cross_sensor_trend_allowed"):
        data = load("sample_firms_hotspots.json")
        data[flag] = True
        fails(MODELS["sample_firms_hotspots.json"], data)


def test_headline_requires_counts_with_denominator_and_units() -> None:
    ev = load("sample_evaluation_summary.json")
    head = ev["landing_headline_metric"]
    assert head["registered_case_count"] == 20
    assert set(head["independent_units"]) >= {"blocks", "regions", "test_years"}
    head["raw_wrong_way_count"] = 21
    fails(MODELS["sample_evaluation_summary.json"], ev)


def test_unavailable_evaluation_has_null_metrics_not_zeros() -> None:
    ev = load("sample_evaluation_unavailable.json")
    assert ev["landing_headline_metric"]["registered_case_count"] is None
    ev["baseline_a_raw_handover"]["mean_reference_relative_error"] = 0.0
    fails(MODELS["sample_evaluation_unavailable.json"], ev)


def test_synthetic_label_required_and_forbidden_on_production() -> None:
    data = load("sample_comparison_normal.json")
    data["fixture_label"] = None
    fails(ComparisonResult, data)
    data = copy.deepcopy(load("sample_comparison_normal.json"))
    data["data_classification"] = "production"
    fails(ComparisonResult, data)


def test_manifest_partition_identity_cannot_cross_geometry() -> None:
    man = load("sample_manifest.json")
    man["partitions"][0]["geometry_id"] = "geo-other"
    fails(MODELS["sample_manifest.json"], man)


def test_manifest_cessation_date_and_checksum() -> None:
    man = load("sample_manifest.json")
    assert man["snpp_cessation_date"] == "2026-11-02"
    man["partitions"][0]["sha256_checksum"] = "xyz"
    fails(MODELS["sample_manifest.json"], man)


# ---- Fix 1: headline / sensitivity derived from registered effects -------------------


def set_effects(data: dict, deltas: list[float]) -> dict:
    for v, d in zip(data["registered_variants"], deltas):
        v["effect_delta"] = d
        v["direction"] = "increase" if d > 0 else "decrease" if d < 0 else "no_change"
    return data


def test_headline_cannot_contradict_effects() -> None:
    data = load("sample_comparison_normal.json")
    data["headline_direction"] = "decrease"
    fails(ComparisonResult, data)
    data["headline_direction"] = "no_change"
    fails(ComparisonResult, data)


def test_headline_for_within_margin_must_be_no_change() -> None:
    data = load("sample_comparison_within_margin_opposite_sign.json")
    data["headline_direction"] = "increase"
    fails(ComparisonResult, data)


def test_stable_label_rejected_when_effects_cross_margin() -> None:
    data = load("sample_comparison_normal.json")  # tau 0.5, all increase
    set_effects(data, [2.0, 0.1, 1.8])  # one variant falls within the margin
    fails(ComparisonResult, data)


def test_stable_label_rejected_when_signs_conflict_without_margin() -> None:
    data = load("sample_comparison_sensitive.json")
    data["sensitivity_status"] = "stable_across_displayed_settings"
    data["reviewed_summary"]["output_category"] = "consistent_across_tested_corrections"
    data["reviewed_summary"]["status_label"] = "Consistent across tested corrections"
    data["headline_direction"] = "increase"
    fails(ComparisonResult, data)


def test_sensitive_label_rejected_when_effects_agree() -> None:
    data = load("sample_comparison_normal.json")
    data["sensitivity_status"] = "sensitive_to_assumptions"
    data["headline_direction"] = "ambiguous"
    data["reviewed_summary"]["output_category"] = "depends_on_the_correction"
    data["reviewed_summary"]["status_label"] = "Depends on the correction"
    fails(ComparisonResult, data)


def test_sensitive_requires_ambiguous_headline() -> None:
    data = load("sample_comparison_sensitive.json")
    data["headline_direction"] = "increase"
    fails(ComparisonResult, data)


def test_sensitive_with_margin_uses_inconsistent_category() -> None:
    data = load("sample_comparison_sensitive.json")
    set_effects(data, [2.0, 0.2, 0.1])  # tau 0.5: increase vs within
    data["practical_change"] = {
        "category": "inconsistent_across_variants", "magnitude": 2.0, "effect_units": "R points",
        "practical_margin_tau": 0.5, "observed_signs": ["increase"],
    }
    ComparisonResult.model_validate_json(json.dumps(data))
    data["practical_change"]["category"] = "meaningful_increase"
    fails(ComparisonResult, data)


def test_magnitude_and_signs_must_match_effects() -> None:
    data = load("sample_comparison_normal.json")
    data["practical_change"]["magnitude"] = 0.1
    fails(ComparisonResult, data)
    data = load("sample_comparison_normal.json")
    data["practical_change"]["observed_signs"] = ["decrease"]
    fails(ComparisonResult, data)


def test_boundary_effect_equal_to_tau_is_within_margin() -> None:
    data = load("sample_comparison_within_margin_opposite_sign.json")
    set_effects(data, [0.5, -0.5, 0.0])
    data["practical_change"]["magnitude"] = 0.5
    data["practical_change"]["observed_signs"] = ["increase", "decrease", "no_change"]
    ComparisonResult.model_validate_json(json.dumps(data))


def test_missing_variant_cannot_publish_category_or_direction() -> None:
    data = load("sample_comparison_missing_evidence.json")
    data["headline_direction"] = "increase"
    fails(ComparisonResult, data)


# ---- Fix 2: claim audit preserves failed / missing / out-of-domain -----------------

AUDIT = {
    "failed_applicability": "sample_claim_audit_stable_failed_applicability.json",
    "missing_required_support": "sample_claim_audit_missing_evidence.json",
    "out_of_domain": "sample_claim_audit_out_of_domain.json",
}
CATEGORY = {
    "failed_applicability": ("calibration_check_failed", "Calibration check failed"),
    "missing_required_support": ("not_enough_usable_evidence", "Not enough usable evidence"),
    "out_of_domain": ("outside_evaluated_calibration", "Outside evaluated calibration"),
}


@pytest.mark.parametrize("status", sorted(AUDIT))
def test_claim_audit_summary_cannot_swap_applicability_state(status: str) -> None:
    assert load(AUDIT[status])["applicability_status"] == status
    for other, (cat, label) in CATEGORY.items():
        if other == status:
            continue
        data = load(AUDIT[status])
        data["reviewed_summary"]["output_category"] = cat
        data["reviewed_summary"]["status_label"] = label
        fails(ClaimAuditRecord, data)


@pytest.mark.parametrize("status", sorted(AUDIT))
def test_claim_audit_cannot_hide_adverse_state_as_consistent(status: str) -> None:
    data = load(AUDIT[status])
    data["reviewed_summary"]["output_category"] = "consistent_across_tested_corrections"
    data["reviewed_summary"]["status_label"] = "Consistent across tested corrections"
    fails(ClaimAuditRecord, data)
    data = load(AUDIT[status])
    data["conclusion_eligible"] = True
    fails(ClaimAuditRecord, data)


def test_claim_audit_applicability_needs_matching_check() -> None:
    data = load(AUDIT["failed_applicability"])
    for c in data["applicability_checks"]:
        c["status"] = "passed"
    fails(ClaimAuditRecord, data)


# ---- Fix 3: genuinely missing data stays missing, with the right reason --------------


@pytest.mark.parametrize("idx,reason", [(3, "source_not_available"), (4, "incomplete_footprint")])
def test_missing_source_or_footprint_keeps_null_d_o(idx: int, reason: str) -> None:
    cal = load("sample_calendar.json")
    rec = cal["monthly_series"][0]["records"][idx]
    assert rec["unavailable_reason"] == reason
    assert rec["detected_fire_cell_days"] is None and rec["usable_land_cell_days"] is None
    assert rec["fire_activity_index"] is None and rec["comparison_eligible"] is False
    # Zero-filling missing data is rejected.
    rec["detected_fire_cell_days"] = 0.0
    rec["usable_land_cell_days"] = 0.0
    fails(MODELS["sample_calendar.json"], cal)


def test_missing_data_cannot_be_labelled_zero_support() -> None:
    cal = load("sample_calendar.json")
    cal["monthly_series"][0]["records"][3]["unavailable_reason"] = "zero_usable_support"
    fails(MODELS["sample_calendar.json"], cal)


def test_observed_zero_support_cannot_be_labelled_missing_source() -> None:
    cal = load("sample_calendar.json")
    rec = cal["monthly_series"][0]["records"][2]
    assert rec["unavailable_reason"] == "zero_usable_support"
    rec["unavailable_reason"] = "source_not_available"
    fails(MODELS["sample_calendar.json"], cal)


def test_unavailable_requires_reason_and_weekly_missing_is_null() -> None:
    cal = load("sample_calendar.json")
    wk = cal["weekly_series"][0]["records"][3]
    assert wk["unavailable_reason"] == "qa_unusable" and wk["usable_land_cell_days"] is None
    wk["unavailable_reason"] = None
    fails(MODELS["sample_calendar.json"], cal)


def test_available_requires_real_values_and_unavailable_not_eligible() -> None:
    cal = load("sample_calendar.json")
    cal["monthly_series"][0]["records"][0]["usable_land_cell_days"] = None
    fails(MODELS["sample_calendar.json"], cal)
    cal = load("sample_calendar.json")
    cal["monthly_series"][0]["records"][3]["comparison_eligible"] = True
    fails(MODELS["sample_calendar.json"], cal)


# ---- Fix 4: five-field cache key ------------------------------------------------------

BASE_KEY = dict(
    artifact_version="v1", geometry_id="g", period_spec="p", method_id="m", policy_id="pol"
)


def test_cache_key_is_exactly_five_fields_and_stable() -> None:
    assert list(CacheKey.model_fields) == [
        "artifact_version", "geometry_id", "period_spec", "method_id", "policy_id"
    ]
    assert CacheKey(**BASE_KEY).digest() == CacheKey(**BASE_KEY).digest()
    assert CacheKey(**BASE_KEY).digest().startswith("tte-cache-v1:")


@pytest.mark.parametrize("field", sorted(BASE_KEY))
def test_changing_any_one_field_changes_the_key(field: str) -> None:
    other = dict(BASE_KEY, **{field: BASE_KEY[field] + "-x"})
    assert CacheKey(**other).digest() != CacheKey(**BASE_KEY).digest()


def test_cache_key_is_delimiter_safe() -> None:
    a = CacheKey(**dict(BASE_KEY, geometry_id="a|b", period_spec="c"))
    b = CacheKey(**dict(BASE_KEY, geometry_id="a", period_spec="b|c"))
    assert a.digest() != b.digest()


@pytest.mark.parametrize("field", sorted(BASE_KEY))
def test_consumer_check_rejects_cross_key_reuse(field: str) -> None:
    art = ComparisonResult.model_validate_json((FIXTURES / "sample_comparison_normal.json").read_text("utf-8"))
    good = art.cache_key()
    assert_cache_key_match(good, art)
    bad = good.model_copy(update={field: getattr(good, field) + "-other"})
    with pytest.raises(CacheKeyMismatch, match=field):
        assert_cache_key_match(bad, art)


def test_subarea_cannot_borrow_parent_cache_key() -> None:
    parent = ComparisonResult.model_validate_json((FIXTURES / "sample_comparison_normal.json").read_text("utf-8"))
    sub = parent.model_copy(update={"geometry_id": "geo-synthetic-sub-a"})
    with pytest.raises(CacheKeyMismatch, match="geometry_id"):
        assert_cache_key_match(parent.cache_key(), sub)


def test_manifest_partition_cache_key_must_match_identity() -> None:
    man = load("sample_manifest.json")
    expected = CacheKey(
        artifact_version=man["artifact_version"], geometry_id=man["geometry_id"],
        period_spec=man["period_spec"], method_id=man["method_id"], policy_id=man["policy_id"],
    ).digest()
    assert man["partitions"][0]["cache_key_sha256"] == expected
    man["artifact_version"] = "synthetic-v2"
    fails(MODELS["sample_manifest.json"], man)