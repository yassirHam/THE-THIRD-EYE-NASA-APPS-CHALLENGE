"""Deterministically build labelled synthetic contract fixtures.

Run: python -m contracts.build_fixtures
All values are invented test data and carry [SYNTHETIC DEV FIXTURE].
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from .schemas.common import CONTRACT_VERSION, CacheKey
from .schemas import (
    CalendarArtifact,
    ClaimAuditRecord,
    ComparisonResult,
    EvaluationSummary,
    FirmsHotspotArtifact,
    ProvenanceManifest,
    RegionSelectorArtifact,
)

FIXTURE_DIR = Path(__file__).parent / "fixtures"
LABEL = "[SYNTHETIC DEV FIXTURE]"
GEO = "geo-synthetic-primary"
PERIOD = "synthetic-2020-2021"
POLICY = "own_support_eligible"


def identity(method: str = "stage_a_finite_factors", geometry: str = GEO) -> dict:
    return {
        "contract_version": CONTRACT_VERSION,
        "artifact_version": "synthetic-v1",
        "geometry_id": geometry,
        "period_spec": PERIOD,
        "method_id": method,
        "policy_id": POLICY,
        "data_classification": "synthetic_dev_fixture",
        "fixture_label": LABEL,
    }


def obs(d: float, o: float) -> dict:
    if o == 0:
        return {
            "detected_fire_cell_days": 0.0,
            "usable_land_cell_days": 0.0,
            "fire_activity_index": None,
            "availability": "unavailable",
            "unavailable_reason": "zero_usable_support",
        }
    return {
        "detected_fire_cell_days": d,
        "usable_land_cell_days": o,
        "fire_activity_index": 1000.0 * d / o,
        "availability": "available",
        "unavailable_reason": None,
    }


def missing(reason: str) -> dict:
    """Genuinely missing data: D, O and R stay null; never zero."""
    return {
        "detected_fire_cell_days": None,
        "usable_land_cell_days": None,
        "fire_activity_index": None,
        "availability": "unavailable",
        "unavailable_reason": reason,
    }


def month(sensor: str, year: int, m: int, d: float, o: float, **kw) -> dict:
    base = {
        **obs(d, o),
        "sensor": sensor,
        "year": year,
        "month": m,
        "baseline_median": None,
        "baseline_p90": None,
        "unusual_status": "insufficient_baseline",
        "is_partial_period": False,
        "comparison_eligible": o > 0,
        "partial_period_reason": None,
    }
    base.update(kw)
    return base


def week(sensor: str, year: int, n: int, start: str, end: str, d: float, o: float, **kw) -> dict:
    base = {
        **obs(d, o),
        "sensor": sensor,
        "year": year,
        "week_number": n,
        "start_date": start,
        "end_date": end,
        "critical_status": "insufficient_baseline",
        "unusual_status": "insufficient_baseline",
        "is_partial_period": False,
        "partial_period_reason": None,
        "comparison_eligible": o > 0,
    }
    base.update(kw)
    return base


def calendar() -> dict:
    snpp = [
        month("VIIRS_SNPP", 2020, 6, 0, 200, baseline_median=1.0, baseline_p90=4.0, unusual_status="not_unusual"),
        month("VIIRS_SNPP", 2020, 7, 30, 200, baseline_median=1.0, baseline_p90=4.0, unusual_status="unusual"),
        month("VIIRS_SNPP", 2020, 8, 0, 0),
        month("VIIRS_SNPP", 2020, 9, 0, 0, **missing("source_not_available")),
        month("VIIRS_SNPP", 2020, 10, 0, 0, **missing("incomplete_footprint")),
        month(
            "VIIRS_SNPP", 2026, 11, 2, 100,
            is_partial_period=True, comparison_eligible=False,
            partial_period_reason="snpp_record_ended_2026_11_02",
            unusual_status="not_applicable",
        ),
    ]
    aqua = [month("MODIS_Aqua", 2020, 6, 5, 250), month("MODIS_Aqua", 2020, 7, 0, 250)]
    return {
        **identity("same_sensor_calendar"),
        "region_name": "Synthetic Test Region",
        "measurement_name": "fire_activity_index",
        "measurement_unit": "detected_fire_cell_days_per_1000_usable_land_cell_days",
        "snpp_delivery_end_at": "2026-11-02T15:40:00Z",
        "monthly_series": [
            {"sensor": "VIIRS_SNPP", "policy_id": POLICY, "records": snpp},
            {"sensor": "MODIS_Aqua", "policy_id": POLICY, "records": aqua},
        ],
        "weekly_series": [
            {
                "sensor": "VIIRS_SNPP",
                "policy_id": POLICY,
                "week_definition": "utc_iso_week",
                "records": [
                    week("VIIRS_SNPP", 2020, 27, "2020-06-29", "2020-07-05", 10, 100,
                         critical_status="critical", unusual_status="unusual"),
                    week("VIIRS_SNPP", 2020, 28, "2020-07-06", "2020-07-12", 0, 100,
                         critical_status="not_critical", unusual_status="not_unusual"),
                    week("VIIRS_SNPP", 2020, 29, "2020-07-13", "2020-07-19", 0, 0),
                    week("VIIRS_SNPP", 2020, 30, "2020-07-20", "2020-07-26", 0, 0,
                         **missing("qa_unusable")),
                    week("VIIRS_SNPP", 2026, 44, "2026-10-27", "2026-11-02", 3, 100,
                         critical_status="not_applicable", unusual_status="not_applicable",
                         is_partial_period=True, comparison_eligible=False,
                         partial_period_reason="snpp_record_ended_2026_11_02"),
                ],
            }
        ],
        "seasonal_baselines": [
            {
                "sensor": "VIIRS_SNPP", "policy_id": POLICY, "status": "available",
                "reference_start_year": 2016, "reference_end_year": 2019,
                "eligible_prior_years": [2016, 2017, 2018, 2019], "minimum_year_count": 3,
                "normal_season_start_month": 6, "normal_season_end_month": 9, "peak_median_month": 7,
            },
            {
                "sensor": "MODIS_Aqua", "policy_id": POLICY, "status": "insufficient_baseline",
                "reference_start_year": 2016, "reference_end_year": 2016,
                "eligible_prior_years": [2016], "minimum_year_count": 3,
                "normal_season_start_month": None, "normal_season_end_month": None,
                "peak_median_month": None,
            },
        ],
    }


def variant(vid: str, factor: float, delta: float, years: list[int]) -> dict:
    return {
        "variant_id": vid, "factor_value": factor, "factor_type": "own_support_a_H",
        "training_years": years, "effect_delta": delta,
        "direction": "increase" if delta > 0 else "decrease" if delta < 0 else "no_change",
    }


REQUIRED = ["full_training", "ex_2016", "ex_2017"]
ALL_VARIANTS = [
    ("full_training", 1.4, [2016, 2017, 2018]),
    ("ex_2016", 1.5, [2017, 2018]),
    ("ex_2017", 1.3, [2016, 2018]),
]


def summary(category: str, label: str, finding: str, limit: str) -> dict:
    return {
        "template_id": "stage_a_default", "template_version": "1",
        "generated_by": "reviewed_deterministic_template",
        "output_category": category, "status_label": label,
        "finding_sentence": f"{LABEL} {finding}", "limit_sentence": limit,
    }


def comparison(**over) -> dict:
    deltas = [2.0, 2.4, 1.8]
    base = {
        **identity(),
        "sensitivity_status": "stable_across_displayed_settings",
        "applicability_status": "applicable",
        "inference_status": "not_established",
        "practical_change": {
            "category": "meaningful_increase", "magnitude": 2.4, "effect_units": "R points",
            "practical_margin_tau": 0.5, "observed_signs": ["increase"],
        },
        "headline_direction": "increase",
        "required_variant_ids": REQUIRED,
        "registered_variants": [variant(v, f, d, y) for (v, f, y), d in zip(ALL_VARIANTS, deltas)],
        "applicability_checks": [
            {"check_id": "support", "status": "passed", "detail": "Support minimum met."},
            {"check_id": "late_period", "status": "passed", "detail": "Late-period check passed."},
        ],
        "missing_evidence_reasons": [],
        "conclusion_eligible": True,
        "reviewed_summary": summary(
            "consistent_across_tested_corrections", "Consistent across tested corrections",
            "The tested corrections agree.", "Counts 1 km cells with detection, not fires.",
        ),
    }
    base.update(over)
    return base


def comparisons() -> dict[str, dict]:
    out = {"sample_comparison_normal.json": comparison()}
    out["sample_comparison_missing_evidence.json"] = comparison(
        sensitivity_status="unavailable",
        applicability_status="missing_required_support",
        practical_change={"category": "unavailable"},
        headline_direction="unavailable",
        registered_variants=[variant("full_training", 1.4, 2.0, [2016, 2017, 2018])],
        applicability_checks=[{"check_id": "support", "status": "missing", "detail": "Support not extracted."}],
        missing_evidence_reasons=["Required leave-one-year-out variants ex_2016 and ex_2017 are missing."],
        conclusion_eligible=False,
        reviewed_summary=summary(
            "not_enough_usable_evidence", "Not enough usable evidence",
            "No eligible conclusion.", "Required evidence is missing.",
        ),
    )
    out["sample_comparison_stable_failed_applicability.json"] = comparison(
        applicability_status="failed_applicability",
        applicability_checks=[
            {"check_id": "support", "status": "passed", "detail": "Support minimum met."},
            {"check_id": "late_period", "status": "failed", "detail": "Late-period check failed."},
        ],
        headline_direction="unavailable",
        conclusion_eligible=False,
        reviewed_summary=summary(
            "calibration_check_failed", "Calibration check failed",
            "Corrections agree but the applicability check failed.", "No directional conclusion is shown.",
        ),
    )
    out["sample_comparison_out_of_domain.json"] = comparison(
        applicability_status="out_of_domain",
        applicability_checks=[{"check_id": "domain", "status": "out_of_domain", "detail": "Outside evaluated domain."}],
        headline_direction="unavailable",
        conclusion_eligible=False,
        reviewed_summary=summary(
            "outside_evaluated_calibration", "Outside evaluated calibration",
            "This area/period was not evaluated.", "Raw observations may still be shown.",
        ),
    )
    out["sample_comparison_sensitive.json"] = comparison(
        sensitivity_status="sensitive_to_assumptions",
        headline_direction="ambiguous",
        practical_change={
            "category": "unspecified", "magnitude": 2.0, "effect_units": "R points",
            "observed_signs": ["increase", "decrease"],
        },
        registered_variants=[variant(v, f, d, y) for (v, f, y), d in zip(ALL_VARIANTS, [2.0, -1.0, 0.5])],
        reviewed_summary=summary(
            "depends_on_the_correction", "Depends on the correction",
            "Registered corrections disagree.", "Both interpretations are shown.",
        ),
    )
    out["sample_comparison_within_margin_opposite_sign.json"] = comparison(
        headline_direction="within_practical_margin",
        practical_change={
            "category": "within_practical_margin", "magnitude": 0.3, "effect_units": "R points",
            "practical_margin_tau": 0.5, "observed_signs": ["increase", "decrease"],
        },
        registered_variants=[variant(v, f, d, y) for (v, f, y), d in zip(ALL_VARIANTS, [0.3, -0.2, 0.1])],
        reviewed_summary=summary(
            "consistent_across_tested_corrections", "Consistent across tested corrections",
            "All tested effects fall within the practical margin.", "Within margin is not equivalence.",
        ),
    )
    return out


def selector() -> dict:
    def opt(gid, name, role, raw, access, reason=None, evaluated=False):
        return {
            "geometry_id": gid, "display_name": name, "geometry_role": role,
            "boundary_source": "synthetic", "boundary_version": "1", "crs": "EPSG:4326",
            "grid_inclusion_rule": "cell centroid inside boundary",
            "raw_data_status": raw, "comparison_access_status": access,
            "unavailable_reason": reason,
            "evaluated_method_id": "stage_a_finite_factors" if evaluated else None,
            "evaluated_policy_id": POLICY if evaluated else None,
            "evaluated_period_spec": PERIOD if evaluated else None,
        }
    return {
        **identity("region_selector"),
        "options": [
            opt(GEO, "Synthetic Primary", "primary_region", "available", "evaluated_comparison", evaluated=True),
            opt("geo-synthetic-sub-a", "Synthetic Sub-area A", "predeclared_sub_area", "available", "raw_only"),
            opt("geo-synthetic-sub-b", "Synthetic Sub-area B", "predeclared_sub_area",
                "unavailable", "unavailable", "incomplete_footprint"),
        ],
    }


def metrics(n=20, answered=17, errors=2, err=0.1):
    return {
        "status": "available", "evaluated_case_count": n, "answered_case_count": answered,
        "abstention_count": n - answered, "mean_reference_relative_error": err,
        "directional_error_count": errors, "decision_coverage_percent": 100.0 * answered / n,
        "unavailable_reason": None,
    }


def evaluation(available: bool = True) -> dict:
    units = {"blocks": 5, "regions": 1, "test_years": 2,
             "dependence_note": "Blocks within one region are dependent."}
    if available:
        head = {
            "status": "available", "description": "Synthetic sensor-switch headline",
            "registered_case_count": 20, "raw_wrong_way_count": 8, "corrected_wrong_way_count": 3,
            "flagged_remaining_error_count": 2, "abstained_count": 3,
            "denominator_statement": "20 registered cases; not independent tests.",
            "independent_units": units, "unavailable_reason": None,
        }
        b = {k: metrics() for k in ("a", "b", "c", "d")}
    else:
        head = {
            "status": "unavailable", "description": "Synthetic sensor-switch headline",
            "registered_case_count": None, "raw_wrong_way_count": None,
            "corrected_wrong_way_count": None, "flagged_remaining_error_count": None,
            "abstained_count": None, "denominator_statement": "No evaluable cases.",
            "independent_units": units, "unavailable_reason": "Evaluation infeasible.",
        }
        un = {
            "status": "unavailable", "evaluated_case_count": 0, "answered_case_count": 0,
            "abstention_count": 0, "mean_reference_relative_error": None,
            "directional_error_count": None, "decision_coverage_percent": None,
            "unavailable_reason": "No evaluable cases.",
        }
        b = {k: un for k in ("a", "b", "c", "d")}
    return {
        **identity("held_out_sensor_switch"),
        "eval_protocol_version": "P0-held-out-sensor-switch-v1",
        "baseline_a_raw_handover": b["a"], "baseline_b_point_a_h": b["b"],
        "baseline_c_uncertainty_aware": b["c"], "baseline_d_stage_a_finite_audit": b["d"],
        "landing_headline_metric": head,
        "failures_and_limitations": ["Synthetic values only; not a result."],
    }


def manifest() -> dict:
    return {
        **identity("artifact_manifest"),
        "manifest_version": "synthetic-manifest-1",
        "generated_at": "2026-11-14T00:20:00Z",
        "snpp_cessation_date": "2026-11-02",
        "canonical_boundary": {
            "type": "Polygon",
            "coordinates": [[[0.0, 0.0], [1.0, 0.0], [1.0, 1.0], [0.0, 1.0], [0.0, 0.0]]],
        },
        "boundary_source": "synthetic", "boundary_version": "1", "crs": "EPSG:4326",
        "grid_inclusion_rule": "cell centroid inside boundary",
        "source_collections": [
            {"collection_id": "MODIS/061/MYD14A1", "sensor": "MODIS_Aqua",
             "source_version": "061", "record_end_date": None},
            {"collection_id": "NASA/VIIRS/002/VNP14A1", "sensor": "VIIRS_SNPP",
             "source_version": "002", "record_end_date": "2026-11-02"},
        ],
        "total_file_size_bytes": 2000, "compressed_bundle_size_bytes": 800,
        "partitions": [{
            "file_path": "synthetic/calendar.json", "geometry_id": GEO, "period_spec": PERIOD,
            "method_id": "artifact_manifest", "policy_id": POLICY, "sensor": "MODIS_Aqua",
            "cache_key_sha256": CacheKey(
                artifact_version="synthetic-v1", geometry_id=GEO, period_spec=PERIOD,
                method_id="artifact_manifest", policy_id=POLICY,
            ).digest(),
            "row_count": 2, "file_size_bytes": 2000,
            "sha256_checksum": hashlib.sha256(b"synthetic").hexdigest(),
            "coverage_status": "complete",
        }],
    }


def claim_audit(comp: dict | None = None, suffix: str = "") -> dict:
    comp = comp or comparison()
    return {
        **identity("claim_audit"),
        "record_id": f"car-synthetic-1{suffix}",
        "statement": "Synthetic claim: activity rose in the target period.",
        "analyst_entity": None, "target_region": "Synthetic Test Region",
        "date_range_tested": "2020-2021",
        "dataset_versions": ["MODIS/061/MYD14A1", "NASA/VIIRS/002/VNP14A1"],
        "formulas_applied": ["R = 1000 * D / O (sums before division)"],
        "sensitivity_status": comp["sensitivity_status"],
        "applicability_status": comp["applicability_status"],
        "inference_status": "not_established",
        "practical_change": comp["practical_change"],
        "applicability_checks": comp["applicability_checks"],
        "missing_evidence_reasons": comp["missing_evidence_reasons"],
        "conclusion_eligible": comp["conclusion_eligible"],
        "reviewed_summary": comp["reviewed_summary"],
        "counterexample_interpretations": [],
        "reproducibility_sha256": hashlib.sha256(b"synthetic-claim").hexdigest(),
        "verification_steps": ["Check O > 0.", "Check all registered variants."],
        "evidence_artifact_versions": ["synthetic-v1"],
    }


def firms() -> dict:
    return {
        **identity("firms_hotspot_view"),
        "view_name": "Reported hotspots", "measurement_unit": "reported_detection_points",
        "processing_level": "standard_archive", "confidence_filter": "all",
        "firms_link": {
            "url": "https://firms.modaps.eosdis.nasa.gov/map/",
            "selected_area": {"west": 0.0, "south": 0.0, "east": 1.0, "north": 1.0},
            "start_date": "2020-07-01", "end_date": "2020-07-07",
            "manual_selection_required": True,
            "limitation": "Select the area and dates manually in FIRMS.",
        },
        "points": [{
            "point_id": "synthetic-1", "latitude": 0.5, "longitude": 0.5,
            "acquired_at": "2020-07-01T10:30:00Z", "platform": "VIIRS_SNPP",
            "confidence_label": "nominal", "source_product": "synthetic",
        }],
        "feeds_grid_math": False, "inherits_grid_calibration": False,
        "cross_sensor_trend_allowed": False,
        "isolation_notice": "FIRMS points are separate from D, O, baselines, factors, and verdicts.",
    }


def all_fixtures() -> dict[str, tuple[type, dict]]:
    out = {
        "sample_calendar.json": (CalendarArtifact, calendar()),
        "sample_region_selector.json": (RegionSelectorArtifact, selector()),
        "sample_evaluation_summary.json": (EvaluationSummary, evaluation(True)),
        "sample_evaluation_unavailable.json": (EvaluationSummary, evaluation(False)),
        "sample_manifest.json": (ProvenanceManifest, manifest()),
        "sample_claim_audit_record.json": (ClaimAuditRecord, claim_audit()),
        "sample_firms_hotspots.json": (FirmsHotspotArtifact, firms()),
    }
    for name, data in comparisons().items():
        out[name] = (ComparisonResult, data)
        if name != "sample_comparison_normal.json":
            audit_name = name.replace("sample_comparison_", "sample_claim_audit_")
            out[audit_name] = (ClaimAuditRecord, claim_audit(data, "-" + audit_name[:-5]))
    return out


def main() -> None:
    FIXTURE_DIR.mkdir(exist_ok=True)
    for stale in FIXTURE_DIR.glob("*.json"):
        stale.unlink()
    for name, (model, data) in all_fixtures().items():
        text = json.dumps(data, indent=2) + "\n"
        model.model_validate_json(text)  # fail before writing invalid fixtures
        (FIXTURE_DIR / name).write_text(text, encoding="utf-8")
        print("wrote", name)


if __name__ == "__main__":
    main()
