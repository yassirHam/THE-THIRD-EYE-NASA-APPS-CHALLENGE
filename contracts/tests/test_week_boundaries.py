"""Week-boundary tests on synthetic dates only.

Nothing here reads, derives from, or depends on real observation values. All D/O numbers
are invented. Period status is decided from period dates alone, never from sealed days.

Layout
- ACTIVE tests encode facts that hold under the registered choice (UTC ISO weeks) and the
  contract as it is today. Expected ISO identities are hard-coded from the ISO 8601
  calendar, independent of the contract's own isocalendar() call.
- PENDING tests (strict xfail) encode the sealed-window rule that P2 proposed and P1/P2
  have not frozen. Each flips to XPASS (a failure) when the contract gains the behaviour,
  which forces the xfail marker, and the proposed names below, to be reviewed.

Assumptions awaiting P1/P2 confirmation (do not treat as frozen):
- Sealed window comes from contracts/config/pending_registrations.json (assumed UTC days,
  2020-01-01 .. 2021-12-31 inclusive) and is NOT registered.
- A week that straddles either sealed edge is partial and comparison-ineligible with null
  labels, for every sensor.
- Baseline treatment of ISO week 53 (include / skip / merge) is a P1 science rule and is
  not tested here. The contract only validates week identity.
"""

from __future__ import annotations

import inspect
import json
from datetime import date
from pathlib import Path

import pytest
from pydantic import ValidationError

from contracts.schemas.calendar import WeekRecord, WeeklyCalendarSeries, snpp_period_status

# Unregistered values come from configuration, never from schema defaults. They stay
# pending until P1/P2 approve and register them (see contracts/config).
CONFIG_PATH = Path(__file__).resolve().parents[1] / "config" / "pending_registrations.json"
CONFIG = json.loads(CONFIG_PATH.read_text(encoding="utf-8-sig"))
SEALED_START = date.fromisoformat(CONFIG["sealed_window"]["start"])
SEALED_END = date.fromisoformat(CONFIG["sealed_window"]["end"])
PROPOSED_SEALED_REASON = CONFIG["sealed_partial_reason"]["value"]
SEALED_RULE_REGISTERED = bool(
    CONFIG["sealed_window"]["registered"] and CONFIG["sealed_partial_reason"]["registered"]
)
# While unregistered: strict xfail. Once registered: the same tests must pass, so a
# missing implementation becomes a hard failure instead of a silent xfail.
PENDING = pytest.mark.xfail(
    condition=not SEALED_RULE_REGISTERED,
    strict=True,
    raises=(ValidationError, ImportError, AttributeError, AssertionError),
    reason="PENDING P1/P2 frozen sealed-window rule; representation proposed, not agreed",
)
SNPP_REASON = "snpp_record_ended_2026_11_02"


def week(
    sensor: str,
    start: date,
    end: date,
    year: int,
    number: int,
    *,
    partial_reason: str | None = None,
    d: float = 5.0,
    o: float = 100.0,
) -> dict:
    partial = partial_reason is not None
    return {
        "sensor": sensor,
        "year": year,
        "week_number": number,
        "start_date": start.isoformat(),
        "end_date": end.isoformat(),
        "detected_fire_cell_days": d,
        "usable_land_cell_days": o,
        "fire_activity_index": None if o == 0 else 1000.0 * d / o,
        "availability": "available",
        "unavailable_reason": None,
        "critical_status": None if partial else "not_critical",
        "unusual_status": None if partial else "not_unusual",
        "is_partial_period": partial,
        "partial_period_reason": partial_reason,
        "comparison_eligible": not partial,
    }


def series(sensor: str, *records: dict, definition: str = "utc_iso_week") -> dict:
    return {"sensor": sensor, "policy_id": "own_support_eligible", "week_definition": definition,
            "records": list(records)}


def accepts(data: dict) -> bool:
    try:
        WeeklyCalendarSeries.model_validate_json(json.dumps(data))
    except ValidationError:
        return False
    return True


# ISO 8601 identities, hard-coded (Mon..Sun, UTC), independent of the contract code.
ISO_WEEKS = [
    (date(2019, 12, 23), date(2019, 12, 29), 2019, 52),
    (date(2019, 12, 30), date(2020, 1, 5), 2020, 1),   # ISO year differs from calendar year of start
    (date(2020, 12, 28), date(2021, 1, 3), 2020, 53),  # 2020 has 53 ISO weeks
    (date(2021, 1, 4), date(2021, 1, 10), 2021, 1),
    (date(2021, 12, 27), date(2022, 1, 2), 2021, 52),
    (date(2022, 1, 3), date(2022, 1, 9), 2022, 1),
    (date(2026, 12, 28), date(2027, 1, 3), 2026, 53),  # 2026 has 53 ISO weeks
]


# ------------------------------------------------------------------ ACTIVE: ISO identity


@pytest.mark.parametrize("start,end,iso_year,iso_week", ISO_WEEKS)
def test_year_boundary_weeks_reject_calendar_year_or_shifted_labels(start, end, iso_year, iso_week) -> None:
    wrong_labels = {
        (start.year, iso_week),            # calendar year of the Monday instead of the ISO year
        (end.year, iso_week),              # calendar year of the Sunday
        (iso_year, iso_week + 1),
        (iso_year, max(1, iso_week - 1)),
        (iso_year + 1, iso_week),
        (iso_year - 1, iso_week),
    } - {(iso_year, iso_week)}
    for year, number in sorted(wrong_labels):
        if not 1 <= number <= 53:
            continue
        data = series("MODIS_Aqua", week("MODIS_Aqua", start, end, year, number))
        assert not accepts(data), (start, year, number)


@pytest.mark.parametrize("start,end,iso_year,iso_week", [w for w in ISO_WEEKS if w[2] in (2019, 2022, 2026)])
def test_year_boundary_weeks_outside_sealed_window_accept_correct_iso_identity(
    start, end, iso_year, iso_week
) -> None:
    assert accepts(series("MODIS_Aqua", week("MODIS_Aqua", start, end, iso_year, iso_week)))


@pytest.mark.parametrize("year,monday", [(2019, date(2019, 12, 23)), (2021, date(2021, 12, 27)),
                                         (2022, date(2022, 12, 26)), (2023, date(2023, 12, 25))])
def test_week_53_identity_rejected_in_52_week_iso_years(year: int, monday: date) -> None:
    sunday = date.fromordinal(monday.toordinal() + 6)
    assert accepts(series("MODIS_Aqua", week("MODIS_Aqua", monday, sunday, year, 52)))
    assert not accepts(series("MODIS_Aqua", week("MODIS_Aqua", monday, sunday, year, 53)))


def test_week_53_identity_accepted_in_53_week_iso_year_outside_sealed_window() -> None:
    start, end = date(2026, 12, 28), date(2027, 1, 3)
    assert accepts(series("MODIS_Aqua", week("MODIS_Aqua", start, end, 2026, 53)))
    assert not accepts(series("MODIS_Aqua", week("MODIS_Aqua", start, end, 2026, 52)))


@pytest.mark.parametrize("start,end", [
    (date(2019, 12, 31), date(2020, 1, 6)),   # Tuesday..Monday
    (date(2019, 12, 29), date(2020, 1, 4)),   # Sunday..Saturday
    (date(2020, 12, 30), date(2021, 1, 5)),
])
def test_non_iso_seven_day_bins_rejected_when_series_declares_iso_weeks(start, end) -> None:
    assert not accepts(series("MODIS_Aqua", week("MODIS_Aqua", start, end, start.year, 1)))


def test_overlapping_year_boundary_weeks_rejected() -> None:
    a = week("MODIS_Aqua", date(2021, 12, 27), date(2022, 1, 2), 2021, 52)
    b = week("MODIS_Aqua", date(2022, 1, 3), date(2022, 1, 9), 2022, 1)
    assert accepts(series("MODIS_Aqua", a, b))
    shifted = week("MODIS_Aqua", date(2022, 1, 2), date(2022, 1, 8), 2022, 1)
    assert not accepts(series("MODIS_Aqua", a, shifted))


# --------------------------------------------------------------- ACTIVE: S-NPP cutoff week


def test_snpp_cutoff_week_is_partial_and_neighbours_behave_as_boundaries() -> None:
    complete = week("VIIRS_SNPP", date(2026, 10, 26), date(2026, 11, 1), 2026, 44)
    cutoff = week("VIIRS_SNPP", date(2026, 11, 2), date(2026, 11, 8), 2026, 45, partial_reason=SNPP_REASON)
    after = week("VIIRS_SNPP", date(2026, 11, 9), date(2026, 11, 15), 2026, 46, partial_reason=SNPP_REASON)
    assert accepts(series("VIIRS_SNPP", complete))
    assert accepts(series("VIIRS_SNPP", complete, cutoff))
    assert not accepts(series("VIIRS_SNPP", after))  # starts after the 15:40Z cessation
    complete_cutoff = {**cutoff, "is_partial_period": False, "partial_period_reason": None,
                       "comparison_eligible": True, "critical_status": "not_critical",
                       "unusual_status": "not_unusual"}
    assert not accepts(series("VIIRS_SNPP", complete_cutoff))


def test_snpp_cutoff_week_needs_null_labels_not_sentinel_or_decisions() -> None:
    base = week("VIIRS_SNPP", date(2026, 11, 2), date(2026, 11, 8), 2026, 45, partial_reason=SNPP_REASON)
    assert accepts(series("VIIRS_SNPP", base))
    for field in ("critical_status", "unusual_status"):
        for bad in ("not_applicable", "critical", "not_critical", "unusual", "not_unusual",
                    "insufficient_baseline"):
            assert not accepts(series("VIIRS_SNPP", {**base, field: bad})), (field, bad)
    assert not accepts(series("VIIRS_SNPP", {**base, "comparison_eligible": True}))


def test_snpp_cutoff_status_uses_dates_only_with_cutoff_day_inside_a_partial_period() -> None:
    assert snpp_period_status(date(2026, 11, 1), date(2026, 11, 1)) == "complete"
    assert snpp_period_status(date(2026, 11, 2), date(2026, 11, 2)) == "partial"
    assert snpp_period_status(date(2026, 11, 3), date(2026, 11, 3)) == "after_record"


def test_other_sensors_on_cutoff_dates_are_not_partial() -> None:
    aqua = week("MODIS_Aqua", date(2026, 11, 2), date(2026, 11, 8), 2026, 45)
    assert accepts(series("MODIS_Aqua", aqua))
    aqua_partial = week("MODIS_Aqua", date(2026, 11, 2), date(2026, 11, 8), 2026, 45, partial_reason=SNPP_REASON)
    assert not accepts(series("MODIS_Aqua", aqua_partial))


# ------------------------------------------------------- ACTIVE: D <= O (confirmed by P2)


@pytest.mark.parametrize("d,o,ok", [(100.0, 100.0, True), (0.0, 100.0, True), (100.000001, 100.0, False),
                                    (1.0, 0.0, False)])
def test_d_not_greater_than_o_at_the_boundary(d: float, o: float, ok: bool) -> None:
    rec = week("MODIS_Aqua", date(2022, 1, 3), date(2022, 1, 9), 2022, 1, d=d, o=o)
    assert accepts(series("MODIS_Aqua", rec)) is ok


# --------------------------------------------- ACTIVE: weeks wholly outside the sealed window


@pytest.mark.parametrize("sensor", ["MODIS_Aqua", "VIIRS_SNPP"])
@pytest.mark.parametrize("start,end,year,number", [
    (date(2019, 12, 23), date(2019, 12, 29), 2019, 52),  # ends the day before the window
    (date(2022, 1, 3), date(2022, 1, 9), 2022, 1),       # starts two days after the window
])
def test_weeks_wholly_outside_sealed_window_stay_complete_and_eligible(sensor, start, end, year, number) -> None:
    assert end < SEALED_START or start > SEALED_END
    assert accepts(series(sensor, week(sensor, start, end, year, number)))


# -------------------------------------------- PENDING: sealed-window crossing weeks (strict xfail)

CROSSING = [
    pytest.param(date(2019, 12, 30), date(2020, 1, 5), 2020, 1, id="crosses-into-2020-01-01"),
    pytest.param(date(2021, 12, 27), date(2022, 1, 2), 2021, 52, id="crosses-out-after-2021-12-31"),
]


def test_crossing_weeks_straddle_a_sealed_edge_by_calendar_fact() -> None:
    for start, end, *_ in (c.values for c in CROSSING):
        assert (start < SEALED_START <= end) or (start <= SEALED_END < end)


@PENDING
@pytest.mark.parametrize("sensor", ["MODIS_Aqua", "VIIRS_SNPP"])
@pytest.mark.parametrize("start,end,year,number", CROSSING)
def test_pending_crossing_week_is_representable_as_partial_with_null_labels(sensor, start, end, year, number) -> None:
    rec = week(sensor, start, end, year, number, partial_reason=PROPOSED_SEALED_REASON)
    WeeklyCalendarSeries.model_validate_json(json.dumps(series(sensor, rec)))


@PENDING
@pytest.mark.parametrize("sensor", ["MODIS_Aqua", "VIIRS_SNPP"])
@pytest.mark.parametrize("start,end,year,number", CROSSING)
def test_pending_crossing_week_cannot_be_complete_eligible_or_labelled(sensor, start, end, year, number) -> None:
    complete = week(sensor, start, end, year, number)
    assert not accepts(series(sensor, complete)), "complete + eligible must be rejected"


@PENDING
@pytest.mark.parametrize("start,end,year,number", CROSSING)
def test_pending_crossing_week_rejects_decisions_sentinel_and_eligibility(start, end, year, number) -> None:
    base = week("MODIS_Aqua", start, end, year, number, partial_reason=PROPOSED_SEALED_REASON)
    assert accepts(series("MODIS_Aqua", base))  # fails first today (reason unknown), pending the rule
    for field in ("critical_status", "unusual_status"):
        for bad in ("not_applicable", "not_critical", "not_unusual", "insufficient_baseline"):
            assert not accepts(series("MODIS_Aqua", {**base, field: bad}))
    assert not accepts(series("MODIS_Aqua", {**base, "comparison_eligible": True}))


@PENDING
def test_pending_sealed_status_is_a_function_of_dates_only() -> None:
    """Period status must be computable without opening any day inside the sealed window."""
    from contracts.schemas.calendar import sealed_window_period_status  # proposed helper name

    assert list(inspect.signature(sealed_window_period_status).parameters) == ["start", "end_inclusive"]
    assert sealed_window_period_status(date(2019, 12, 23), date(2019, 12, 29)) == "outside"
    assert sealed_window_period_status(date(2019, 12, 30), date(2020, 1, 5)) == "partial"
    assert sealed_window_period_status(date(2021, 12, 27), date(2022, 1, 2)) == "partial"
    assert sealed_window_period_status(date(2022, 1, 3), date(2022, 1, 9)) == "outside"


@PENDING
def test_pending_sealed_reason_and_snpp_reason_are_distinct_and_both_partial() -> None:
    sealed = week("MODIS_Aqua", date(2019, 12, 30), date(2020, 1, 5), 2020, 1, partial_reason=PROPOSED_SEALED_REASON)
    snpp = week("VIIRS_SNPP", date(2026, 11, 2), date(2026, 11, 8), 2026, 45, partial_reason=SNPP_REASON)
    assert accepts(series("MODIS_Aqua", sealed))
    assert accepts(series("VIIRS_SNPP", snpp))
    # A sealed reason must not be usable to mask the S-NPP cutoff, and vice versa.
    assert not accepts(series("VIIRS_SNPP", {**snpp, "partial_period_reason": PROPOSED_SEALED_REASON}))
    assert not accepts(series("MODIS_Aqua", {**sealed, "partial_period_reason": SNPP_REASON}))


# ------------------------------------------- GUARDS: unregistered values stay configuration


def test_unregistered_values_are_not_schema_defaults() -> None:
    from contracts.schemas import calendar as calendar_module
    from contracts.schemas.calendar import CalendarArtifact

    assert WeeklyCalendarSeries.model_fields["week_definition"].is_required()
    assert "week_definition" not in CalendarArtifact.model_fields
    source = Path(calendar_module.__file__).read_text(encoding="utf-8")
    for token in (CONFIG["sealed_window"]["start"], CONFIG["sealed_window"]["end"], PROPOSED_SEALED_REASON):
        assert token not in source, f"{token} is hard-coded in the schema before registration"


def test_registration_entries_cannot_claim_frozen_without_date_and_reference() -> None:
    expected = {"week_definition", "sealed_window", "sealed_partial_reason", "week_53_rule"}
    assert expected <= set(CONFIG)
    for name in expected:
        entry = CONFIG[name]
        assert {"registered", "decision_date", "reference"} <= set(entry), name
        if entry["registered"]:
            assert entry["decision_date"] and entry["reference"], f"{name}: registered without date/reference"
            date.fromisoformat(entry["decision_date"])
        else:
            assert entry["decision_date"] is None and entry["reference"] is None, name


def test_week_53_rule_has_no_value_until_registered() -> None:
    entry = CONFIG["week_53_rule"]
    assert entry["registered"] is False and entry["value"] is None


def test_week_definition_is_declared_per_series_not_inferred() -> None:
    data = series("MODIS_Aqua", week("MODIS_Aqua", date(2022, 1, 3), date(2022, 1, 9), 2022, 1))
    del data["week_definition"]
    assert not accepts(data)
