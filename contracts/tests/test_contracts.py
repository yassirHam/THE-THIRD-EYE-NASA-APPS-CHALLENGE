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
from contracts.schemas.calendar import CalendarArtifact
from contracts.tests._coverage import CalendarWithDerivedCoverage

# Calendar checks recompute 1.4.0 coverage fields first (see tests/_coverage.py); raw validation
# of committed fixtures and of the coverage rules is in test_coverage_reasons.py.
MODELS = {name: (CalendarWithDerivedCoverage if model is CalendarArtifact else model)
          for name, (model, _) in bf.all_fixtures().items()}
# Test-only artifact for the reserved S-NPP cutoff path (P2 r8 item 3). It is never written to
# contracts/fixtures, because current-phase consumer fixtures hold no data after 2025-12-31.
CUTOFF = "reserved_cutoff_calendar"
CAL_MODEL = MODELS["sample_calendar.json"]


def load(name: str) -> dict:
    if name == CUTOFF:
        return json.loads(json.dumps(bf.reserved_cutoff_calendar()))
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
    cal = load(CUTOFF)
    aug = cal["monthly_series"][0]["records"][2]
    assert aug["fire_activity_index"] is None and aug["availability"] == "unavailable"
    aug["fire_activity_index"] = 0.0
    fails(CAL_MODEL, cal)


def test_valid_zero_rate_with_positive_support_is_available() -> None:
    cal = load(CUTOFF)
    june = cal["monthly_series"][0]["records"][0]
    assert june["fire_activity_index"] == 0.0 and june["availability"] == "available"
    june["availability"] = "unavailable"
    fails(CAL_MODEL, cal)


def test_rate_must_equal_sum_ratio() -> None:
    cal = load(CUTOFF)
    cal["monthly_series"][0]["records"][1]["fire_activity_index"] = 1.0
    fails(CAL_MODEL, cal)


def test_threshold_tie_is_not_unusual() -> None:
    cal = load(CUTOFF)
    rec = cal["monthly_series"][0]["records"][1]  # R = 150
    rec["baseline_p90"] = rec["fire_activity_index"]
    fails(CAL_MODEL, cal)  # still labelled unusual
    rec["unusual_status"] = "not_unusual"
    CAL_MODEL.model_validate_json(json.dumps(cal))


def test_snpp_partial_november_and_no_extension() -> None:
    cal = load(CUTOFF)
    nov = cal["monthly_series"][0]["records"][5]
    assert nov["is_partial_period"] and not nov["comparison_eligible"]
    nov["comparison_eligible"] = True
    fails(CAL_MODEL, cal)
    cal = load(CUTOFF)
    cal["monthly_series"][0]["records"][5]["month"] = 12
    fails(CAL_MODEL, cal)


def test_series_cannot_mix_sensors() -> None:
    cal = load(CUTOFF)
    cal["monthly_series"][0]["records"][0]["sensor"] = "MODIS_Aqua"
    fails(CAL_MODEL, cal)


def test_insufficient_baseline_publishes_no_season() -> None:
    cal = load(CUTOFF)
    cal["seasonal_baselines"][1]["peak_median_month"] = 7
    fails(CAL_MODEL, cal)


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


def test_headline_for_within_margin_cannot_be_no_change() -> None:
    data = load("sample_comparison_within_margin_opposite_sign.json")
    assert data["headline_direction"] == "within_practical_margin"
    # Cannot describe effects within the practical margin as no_change because effects are non-zero (+0.3, -0.2, +0.1)
    data["headline_direction"] = "no_change"
    fails(ComparisonResult, data)
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


def test_missing_required_variant_preserves_observed_sensitivity_while_unavailable() -> None:
    data = load("sample_comparison_sensitive.json")
    # Pop one required variant so required variants are incomplete
    data["registered_variants"].pop()  # leaves full_training (+2.0) and ex_2016 (-1.0)
    data["headline_direction"] = "unavailable"
    data["practical_change"] = {"category": "unavailable", "observed_signs": ["increase", "decrease"]}
    data["missing_evidence_reasons"] = ["Required leave-one-year-out variant ex_2017 is missing."]
    data["conclusion_eligible"] = False
    data["reviewed_summary"]["output_category"] = "not_enough_usable_evidence"
    data["reviewed_summary"]["status_label"] = "Not enough usable evidence"
    # Sensitivity is observed among available variants -> preserved as sensitive_to_assumptions
    ComparisonResult.model_validate_json(json.dumps(data))

    # Setting sensitivity to unavailable when available variants disagree is rejected
    data["sensitivity_status"] = "unavailable"
    fails(ComparisonResult, data)

    # Setting sensitivity to stable when required variant is missing is rejected
    data["sensitivity_status"] = "stable_across_displayed_settings"
    fails(ComparisonResult, data)

    # Trying to publish a conclusion or direction while incomplete is rejected
    data["sensitivity_status"] = "sensitive_to_assumptions"
    data["conclusion_eligible"] = True
    fails(ComparisonResult, data)
    data["conclusion_eligible"] = False
    data["headline_direction"] = "ambiguous"
    fails(ComparisonResult, data)


def test_failed_applicability_with_missing_variant_preserves_both_facts() -> None:
    data = load("sample_comparison_stable_failed_applicability.json")
    data["registered_variants"].pop()
    data["missing_evidence_reasons"] = ["Required variant ex_2017 missing."]
    data["sensitivity_status"] = "unavailable"
    data["headline_direction"] = "unavailable"
    data["practical_change"] = {"category": "unavailable"}
    data["conclusion_eligible"] = False

    # Hiding failed check under generic "not_enough_usable_evidence" is rejected
    data["reviewed_summary"]["output_category"] = "not_enough_usable_evidence"
    data["reviewed_summary"]["status_label"] = "Not enough usable evidence"
    fails(ComparisonResult, data)

    # Hiding missing evidence under "calibration_check_failed" is rejected
    data["reviewed_summary"]["output_category"] = "calibration_check_failed"
    data["reviewed_summary"]["status_label"] = "Calibration check failed"
    fails(ComparisonResult, data)

    # Both facts preserved in compound category passes
    data["reviewed_summary"]["output_category"] = "calibration_check_failed_and_missing_evidence"
    data["reviewed_summary"]["status_label"] = "Calibration check failed and required evidence missing"
    ComparisonResult.model_validate_json(json.dumps(data))


def test_claim_audit_failed_applicability_with_missing_evidence_preserves_both() -> None:
    data = load("sample_claim_audit_stable_failed_applicability.json")
    data["missing_evidence_reasons"] = ["Required factor variant support file missing."]
    data["sensitivity_status"] = "unavailable"
    data["practical_change"] = {"category": "unavailable"}
    data["conclusion_eligible"] = False

    # Hiding failed check under generic "not_enough_usable_evidence" is rejected
    data["reviewed_summary"]["output_category"] = "not_enough_usable_evidence"
    data["reviewed_summary"]["status_label"] = "Not enough usable evidence"
    fails(ClaimAuditRecord, data)

    # Hiding missing evidence under "calibration_check_failed" is rejected
    data["reviewed_summary"]["output_category"] = "calibration_check_failed"
    data["reviewed_summary"]["status_label"] = "Calibration check failed"
    fails(ClaimAuditRecord, data)

    # Both facts preserved in compound category passes
    data["reviewed_summary"]["output_category"] = "calibration_check_failed_and_missing_evidence"
    data["reviewed_summary"]["status_label"] = "Calibration check failed and required evidence missing"
    ClaimAuditRecord.model_validate_json(json.dumps(data))


def test_comparison_failed_check_with_missing_check_and_present_variants_preserves_both() -> None:
    # F-01 regression: all variants present, failed check + missing check + explicit reason
    data = load("sample_comparison_stable_failed_applicability.json")
    data["applicability_checks"].append({"check_id": "sensor_calibration", "status": "missing", "detail": "Missing sensor check"})
    data["missing_evidence_reasons"] = ["Sensor calibration check missing"]
    data["conclusion_eligible"] = False

    # Validating with calibration_check_failed conceals missing evidence and is rejected
    data["reviewed_summary"]["output_category"] = "calibration_check_failed"
    data["reviewed_summary"]["status_label"] = "Calibration check failed"
    fails(ComparisonResult, data)

    # Preserving both facts in compound category passes
    data["reviewed_summary"]["output_category"] = "calibration_check_failed_and_missing_evidence"
    data["reviewed_summary"]["status_label"] = "Calibration check failed and required evidence missing"
    ComparisonResult.model_validate_json(json.dumps(data))


def test_claim_audit_failed_check_with_missing_check_empty_reasons_preserves_both() -> None:
    # F-01 regression: claim audit with failed check + missing check and empty reasons
    data = load("sample_claim_audit_stable_failed_applicability.json")
    data["applicability_checks"].append({"check_id": "sensor_check", "status": "missing", "detail": "Missing sensor support"})
    data["missing_evidence_reasons"] = []
    data["conclusion_eligible"] = False

    # Validating with calibration_check_failed conceals missing check and is rejected
    data["reviewed_summary"]["output_category"] = "calibration_check_failed"
    data["reviewed_summary"]["status_label"] = "Calibration check failed"
    fails(ClaimAuditRecord, data)

    # Preserving both facts in compound category passes
    data["reviewed_summary"]["output_category"] = "calibration_check_failed_and_missing_evidence"
    data["reviewed_summary"]["status_label"] = "Calibration check failed and required evidence missing"
    ClaimAuditRecord.model_validate_json(json.dumps(data))


def test_out_of_domain_with_missing_variant_preserves_both_facts() -> None:
    # F-02 regression: out-of-domain check + missing required variant
    data = load("sample_comparison_out_of_domain.json")
    data["registered_variants"].pop()
    data["missing_evidence_reasons"] = ["Required variant ex_2017 missing."]
    data["sensitivity_status"] = "unavailable"
    data["headline_direction"] = "unavailable"
    data["practical_change"] = {"category": "unavailable"}
    data["conclusion_eligible"] = False

    # Hiding out_of_domain under generic "not_enough_usable_evidence" is rejected
    data["reviewed_summary"]["output_category"] = "not_enough_usable_evidence"
    data["reviewed_summary"]["status_label"] = "Not enough usable evidence"
    fails(ComparisonResult, data)

    # Hiding missing variant under "outside_evaluated_calibration" is rejected
    data["reviewed_summary"]["output_category"] = "outside_evaluated_calibration"
    data["reviewed_summary"]["status_label"] = "Outside evaluated calibration"
    fails(ComparisonResult, data)

    # Preserving both facts in compound category passes
    data["reviewed_summary"]["output_category"] = "outside_evaluated_calibration_and_missing_evidence"
    data["reviewed_summary"]["status_label"] = "Outside evaluated calibration and required evidence missing"
    ComparisonResult.model_validate_json(json.dumps(data))


def test_claim_audit_out_of_domain_with_missing_evidence_preserves_both() -> None:
    # F-02 regression: claim audit with out_of_domain and missing evidence reasons
    data = load("sample_claim_audit_out_of_domain.json")
    data["missing_evidence_reasons"] = ["Required spatial boundary evidence missing."]
    data["sensitivity_status"] = "unavailable"
    data["practical_change"] = {"category": "unavailable"}
    data["conclusion_eligible"] = False

    # Hiding out_of_domain under generic "not_enough_usable_evidence" is rejected
    data["reviewed_summary"]["output_category"] = "not_enough_usable_evidence"
    data["reviewed_summary"]["status_label"] = "Not enough usable evidence"
    fails(ClaimAuditRecord, data)

    # Hiding missing evidence under "outside_evaluated_calibration" is rejected
    data["reviewed_summary"]["output_category"] = "outside_evaluated_calibration"
    data["reviewed_summary"]["status_label"] = "Outside evaluated calibration"
    fails(ClaimAuditRecord, data)

    # Preserving both facts in compound category passes
    data["reviewed_summary"]["output_category"] = "outside_evaluated_calibration_and_missing_evidence"
    data["reviewed_summary"]["status_label"] = "Outside evaluated calibration and required evidence missing"
    ClaimAuditRecord.model_validate_json(json.dumps(data))


def test_mixed_failed_and_out_of_domain_checks_strictly_rejected() -> None:
    # F-03 regression: cannot mix failed and out_of_domain checks
    comp = load("sample_comparison_out_of_domain.json")
    comp["applicability_checks"].append({"check_id": "late_period", "status": "failed", "detail": "Late period failed"})
    fails(ComparisonResult, comp)

    audit = load("sample_claim_audit_out_of_domain.json")
    audit["applicability_checks"].append({"check_id": "late_period", "status": "failed", "detail": "Late period failed"})
    fails(ClaimAuditRecord, audit)

    comp2 = load("sample_comparison_stable_failed_applicability.json")
    comp2["applicability_checks"].append({"check_id": "domain", "status": "out_of_domain", "detail": "Domain boundary exceeded"})
    fails(ComparisonResult, comp2)

    audit2 = load("sample_claim_audit_stable_failed_applicability.json")
    audit2["applicability_checks"].append({"check_id": "domain", "status": "out_of_domain", "detail": "Domain boundary exceeded"})
    fails(ClaimAuditRecord, audit2)


def test_missing_support_status_cannot_mask_failed_or_out_of_domain_check() -> None:
    # F-05 regression: missing_required_support status cannot mask failed or out_of_domain check
    comp_fail = load("sample_comparison_missing_evidence.json")
    comp_fail["applicability_checks"].append({"check_id": "late_period", "status": "failed", "detail": "Late period failed"})
    fails(ComparisonResult, comp_fail)

    audit_fail = load("sample_claim_audit_missing_evidence.json")
    audit_fail["applicability_checks"].append({"check_id": "late_period", "status": "failed", "detail": "Late period failed"})
    fails(ClaimAuditRecord, audit_fail)

    comp_ood = load("sample_comparison_missing_evidence.json")
    comp_ood["applicability_checks"].append({"check_id": "domain", "status": "out_of_domain", "detail": "Domain boundary exceeded"})
    fails(ComparisonResult, comp_ood)

    audit_ood = load("sample_claim_audit_missing_evidence.json")
    audit_ood["applicability_checks"].append({"check_id": "domain", "status": "out_of_domain", "detail": "Domain boundary exceeded"})
    fails(ClaimAuditRecord, audit_ood)






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
    cal = load(CUTOFF)
    rec = cal["monthly_series"][0]["records"][idx]
    assert rec["unavailable_reason"] == reason
    assert rec["detected_fire_cell_days"] is None and rec["usable_land_cell_days"] is None
    assert rec["fire_activity_index"] is None and rec["comparison_eligible"] is False
    # Zero-filling missing data is rejected.
    rec["detected_fire_cell_days"] = 0.0
    rec["usable_land_cell_days"] = 0.0
    fails(CAL_MODEL, cal)


def test_missing_data_cannot_be_labelled_zero_support() -> None:
    cal = load(CUTOFF)
    cal["monthly_series"][0]["records"][3]["unavailable_reason"] = "zero_usable_support"
    fails(CAL_MODEL, cal)


def test_observed_zero_support_cannot_be_labelled_missing_source() -> None:
    cal = load(CUTOFF)
    rec = cal["monthly_series"][0]["records"][2]
    assert rec["unavailable_reason"] == "zero_usable_support"
    rec["unavailable_reason"] = "source_not_available"
    fails(CAL_MODEL, cal)


def test_unavailable_requires_reason_and_weekly_missing_is_null() -> None:
    cal = load(CUTOFF)
    wk = cal["weekly_series"][0]["records"][3]
    assert wk["unavailable_reason"] == "qa_unusable" and wk["usable_land_cell_days"] is None
    wk["unavailable_reason"] = None
    fails(CAL_MODEL, cal)


def test_available_requires_real_values_and_unavailable_not_eligible() -> None:
    cal = load(CUTOFF)
    cal["monthly_series"][0]["records"][0]["usable_land_cell_days"] = None
    fails(CAL_MODEL, cal)
    cal = load(CUTOFF)
    cal["monthly_series"][0]["records"][3]["comparison_eligible"] = True
    fails(CAL_MODEL, cal)


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

# ---- Round 4 (P1 review): S-NPP cutoff enforced by period boundaries ------------------

CAL = CUTOFF  # behavioural calendar tests run on the test-only cutoff artifact
NOV = 5  # index of the partial November 2026 month in the fixture
PARTIAL_WEEK = 4  # index of the 2026-11-02..2026-11-08 S-NPP week 45 in the fixture


def nov_month(cal: dict) -> dict:
    rec = cal["monthly_series"][0]["records"][NOV]
    assert (rec["year"], rec["month"]) == (2026, 11)
    return rec


def partial_week(cal: dict) -> dict:
    rec = cal["weekly_series"][0]["records"][PARTIAL_WEEK]
    assert rec["start_date"] == "2026-11-02" and rec["end_date"] == "2026-11-08"
    assert (rec["year"], rec["week_number"]) == (2026, 45)
    return rec


def test_partial_november_fixture_has_no_baseline_or_label() -> None:
    rec = nov_month(load(CAL))
    assert rec["unusual_status"] is None
    assert rec["baseline_median"] is None and rec["baseline_p90"] is None
    assert rec["is_partial_period"] and not rec["comparison_eligible"]


@pytest.mark.parametrize("label", ["unusual", "not_unusual", "insufficient_baseline"])
def test_partial_month_rejects_every_normal_or_unusual_label(label: str) -> None:
    cal = load(CAL)
    rec = nov_month(cal)
    rec["unusual_status"] = label
    if label != "insufficient_baseline":
        rec["baseline_median"], rec["baseline_p90"] = 1.0, 4.0
    fails(CAL_MODEL, cal)


@pytest.mark.parametrize("field", ["baseline_median", "baseline_p90"])
def test_partial_month_rejects_baseline_thresholds(field: str) -> None:
    cal = load(CAL)
    nov_month(cal)[field] = 1.0
    fails(CAL_MODEL, cal)


def test_partial_month_cannot_be_comparison_eligible_or_unflagged() -> None:
    for field, value in (("comparison_eligible", True), ("is_partial_period", False)):
        cal = load(CAL)
        nov_month(cal)[field] = value
        fails(CAL_MODEL, cal)


def test_complete_snpp_month_before_cutoff_still_labelled_normally() -> None:
    cal = load(CAL)
    oct_rec = cal["monthly_series"][0]["records"][4]
    assert (oct_rec["year"], oct_rec["month"]) == (2023, 10)
    cal["monthly_series"][0]["records"][4] = {
        **oct_rec, "year": 2026, "month": 10, "detected_fire_cell_days": 5.0,
        "usable_land_cell_days": 100.0, "fire_activity_index": 50.0, "availability": "available",
        "unavailable_reason": None, "comparison_eligible": True,
        "baseline_median": 1.0, "baseline_p90": 4.0, "unusual_status": "unusual",
    }
    CAL_MODEL.model_validate_json(json.dumps(cal))


def test_partial_week_fixture_is_ineligible_and_unlabelled() -> None:
    wk = partial_week(load(CAL))
    assert wk["is_partial_period"] and not wk["comparison_eligible"]
    assert wk["critical_status"] is None and wk["unusual_status"] is None


def test_snpp_week_straddling_cutoff_cannot_be_eligible_with_available_rate() -> None:
    cal = load(CAL)
    wk = partial_week(cal)
    # Available rate + comparison_eligible=True must be rejected for partial week.
    wk["availability"], wk["comparison_eligible"] = "available", True
    fails(CAL_MODEL, cal)


def test_snpp_week_straddling_cutoff_rejects_unflagged_or_unreasoned() -> None:
    for field, value in (("is_partial_period", False), ("partial_period_reason", None)):
        cal = load(CAL)
        partial_week(cal)[field] = value
        fails(CAL_MODEL, cal)


@pytest.mark.parametrize(
    "field,label",
    [
        ("critical_status", "critical"),
        ("critical_status", "not_critical"),
        ("critical_status", "insufficient_baseline"),
        ("unusual_status", "unusual"),
        ("unusual_status", "not_unusual"),
        ("unusual_status", "insufficient_baseline"),
    ],
)
def test_snpp_week_straddling_cutoff_rejects_labels(field: str, label: str) -> None:
    cal = load(CAL)
    partial_week(cal)[field] = label
    fails(CAL_MODEL, cal)


def test_snpp_week_ending_day_before_cutoff_is_complete_and_eligible() -> None:
    cal = load(CAL)
    wk = partial_week(cal)
    wk.update(
        year=2026, week_number=44,
        start_date="2026-10-26", end_date="2026-11-01", is_partial_period=False,
        partial_period_reason=None, comparison_eligible=True, days_with_file=7,
        critical_status="not_critical", unusual_status="not_unusual",
    )
    CAL_MODEL.model_validate_json(json.dumps(cal))


def test_snpp_week_past_cutoff_still_rejected() -> None:
    cal = load(CAL)
    wk = partial_week(cal)
    # Week starting after cessation (Nov 9..15) is after_record
    wk.update(year=2026, week_number=46, start_date="2026-11-09", end_date="2026-11-15")
    fails(CAL_MODEL, cal)


def test_weekly_series_rejects_non_monday_start_for_iso_week() -> None:
    cal = load(CAL)
    # Tuesday to Monday period cannot be accepted as utc_iso_week
    cal["weekly_series"][0]["records"][0].update(
        start_date="2023-07-04", end_date="2023-07-10"
    )
    fails(CAL_MODEL, cal)


def test_weekly_series_rejects_mismatched_iso_week_number() -> None:
    cal = load(CAL)
    # 2023-07-03 is ISO week 27, cannot claim week 28
    cal["weekly_series"][0]["records"][0]["week_number"] = 28
    fails(CAL_MODEL, cal)


def test_weekly_series_fixed_7_day_bins_validation() -> None:
    cal = load(CAL)
    cal["weekly_series"][0]["week_definition"] = "fixed_7_day_bins"
    # Bin 1 for 2023 starts 2023-01-01
    cal["weekly_series"][0]["records"] = [
        {
            **cal["weekly_series"][0]["records"][0],
            "year": 2023,
            "week_number": 1,
            "start_date": "2023-01-01",
            "end_date": "2023-01-07",
            "paired_comparison_eligible": False,  # no fixed-bin Aqua twin in this artifact
        }
    ]
    for r in cal["weekly_series"][1]["records"]:  # their ISO-week VIIRS twins were replaced
        r["paired_comparison_eligible"] = False
    CAL_MODEL.model_validate_json(json.dumps(cal))
    # Bin 1 with wrong start date fails
    cal["weekly_series"][0]["records"][0]["start_date"] = "2023-01-02"
    fails(CAL_MODEL, cal)


def test_partial_period_fixtures_carry_explicit_json_nulls() -> None:
    cal = load(CAL)
    month = nov_month(cal)
    week = partial_week(cal)
    for rec, keys in ((month, ["unusual_status"]), (week, ["critical_status", "unusual_status"])):
        for key in keys:
            assert key in rec and rec[key] is None, key
        assert rec["is_partial_period"] is True and rec["comparison_eligible"] is False
    assert month["baseline_median"] is None and month["baseline_p90"] is None


@pytest.mark.parametrize(
    "label",
    ["unusual", "not_unusual", "insufficient_baseline", "not_applicable"],
)
def test_partial_month_requires_null_not_any_label_or_sentinel(label: str) -> None:
    cal = load(CAL)
    nov_month(cal)["unusual_status"] = label
    fails(CAL_MODEL, cal)


@pytest.mark.parametrize(
    "field,label",
    [
        ("critical_status", "critical"),
        ("critical_status", "not_critical"),
        ("critical_status", "insufficient_baseline"),
        ("critical_status", "not_applicable"),
        ("unusual_status", "unusual"),
        ("unusual_status", "not_unusual"),
        ("unusual_status", "insufficient_baseline"),
        ("unusual_status", "not_applicable"),
    ],
)
def test_partial_week_requires_null_not_any_label_or_sentinel(field: str, label: str) -> None:
    cal = load(CAL)
    partial_week(cal)[field] = label
    fails(CAL_MODEL, cal)


def test_partial_month_requires_label_key_to_be_present() -> None:
    cal = load(CAL)
    del nov_month(cal)["unusual_status"]  # omitted is not the same as an explicit null
    fails(CAL_MODEL, cal)


@pytest.mark.parametrize("key", ["critical_status", "unusual_status"])
def test_partial_week_requires_label_keys_to_be_present(key: str) -> None:
    cal = load(CAL)
    del partial_week(cal)[key]
    fails(CAL_MODEL, cal)


def test_label_keys_are_required_on_complete_periods_too() -> None:
    cal = load(CAL)
    del cal["monthly_series"][0]["records"][0]["unusual_status"]
    fails(CAL_MODEL, cal)
    cal = load(CAL)
    del cal["weekly_series"][0]["records"][0]["critical_status"]
    fails(CAL_MODEL, cal)


def test_partial_periods_with_explicit_null_labels_stay_comparison_ineligible() -> None:
    for locate, rec_name in ((nov_month, "month"), (partial_week, "week")):
        cal = load(CAL)
        locate(cal)["comparison_eligible"] = True  # labels are valid nulls; eligibility must still fail
        fails(CAL_MODEL, cal)
        cal = load(CAL)
        locate(cal)["is_partial_period"] = False
        fails(CAL_MODEL, cal)


def test_partial_period_with_null_labels_validates() -> None:
    CAL_MODEL.model_validate_json(json.dumps(load(CAL)))


def test_partial_month_rejects_baseline_thresholds_even_with_null_label() -> None:
    for field in ("baseline_median", "baseline_p90"):
        cal = load(CAL)
        nov_month(cal)[field] = 1.0
        fails(CAL_MODEL, cal)


def test_available_aggregate_never_implies_whole_footprint_completeness() -> None:
    """Whole-footprint completeness is conditional on P2's documented certification.

    The contract must not derive it from `availability == "available"`: no calendar
    field claims completeness, and an incomplete footprint can only be carried as an
    unavailable record with null D/O. A completeness/certification field needs a
    separate, P2-approved contract revision.
    """
    from contracts.schemas.calendar import CalendarArtifact, MonthRecord, ObservationRecord, WeekRecord

    from contracts.schemas.calendar import FootprintCertification

    # No record-level field may claim completeness; the only carrier is the explicit,
    # documented FootprintCertification object on the artifact (P2 certification).
    for model in (ObservationRecord, MonthRecord, WeekRecord):
        for name in model.model_fields:
            assert not any(word in name for word in ("complete", "certif", "whole_footprint")), (model, name)
    artifact_hits = [n for n in CalendarArtifact.model_fields if any(w in n for w in ("complete", "certif", "footprint"))]
    assert artifact_hits == ["footprint_certification"]
    assert CalendarArtifact.model_fields["footprint_certification"].is_required()
    assert FootprintCertification.model_fields["status"].is_required()
    cal = load(CAL)
    rec = cal["monthly_series"][0]["records"][0]
    rec["unavailable_reason"] = "incomplete_footprint"  # available + incomplete footprint
    fails(CAL_MODEL, cal)
    rec.update(availability="unavailable", comparison_eligible=False, unusual_status=None,
               detected_fire_cell_days=None, usable_land_cell_days=None, fire_activity_index=None,
               baseline_median=None, baseline_p90=None, paired_comparison_eligible=False)
    fails(CAL_MODEL, cal)  # the Aqua twin still claims a pair that no longer exists
    cal["monthly_series"][1]["records"][0]["paired_comparison_eligible"] = False
    CAL_MODEL.model_validate_json(json.dumps(cal))


def test_complete_period_rejects_null_or_not_applicable() -> None:
    cal = load(CAL)
    rec = cal["monthly_series"][0]["records"][0]
    rec["unusual_status"] = None
    fails(CAL_MODEL, cal)
    rec["unusual_status"] = "not_applicable"
    fails(CAL_MODEL, cal)

    wk = cal["weekly_series"][0]["records"][0]
    wk["critical_status"] = None
    fails(CAL_MODEL, cal)
    wk["critical_status"] = "not_applicable"
    fails(CAL_MODEL, cal)


def test_unavailable_week_rejects_unusual_or_critical_decisions() -> None:
    from contracts.schemas.calendar import WeekRecord
    from datetime import date
    base = dict(
        sensor="MODIS_Aqua", availability="unavailable",
        unavailable_reason="source_not_available", comparison_eligible=False,
        year=2023, week_number=1, start_date=date(2023, 1, 2), end_date=date(2023, 1, 8),
        days_in_period=7, days_with_file=0, paired_comparison_eligible=False,
        coverage_state="unavailable", coverage_reasons=["no_file"],
    )
    # Decisions and partial-sentinel are strictly forbidden when observation is unavailable
    for status_field, decision in [
        ("unusual_status", "unusual"),
        ("unusual_status", "not_unusual"),
        ("critical_status", "critical"),
        ("critical_status", "not_critical"),
        ("unusual_status", "not_applicable"),
        ("critical_status", "not_applicable"),
    ]:
        with pytest.raises(ValueError):
            WeekRecord(**{**base, status_field: decision})
    # Both not_applicable on unavailable complete week rejected
    with pytest.raises(ValueError, match="not_applicable"):
        WeekRecord(**{**base, "unusual_status": "not_applicable", "critical_status": "not_applicable"})
    # Non-decisions ("insufficient_baseline" or None) are accepted
    WeekRecord(**{**base, "unusual_status": "insufficient_baseline", "critical_status": "insufficient_baseline"})
    WeekRecord(**{**base, "unusual_status": None, "critical_status": None})
    WeekRecord(**{**base, "unusual_status": "insufficient_baseline", "critical_status": None})


def test_weekly_series_rejects_overlapping_dates_and_cross_year_bins() -> None:
    from contracts.schemas.calendar import WeekRecord, WeeklyCalendarSeries
    from datetime import date
    common = dict(
        sensor="MODIS_Aqua", availability="unavailable", unavailable_reason="source_not_available",
        comparison_eligible=False, critical_status="insufficient_baseline", unusual_status="insufficient_baseline",
        days_in_period=7, days_with_file=0, paired_comparison_eligible=False,
        coverage_state="unavailable", coverage_reasons=["no_file"],
    )
    # Overlapping dates in same series rejected
    a = WeekRecord(year=2023, week_number=1, start_date=date(2023, 1, 2), end_date=date(2023, 1, 8), **common)
    b = WeekRecord(year=2023, week_number=2, start_date=date(2023, 1, 6), end_date=date(2023, 1, 12), **common)
    with pytest.raises(ValueError, match="overlap"):
        WeeklyCalendarSeries(sensor="MODIS_Aqua", policy_id="p", week_definition="utc_iso_week", week_53_baselines=[], records=[a, b])

    # Fixed 7-day bin crossing year boundary rejected
    c = WeekRecord(year=2023, week_number=53, start_date=date(2023, 12, 31), end_date=date(2024, 1, 6), **common)
    with pytest.raises(ValueError, match="week_number cannot exceed 52"):
        WeeklyCalendarSeries(sensor="MODIS_Aqua", policy_id="p", week_definition="fixed_7_day_bins", week_53_baselines=[], records=[c])


def test_non_snpp_sensor_week_on_same_dates_is_not_partial() -> None:
    from contracts.schemas.calendar import WeeklyCalendarSeries

    wk = {**partial_week(load(CAL)), "sensor": "MODIS_Aqua"}
    series = {"sensor": "MODIS_Aqua", "policy_id": "p", "week_definition": "utc_iso_week",
              "week_53_baselines": [], "records": [wk]}
    with pytest.raises(ValidationError):  # partial flags are invalid without the S-NPP cutoff
        WeeklyCalendarSeries.model_validate_json(json.dumps(series))
    wk.update(is_partial_period=False, partial_period_reason=None, comparison_eligible=True,
              days_with_file=7, critical_status="not_critical", unusual_status="not_unusual",
              coverage_state="complete", coverage_reasons=[])
    WeeklyCalendarSeries.model_validate_json(json.dumps(series))
    # In an artifact, an Aqua week in 2026 lies outside the declared current-phase Aqua record.
    cal = load(CAL)
    cal["weekly_series"][1]["records"].append(wk)
    fails(CAL_MODEL, cal)


def test_cutoff_boundary_helper_uses_period_boundaries() -> None:
    from datetime import date

    from contracts.schemas.calendar import snpp_period_status

    assert snpp_period_status(date(2026, 10, 26), date(2026, 11, 1)) == "complete"
    assert snpp_period_status(date(2026, 10, 27), date(2026, 11, 2)) == "partial"
    assert snpp_period_status(date(2026, 11, 2), date(2026, 11, 2)) == "partial"
    assert snpp_period_status(date(2026, 11, 3), date(2026, 11, 9)) == "after_record"
    assert snpp_period_status(date(2026, 11, 1), date(2026, 11, 30)) == "partial"
    assert snpp_period_status(date(2026, 12, 1), date(2026, 12, 31)) == "after_record"


# ---- Round 3 rule preserved: adverse applicability + missing evidence stay visible ----


def test_round3_failed_and_out_of_domain_remain_ineligible_with_missing_evidence_visible() -> None:
    for name in (
        "sample_comparison_stable_failed_applicability.json",
        "sample_comparison_out_of_domain.json",
        "sample_comparison_missing_evidence.json",
        "sample_claim_audit_stable_failed_applicability.json",
        "sample_claim_audit_out_of_domain.json",
        "sample_claim_audit_missing_evidence.json",
    ):
        data = load(name)
        assert data["conclusion_eligible"] is False, name
        model = ComparisonResult if "comparison" in name else ClaimAuditRecord
        data["conclusion_eligible"] = True
        fails(model, data)
