"""Week-boundary, sealed-window, week-53 and footprint tests on synthetic data only.

No test reads, derives from, or depends on real observations or sealed outcomes. All D/O
values are invented. Period status is decided from period dates alone.

Registration state lives in contracts/config/pending_registrations.json. Everything there
is unregistered: the week definition (UTC ISO weeks, P4's choice), the sealed window, the
proposed sealed reason, the week-53 minimum (blocked by the external-registry check and
P5's holdout-policy decision) and the footprint-certification shape (pending P2 Q3).
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pytest
from pydantic import ValidationError

from contracts import build_fixtures as bf
from contracts.schemas import calendar as calendar_module
from contracts.schemas.calendar import (
    CalendarArtifact,
    Week53Baseline,
    days_outside_window,
    has_iso_week_53,
    FootprintCertification,
    SealedWindow,
    Week53Rule,
    WeeklyCalendarSeries,
    sealed_window_period_status,
    snpp_period_status,
)

CONTRACTS = Path(__file__).resolve().parents[1]
CONFIG = json.loads((CONTRACTS / "config" / "pending_registrations.json").read_text(encoding="utf-8-sig"))
FIXTURES = CONTRACTS / "fixtures"
SEALED_START = date.fromisoformat(CONFIG["sealed_window"]["start"])
SEALED_END = date.fromisoformat(CONFIG["sealed_window"]["end"])
SEALED_REASON = CONFIG["sealed_partial_reason"]["value"]
SNPP_REASON = "snpp_record_ended_2026_11_02"


def week(sensor, start, end, year, number, *, partial_reason=None, d=5.0, o=100.0, eligible=None) -> dict:
    partial = partial_reason is not None
    return {
        "sensor": sensor, "year": year, "week_number": number,
        "start_date": start.isoformat(), "end_date": end.isoformat(),
        "detected_fire_cell_days": d, "usable_land_cell_days": o,
        "fire_activity_index": None if o == 0 else 1000.0 * d / o,
        "availability": "available", "unavailable_reason": None,
        "critical_status": None if partial else "not_critical",
        "unusual_status": None if partial else "not_unusual",
        "is_partial_period": partial, "partial_period_reason": partial_reason,
        "comparison_eligible": (not partial) if eligible is None else eligible,
        "included_day_count": None,
        "days_in_period": 7, "days_with_file": 7, "paired_comparison_eligible": False,
    }


def series(sensor: str, *records: dict, definition: str = "utc_iso_week") -> dict:
    return {"sensor": sensor, "policy_id": "own_support_eligible", "week_definition": definition,
            "week_53_baselines": [], "records": list(records)}


def series_ok(data: dict) -> bool:
    try:
        WeeklyCalendarSeries.model_validate_json(json.dumps(data))
    except ValidationError:
        return False
    return True


def sealed_artifact() -> dict:
    return json.loads((FIXTURES / "sample_calendar_sealed_boundary.json").read_text(encoding="utf-8"))


def plain_artifact() -> dict:
    return json.loads((FIXTURES / "sample_calendar.json").read_text(encoding="utf-8"))


def artifact_ok(data: dict) -> bool:
    try:
        CalendarArtifact.model_validate_json(json.dumps(data))
    except ValidationError:
        return False
    return True


def sealed_weeks(data: dict) -> list[dict]:
    return data["weekly_series"][0]["records"]


# Sealed fixture weekly records: 0 = 2015-W53, 1 = 2019-W52, 2 = 2020-W01 (crosses in),
# 3 = 2021-W52 (crosses out), 4 = 2022-W01.
CROSS = [2, 3]
OUTSIDE = [1, 4]
CROSS_IDS = ["crosses-into-2020-01-01", "crosses-out-after-2021-12-31"]


# ISO 8601 identities, hard-coded (Mon..Sun, UTC), independent of the contract code.
ISO_WEEKS = [
    (date(2019, 12, 23), date(2019, 12, 29), 2019, 52),
    (date(2019, 12, 30), date(2020, 1, 5), 2020, 1),
    (date(2020, 12, 28), date(2021, 1, 3), 2020, 53),
    (date(2021, 1, 4), date(2021, 1, 10), 2021, 1),
    (date(2021, 12, 27), date(2022, 1, 2), 2021, 52),
    (date(2022, 1, 3), date(2022, 1, 9), 2022, 1),
    (date(2026, 12, 28), date(2027, 1, 3), 2026, 53),
]


# ---------------------------------------------------------------------- ISO identity


@pytest.mark.parametrize("start,end,iso_year,iso_week", ISO_WEEKS)
def test_year_boundary_weeks_reject_calendar_year_or_shifted_labels(start, end, iso_year, iso_week) -> None:
    wrong = {(start.year, iso_week), (end.year, iso_week), (iso_year, iso_week + 1),
             (iso_year, max(1, iso_week - 1)), (iso_year + 1, iso_week), (iso_year - 1, iso_week)}
    for year, number in sorted(wrong - {(iso_year, iso_week)}):
        if 1 <= number <= 53:
            assert not series_ok(series("MODIS_Aqua", week("MODIS_Aqua", start, end, year, number))), (year, number)


@pytest.mark.parametrize("start,end,iso_year,iso_week", ISO_WEEKS)
def test_year_boundary_weeks_accept_correct_iso_identity(start, end, iso_year, iso_week) -> None:
    assert series_ok(series("MODIS_Aqua", week("MODIS_Aqua", start, end, iso_year, iso_week)))


@pytest.mark.parametrize("year,monday", [(2019, date(2019, 12, 23)), (2021, date(2021, 12, 27)),
                                         (2022, date(2022, 12, 26)), (2023, date(2023, 12, 25))])
def test_week_53_identity_rejected_in_52_week_iso_years(year: int, monday: date) -> None:
    sunday = date.fromordinal(monday.toordinal() + 6)
    assert series_ok(series("MODIS_Aqua", week("MODIS_Aqua", monday, sunday, year, 52)))
    assert not series_ok(series("MODIS_Aqua", week("MODIS_Aqua", monday, sunday, year, 53)))


@pytest.mark.parametrize("start,end", [(date(2019, 12, 31), date(2020, 1, 6)),
                                       (date(2019, 12, 29), date(2020, 1, 4)),
                                       (date(2020, 12, 30), date(2021, 1, 5))])
def test_non_iso_seven_day_bins_rejected_when_series_declares_iso_weeks(start, end) -> None:
    assert not series_ok(series("MODIS_Aqua", week("MODIS_Aqua", start, end, start.year, 1)))


def test_overlapping_year_boundary_weeks_rejected() -> None:
    a = week("MODIS_Aqua", date(2021, 12, 27), date(2022, 1, 2), 2021, 52)
    b = week("MODIS_Aqua", date(2022, 1, 3), date(2022, 1, 9), 2022, 1)
    assert series_ok(series("MODIS_Aqua", a, b))
    assert not series_ok(series("MODIS_Aqua", a, week("MODIS_Aqua", date(2022, 1, 2), date(2022, 1, 8), 2022, 1)))


def test_week_definition_is_declared_per_series_not_inferred() -> None:
    data = series("MODIS_Aqua", week("MODIS_Aqua", date(2022, 1, 3), date(2022, 1, 9), 2022, 1))
    del data["week_definition"]
    assert not series_ok(data)


# ---------------------------------------------------------------------- S-NPP cutoff


def test_snpp_cutoff_week_is_partial_and_neighbours_behave_as_boundaries() -> None:
    complete = week("VIIRS_SNPP", date(2026, 10, 26), date(2026, 11, 1), 2026, 44)
    cutoff = week("VIIRS_SNPP", date(2026, 11, 2), date(2026, 11, 8), 2026, 45, partial_reason=SNPP_REASON)
    after = week("VIIRS_SNPP", date(2026, 11, 9), date(2026, 11, 15), 2026, 46, partial_reason=SNPP_REASON)
    assert series_ok(series("VIIRS_SNPP", complete, cutoff))
    assert not series_ok(series("VIIRS_SNPP", after))
    as_complete = {**cutoff, "is_partial_period": False, "partial_period_reason": None,
                   "comparison_eligible": True, "critical_status": "not_critical", "unusual_status": "not_unusual"}
    assert not series_ok(series("VIIRS_SNPP", as_complete))


def test_snpp_cutoff_week_needs_null_labels_and_cannot_use_sealed_reason() -> None:
    base = week("VIIRS_SNPP", date(2026, 11, 2), date(2026, 11, 8), 2026, 45, partial_reason=SNPP_REASON)
    for field in ("critical_status", "unusual_status"):
        for bad in ("not_applicable", "critical", "not_critical", "unusual", "not_unusual", "insufficient_baseline"):
            assert not series_ok(series("VIIRS_SNPP", {**base, field: bad})), (field, bad)
    assert not series_ok(series("VIIRS_SNPP", {**base, "comparison_eligible": True}))
    assert not series_ok(series("VIIRS_SNPP", {**base, "partial_period_reason": SEALED_REASON}))


def test_snpp_cutoff_status_uses_dates_only() -> None:
    assert snpp_period_status(date(2026, 11, 1), date(2026, 11, 1)) == "complete"
    assert snpp_period_status(date(2026, 11, 2), date(2026, 11, 2)) == "partial"
    assert snpp_period_status(date(2026, 11, 3), date(2026, 11, 3)) == "after_record"


def test_other_sensors_on_cutoff_dates_are_not_partial() -> None:
    assert series_ok(series("MODIS_Aqua", week("MODIS_Aqua", date(2026, 11, 2), date(2026, 11, 8), 2026, 45)))
    assert not series_ok(series("MODIS_Aqua", week("MODIS_Aqua", date(2026, 11, 2), date(2026, 11, 8), 2026, 45,
                                                   partial_reason=SNPP_REASON)))


# ---------------------------------------------------------------------- D <= O (P2)


@pytest.mark.parametrize("d,o,ok", [(100.0, 100.0, True), (0.0, 100.0, True), (100.000001, 100.0, False),
                                    (1.0, 0.0, False)])
def test_d_not_greater_than_o_at_the_boundary(d: float, o: float, ok: bool) -> None:
    assert series_ok(series("MODIS_Aqua", week("MODIS_Aqua", date(2022, 1, 3), date(2022, 1, 9), 2022, 1, d=d, o=o))) is ok


# ---------------------------------------------------------------------- sealed window


def test_sealed_status_is_a_pure_function_of_dates() -> None:
    w = (SEALED_START, SEALED_END)
    assert sealed_window_period_status(date(2019, 12, 23), date(2019, 12, 29), *w) == "outside"
    assert sealed_window_period_status(date(2019, 12, 30), date(2020, 1, 5), *w) == "partial"
    assert sealed_window_period_status(date(2020, 6, 1), date(2020, 6, 7), *w) == "inside"
    assert sealed_window_period_status(date(2021, 12, 27), date(2022, 1, 2), *w) == "partial"
    assert sealed_window_period_status(date(2022, 1, 3), date(2022, 1, 9), *w) == "outside"
    # Single-day edges.
    assert sealed_window_period_status(SEALED_START, SEALED_START, *w) == "inside"
    assert sealed_window_period_status(date(2019, 12, 31), date(2019, 12, 31), *w) == "outside"


def test_sealed_fixture_is_valid_and_uses_proposed_unregistered_window() -> None:
    data = sealed_artifact()
    assert artifact_ok(data)
    assert data["sealed_window"]["registration_status"] == "proposed_unregistered"
    assert data["fixture_label"] == "[SYNTHETIC DEV FIXTURE]"


@pytest.mark.parametrize("idx", CROSS, ids=CROSS_IDS)
def test_crossing_week_must_be_partial_ineligible_with_null_labels(idx: int) -> None:
    rec = sealed_weeks(sealed_artifact())[idx]
    assert rec["is_partial_period"] and not rec["comparison_eligible"]
    assert rec["partial_period_reason"] == SEALED_REASON
    assert rec["critical_status"] is None and rec["unusual_status"] is None
    assert rec["days_with_file"] <= rec["included_day_count"] == 2  # only permitted days are used
    for patch in ({"comparison_eligible": True}, {"days_with_file": 3},
                  {"is_partial_period": False, "partial_period_reason": None, "comparison_eligible": True,
                   "included_day_count": None, "days_with_file": 7,
                   "critical_status": "not_critical", "unusual_status": "not_unusual"},
                  {"critical_status": "not_applicable"}, {"unusual_status": "insufficient_baseline"},
                  {"critical_status": "critical"}, {"partial_period_reason": SNPP_REASON}):
        data = sealed_artifact()
        sealed_weeks(data)[idx].update(patch)
        assert not artifact_ok(data), patch


@pytest.mark.parametrize("sensor", ["MODIS_Aqua", "VIIRS_SNPP"])
def test_crossing_rule_applies_to_every_sensor(sensor: str) -> None:
    data = sealed_artifact()
    s = data["weekly_series"][0]
    s["sensor"] = sensor
    for r in s["records"]:
        r["sensor"] = sensor
    assert artifact_ok(data)
    sealed_weeks(data)[CROSS[0]].update(
        is_partial_period=False, partial_period_reason=None, comparison_eligible=True, included_day_count=None,
        days_with_file=7, critical_status="not_critical", unusual_status="not_unusual")
    assert not artifact_ok(data)


@pytest.mark.parametrize("idx", OUTSIDE, ids=["ends-before-window", "starts-after-window"])
def test_weeks_wholly_outside_the_window_stay_complete_and_cannot_claim_sealed_reason(idx: int) -> None:
    data = sealed_artifact()
    rec = sealed_weeks(data)[idx]
    assert not rec["is_partial_period"] and rec["comparison_eligible"]
    rec.update(is_partial_period=True, partial_period_reason=SEALED_REASON, comparison_eligible=False,
               critical_status=None, unusual_status=None)
    assert not artifact_ok(data)


def test_sealed_reason_requires_a_declared_window() -> None:
    data = sealed_artifact()
    data["sealed_window"] = None
    assert not artifact_ok(data)


def test_crossing_months_are_sealed_partial_too() -> None:
    # Synthetic window (not the sealed dates) that cuts June/July 2023 and ISO week 2023-W27.
    data = plain_artifact()
    data["sealed_window"] = {**sealed_artifact()["sealed_window"], "start": "2023-06-20", "end": "2023-07-05"}
    assert not artifact_ok(data)  # June, July and W27 straddle it and are not marked
    permitted_months = {(2023, 6): 19, (2023, 7): 26}  # Jun 1-19 and Jul 6-31
    for s in data["monthly_series"]:
        for rec in s["records"]:
            key = (rec["year"], rec["month"])
            if key in permitted_months:
                rec.update(is_partial_period=True, partial_period_reason=SEALED_REASON, comparison_eligible=False,
                           paired_comparison_eligible=False, unusual_status=None, baseline_median=None,
                           baseline_p90=None, included_day_count=permitted_months[key],
                           days_with_file=permitted_months[key])
    assert not artifact_ok(data)  # 2023-W27 (Jul 3-9) still unmarked for both sensors
    for s in data["weekly_series"]:
        for rec in s["records"]:
            if (rec["year"], rec["week_number"]) == (2023, 27):
                rec.update(is_partial_period=True, partial_period_reason=SEALED_REASON, comparison_eligible=False,
                           paired_comparison_eligible=False, critical_status=None, unusual_status=None,
                           included_day_count=4, days_with_file=4)  # Jul 6-9
    assert artifact_ok(data)


def test_available_period_wholly_inside_window_is_rejected_but_placeholder_is_allowed() -> None:
    data = sealed_artifact()
    inside = week("MODIS_Aqua", date(2020, 6, 1), date(2020, 6, 7), 2020, 23)  # fabricated values
    sealed_weeks(data).append(inside)
    assert not artifact_ok(data)
    inside.update(detected_fire_cell_days=None, usable_land_cell_days=None, fire_activity_index=None,
                  availability="unavailable", unavailable_reason="source_not_available", comparison_eligible=False,
                  days_with_file=0, critical_status="insufficient_baseline", unusual_status="insufficient_baseline")
    assert artifact_ok(data)
    inside["unusual_status"] = "not_unusual"
    assert not artifact_ok(data)


def test_sealed_window_registration_needs_reference_and_date_and_is_required_in_production() -> None:
    with pytest.raises(ValidationError):
        SealedWindow(start=SEALED_START, end=SEALED_END, registration_status="registered")
    with pytest.raises(ValidationError):
        SealedWindow(start=SEALED_START, end=SEALED_END, registration_status="proposed_unregistered",
                     registration_ref="x")
    data = sealed_artifact()
    data.update(data_classification="production", fixture_label=None)
    assert not artifact_ok(data)


# ------------------------------------------------- sealed years never enter later baselines


@pytest.mark.parametrize("year", [2020, 2021])
def test_sealed_years_cannot_be_baseline_prior_years(year: int) -> None:
    data = sealed_artifact()
    data["seasonal_baselines"][0]["eligible_prior_years"] = [2016, 2017, 2018, 2019, year]
    data["seasonal_baselines"][0]["reference_end_year"] = max(year, data["seasonal_baselines"][0]["reference_end_year"])
    assert not artifact_ok(data)


def test_years_outside_the_window_remain_valid_baseline_years() -> None:
    data = sealed_artifact()
    data["seasonal_baselines"][0]["eligible_prior_years"] = [2016, 2017, 2018, 2019, 2022]
    data["seasonal_baselines"][0]["reference_end_year"] = 2022
    assert not artifact_ok(data)  # 2022 has no declared VIIRS annual coverage yet
    data["annual_coverage"].append(bf.annual(data["sensor_coverage"], "VIIRS_SNPP", 2022))
    assert artifact_ok(data)


# ---------------------------------------------------------------------- week-53 rule
# Agreed rule: three complete, supported, eligible prior week-53 observations from the same
# sensor and policy; otherwise insufficient_baseline and no unusual label. The minimum is
# configuration; fixtures keep the rule unregistered. Tests register a synthetic rule only
# to exercise the mechanism; "synthetic-test-only" is not a real decision reference.

SYNTHETIC_RULE = {"registration_status": "registered", "minimum_year_count": CONFIG["week_53_minimum"]["value"],
                  "registration_ref": "synthetic-test-only", "decision_at": "2026-11-15T00:00:00Z"}


def w53_record(data: dict, year: int) -> dict:
    return next(r for r in data["weekly_series"][0]["records"] if (r["year"], r["week_number"]) == (year, 53))


def w53_baseline(data: dict, year: int) -> dict:
    return next(b for b in data["weekly_series"][0]["week_53_baselines"] if b["target_year"] == year)


def mechanism_artifact() -> dict:
    """TEST-ONLY: hypothetical Aqua coverage through 2027-01-03 so 2026-W53 has three priors.

    In the current phase (P2 r8 scope, data to 2025-12-31) no ISO week 53 has three
    eligible prior week-53 years, so the rule can only be exercised on hypothetical data.
    """
    data = sealed_artifact()
    for cov in data["sensor_coverage"]:
        if cov["sensor"] == "MODIS_Aqua":
            cov.update(record_end="2027-01-03", scope_ref="synthetic-test-only: week-53 mechanism")
    s = data["weekly_series"][0]
    s["week_53_baselines"].append({
        "target_year": 2026, "status": "insufficient_baseline",
        "prior_observations": [{"iso_year": y, "period_complete": True, "support_ok": True}
                               for y in (2004, 2009, 2015)],
    })
    rec = week("MODIS_Aqua", date(2026, 12, 28), date(2027, 1, 3), 2026, 53)
    rec.update(critical_status="insufficient_baseline", unusual_status="insufficient_baseline")
    s["records"].append(rec)
    return data


def registered(data: dict, status: str = "available", unusual: str = "not_unusual",
               critical: str = "not_critical", year: int = 2026) -> dict:
    data["week_53_rule"] = dict(SYNTHETIC_RULE)
    w53_baseline(data, year)["status"] = status
    w53_record(data, year).update(unusual_status=unusual, critical_status=critical)
    return data


def test_agreed_minimum_is_three_in_config_and_not_registered() -> None:
    entry = CONFIG["week_53_minimum"]
    assert entry["value"] == 3 and entry["registered"] is False
    assert entry["decision_date"] is None and entry["reference"] is None


def test_iso_53_week_years_used_by_the_synthetic_cases() -> None:
    assert [y for y in range(2000, 2031) if has_iso_week_53(y)] == [2004, 2009, 2015, 2020, 2026]


def test_fixture_week_53_is_insufficient_while_rule_unregistered() -> None:
    data = sealed_artifact()
    assert w53_baseline(data, 2015)["status"] == "insufficient_baseline"
    assert w53_record(data, 2015)["unusual_status"] == "insufficient_baseline"
    assert artifact_ok(data)
    w53_baseline(data, 2015)["status"] = "available"  # no registered rule
    assert not artifact_ok(data)


def test_current_phase_week_53_stays_insufficient_even_with_a_registered_rule() -> None:
    # 2015-W53 has only two earlier week-53 years (2004, 2009); 2020 is sealed; 2026 is beyond 2025-12-31.
    data = registered(sealed_artifact(), year=2015)
    assert not artifact_ok(data)
    registered(data, status="insufficient_baseline", unusual="insufficient_baseline",
               critical="insufficient_baseline", year=2015)
    assert artifact_ok(data)


def test_three_complete_supported_priors_allow_a_decision() -> None:
    assert artifact_ok(mechanism_artifact())
    assert artifact_ok(registered(mechanism_artifact()))
    assert artifact_ok(registered(mechanism_artifact(), unusual="unusual", critical="critical"))


@pytest.mark.parametrize("field", ["period_complete", "support_ok"])
def test_two_eligible_priors_force_insufficient_baseline(field: str) -> None:
    data = registered(mechanism_artifact())
    w53_baseline(data, 2026)["prior_observations"][0][field] = False  # now only 2 eligible
    assert not artifact_ok(data)  # cannot stay available
    registered(data, status="insufficient_baseline", unusual="insufficient_baseline",
               critical="insufficient_baseline")
    assert artifact_ok(data)


@pytest.mark.parametrize("unusual", ["unusual", "not_unusual"])
def test_insufficient_week_53_cannot_carry_an_unusual_label(unusual: str) -> None:
    data = registered(mechanism_artifact(), status="insufficient_baseline", unusual=unusual,
                      critical="insufficient_baseline")
    w53_baseline(data, 2026)["prior_observations"].pop()
    assert not artifact_ok(data)


def test_insufficient_week_53_must_say_insufficient_baseline_not_null() -> None:
    data = sealed_artifact()
    w53_record(data, 2015)["unusual_status"] = None
    assert not artifact_ok(data)


def test_missing_week_53_baseline_entry_blocks_decisions() -> None:
    data = registered(mechanism_artifact())
    data["weekly_series"][0]["week_53_baselines"] = []
    assert not artifact_ok(data)


def test_sealed_week_53_year_cannot_be_a_prior_observation() -> None:
    data = registered(mechanism_artifact())
    w53_baseline(data, 2026)["prior_observations"][2]["iso_year"] = 2020  # the only sealed 53-week year
    assert not artifact_ok(data)


@pytest.mark.parametrize("year", [2019, 2021, 2023])
def test_years_without_iso_week_53_cannot_be_priors(year: int) -> None:
    with pytest.raises(ValidationError):
        Week53Baseline(target_year=2026, status="insufficient_baseline",
                       prior_observations=[{"iso_year": year, "period_complete": True, "support_ok": True}])


def test_priors_must_precede_target_and_be_unique() -> None:
    for years in ([2004, 2004, 2009], [2004, 2009, 2026]):
        with pytest.raises(ValidationError):
            Week53Baseline(target_year=2026, status="insufficient_baseline",
                           prior_observations=[{"iso_year": y, "period_complete": True, "support_ok": True}
                                               for y in years])
    with pytest.raises(ValidationError):
        Week53Baseline(target_year=2025, status="insufficient_baseline", prior_observations=[])


def test_week_53_baseline_is_per_series_so_sensor_and_policy_cannot_mix() -> None:
    data = registered(mechanism_artifact())
    other = {"sensor": "VIIRS_SNPP", "policy_id": data["policy_id"], "week_definition": "utc_iso_week",
             "week_53_baselines": [], "records": [week("VIIRS_SNPP", date(2022, 1, 3), date(2022, 1, 9), 2022, 1)]}
    data["weekly_series"].append(other)
    assert artifact_ok(data)  # the VIIRS series has no week-53 baseline and cannot borrow Aqua's
    other["records"].append(week("VIIRS_SNPP", date(2015, 12, 28), date(2016, 1, 3), 2015, 53))
    assert not artifact_ok(data)  # VIIRS 2015-W53 decision with no VIIRS week-53 baseline


def test_registered_rule_needs_reference_and_utc_timestamp() -> None:
    from contracts.schemas.calendar import Week53Rule

    with pytest.raises(ValidationError):
        Week53Rule(registration_status="registered", minimum_year_count=3)
    with pytest.raises(ValidationError):
        Week53Rule.model_validate_json(json.dumps({**SYNTHETIC_RULE, "decision_at": "2026-11-15T00:00:00"}))
    for minimum in (1, 2, 3):
        with pytest.raises(ValidationError):
            Week53Rule(registration_status="proposed_unregistered", minimum_year_count=minimum)


# ---------------------------------------------------------------------- footprint coverage
# complete / partial / unverified, PROPOSED pending P2's Q3 certification rule.

DOC = {"certification_ref": "synthetic-p2-doc", "certified_at": "2026-11-15T10:00:00Z"}


def footprint(data: dict, status: str, **extra) -> dict:
    data["footprint_certification"] = {"geometry_id": data["geometry_id"], "status": status,
                                       "certification_ref": None, "certified_at": None, "coverage_fraction": None,
                                       **extra}
    return data


def registered_window_for_plain_fixture() -> dict:
    # Synthetic window placed where the plain fixture has no records, so no period straddles it.
    return {"start": "2011-01-01", "end": "2011-12-31", "registration_status": "registered",
            "registration_ref": "synthetic-ref", "decision_date": "2026-11-15"}


def production(data: dict) -> dict:
    data.update(data_classification="production", fixture_label=None,
                sealed_window=registered_window_for_plain_fixture())
    return data


def test_complete_footprint_requires_p2_documentation() -> None:
    with pytest.raises(ValidationError):
        FootprintCertification(geometry_id="g", status="complete")
    assert artifact_ok(footprint(plain_artifact(), "complete", **DOC))


def test_partial_footprint_requires_documentation_and_fraction() -> None:
    with pytest.raises(ValidationError):
        FootprintCertification.model_validate_json(json.dumps(
            {"geometry_id": "g", "status": "partial", **DOC}))
    for bad in (0.0, 1.0, 1.2):
        with pytest.raises(ValidationError):
            FootprintCertification.model_validate_json(json.dumps(
                {"geometry_id": "g", "status": "partial", "coverage_fraction": bad, **DOC}))
    FootprintCertification.model_validate_json(json.dumps(
        {"geometry_id": "g", "status": "partial", "coverage_fraction": 0.8, **DOC}))


def test_unverified_footprint_cannot_carry_documentation_or_fraction() -> None:
    for extra in (DOC, {"coverage_fraction": 0.5}):
        with pytest.raises(ValidationError):
            FootprintCertification.model_validate_json(json.dumps(
                {"geometry_id": "g", "status": "unverified", **extra}))


@pytest.mark.parametrize("status,extra", [("partial", {"coverage_fraction": 0.8, **DOC}), ("unverified", {})])
def test_partial_or_unverified_footprint_blocks_comparison_eligibility(status: str, extra: dict) -> None:
    assert not artifact_ok(footprint(plain_artifact(), status, **extra))


@pytest.mark.parametrize("status,extra", [("partial", {"coverage_fraction": 0.8, **DOC}), ("unverified", {})])
def test_partial_or_unverified_footprint_is_valid_without_eligible_periods(status: str, extra: dict) -> None:
    data = footprint(sealed_artifact(), status, **extra)
    for s in data["monthly_series"] + data["weekly_series"]:
        for r in s["records"]:
            r["comparison_eligible"] = False
            r["paired_comparison_eligible"] = False
    assert artifact_ok(data)


def test_production_eligible_periods_require_p2_certified_complete_footprint() -> None:
    data = production(plain_artifact())
    assert not artifact_ok(data)  # an available aggregate never implies completeness
    for status, extra in (("unverified", {}), ("partial", {"coverage_fraction": 0.9, **DOC})):
        assert not artifact_ok(footprint(production(plain_artifact()), status, **extra))
    assert artifact_ok(footprint(production(plain_artifact()), "complete", **DOC))


def test_footprint_certification_cannot_cross_geometry() -> None:
    data = footprint(plain_artifact(), "complete", **DOC)
    data["footprint_certification"]["geometry_id"] = "geo-other"
    assert not artifact_ok(data)


# ---------------------------------------------------- sealed-boundary partials: permitted days only


def test_permitted_day_count_is_computed_from_dates_only() -> None:
    w = (SEALED_START, SEALED_END)
    assert days_outside_window(date(2019, 12, 30), date(2020, 1, 5), *w) == 2   # Dec 30-31
    assert days_outside_window(date(2021, 12, 27), date(2022, 1, 2), *w) == 2   # Jan 1-2
    assert days_outside_window(date(2022, 1, 3), date(2022, 1, 9), *w) == 7
    assert days_outside_window(date(2020, 6, 1), date(2020, 6, 7), *w) == 0


@pytest.mark.parametrize("idx", CROSS, ids=CROSS_IDS)
@pytest.mark.parametrize("count", [None, 1, 3, 6])
def test_crossing_week_must_declare_exactly_its_permitted_days(idx: int, count) -> None:
    data = sealed_artifact()
    assert sealed_weeks(data)[idx]["included_day_count"] == 2
    sealed_weeks(data)[idx]["included_day_count"] = count  # any other value would use sealed days or hide some
    assert not artifact_ok(data)


def test_included_day_count_only_on_sealed_boundary_partials() -> None:
    data = sealed_artifact()
    sealed_weeks(data)[OUTSIDE[0]]["included_day_count"] = 7  # complete week
    assert not artifact_ok(data)
    data = bf.reserved_cutoff_calendar()
    snpp = next(r for r in data["weekly_series"][0]["records"] if (r["year"], r["week_number"]) == (2026, 45))
    assert snpp["partial_period_reason"] == SNPP_REASON and snpp["included_day_count"] is None
    snpp["included_day_count"] = 1  # S-NPP cutoff partials do not use the sealed permitted-day field
    assert not artifact_ok(data)


@pytest.mark.parametrize("key", ["sealed_window", "week_53_rule", "footprint_certification"])
def test_registration_keys_are_required_explicit_nulls(key: str) -> None:
    data = plain_artifact()
    assert key in data and data[key] is None
    del data[key]
    assert not artifact_ok(data)


# ------------------------------------------- guards: unregistered values stay configuration


def test_unregistered_values_are_not_schema_defaults() -> None:
    assert WeeklyCalendarSeries.model_fields["week_definition"].is_required()
    for key in ("sealed_window", "week_53_rule", "footprint_certification"):
        assert CalendarArtifact.model_fields[key].is_required(), key
    assert Week53Rule.model_fields["minimum_year_count"].default is None
    source = Path(calendar_module.__file__).read_text(encoding="utf-8")
    for token in (CONFIG["sealed_window"]["start"], CONFIG["sealed_window"]["end"]):
        assert token not in source, f"{token} is hard-coded in the schema before registration"


def test_config_entries_cannot_claim_frozen_without_date_and_reference() -> None:
    expected = {"week_definition", "sealed_window", "sealed_partial_reason", "week_53_minimum",
                "footprint_certification"}
    assert expected <= set(CONFIG)
    for name in expected:
        entry = CONFIG[name]
        assert entry["registered"] is False, f"{name} must stay unregistered until P1/P2 approve"
        assert entry["decision_date"] is None and entry["reference"] is None, name


# ------------------------------------------- P5 holdout decision (handoff d0b8c90), synthetic only


def test_production_artifact_must_declare_a_registered_sealed_window() -> None:
    data = plain_artifact()
    data.update(data_classification="production", fixture_label=None, footprint_certification={
        "geometry_id": data["geometry_id"], "status": "certified_complete",
        "certification_ref": "synthetic-p2-doc", "certified_at": "2026-11-15T10:00:00Z"})
    assert data["sealed_window"] is None
    assert not artifact_ok(data)  # no window -> sealed years could not be excluded
    data["sealed_window"] = {**sealed_artifact()["sealed_window"], "registration_status": "proposed_unregistered"}
    assert not artifact_ok(data)  # a proposed window is not enough for production


def test_no_fixture_lists_sealed_years_as_baseline_prior_years() -> None:
    for path in FIXTURES.glob("*.json"):
        data = json.loads(path.read_text(encoding="utf-8"))
        for baseline in data.get("seasonal_baselines", []):
            sealed = [y for y in baseline["eligible_prior_years"] if SEALED_START.year <= y <= SEALED_END.year]
            assert not sealed, (path.name, sealed)


def test_too_few_years_after_excluding_sealed_years_must_be_insufficient_baseline() -> None:
    data = sealed_artifact()
    b = data["seasonal_baselines"][0]
    b.update(eligible_prior_years=[2018, 2019], minimum_year_count=3)  # sealed years removed, now short
    assert not artifact_ok(data)  # cannot stay "available"
    b.update(status="insufficient_baseline", normal_season_start_month=None,
             normal_season_end_month=None, peak_median_month=None)
    assert artifact_ok(data)


# ------------------------------- P1: fabricated 2020-2021 dates only in sealed-boundary fixtures

BOUNDARY_FIXTURES = {"sample_calendar_sealed_boundary.json"}


def _sealed_dates(node, path="$"):
    if isinstance(node, dict):
        for key, value in node.items():
            yield from _sealed_dates(value, f"{path}.{key}")
    elif isinstance(node, list):
        for i, value in enumerate(node):
            yield from _sealed_dates(value, f"{path}[{i}]")
    elif isinstance(node, bool):
        return
    elif isinstance(node, int) and node in (2020, 2021):
        yield path, node
    elif isinstance(node, str) and node[:5] in ("2020-", "2021-"):
        yield path, node


def test_non_boundary_fixtures_use_no_2020_2021_dates() -> None:
    for path in sorted(FIXTURES.glob("*.json")):
        if path.name in BOUNDARY_FIXTURES:
            continue
        hits = list(_sealed_dates(json.loads(path.read_text(encoding="utf-8"))))
        assert not hits, (path.name, hits[:5])


def test_boundary_fixture_is_fabricated_and_labelled() -> None:
    for name in BOUNDARY_FIXTURES:
        data = json.loads((FIXTURES / name).read_text(encoding="utf-8"))
        assert data["data_classification"] == "synthetic_dev_fixture"
        assert data["fixture_label"] == "[SYNTHETIC DEV FIXTURE]"


# --------------------------- P2 r8 item 2: record-boundary partial periods (synthetic values)

# (series kind, sensor, key) -> (days_in_period, days inside the P2-stated record)
P2_BOUNDARY_PERIODS = {
    ("month", "MODIS_Aqua", (2002, 7)): (31, 28),          # Aqua record from 2002-07-04
    ("week", "MODIS_Aqua", (2002, 27)): (7, 4),             # 2002-07-01..07, record from 07-04
    ("month", "VIIRS_SNPP", (2012, 1)): (31, 13),           # VIIRS record from 2012-01-19
    ("week", "VIIRS_SNPP", (2012, 3)): (7, 4),              # 2012-01-16..22
    ("week", "VIIRS_SNPP", (2026, 1)): (7, 3),              # 2025-12-29..31 only
    ("week", "MODIS_Aqua", (2026, 1)): (7, 3),
}


def find(data: dict, kind: str, sensor: str, key: tuple) -> dict:
    groups = data["monthly_series"] if kind == "month" else data["weekly_series"]
    for s in groups:
        if s["sensor"] != sensor:
            continue
        for r in s["records"]:
            if (r["year"], r["month"] if kind == "month" else r["week_number"]) == key:
                return r
    raise KeyError((kind, sensor, key))


@pytest.mark.parametrize("kind,sensor,key", sorted(P2_BOUNDARY_PERIODS))
def test_p2_boundary_periods_are_represented_as_partial(kind: str, sensor: str, key: tuple) -> None:
    rec = find(plain_artifact(), kind, sensor, key)
    total, inside = P2_BOUNDARY_PERIODS[(kind, sensor, key)]
    assert rec["days_in_period"] == total and rec["days_with_file"] == inside
    assert rec["is_partial_period"] and rec["partial_period_reason"] == "outside_sensor_record"
    assert not rec["comparison_eligible"] and not rec["paired_comparison_eligible"]
    assert rec["unusual_status"] is None
    assert rec.get("critical_status") is None


@pytest.mark.parametrize("kind,sensor,key", sorted(P2_BOUNDARY_PERIODS))
@pytest.mark.parametrize("patch", [
    {"comparison_eligible": True},
    {"is_partial_period": False, "partial_period_reason": None,
     "unusual_status": "insufficient_baseline", "critical_status": "insufficient_baseline"},
    {"partial_period_reason": "crosses_sealed_evaluation_boundary"},
    {"days_with_file": 7},
], ids=["eligible", "unflagged", "wrong-reason", "files-outside-record"])
def test_p2_boundary_periods_reject_completion(kind: str, sensor: str, key: tuple, patch: dict) -> None:
    data = plain_artifact()
    rec = find(data, kind, sensor, key)
    rec.update(patch)
    if kind == "month":
        rec.pop("critical_status", None)  # months carry no critical label
        if patch.get("days_with_file") == 7:
            rec["days_with_file"] = rec["days_in_period"]
    assert not artifact_ok(data)


def test_p2_partial_years_are_declared_and_cannot_be_baseline_years() -> None:
    data = plain_artifact()
    years = {(a["sensor"], a["year"]): a for a in data["annual_coverage"]}
    assert years[("MODIS_Aqua", 2002)]["days_with_file"] == 181 and years[("MODIS_Aqua", 2002)]["is_partial_period"]
    assert years[("VIIRS_SNPP", 2012)]["days_with_file"] == 348 and years[("VIIRS_SNPP", 2012)]["is_partial_period"]
    data["seasonal_baselines"][1]["eligible_prior_years"] = [2002, 2016]
    assert not artifact_ok(data)
    data = plain_artifact()
    data["seasonal_baselines"][0]["eligible_prior_years"] = [2012, 2016, 2017, 2018, 2019]
    assert not artifact_ok(data)
    data = plain_artifact()
    years = {(a["sensor"], a["year"]): a for a in data["annual_coverage"]}
    years[("MODIS_Aqua", 2002)].update(is_partial_period=False, partial_period_reason=None)
    assert not artifact_ok(data)  # a year straddling the record start cannot be declared complete


def test_baseline_year_without_declared_annual_coverage_is_rejected() -> None:
    data = plain_artifact()
    data["annual_coverage"] = [a for a in data["annual_coverage"] if (a["sensor"], a["year"]) != ("VIIRS_SNPP", 2017)]
    assert not artifact_ok(data)


@pytest.mark.parametrize("kind,sensor,key,start,end", [
    ("month", "MODIS_Aqua", (2002, 6), None, None),
    ("month", "VIIRS_SNPP", (2011, 12), None, None),
    ("week", "VIIRS_SNPP", (2026, 2), date(2026, 1, 5), date(2026, 1, 11)),
])
def test_periods_wholly_outside_the_declared_record_are_rejected(kind, sensor, key, start, end) -> None:
    data = plain_artifact()
    if kind == "month":
        idx = 1 if sensor == "MODIS_Aqua" else 0
        data["monthly_series"][idx]["records"].append(bf.month(sensor, key[0], key[1], 1, 50))
    else:
        data["weekly_series"][0]["records"].append(week(sensor, start, end, key[0], key[1]))
    assert not artifact_ok(data)


def test_paired_comparison_requires_both_sensors_complete() -> None:
    data = plain_artifact()
    viirs = find(data, "month", "VIIRS_SNPP", (2023, 6))
    aqua = find(data, "month", "MODIS_Aqua", (2023, 6))
    assert viirs["paired_comparison_eligible"] and aqua["paired_comparison_eligible"]
    aqua["days_with_file"] = 29  # one Aqua day without a file
    assert not artifact_ok(data)  # Aqua can no longer be comparison-eligible
    aqua.update(comparison_eligible=False, paired_comparison_eligible=False, unusual_status="insufficient_baseline")
    assert not artifact_ok(data)  # VIIRS still claims a pair with an incomplete Aqua month
    viirs["paired_comparison_eligible"] = False
    assert artifact_ok(data)  # VIIRS stays comparison-eligible on its own; only the pair is dropped


def test_paired_comparison_needs_a_twin_record() -> None:
    data = plain_artifact()
    data["monthly_series"][1]["records"] = [r for r in data["monthly_series"][1]["records"]
                                            if (r["year"], r["month"]) != (2023, 7)]
    assert not artifact_ok(data)


# ------------------------------- P2 r8 item 3: reserved/inactive scope for the current phase


def test_current_phase_coverage_comes_from_p2_scope_in_config() -> None:
    phase = CONFIG["current_phase_coverage"]
    assert phase["registered"] is False and phase["source_ref"].startswith("P2 r8 verdict")
    data = plain_artifact()
    cov = {c["sensor"]: c for c in data["sensor_coverage"]}
    assert set(cov) == {"MODIS_Aqua", "VIIRS_SNPP", "VIIRS_NOAA20", "VIIRS_NOAA21"}
    assert cov["MODIS_Aqua"]["record_start"] == "2002-07-04" and cov["VIIRS_SNPP"]["record_start"] == "2012-01-19"
    assert cov["MODIS_Aqua"]["record_end"] == cov["VIIRS_SNPP"]["record_end"] == "2025-12-31"
    for sensor in ("VIIRS_NOAA20", "VIIRS_NOAA21"):
        assert cov[sensor]["status"] == "reserved_inactive" and cov[sensor]["record_start"] is None
    assert data["snpp_cutoff_status"] == "reserved_inactive"


def test_consumer_fixtures_hold_no_data_after_the_phase_end() -> None:
    end = date.fromisoformat(CONFIG["current_phase_coverage"]["active"][0]["record_end"])
    for name in ("sample_calendar.json", "sample_calendar_sealed_boundary.json"):
        data = json.loads((FIXTURES / name).read_text(encoding="utf-8"))
        for s in data["monthly_series"]:
            for r in s["records"]:
                assert date(r["year"], r["month"], 1) <= end, (name, r["year"], r["month"])
        for s in data["weekly_series"]:
            for r in s["records"]:
                assert date.fromisoformat(r["start_date"]) <= end, (name, r["start_date"])
                if date.fromisoformat(r["end_date"]) > end:
                    assert r["is_partial_period"] and r["days_with_file"] <= (end - date.fromisoformat(r["start_date"])).days + 1


def test_reserved_sensors_cannot_carry_records_or_dates() -> None:
    data = plain_artifact()
    data["weekly_series"].append({"sensor": "VIIRS_NOAA20", "policy_id": data["policy_id"],
                                  "week_definition": "utc_iso_week", "week_53_baselines": [],
                                  "records": [week("VIIRS_NOAA20", date(2023, 7, 3), date(2023, 7, 9), 2023, 27)]})
    assert not artifact_ok(data)
    data = plain_artifact()
    noaa = next(c for c in data["sensor_coverage"] if c["sensor"] == "VIIRS_NOAA21")
    noaa.update(record_start="2023-01-01")
    assert not artifact_ok(data)


def test_every_sensor_coverage_must_be_declared() -> None:
    data = plain_artifact()
    data["sensor_coverage"] = [c for c in data["sensor_coverage"] if c["sensor"] != "VIIRS_NOAA20"]
    assert not artifact_ok(data)


def test_snpp_cutoff_is_inactive_unless_snpp_coverage_reaches_it() -> None:
    data = plain_artifact()
    data["snpp_cutoff_status"] = "active"
    assert not artifact_ok(data)
    cutoff = bf.reserved_cutoff_calendar()  # test-only artifact
    assert cutoff["snpp_cutoff_status"] == "active" and artifact_ok(cutoff)
    cutoff["snpp_cutoff_status"] = "reserved_inactive"
    assert not artifact_ok(cutoff)
    data = plain_artifact()
    snpp = next(c for c in data["sensor_coverage"] if c["sensor"] == "VIIRS_SNPP")
    snpp["record_end"] = "2026-11-03"
    assert not artifact_ok(data)


def test_manifest_cutoff_status_reflects_listed_sources() -> None:
    from contracts.schemas import ProvenanceManifest

    man = json.loads((FIXTURES / "sample_manifest.json").read_text(encoding="utf-8"))
    assert man["snpp_cutoff_status"] == "reserved_inactive"
    assert all(c["record_end_date"] == "2025-12-31" for c in man["source_collections"])
    man["snpp_cutoff_status"] = "active"
    with pytest.raises(ValidationError):
        ProvenanceManifest.model_validate_json(json.dumps(man))


def test_p2_scope_dates_are_not_hard_coded_in_the_schema() -> None:
    source = Path(calendar_module.__file__).read_text(encoding="utf-8")
    for token in ("2002-07-04", "2012-01-19", "2025-12-31", "2002, 7, 4", "2012, 1, 19", "2025, 12, 31"):
        assert token not in source, token
