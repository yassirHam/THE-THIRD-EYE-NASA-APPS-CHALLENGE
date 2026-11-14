"""Deterministically build labelled synthetic contract fixtures.

Run: python -m contracts.build_fixtures
All values are invented test data and carry [SYNTHETIC DEV FIXTURE].
"""

from __future__ import annotations

import hashlib
import json
from datetime import date, timedelta
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
CONFIG_PATH = Path(__file__).parent / "config" / "pending_registrations.json"
LABEL = "[SYNTHETIC DEV FIXTURE]"
GEO = "geo-synthetic-primary"
PERIOD = "synthetic-2023"  # P1: fabricated 2020-2021 dates only in boundary tests
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


def _days(start: date, end: date) -> int:
    return (end - start).days + 1


def _month_bounds(year: int, m: int) -> tuple[date, date]:
    nxt = date(year + (m == 12), m % 12 + 1, 1)
    return date(year, m, 1), nxt - timedelta(days=1)


def month(sensor: str, year: int, m: int, d: float, o: float, **kw) -> dict:
    first, last = _month_bounds(year, m)
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
        "included_day_count": None,
        "days_in_period": _days(first, last),
        "days_with_file": _days(first, last),
        "paired_comparison_eligible": False,
        "coverage_state": None,  # filled by fill_coverage from dates, files and record bounds
        "coverage_reasons": [],
    }
    base.update(kw)
    if base["unavailable_reason"] == "source_not_available" and "days_with_file" not in kw:
        base["days_with_file"] = 0
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
        "included_day_count": None,
        "days_in_period": 7,
        "days_with_file": 7,
        "paired_comparison_eligible": False,
        "coverage_state": None,  # filled by fill_coverage from dates, files and record bounds
        "coverage_reasons": [],
    }
    base.update(kw)
    if base["unavailable_reason"] == "source_not_available" and "days_with_file" not in kw:
        base["days_with_file"] = 0
    return base


# P2 r9 reason vocabulary: contract partial reason -> P2 coverage reason.
P2_REASON = {
    "outside_sensor_record": "period_clipped",
    "snpp_record_ended_2026_11_02": "period_clipped",
    "crosses_sealed_evaluation_boundary": "partition_boundary",
    "missing_days_or_tiles": "missing_days_or_tiles",
    "low_processed_coverage": "low_processed_coverage",
}


def _record_bounds(rec: dict) -> tuple[date, date]:
    if "month" in rec:
        return _month_bounds(rec["year"], rec["month"])
    return date.fromisoformat(rec["start_date"]), date.fromisoformat(rec["end_date"])


def fill_record_coverage(rec: dict, inside: int | None = None, permitted: int | None = None,
                         wholly_sealed: bool = False) -> dict:
    """Set coverage_state / coverage_reasons on one record dict (P2 r9 vocabulary).

    inside: days of the period inside the sensor record; permitted: of those, days outside the
    sealed window. Both default to the whole period (no record or window information).
    """
    start, end = _record_bounds(rec)
    total = _days(start, end)
    inside = total if inside is None else inside
    permitted = inside if permitted is None else permitted
    files = rec["days_with_file"]
    reasons: list[str] = []
    if rec.get("partial_period_reason"):
        reasons.append(P2_REASON[rec["partial_period_reason"]])
    if wholly_sealed:
        reasons.append("partition_boundary")
    if inside == 0:
        reasons.append("sensor_not_operating")
    elif files == 0 and permitted > 0:
        reasons.append("no_file")
    elif 0 < files < permitted:
        reasons.append("missing_days_or_tiles")
    pc = rec.get("processed_coverage")
    if pc is not None and pc < 1.0:
        reasons.append("low_processed_coverage")
    rec["coverage_reasons"] = list(dict.fromkeys(reasons))
    rec["coverage_state"] = "unavailable" if files == 0 else "partial" if rec["is_partial_period"] else "complete"
    return rec


def fill_coverage(art: dict) -> dict:
    """Fill coverage fields of every record of a calendar artifact dict from its own data."""
    cov = {c["sensor"]: c for c in art["sensor_coverage"]}
    win = art.get("sealed_window")
    ws = date.fromisoformat(win["start"]) if win else None
    we = date.fromisoformat(win["end"]) if win else None
    for series in [*art["monthly_series"], *art["weekly_series"]]:
        for rec in series["records"]:
            c = cov.get(rec["sensor"])
            if c is None or c["status"] != "active":
                fill_record_coverage(rec)
                continue
            start, end = _record_bounds(rec)
            lo = max(start, date.fromisoformat(c["record_start"]))
            hi = min(end, date.fromisoformat(c["record_end"]))
            days = [lo + timedelta(days=i) for i in range((hi - lo).days + 1)] if lo <= hi else []
            permitted = [d for d in days if not (ws and ws <= d <= we)]
            wholly = bool(ws) and ws <= start and end <= we and bool(days)
            fill_record_coverage(rec, len(days), len(permitted), wholly)
    return art

def _config() -> dict:
    return json.loads(CONFIG_PATH.read_text(encoding="utf-8-sig"))


def phase() -> dict:
    """Current-phase coverage as stated by P2 (r8 review), read from config."""
    return _config()["current_phase_coverage"]


def sensor_coverage(snpp_end: str | None = None, snpp_scope: str | None = None) -> list[dict]:
    ph = phase()
    out = []
    for entry in ph["active"]:
        cov = {**entry, "status": "active", "scope_ref": ph["source_ref"]}
        if entry["sensor"] == "VIIRS_SNPP" and snpp_end is not None:
            cov.update(record_end=snpp_end, scope_ref=snpp_scope)
        out.append(cov)
    for sensor in ph["reserved_inactive"]:
        out.append({"sensor": sensor, "status": "reserved_inactive", "collection_id": None,
                    "record_start": None, "record_end": None, "scope_ref": None})
    return out


def annual(coverage: list[dict], sensor: str, year: int) -> dict:
    cov = next(c for c in coverage if c["sensor"] == sensor)
    rs, re_ = date.fromisoformat(cov["record_start"]), date.fromisoformat(cov["record_end"])
    start, end = date(year, 1, 1), date(year, 12, 31)
    inside = max(0, _days(max(start, rs), min(end, re_))) if max(start, rs) <= min(end, re_) else 0
    total = _days(start, end)
    partial = inside < total
    reason = None
    if partial:
        reason = ("snpp_record_ended_2026_11_02" if sensor == "VIIRS_SNPP" and re_ >= date(2026, 11, 2)
                  and year == 2026 else "outside_sensor_record")
    return {"sensor": sensor, "year": year, "days_in_period": total, "days_with_file": inside,
            "is_partial_period": partial, "partial_period_reason": reason}


EDGE = {"is_partial_period": True, "partial_period_reason": "outside_sensor_record",
        "comparison_eligible": False, "paired_comparison_eligible": False}
EDGE_WEEK = {**EDGE, "critical_status": None, "unusual_status": None}
EDGE_MONTH = {**EDGE, "unusual_status": None}


def _baselines() -> list[dict]:
    return [
        {
            "sensor": "VIIRS_SNPP", "policy_id": POLICY, "status": "available",
            "reference_start_year": 2016, "reference_end_year": 2019,
            "eligible_prior_years": [2016, 2017, 2018, 2019], "excluded_years": [],
            "unavailable_reason": None, "minimum_year_count": 3,
            "normal_season_start_month": 6, "normal_season_end_month": 9, "peak_median_month": 7,
        },
        {
            "sensor": "MODIS_Aqua", "policy_id": POLICY, "status": "insufficient_baseline",
            "reference_start_year": 2016, "reference_end_year": 2016,
            "eligible_prior_years": [2016], "excluded_years": [],
            "unavailable_reason": None, "minimum_year_count": 3,
            "normal_season_start_month": None, "normal_season_end_month": None,
            "peak_median_month": None,
        },
    ]


def _calendar_core(coverage: list[dict], cutoff_status: str) -> dict:
    paired = {"paired_comparison_eligible": True}
    snpp = [
        month("VIIRS_SNPP", 2023, 6, 0, 200, baseline_median=1.0, baseline_p90=4.0,
              unusual_status="not_unusual", **paired),
        month("VIIRS_SNPP", 2023, 7, 30, 200, baseline_median=1.0, baseline_p90=4.0,
              unusual_status="unusual", **paired),
        month("VIIRS_SNPP", 2023, 8, 0, 0),
        month("VIIRS_SNPP", 2023, 9, 0, 0, **missing("source_not_available")),
        month("VIIRS_SNPP", 2023, 10, 0, 0, **missing("incomplete_footprint")),
    ]
    aqua = [month("MODIS_Aqua", 2023, 6, 5, 250, **paired), month("MODIS_Aqua", 2023, 7, 0, 250, **paired)]
    snpp_weeks = [
        week("VIIRS_SNPP", 2023, 27, "2023-07-03", "2023-07-09", 10, 100,
             critical_status="critical", unusual_status="unusual", **paired),
        week("VIIRS_SNPP", 2023, 28, "2023-07-10", "2023-07-16", 0, 100,
             critical_status="not_critical", unusual_status="not_unusual", **paired),
        week("VIIRS_SNPP", 2023, 29, "2023-07-17", "2023-07-23", 0, 0),
        week("VIIRS_SNPP", 2023, 30, "2023-07-24", "2023-07-30", 0, 0, **missing("qa_unusable")),
    ]
    aqua_weeks = [
        week("MODIS_Aqua", 2023, 27, "2023-07-03", "2023-07-09", 4, 120,
             critical_status="not_critical", unusual_status="not_unusual", **paired),
        week("MODIS_Aqua", 2023, 28, "2023-07-10", "2023-07-16", 1, 120,
             critical_status="not_critical", unusual_status="not_unusual", **paired),
    ]
    years = [("VIIRS_SNPP", y) for y in (2016, 2017, 2018, 2019)] + [("MODIS_Aqua", 2016)]
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
            {"sensor": "VIIRS_SNPP", "policy_id": POLICY, "week_definition": "utc_iso_week",
             "week_53_baselines": [], "records": snpp_weeks},
            {"sensor": "MODIS_Aqua", "policy_id": POLICY, "week_definition": "utc_iso_week",
             "week_53_baselines": [], "records": aqua_weeks},
        ],
        "sealed_window": None,
        "week_53_rule": None,
        # Synthetic fixture value: demonstrates the certified path. It is NOT a P2 certification;
        # P2 r9 states no region-period is certified complete today (see the unverified fixture).
        "footprint_certification": {
            "geometry_id": GEO, "status": "complete", "footprint_evidence": "cell_level",
            "certification_ref": "SYNTHETIC-TEST-ONLY: not a P2 certification",
            "certified_at": "2026-11-14T00:00:00Z", "coverage_fraction": None,
        },
        "sensor_coverage": coverage,
        "snpp_cutoff_status": cutoff_status,
        "annual_coverage": [annual(coverage, s, y) for s, y in years],
        "seasonal_baselines": _baselines(),
    }


def calendar() -> dict:
    """Consumer fixture for the current phase (P2 r8 scope): no data after 2025-12-31.

    Includes P2's record-boundary partial periods: Aqua July 2002 and 2002-W27 (record from
    2002-07-04), VIIRS January 2012 and 2012-W03 (record from 2012-01-19), the last ISO week
    2026-W01 (2025-12-29..2025-12-31 only) for both sensors, and partial years 2002 and 2012.
    """
    coverage = sensor_coverage()
    data = _calendar_core(coverage, "reserved_inactive")
    data["monthly_series"][0]["records"].append(
        month("VIIRS_SNPP", 2012, 1, 1, 90, days_with_file=13, **EDGE_MONTH))
    data["monthly_series"][1]["records"].insert(
        0, month("MODIS_Aqua", 2002, 7, 2, 140, days_with_file=28, **EDGE_MONTH))
    data["weekly_series"][0]["records"] += [
        week("VIIRS_SNPP", 2012, 3, "2012-01-16", "2012-01-22", 0, 30, days_with_file=4, **EDGE_WEEK),
        week("VIIRS_SNPP", 2026, 1, "2025-12-29", "2026-01-04", 1, 40, days_with_file=3, **EDGE_WEEK),
    ]
    data["weekly_series"][1]["records"] = (
        [week("MODIS_Aqua", 2002, 27, "2002-07-01", "2002-07-07", 0, 20, days_with_file=4, **EDGE_WEEK)]
        + data["weekly_series"][1]["records"]
        + [week("MODIS_Aqua", 2026, 1, "2025-12-29", "2026-01-04", 0, 35, days_with_file=3, **EDGE_WEEK)]
    )
    data["annual_coverage"] += [annual(coverage, "MODIS_Aqua", 2002), annual(coverage, "VIIRS_SNPP", 2012)]
    # P2 r9 Q3: missing files inside the record -> partial (missing_days_or_tiles), ineligible,
    # null labels and thresholds; D/O cover only the days that have a file.
    data["monthly_series"][0]["records"].append(month(
        "VIIRS_SNPP", 2023, 11, 2, 150, days_with_file=25, is_partial_period=True,
        partial_period_reason="missing_days_or_tiles", unusual_status=None, comparison_eligible=False))
    data["weekly_series"][1]["records"].insert(-1, week(
        "MODIS_Aqua", 2023, 29, "2023-07-17", "2023-07-23", 1, 80, days_with_file=5, is_partial_period=True,
        partial_period_reason="missing_days_or_tiles", critical_status=None, unusual_status=None,
        comparison_eligible=False))
    # P2 r9 Q5: a period wholly before the VIIRS record start is unavailable, not rejected.
    data["monthly_series"][0]["records"].append(month(
        "VIIRS_SNPP", 2011, 12, 0, 0, **missing("sensor_not_operating"), days_with_file=0,
        unusual_status=None, comparison_eligible=False))
    return fill_coverage(data)


def unverified_footprint_calendar() -> dict:
    """Current-phase truth per P2 r9 Q3: footprint UNVERIFIED (day-level evidence only).

    No period is comparison-eligible. The Aqua baseline shows a required year with missing file
    days: the baseline is unavailable (required_year_invalid), never shortened.
    """
    data = calendar()
    data["footprint_certification"] = {
        "geometry_id": GEO, "status": "unverified", "footprint_evidence": "day_level",
        "certification_ref": None, "certified_at": None, "coverage_fraction": None,
    }
    for series in [*data["monthly_series"], *data["weekly_series"]]:
        for rec in series["records"]:
            rec["comparison_eligible"] = False
            rec["paired_comparison_eligible"] = False
    coverage = data["sensor_coverage"]
    gap_year = annual(coverage, "MODIS_Aqua", 2017)
    gap_year["days_with_file"] = gap_year["days_in_period"] - 5  # fabricated: five days without a file
    data["annual_coverage"] += [gap_year] + [annual(coverage, "MODIS_Aqua", y) for y in (2018, 2019)]
    data["seasonal_baselines"][1] = {
        "sensor": "MODIS_Aqua", "policy_id": POLICY, "status": "unavailable",
        "reference_start_year": 2016, "reference_end_year": 2019,
        "eligible_prior_years": [2016, 2018, 2019],
        "excluded_years": [{"year": 2017, "reason": "required_year_invalid",
                            "detail": "Five UTC days without a file; P1 year-validity rule unregistered."}],
        "unavailable_reason": "required_year_invalid", "minimum_year_count": 3,
        "normal_season_start_month": None, "normal_season_end_month": None, "peak_median_month": None,
    }
    return fill_coverage(data)


def reserved_cutoff_calendar() -> dict:
    """TEST-ONLY artifact exercising the reserved S-NPP cutoff path. Never written to fixtures/.

    It declares a hypothetical S-NPP coverage through 2026-11-02 so the cutoff month and the
    ISO week 2026-W45 can be validated. It does not describe data that exist in this phase.
    """
    coverage = sensor_coverage("2026-11-02", "synthetic-test-only: reserved S-NPP cutoff path")
    data = _calendar_core(coverage, "active")
    data["monthly_series"][0]["records"].append(month(
        "VIIRS_SNPP", 2026, 11, 2, 100, days_with_file=2,
        is_partial_period=True, comparison_eligible=False,
        partial_period_reason="snpp_record_ended_2026_11_02", unusual_status=None))
    data["weekly_series"][0]["records"].append(week(
        "VIIRS_SNPP", 2026, 45, "2026-11-02", "2026-11-08", 3, 100, days_with_file=1,
        critical_status=None, unusual_status=None, is_partial_period=True, comparison_eligible=False,
        partial_period_reason="snpp_record_ended_2026_11_02"))
    return fill_coverage(data)


def sealed_boundary_calendar() -> dict:
    """Synthetic artifact with a PROPOSED (unregistered) sealed window read from config.

    Fabricated 2020-2021 dates appear here only to test sealed-boundary handling (P1).
    """
    cfg = _config()
    reason = cfg["sealed_partial_reason"]["value"]
    data = calendar()
    data["sealed_window"] = {
        "start": cfg["sealed_window"]["start"], "end": cfg["sealed_window"]["end"],
        "registration_status": "proposed_unregistered", "registration_ref": None, "decision_date": None,
    }
    data["week_53_rule"] = {
        "registration_status": "proposed_unregistered", "minimum_year_count": None,
        "registration_ref": None, "decision_at": None,
    }
    sealed = {"is_partial_period": True, "partial_period_reason": reason, "comparison_eligible": False,
              "critical_status": None, "unusual_status": None,
              "included_day_count": 2, "days_with_file": 2}  # only the 2 permitted days are used
    data["weekly_series"] = [{
        "sensor": "MODIS_Aqua", "policy_id": POLICY, "week_definition": "utc_iso_week",
        # Synthetic: 2015-W53 has only two earlier ISO week-53 years (2004, 2009); the rule is
        # unregistered, so the baseline is insufficient and the week carries no unusual label.
        "week_53_baselines": [{
            "target_year": 2015, "status": "insufficient_baseline",
            "prior_observations": [
                {"iso_year": 2004, "period_complete": True, "support_ok": True},
                {"iso_year": 2009, "period_complete": True, "support_ok": True},
            ],
        }],
        "records": [
            week("MODIS_Aqua", 2015, 53, "2015-12-28", "2016-01-03", 5, 100,
                 critical_status="insufficient_baseline", unusual_status="insufficient_baseline"),
            week("MODIS_Aqua", 2019, 52, "2019-12-23", "2019-12-29", 5, 100,
                 critical_status="not_critical", unusual_status="not_unusual"),
            week("MODIS_Aqua", 2020, 1, "2019-12-30", "2020-01-05", 5, 100, **sealed),
            week("MODIS_Aqua", 2021, 52, "2021-12-27", "2022-01-02", 5, 100, **sealed),
            week("MODIS_Aqua", 2022, 1, "2022-01-03", "2022-01-09", 5, 100,
                 critical_status="not_critical", unusual_status="not_unusual"),
        ],
    }]
    return fill_coverage(data)


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


def _phase_end(sensor: str) -> str:
    return next(e["record_end"] for e in phase()["active"] if e["sensor"] == sensor)


def manifest() -> dict:
    return {
        # The manifest describes the calendar, so it carries the calendar's five-field identity.
        **identity("same_sensor_calendar"),
        "manifest_version": "synthetic-manifest-1",
        "described_artifact_type": "calendar",
        "generated_at": "2026-11-14T00:20:00Z",
        "snpp_cessation_date": "2026-11-02",
        "snpp_cutoff_status": "reserved_inactive",  # P2 r8 item 3: no S-NPP data reach the cutoff
        "canonical_boundary": {
            "type": "Polygon",
            "coordinates": [[[0.0, 0.0], [1.0, 0.0], [1.0, 1.0], [0.0, 1.0], [0.0, 0.0]]],
        },
        "boundary_source": "synthetic", "boundary_version": "1", "crs": "EPSG:4326",
        "grid_inclusion_rule": "cell centroid inside boundary",
        "source_collections": [
            {"collection_id": "MODIS/061/MYD14A1", "sensor": "MODIS_Aqua",
             "source_version": "061", "record_end_date": _phase_end("MODIS_Aqua")},
            {"collection_id": "NASA/VIIRS/002/VNP14A1", "sensor": "VIIRS_SNPP",
             "source_version": "002", "record_end_date": _phase_end("VIIRS_SNPP")},
        ],
        "total_file_size_bytes": 2000, "compressed_bundle_size_bytes": 800,
        "partitions": [{
            "file_path": "synthetic/calendar.json", "geometry_id": GEO, "period_spec": PERIOD,
            "method_id": "same_sensor_calendar", "policy_id": POLICY, "sensor": "MODIS_Aqua",
            "cache_key_sha256": CacheKey(
                artifact_version="synthetic-v1", geometry_id=GEO, period_spec=PERIOD,
                method_id="same_sensor_calendar", policy_id=POLICY,
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
        "date_range_tested": "2023",
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
            "start_date": "2023-07-03", "end_date": "2023-07-09",
            "manual_selection_required": True,
            "limitation": "Select the area and dates manually in FIRMS.",
        },
        "points": [{
            "point_id": "synthetic-1", "latitude": 0.5, "longitude": 0.5,
            "acquired_at": "2023-07-03T10:30:00Z", "platform": "VIIRS_SNPP",
            "confidence_label": "nominal", "source_product": "synthetic",
        }],
        "feeds_grid_math": False, "inherits_grid_calibration": False,
        "cross_sensor_trend_allowed": False,
        "isolation_notice": "FIRMS points are separate from D, O, baselines, factors, and verdicts.",
    }


def all_fixtures() -> dict[str, tuple[type, dict]]:
    out = {
        "sample_calendar.json": (CalendarArtifact, calendar()),
        "sample_calendar_sealed_boundary.json": (CalendarArtifact, sealed_boundary_calendar()),
        "sample_calendar_unverified_footprint.json": (CalendarArtifact, unverified_footprint_calendar()),
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
