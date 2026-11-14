"""Monthly and weekly same-sensor calendar contracts."""

from __future__ import annotations

import math
from datetime import date, datetime, time, timedelta, timezone
from typing import Literal

from pydantic import Field, model_validator

from .common import ArtifactIdentity, SensorType, StrictContractModel

ObservationAvailability = Literal["available", "unavailable"]
UnavailableReason = Literal[
    "zero_usable_support",
    "source_not_available",
    "incomplete_footprint",
    "qa_unusable",
]
BaselineLabelStatus = Literal[
    "unusual",
    "not_unusual",
    "critical",
    "not_critical",
    "insufficient_baseline",
    "not_applicable",
]
BaselineAvailability = Literal["available", "insufficient_baseline"]
WeekDefinition = Literal["utc_iso_week", "fixed_7_day_bins"]
# PROPOSED sealed-boundary reason: representation under P1/P2 review, not yet registered.
SEALED_BOUNDARY_REASON = "crosses_sealed_evaluation_boundary"
SNPP_CESSATION_REASON = "snpp_record_ended_2026_11_02"
PartialReason = Literal["snpp_record_ended_2026_11_02", "crosses_sealed_evaluation_boundary"]
SNPP_CESSATION_AT = datetime(2026, 11, 2, 15, 40, tzinfo=timezone.utc)
SNPP_LAST_RECORD_DATE = date(2026, 11, 2)
# Incomplete periods carry explicit null labels. The "not_applicable" sentinel is
# rejected on every period; it remains in the label enums only for type stability.
INCOMPLETE_LABEL = "not_applicable"


def _utc_start(day: date) -> datetime:
    return datetime.combine(day, time.min, tzinfo=timezone.utc)


def snpp_period_status(start: date, end_inclusive: date) -> Literal["complete", "partial", "after_record"]:
    """Classify the UTC period [start 00:00, end_inclusive + 1 day 00:00) against the S-NPP cutoff."""
    period_start = _utc_start(start)
    period_end = _utc_start(end_inclusive + timedelta(days=1))
    if period_start >= SNPP_CESSATION_AT:
        return "after_record"
    if period_end > SNPP_CESSATION_AT:
        return "partial"
    return "complete"


def month_bounds(year: int, month: int) -> tuple[date, date]:
    first = date(year, month, 1)
    next_first = date(year + (month == 12), month % 12 + 1, 1)
    return first, next_first - timedelta(days=1)


def sealed_window_period_status(
    start: date, end_inclusive: date, window_start: date, window_end: date
) -> Literal["outside", "partial", "inside"]:
    """Classify a UTC period against a sealed window using period dates only.

    No observation is read: a period that straddles either edge is "partial" because
    part of it lies in the window, whatever the data inside it would show. The window
    comes from the artifact (configuration), never from a schema constant.
    """
    if end_inclusive < window_start or start > window_end:
        return "outside"
    if start >= window_start and end_inclusive <= window_end:
        return "inside"
    return "partial"


class SealedWindow(StrictContractModel):
    """Sealed evaluation window declared by the artifact, with its registration state."""

    start: date
    end: date
    registration_status: Literal["registered", "proposed_unregistered"]
    registration_ref: str | None = None
    decision_date: date | None = None

    @model_validator(mode="after")
    def validate_window(self) -> "SealedWindow":
        if self.end < self.start:
            raise ValueError("sealed window end must not precede start")
        registered = self.registration_status == "registered"
        has_proof = bool(self.registration_ref) and self.decision_date is not None
        if registered and not has_proof:
            raise ValueError("a registered sealed window requires registration_ref and decision_date")
        if not registered and (self.registration_ref is not None or self.decision_date is not None):
            raise ValueError("an unregistered sealed window cannot carry a registration reference or date")
        return self


def _utc_aware(value: datetime | None, name: str) -> None:
    if value is not None and (value.tzinfo is None or value.utcoffset() != timedelta(0)):
        raise ValueError(f"{name} must be an explicit UTC timestamp")


class Week53Rule(StrictContractModel):
    """Carrier for the ISO week-53 baseline minimum. It is configuration, never a default.

    While unregistered, the minimum is null: no value may be assumed or hard-coded.
    """

    registration_status: Literal["registered", "proposed_unregistered"]
    minimum_year_count: int | None = Field(default=None, ge=1)
    registration_ref: str | None = None
    decision_at: datetime | None = None

    @model_validator(mode="after")
    def validate_rule(self) -> "Week53Rule":
        _utc_aware(self.decision_at, "decision_at")
        proof = (self.minimum_year_count, self.registration_ref, self.decision_at)
        if self.registration_status == "registered":
            if any(v is None for v in proof) or not self.registration_ref:
                raise ValueError("a registered week-53 rule requires minimum, reference, and decision timestamp")
        elif any(v is not None for v in proof):
            raise ValueError("an unregistered week-53 rule cannot carry a minimum, reference, or timestamp")
        return self


class FootprintCertification(StrictContractModel):
    """Whole-footprint completeness, certified by P2's documentation (PROPOSED shape).

    Completeness is never inferred from availability == "available". Pending P2's Q3
    coverage rules; the field set below may change when those rules are frozen.
    """

    geometry_id: str = Field(min_length=1)
    status: Literal["certified_complete", "not_certified"]
    certification_ref: str | None = None
    certified_at: datetime | None = None

    @model_validator(mode="after")
    def validate_certification(self) -> "FootprintCertification":
        _utc_aware(self.certified_at, "certified_at")
        if self.status == "certified_complete":
            if not self.certification_ref or self.certified_at is None:
                raise ValueError("a footprint certification requires a documented reference and UTC timestamp")
        elif self.certification_ref is not None or self.certified_at is not None:
            raise ValueError("a not_certified footprint cannot carry a reference or timestamp")
        return self


class ObservationRecord(StrictContractModel):
    """D/O accounting that keeps four states apart.

    - available: O > 0, R = 1000*D/O (a valid 0.0 stays available).
    - zero_usable_support: observed O == 0 (and D == 0); R is null.
    - source_not_available / incomplete_footprint / qa_unusable: D, O and R are
      all null. Missing data is never converted to zero.
    """

    detected_fire_cell_days: float | None = Field(default=None, ge=0.0)
    usable_land_cell_days: float | None = Field(default=None, ge=0.0)
    fire_activity_index: float | None = Field(
        default=None,
        ge=0.0,
        description="R = 1000 * D / O; null unless O is positive.",
    )
    availability: ObservationAvailability
    unavailable_reason: UnavailableReason | None = None

    @model_validator(mode="after")
    def validate_observation_accounting(self) -> "ObservationRecord":
        d = self.detected_fire_cell_days
        o = self.usable_land_cell_days
        if self.availability == "available":
            if self.unavailable_reason is not None:
                raise ValueError("available observations cannot carry an unavailable reason")
            if d is None or o is None or o <= 0.0 or self.fire_activity_index is None:
                raise ValueError("available requires D, positive O, and R (a valid 0.0 is allowed)")
            if d > o:
                raise ValueError("D cannot exceed usable support O")
            expected = 1000.0 * d / o
            if not math.isclose(self.fire_activity_index, expected, rel_tol=1e-12, abs_tol=1e-12):
                raise ValueError("R must equal 1000 * D / O at full artifact precision")
            return self

        if self.unavailable_reason is None:
            raise ValueError("unavailable observations require a reason")
        if self.fire_activity_index is not None:
            raise ValueError("R must be null when the observation is unavailable")
        if self.unavailable_reason == "zero_usable_support":
            if o != 0.0 or d != 0.0:
                raise ValueError("zero_usable_support means observed O == 0 and D == 0")
        elif d is not None or o is not None:
            raise ValueError("missing source/footprint/QA data must keep D and O null, not zero")
        return self


class MonthRecord(ObservationRecord):
    sensor: SensorType
    year: int = Field(ge=2000, le=2100)
    month: int = Field(ge=1, le=12)
    baseline_median: float | None = Field(default=None, ge=0.0)
    baseline_p90: float | None = Field(default=None, ge=0.0)
    # Required key, nullable value: a partial month must carry an explicit JSON null.
    unusual_status: Literal["unusual", "not_unusual", "insufficient_baseline", "not_applicable"] | None
    is_partial_period: bool = False
    comparison_eligible: bool
    partial_period_reason: PartialReason | None = None

    @model_validator(mode="after")
    def validate_month_labels(self) -> "MonthRecord":
        if self.availability == "unavailable" and self.comparison_eligible:
            raise ValueError("unavailable months cannot be comparison-eligible")
        baseline_missing = self.baseline_median is None or self.baseline_p90 is None
        if self.unusual_status in {"unusual", "not_unusual"}:
            if baseline_missing or self.fire_activity_index is None:
                raise ValueError("an unusual-month decision requires baseline values and available R")
            above = self.fire_activity_index > self.baseline_p90  # type: ignore[operator]
            if above != (self.unusual_status == "unusual"):
                raise ValueError("unusual means R strictly above p90; ties are not unusual")
        elif self.unusual_status == "insufficient_baseline" and not baseline_missing:
            raise ValueError("insufficient baseline cannot carry baseline thresholds")
        status = "complete"
        if self.sensor == "VIIRS_SNPP":
            status = snpp_period_status(*month_bounds(self.year, self.month))
        if status == "after_record":
            raise ValueError("S-NPP records cannot start after the 2026-11-02 15:40 UTC cessation")
        if status == "partial":
            if not self.is_partial_period or self.comparison_eligible:
                raise ValueError("a month straddling the S-NPP cutoff must be partial and comparison-ineligible")
            if self.partial_period_reason != SNPP_CESSATION_REASON:
                raise ValueError("a partial S-NPP month requires its cessation reason")
            if (
                self.unusual_status is not None
                or self.baseline_median is not None
                or self.baseline_p90 is not None
            ):
                raise ValueError(
                    "a partial month requires an explicit null unusual label and null baseline thresholds"
                )
        elif self.partial_period_reason == SEALED_BOUNDARY_REASON:
            if not self.is_partial_period or self.comparison_eligible:
                raise ValueError("a sealed-boundary month must be partial and comparison-ineligible")
            if (
                self.unusual_status is not None
                or self.baseline_median is not None
                or self.baseline_p90 is not None
            ):
                raise ValueError(
                    "a sealed-boundary month requires an explicit null unusual label and null baseline thresholds"
                )
        elif self.is_partial_period or self.partial_period_reason is not None:
            raise ValueError("partial-period flags are only valid for periods straddling a registered boundary")
        elif status == "complete":
            if self.unusual_status == INCOMPLETE_LABEL:
                raise ValueError("a complete month cannot use not_applicable sentinel")
            if self.availability == "available" and self.unusual_status is None:
                raise ValueError("an available complete month requires an unusual-status decision")
            if self.availability == "unavailable" and self.unusual_status in {"unusual", "not_unusual"}:
                raise ValueError("an unusual-month decision requires an available observation")
        return self


class WeekRecord(ObservationRecord):
    sensor: SensorType
    year: int = Field(ge=2000, le=2100)
    week_number: int = Field(ge=1, le=53)
    start_date: date
    end_date: date
    # Required keys, nullable values: a partial week must carry explicit JSON nulls.
    critical_status: Literal["critical", "not_critical", "insufficient_baseline", "not_applicable"] | None
    unusual_status: Literal["unusual", "not_unusual", "insufficient_baseline", "not_applicable"] | None
    is_partial_period: bool = False
    partial_period_reason: PartialReason | None = None
    comparison_eligible: bool

    @model_validator(mode="after")
    def validate_week(self) -> "WeekRecord":
        if self.availability == "unavailable" and self.comparison_eligible:
            raise ValueError("unavailable weeks cannot be comparison-eligible")
        if self.end_date < self.start_date:
            raise ValueError("week end date must not precede start date")
        if (self.end_date - self.start_date).days != 6:
            raise ValueError("weekly records must cover exactly seven inclusive UTC dates")
        status = "complete"
        if self.sensor == "VIIRS_SNPP":
            status = snpp_period_status(self.start_date, self.end_date)
        if status == "after_record":
            raise ValueError("S-NPP weekly records cannot start after the 2026-11-02 15:40 UTC cessation")
        if status == "partial":
            if not self.is_partial_period or self.comparison_eligible:
                raise ValueError("a week straddling the S-NPP cutoff must be partial and comparison-ineligible")
            if self.partial_period_reason != SNPP_CESSATION_REASON:
                raise ValueError("a partial S-NPP week requires its cessation reason")
            if self.critical_status is not None or self.unusual_status is not None:
                raise ValueError("a partial week requires explicit null critical and unusual labels")
        elif self.partial_period_reason == SEALED_BOUNDARY_REASON:
            if not self.is_partial_period or self.comparison_eligible:
                raise ValueError("a sealed-boundary week must be partial and comparison-ineligible")
            if self.critical_status is not None or self.unusual_status is not None:
                raise ValueError("a sealed-boundary week requires explicit null critical and unusual labels")
        elif self.is_partial_period or self.partial_period_reason is not None:
            raise ValueError("partial-period flags are only valid for periods straddling a registered boundary")
        elif status == "complete":
            if self.critical_status == INCOMPLETE_LABEL or self.unusual_status == INCOMPLETE_LABEL:
                raise ValueError("a complete week cannot use not_applicable sentinel")
            if self.availability == "available":
                if self.critical_status is None or self.unusual_status is None:
                    raise ValueError("an available complete week requires critical and unusual status decisions")
            elif self.availability == "unavailable":
                if self.unusual_status in {"unusual", "not_unusual"}:
                    raise ValueError("an unusual-week decision requires an available observation")
                if self.critical_status in {"critical", "not_critical"}:
                    raise ValueError("a critical-week decision requires an available observation")
        return self


class SeasonalBaselineInfo(StrictContractModel):
    sensor: SensorType
    policy_id: str = Field(min_length=1)
    status: BaselineAvailability
    reference_start_year: int = Field(ge=2000, le=2100)
    reference_end_year: int = Field(ge=2000, le=2100)
    eligible_prior_years: list[int]
    minimum_year_count: int = Field(ge=1)
    normal_season_start_month: int | None = Field(default=None, ge=1, le=12)
    normal_season_end_month: int | None = Field(default=None, ge=1, le=12)
    peak_median_month: int | None = Field(default=None, ge=1, le=12)

    @model_validator(mode="after")
    def validate_baseline(self) -> "SeasonalBaselineInfo":
        if self.reference_end_year < self.reference_start_year:
            raise ValueError("baseline end year must not precede start year")
        if len(set(self.eligible_prior_years)) != len(self.eligible_prior_years):
            raise ValueError("eligible baseline years must be unique")
        season_values = (
            self.normal_season_start_month,
            self.normal_season_end_month,
            self.peak_median_month,
        )
        if self.status == "available":
            if len(self.eligible_prior_years) < self.minimum_year_count or any(v is None for v in season_values):
                raise ValueError("available baseline requires minimum years and complete season fields")
        elif any(v is not None for v in season_values):
            raise ValueError("insufficient baseline cannot publish a normal season")
        return self


class MonthlyCalendarSeries(StrictContractModel):
    sensor: SensorType
    policy_id: str = Field(min_length=1)
    records: list[MonthRecord] = Field(min_length=1)

    @model_validator(mode="after")
    def enforce_same_sensor_months(self) -> "MonthlyCalendarSeries":
        if any(record.sensor != self.sensor for record in self.records):
            raise ValueError("a monthly series must remain same-sensor")
        keys = [(record.year, record.month) for record in self.records]
        if len(keys) != len(set(keys)):
            raise ValueError("monthly series cannot contain duplicate periods")
        return self


class WeeklyCalendarSeries(StrictContractModel):
    sensor: SensorType
    policy_id: str = Field(min_length=1)
    week_definition: WeekDefinition
    records: list[WeekRecord] = Field(min_length=1)

    @model_validator(mode="after")
    def enforce_same_sensor_weeks(self) -> "WeeklyCalendarSeries":
        if any(record.sensor != self.sensor for record in self.records):
            raise ValueError("a weekly series must remain same-sensor")
        keys = [(record.year, record.week_number) for record in self.records]
        if len(keys) != len(set(keys)):
            raise ValueError("weekly series cannot contain duplicate periods")
        sorted_records = sorted(self.records, key=lambda r: (r.start_date, r.end_date))
        for i in range(len(sorted_records) - 1):
            if sorted_records[i].end_date >= sorted_records[i + 1].start_date:
                raise ValueError(
                    f"Weekly series records cannot overlap: {sorted_records[i].start_date}..{sorted_records[i].end_date} "
                    f"overlaps with {sorted_records[i + 1].start_date}..{sorted_records[i + 1].end_date}"
                )
        if self.week_definition == "utc_iso_week":
            for record in self.records:
                if record.start_date.weekday() != 0:
                    raise ValueError(
                        f"UTC ISO week start date must be a Monday (weekday 0), got {record.start_date.isoformat()} (weekday {record.start_date.weekday()})"
                    )
                if record.end_date.weekday() != 6:
                    raise ValueError(
                        f"UTC ISO week end date must be a Sunday (weekday 6), got {record.end_date.isoformat()} (weekday {record.end_date.weekday()})"
                    )
                iso_year, iso_week, _ = record.start_date.isocalendar()
                if record.year != iso_year or record.week_number != iso_week:
                    raise ValueError(
                        f"Record {record.year}-W{record.week_number} does not match "
                        f"ISO calendar ({iso_year}-W{iso_week}) for start date {record.start_date.isoformat()}"
                    )
        elif self.week_definition == "fixed_7_day_bins":
            for record in self.records:
                if record.week_number > 52:
                    raise ValueError(
                        f"Fixed 7-day bin week_number cannot exceed 52, got {record.week_number}"
                    )
                expected_start = date(record.year, 1, 1) + timedelta(days=(record.week_number - 1) * 7)
                if record.start_date != expected_start:
                    raise ValueError(
                        f"Fixed 7-day bin {record.year}-W{record.week_number} expected start date {expected_start.isoformat()}, "
                        f"got {record.start_date.isoformat()}"
                    )
                if record.end_date.year != record.year:
                    raise ValueError(
                        f"Fixed 7-day bin {record.year}-W{record.week_number} end date {record.end_date.isoformat()} cannot cross into next year"
                    )
        return self


class CalendarArtifact(ArtifactIdentity):
    region_name: str = Field(min_length=1)
    measurement_name: Literal["fire_activity_index"] = "fire_activity_index"
    measurement_unit: Literal["detected_fire_cell_days_per_1000_usable_land_cell_days"]
    snpp_delivery_end_at: datetime
    monthly_series: list[MonthlyCalendarSeries] = Field(min_length=1)
    weekly_series: list[WeeklyCalendarSeries] = Field(min_length=1)
    seasonal_baselines: list[SeasonalBaselineInfo] = Field(min_length=1)
    # Required key, nullable value. None means "no sealed window declared": the artifact
    # then carries no sealed-boundary partials. There is no schema default window.
    sealed_window: SealedWindow | None
    week_53_rule: Week53Rule | None
    footprint_certification: FootprintCertification | None

    @model_validator(mode="after")
    def validate_calendar(self) -> "CalendarArtifact":
        if self.snpp_delivery_end_at != SNPP_CESSATION_AT:
            raise ValueError("S-NPP cessation timestamp must be 2026-11-02T15:40:00Z")
        for series in [*self.monthly_series, *self.weekly_series]:
            if series.policy_id != self.policy_id:
                raise ValueError("calendar series policy must match artifact identity")
        window = self.sealed_window
        if self.data_classification == "production":
            # P5 binding decision (handoff d0b8c90): sealed years stay out of baselines.
            # Exclusion is only enforceable against a declared window, so production must declare one.
            if window is None or window.registration_status != "registered":
                raise ValueError("production artifacts require a declared, registered sealed window")
        periods: list[tuple[str, date, date, str | None]] = []
        for m_series in self.monthly_series:
            for m in m_series.records:
                first, last = month_bounds(m.year, m.month)
                periods.append((f"{m.year}-{m.month:02d} month", first, last, m.partial_period_reason))
        for w_series in self.weekly_series:
            for w in w_series.records:
                periods.append((f"{w.year}-W{w.week_number} week", w.start_date, w.end_date, w.partial_period_reason))
        for label, start, end, reason in periods:
            if window is None:
                if reason == SEALED_BOUNDARY_REASON:
                    raise ValueError(f"{label}: sealed-boundary partial without a declared sealed window")
                continue
            status = sealed_window_period_status(start, end, window.start, window.end)
            if status == "partial" and reason != SEALED_BOUNDARY_REASON:
                raise ValueError(f"{label}: period straddles the sealed window and must be sealed-boundary partial")
            if status != "partial" and reason == SEALED_BOUNDARY_REASON:
                raise ValueError(f"{label}: sealed-boundary reason on a period that does not straddle the window")

        # Sealed years never feed later baselines.
        if window is not None:
            for baseline in self.seasonal_baselines:
                for year in baseline.eligible_prior_years:
                    if sealed_window_period_status(date(year, 1, 1), date(year, 12, 31), window.start, window.end) != "outside":
                        raise ValueError(f"baseline year {year} overlaps the sealed window and cannot be a prior year")

        # ISO week 53 carries no baseline decision until its minimum is registered.
        week_53_registered = self.week_53_rule is not None and self.week_53_rule.registration_status == "registered"
        decisions = {"critical", "not_critical", "unusual", "not_unusual"}
        for w_series in self.weekly_series:
            for w in w_series.records:
                if w.week_number == 53 and not week_53_registered:
                    if w.critical_status in decisions or w.unusual_status in decisions:
                        raise ValueError(
                            f"{w.year}-W53: no baseline decision before the week-53 minimum is registered"
                        )

        # Whole-footprint completeness is conditional on documented certification.
        cert = self.footprint_certification
        if cert is not None and cert.geometry_id != self.geometry_id:
            raise ValueError("footprint certification must be for this artifact's geometry")
        any_eligible = any(r.comparison_eligible for s in self.monthly_series for r in s.records) or any(
            r.comparison_eligible for s in self.weekly_series for r in s.records
        )
        if any_eligible:
            if cert is not None and cert.status == "not_certified":
                raise ValueError("a not-certified footprint cannot support comparison-eligible periods")
            if self.data_classification == "production" and (cert is None or cert.status != "certified_complete"):
                raise ValueError("production comparison-eligible periods require a certified-complete footprint")
        return self

