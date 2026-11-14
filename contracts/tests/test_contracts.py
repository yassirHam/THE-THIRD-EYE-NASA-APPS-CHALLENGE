"""Contract tests: fixtures validate and forbidden states are rejected."""

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from contracts import build_fixtures as bf
from contracts import generate_ts
from contracts.schemas import ComparisonResult

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
    nov = cal["monthly_series"][0]["records"][3]
    assert nov["is_partial_period"] and not nov["comparison_eligible"]
    nov["comparison_eligible"] = True
    fails(MODELS["sample_calendar.json"], cal)
    cal = load("sample_calendar.json")
    cal["monthly_series"][0]["records"][3]["month"] = 12
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
