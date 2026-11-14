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


@pytest.mark.parametrize("idx", [1, 2], ids=["crosses-into-2020-01-01", "crosses-out-after-2021-12-31"])
def test_crossing_week_must_be_partial_ineligible_with_null_labels(idx: int) -> None:
    rec = sealed_weeks(sealed_artifact())[idx]
    assert rec["is_partial_period"] and not rec["comparison_eligible"]
    assert rec["partial_period_reason"] == SEALED_REASON
    assert rec["critical_status"] is None and rec["unusual_status"] is None
    for patch in ({"comparison_eligible": True},
                  {"is_partial_period": False, "partial_period_reason": None, "comparison_eligible": True,
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
    if sensor == "VIIRS_SNPP":  # S-NPP has no record after 2026-11-02; drop the synthetic 2026-W53 case
        s["records"] = [r for r in s["records"] if r["year"] != 2026]
        s["week_53_baselines"] = []
    for r in s["records"]:
        r["sensor"] = sensor
    assert artifact_ok(data)
    sealed_weeks(data)[1].update(is_partial_period=False, partial_period_reason=None, comparison_eligible=True,
                                 critical_status="not_critical", unusual_status="not_unusual")
    assert not artifact_ok(data)


@pytest.mark.parametrize("idx", [0, 3], ids=["ends-before-window", "starts-after-window"])
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
    data = plain_artifact()
    data["sealed_window"] = sealed_artifact()["sealed_window"]
    data["sealed_window"].update(start="2023-06-15", end="2023-07-12")  # synthetic window, not the sealed dates
    assert not artifact_ok(data)  # June and July 2023 straddle it and are not marked
    permitted = {(2023, 6): 14, (2023, 7): 19}  # June 1-14 and July 13-31 lie outside Jun 15 - Jul 12
    for series_idx in (0, 1):
        for rec in data["monthly_series"][series_idx]["records"]:
            key = (rec["year"], rec["month"])
            if key in permitted:
                rec.update(is_partial_period=True, partial_period_reason=SEALED_REASON, comparison_eligible=False,
                           unusual_status=None, included_day_count=permitted[key])
                if series_idx == 0:
                    rec.update(baseline_median=None, baseline_p90=None)
    data["seasonal_baselines"][0]["eligible_prior_years"] = [2016, 2017, 2018, 2019]
    assert not artifact_ok(data)  # 2023-W28 (Jul 10-16) also straddles Jul 12 and is not yet marked
    for rec in data["weekly_series"][0]["records"]:
        if (rec["year"], rec["week_number"]) == (2023, 28):
            rec.update(is_partial_period=True, partial_period_reason=SEALED_REASON, comparison_eligible=False,
                       critical_status=None, unusual_status=None, included_day_count=4)  # Jul 13-16
    assert artifact_ok(data)


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
    assert artifact_ok(data)


# ---------------------------------------------------------------------- week-53 rule
# Agreed rule: three complete, supported, eligible prior week-53 observations from the same
# sensor and policy; otherwise insufficient_baseline and no unusual label. The minimum is
# configuration; fixtures keep the rule unregistered. Tests register a synthetic rule only
# to exercise the mechanism; "synthetic-test-only" is not a real decision reference.

W53_START, W53_END = date(2026, 12, 28), date(2027, 1, 3)
SYNTHETIC_RULE = {"registration_status": "registered", "minimum_year_count": CONFIG["week_53_minimum"]["value"],
                  "registration_ref": "synthetic-test-only", "decision_at": "2026-11-15T00:00:00Z"}


def w53_series(data: dict) -> dict:
    return data["weekly_series"][0]


def w53_record(data: dict) -> dict:
    return next(r for r in w53_series(data)["records"] if r["week_number"] == 53)


def w53_baseline(data: dict) -> dict:
    return w53_series(data)["week_53_baselines"][0]


def registered(data: dict, status: str = "available", unusual: str = "not_unusual",
               critical: str = "not_critical") -> dict:
    data["week_53_rule"] = dict(SYNTHETIC_RULE)
    w53_baseline(data)["status"] = status
    w53_record(data).update(unusual_status=unusual, critical_status=critical)
    return data


def test_agreed_minimum_is_three_in_config_and_not_registered() -> None:
    entry = CONFIG["week_53_minimum"]
    assert entry["value"] == 3 and entry["registered"] is False
    assert entry["decision_date"] is None and entry["reference"] is None


def test_iso_53_week_years_used_by_the_synthetic_cases() -> None:
    assert [y for y in range(2000, 2031) if has_iso_week_53(y)] == [2004, 2009, 2015, 2020, 2026]


def test_fixture_week_53_is_insufficient_while_rule_unregistered() -> None:
    data = sealed_artifact()
    assert w53_baseline(data)["status"] == "insufficient_baseline"
    assert w53_record(data)["unusual_status"] == "insufficient_baseline"
    assert artifact_ok(data)
    w53_baseline(data)["status"] = "available"  # three priors exist, but no registered rule
    assert not artifact_ok(data)


def test_three_complete_supported_priors_allow_a_decision() -> None:
    assert artifact_ok(registered(sealed_artifact()))
    assert artifact_ok(registered(sealed_artifact(), unusual="unusual", critical="critical"))


@pytest.mark.parametrize("field", ["period_complete", "support_ok"])
def test_two_eligible_priors_force_insufficient_baseline(field: str) -> None:
    data = registered(sealed_artifact())
    w53_baseline(data)["prior_observations"][0][field] = False  # now only 2 eligible
    assert not artifact_ok(data)  # cannot stay available
    registered(data, status="insufficient_baseline", unusual="insufficient_baseline",
               critical="insufficient_baseline")
    assert artifact_ok(data)


@pytest.mark.parametrize("unusual", ["unusual", "not_unusual"])
def test_insufficient_week_53_cannot_carry_an_unusual_label(unusual: str) -> None:
    data = registered(sealed_artifact(), status="insufficient_baseline", unusual=unusual,
                      critical="insufficient_baseline")
    w53_baseline(data)["prior_observations"].pop()
    assert not artifact_ok(data)


def test_insufficient_week_53_must_say_insufficient_baseline_not_null() -> None:
    data = sealed_artifact()
    w53_record(data)["unusual_status"] = None
    assert not artifact_ok(data)


def test_missing_week_53_baseline_entry_blocks_decisions() -> None:
    data = registered(sealed_artifact())
    w53_series(data)["week_53_baselines"] = []
    assert not artifact_ok(data)


def test_sealed_week_53_year_cannot_be_a_prior_observation() -> None:
    data = registered(sealed_artifact())
    w53_baseline(data)["prior_observations"][2]["iso_year"] = 2020  # the only sealed 53-week year
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
    data = registered(sealed_artifact())
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


@pytest.mark.parametrize("idx", [1, 2], ids=["crosses-into-2020-01-01", "crosses-out-after-2021-12-31"])
@pytest.mark.parametrize("count", [None, 1, 3, 6])
def test_crossing_week_must_declare_exactly_its_permitted_days(idx: int, count) -> None:
    data = sealed_artifact()
    assert sealed_weeks(data)[idx]["included_day_count"] == 2
    sealed_weeks(data)[idx]["included_day_count"] = count  # any other value would use sealed days or hide some
    assert not artifact_ok(data)


def test_included_day_count_only_on_sealed_boundary_partials() -> None:
    data = sealed_artifact()
    sealed_weeks(data)[0]["included_day_count"] = 7  # complete week
    assert not artifact_ok(data)
    data = plain_artifact()
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
