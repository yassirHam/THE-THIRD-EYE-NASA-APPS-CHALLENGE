"""Monthly and weekly same-sensor calendar contracts."""

from __future__ import annotations

import math
from datetime import date, datetime, time, timedelta, timezone
from typing import Literal, get_args

from pydantic import Field, model_validator

from .common import ArtifactIdentity, SensorType, StrictContractModel

ObservationAvailability = Literal["available", "unavailable"]
UnavailableReason = Literal[
    "zero_usable_support",
    "source_not_available",
    "incomplete_footprint",
    "qa_unusable",
    # P2 r9 Q5: a period wholly outside an active sensor's record (for example VIIRS before its
    # declared record start) is represented as unavailable, not rejected.
    "sensor_not_operating",
]
BaselineLabelStatus = Literal[
    "unusual",
    "not_unusual",
    "critical",
    "not_critical",
    "insufficient_baseline",
    "not_applicable",
]
BaselineAvailability = Literal["available", "insufficient_baseline", "unavailable"]
WeekDefinition = Literal["utc_iso_week", "fixed_7_day_bins"]
# PROPOSED sealed-boundary reason: representation under P1/P2 review, not yet registered.
SEALED_BOUNDARY_REASON = "crosses_sealed_evaluation_boundary"
SNPP_CESSATION_REASON = "snpp_record_ended_2026_11_02"
# P2 r8 (handoff 6201f21): periods straddling a sensor's declared record start or end.
SENSOR_RECORD_BOUNDARY_REASON = "outside_sensor_record"
# P2 r9 required change 1: periods inside the record with missing days/tiles, or with
# processed coverage below 100%, are partial too. Boundary reasons take precedence as the
# primary reason; every applicable P2 reason is listed in coverage_reasons.
MISSING_DAYS_REASON = "missing_days_or_tiles"
LOW_COVERAGE_REASON = "low_processed_coverage"
PartialReason = Literal[
    "snpp_record_ended_2026_11_02",
    "crosses_sealed_evaluation_boundary",
    "outside_sensor_record",
    "missing_days_or_tiles",
    "low_processed_coverage",
]
# Boundaries whose dates are artifact data, checked at artifact level.
ARTIFACT_BOUNDARY_REASONS = {"crosses_sealed_evaluation_boundary", "outside_sensor_record"}
COVERAGE_GAP_REASONS = {MISSING_DAYS_REASON, LOW_COVERAGE_REASON}
# Every partial reason that is not the S-NPP cessation (checked at artifact level).
NON_SNPP_PARTIAL_REASONS = ARTIFACT_BOUNDARY_REASONS | COVERAGE_GAP_REASONS

# P2 r9 per-sensor, per-period coverage vocabulary (handoff b18ed3e, r9-P2.md section 1/5).
CoverageState = Literal["complete", "partial", "unavailable"]
CoverageReason = Literal[
    "period_clipped",
    "sensor_not_operating",
    "partition_boundary",
    "missing_days_or_tiles",
    "low_processed_coverage",
    "no_file",
]
# Explicit mapping from contract partial reasons to P2 coverage reasons (P2 r9 required change 3).
PARTIAL_REASON_TO_P2: dict[str, str] = {
    "outside_sensor_record": "period_clipped",
    "snpp_record_ended_2026_11_02": "period_clipped",
    "crosses_sealed_evaluation_boundary": "partition_boundary",
    "missing_days_or_tiles": "missing_days_or_tiles",
    "low_processed_coverage": "low_processed_coverage",
}
# P2 reasons that mean "no day of this period has a file".
NO_DATA_REASONS = {"no_file", "sensor_not_operating"}
# Sensors that form a MODIS/VIIRS pair in the current phase.
PAIRED_SENSOR = {"MODIS_Aqua": "VIIRS_SNPP", "VIIRS_SNPP": "MODIS_Aqua"}
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


def has_iso_week_53(iso_year: int) -> bool:
    # Dec 28 always falls in the last ISO week of its ISO year.
    return date(iso_year, 12, 28).isocalendar()[1] == 53


def days_outside_window(start: date, end_inclusive: date, window_start: date, window_end: date) -> int:
    """Number of UTC days of [start, end_inclusive] that lie outside the sealed window (dates only)."""
    total = (end_inclusive - start).days + 1
    overlap_start = max(start, window_start)
    overlap_end = min(end_inclusive, window_end)
    inside = max(0, (overlap_end - overlap_start).days + 1)
    return total - inside


def days_within(start: date, end_inclusive: date, range_start: date, range_end: date) -> int:
    """Number of UTC days of [start, end_inclusive] inside [range_start, range_end] (dates only)."""
    return (end_inclusive - start).days + 1 - days_outside_window(start, end_inclusive, range_start, range_end)


def year_bounds(year: int) -> tuple[date, date]:
    return date(year, 1, 1), date(year, 12, 31)


class SensorCoverage(StrictContractModel):
    """Declared record coverage of one sensor for this artifact (data, not a schema default).

    active: the artifact's source collection and record dates for this sensor.
    reserved_inactive: the sensor exists in the vocabulary but has no data in this phase.
    """

    sensor: SensorType
    status: Literal["active", "reserved_inactive"]
    collection_id: str | None = None
    record_start: date | None = None
    record_end: date | None = None
    scope_ref: str | None = None

    @model_validator(mode="after")
    def validate_coverage(self) -> "SensorCoverage":
        values = (self.collection_id, self.record_start, self.record_end, self.scope_ref)
        if self.status == "active":
            if any(v is None for v in values) or not self.collection_id or not self.scope_ref:
                raise ValueError(f"{self.sensor}: active coverage needs collection, record dates and scope_ref")
            if self.record_end < self.record_start:  # type: ignore[operator]
                raise ValueError(f"{self.sensor}: record_end precedes record_start")
            if self.sensor == "VIIRS_SNPP" and self.record_end > SNPP_LAST_RECORD_DATE:  # type: ignore[operator]
                raise ValueError("VIIRS_SNPP coverage cannot extend past the 2026-11-02 cessation")
        elif any(v is not None for v in values):
            raise ValueError(f"{self.sensor}: reserved_inactive coverage cannot carry dates or a collection")
        return self


class AnnualCoverage(StrictContractModel):
    """Per-sensor file coverage of one calendar year (UTC)."""

    sensor: SensorType
    year: int = Field(ge=2000, le=2100)
    days_in_period: int = Field(ge=365, le=366)
    days_with_file: int = Field(ge=0)
    is_partial_period: bool
    partial_period_reason: Literal["outside_sensor_record", "snpp_record_ended_2026_11_02"] | None

    @model_validator(mode="after")
    def validate_year(self) -> "AnnualCoverage":
        start, end = year_bounds(self.year)
        if self.days_in_period != (end - start).days + 1:
            raise ValueError(f"{self.year}: days_in_period must equal the number of days in the year")
        if self.days_with_file > self.days_in_period:
            raise ValueError(f"{self.year}: days_with_file cannot exceed days_in_period")
        if self.is_partial_period != (self.partial_period_reason is not None):
            raise ValueError(f"{self.year}: a partial year needs a reason, and only a partial year has one")
        return self


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
    """Footprint coverage for this artifact's geometry (P2 r9 Q3 rule, handoff b18ed3e).

    - complete: P2 documented, from cell-level evidence, that the whole footprint is covered.
    - partial: P2 documented, from cell-level evidence, a coverage fraction below 1.
    - unverified: no P2 certification exists.
    footprint_evidence records what P2's evidence is: cell_level (per-cell processed vs
    expected cell-days), day_level (a file was present per day, as in the current Earth Engine
    monthly aggregates) or none. Day-level evidence and availability == "available" never
    certify a complete footprint.
    """

    geometry_id: str = Field(min_length=1)
    status: Literal["complete", "partial", "unverified"]
    footprint_evidence: Literal["cell_level", "day_level", "none"]
    certification_ref: str | None = None
    certified_at: datetime | None = None
    coverage_fraction: float | None = Field(default=None, gt=0.0, lt=1.0)

    @model_validator(mode="after")
    def validate_certification(self) -> "FootprintCertification":
        _utc_aware(self.certified_at, "certified_at")
        documented = bool(self.certification_ref) and self.certified_at is not None
        if self.status in ("complete", "partial"):
            if not documented:
                raise ValueError(f"a {self.status} footprint requires P2's documented reference and UTC timestamp")
            if self.footprint_evidence != "cell_level":
                raise ValueError(f"a {self.status} footprint requires cell-level evidence; day-level file "
                                 "presence or available data never certify footprint coverage")
        elif self.certification_ref is not None or self.certified_at is not None:
            raise ValueError("an unverified footprint cannot carry a certification reference or timestamp")
        if self.status == "partial" and self.coverage_fraction is None:
            raise ValueError("a partial footprint requires its documented coverage fraction")
        if self.status != "partial" and self.coverage_fraction is not None:
            raise ValueError("only a partial footprint carries a coverage fraction")
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


def _check_file_days(record: "MonthRecord | WeekRecord", period_days: int, label: str) -> None:
    if record.days_in_period != period_days:
        raise ValueError(f"{label}: days_in_period must be {period_days}")
    if record.days_with_file > record.days_in_period:
        raise ValueError(f"{label}: days_with_file cannot exceed days_in_period")
    if record.days_with_file == 0 and record.availability == "available":
        raise ValueError(f"{label}: an observation with no source-file days cannot be available")
    if record.comparison_eligible and record.days_with_file != record.days_in_period:
        raise ValueError(f"{label}: comparison-eligible periods need a file for every day")
    if record.paired_comparison_eligible and not record.comparison_eligible:
        raise ValueError(f"{label}: paired comparison requires the period itself to be comparison-eligible")
    if record.included_day_count is not None and record.days_with_file > record.included_day_count:
        raise ValueError(f"{label}: a sealed-boundary partial cannot use files beyond its permitted days")
    _check_coverage(record, label)


def _check_coverage(record: "MonthRecord | WeekRecord", label: str) -> None:
    """Record-level consistency of the P2 coverage state and reasons (P2 r9).

    The reasons that depend on the sensor record and the sealed window are checked again at
    artifact level (CalendarArtifact._validate_coverage_reasons).
    """
    reasons = set(record.coverage_reasons)
    if len(reasons) != len(record.coverage_reasons):
        raise ValueError(f"{label}: coverage reasons must be unique")
    if record.days_with_file == 0:
        expected_state = "unavailable"
    elif record.is_partial_period:
        expected_state = "partial"
    else:
        expected_state = "complete"
    if record.coverage_state != expected_state:
        raise ValueError(f"{label}: coverage_state must be {expected_state} for these file days and partial flags")
    if record.coverage_state == "complete" and reasons:
        raise ValueError(f"{label}: a complete period carries no coverage reasons")
    if record.coverage_state != "complete" and not reasons:
        raise ValueError(f"{label}: a {record.coverage_state} period needs at least one P2 coverage reason")
    if record.days_with_file == 0:
        if record.unavailable_reason not in ("source_not_available", "sensor_not_operating"):
            raise ValueError(f"{label}: a period with no file days is unavailable as source_not_available "
                             "(no_file) or sensor_not_operating, never a zero or a QA state")
    if record.partial_period_reason is not None:
        mapped = PARTIAL_REASON_TO_P2[record.partial_period_reason]
        if mapped not in reasons:
            raise ValueError(f"{label}: partial reason {record.partial_period_reason} must list P2 reason {mapped}")
    if (reasons & COVERAGE_GAP_REASONS) and record.days_with_file > 0 and not record.is_partial_period:
        raise ValueError(f"{label}: missing days/tiles or low processed coverage make the period partial")
    low = record.processed_coverage is not None and record.processed_coverage < 1.0
    if low != (LOW_COVERAGE_REASON in reasons):
        # C_MIN is unregistered (P2 proposes 0.99): until it is, any shortfall below 1.0 is low.
        raise ValueError(f"{label}: low_processed_coverage is listed exactly when processed coverage < 1.0")
    if ("sensor_not_operating" in reasons) != (record.unavailable_reason == "sensor_not_operating"):
        raise ValueError(f"{label}: sensor_not_operating coverage and unavailable reason must agree")
    if "no_file" in reasons and record.unavailable_reason != "source_not_available":
        raise ValueError(f"{label}: no_file coverage requires unavailable reason source_not_available")
    if record.comparison_eligible and record.coverage_state != "complete":
        raise ValueError(f"{label}: only a complete-coverage period can be comparison-eligible")
    if record.unavailable_reason == "sensor_not_operating":
        labels = [getattr(record, "unusual_status", None), getattr(record, "critical_status", None)]
        if any(v is not None for v in labels) or record.is_partial_period:
            raise ValueError(f"{label}: a period outside the sensor record carries null labels and is not partial")


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
    # Sealed-boundary partials only: number of permitted (outside-window) UTC days used.
    included_day_count: int | None = Field(default=None, ge=1)
    # P2 r8: per-sensor file coverage of this period (required, explicit).
    days_in_period: int = Field(ge=28, le=31)
    days_with_file: int = Field(ge=0)
    # P2 r8: eligible for MODIS/VIIRS paired comparison only when both sensors are complete.
    paired_comparison_eligible: bool
    # P2 r9: per-sensor coverage state and every applicable P2 reason (required, explicit).
    coverage_state: CoverageState
    coverage_reasons: list[CoverageReason]
    # Processed footprint cell-days / (footprint cells x days with file), when P2 supplies it.
    processed_coverage: float | None = Field(default=None, ge=0.0, le=1.0)

    @model_validator(mode="after")
    def validate_month_labels(self) -> "MonthRecord":
        first, last = month_bounds(self.year, self.month)
        _check_file_days(self, (last - first).days + 1, f"{self.year}-{self.month:02d}")
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
        if status == "after_record" and self.unavailable_reason != "sensor_not_operating":
            raise ValueError("S-NPP records after the 2026-11-02 15:40 UTC cessation can only be unavailable "
                             "(sensor_not_operating)")
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
        elif self.partial_period_reason in NON_SNPP_PARTIAL_REASONS:
            if not self.is_partial_period or self.comparison_eligible:
                raise ValueError("a boundary or coverage-gap partial month must be partial and comparison-ineligible")
            if (
                self.unusual_status is not None
                or self.baseline_median is not None
                or self.baseline_p90 is not None
            ):
                raise ValueError(
                    "a boundary or coverage-gap partial month requires an explicit null unusual label and null baseline thresholds"
                )
        elif self.is_partial_period or self.partial_period_reason is not None:
            raise ValueError("partial-period flags are only valid for boundary periods or periods with coverage gaps")
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
    # Sealed-boundary partials only: number of permitted (outside-window) UTC days used.
    included_day_count: int | None = Field(default=None, ge=1, le=6)
    # P2 r8: per-sensor file coverage of this period (required, explicit).
    days_in_period: int = Field(ge=7, le=7)
    days_with_file: int = Field(ge=0)
    # P2 r8: eligible for MODIS/VIIRS paired comparison only when both sensors are complete.
    paired_comparison_eligible: bool
    # P2 r9: per-sensor coverage state and every applicable P2 reason (required, explicit).
    coverage_state: CoverageState
    coverage_reasons: list[CoverageReason]
    # Processed footprint cell-days / (footprint cells x days with file), when P2 supplies it.
    processed_coverage: float | None = Field(default=None, ge=0.0, le=1.0)

    @model_validator(mode="after")
    def validate_week(self) -> "WeekRecord":
        _check_file_days(self, (self.end_date - self.start_date).days + 1, f"{self.year}-W{self.week_number}")
        if self.availability == "unavailable" and self.comparison_eligible:
            raise ValueError("unavailable weeks cannot be comparison-eligible")
        if self.end_date < self.start_date:
            raise ValueError("week end date must not precede start date")
        if (self.end_date - self.start_date).days != 6:
            raise ValueError("weekly records must cover exactly seven inclusive UTC dates")
        status = "complete"
        if self.sensor == "VIIRS_SNPP":
            status = snpp_period_status(self.start_date, self.end_date)
        if status == "after_record" and self.unavailable_reason != "sensor_not_operating":
            raise ValueError("S-NPP weekly records after the 2026-11-02 15:40 UTC cessation can only be "
                             "unavailable (sensor_not_operating)")
        if status == "partial":
            if not self.is_partial_period or self.comparison_eligible:
                raise ValueError("a week straddling the S-NPP cutoff must be partial and comparison-ineligible")
            if self.partial_period_reason != SNPP_CESSATION_REASON:
                raise ValueError("a partial S-NPP week requires its cessation reason")
            if self.critical_status is not None or self.unusual_status is not None:
                raise ValueError("a partial week requires explicit null critical and unusual labels")
        elif self.partial_period_reason in NON_SNPP_PARTIAL_REASONS:
            if not self.is_partial_period or self.comparison_eligible:
                raise ValueError("a boundary or coverage-gap partial week must be partial and comparison-ineligible")
            if self.critical_status is not None or self.unusual_status is not None:
                raise ValueError("a boundary or coverage-gap partial week requires explicit null critical and unusual labels")
        elif self.is_partial_period or self.partial_period_reason is not None:
            raise ValueError("partial-period flags are only valid for boundary periods or periods with coverage gaps")
        elif status == "complete":
            if self.critical_status == INCOMPLETE_LABEL or self.unusual_status == INCOMPLETE_LABEL:
                raise ValueError("a complete week cannot use not_applicable sentinel")
            if self.availability == "available" and self.week_number != 53:
                # Week 53 labels are governed at artifact level (P1 decision: unranked for critical
                # weeks; unusual label withheld without an available week-53 baseline).
                if self.critical_status is None or self.unusual_status is None:
                    raise ValueError("an available complete week requires critical and unusual status decisions")
            elif self.availability == "unavailable":
                if self.unusual_status in {"unusual", "not_unusual"}:
                    raise ValueError("an unusual-week decision requires an available observation")
                if self.critical_status in {"critical", "not_critical"}:
                    raise ValueError("a critical-week decision requires an available observation")
        return self


class BaselineYearExclusion(StrictContractModel):
    """A year inside the registered baseline span that is not used, with the reason.

    Every year from reference_start_year to reference_end_year is either an eligible prior
    year or listed here, so a baseline can never be shortened silently.
    - sealed_evaluation_window: the year overlaps the declared sealed window (P5 d0b8c90).
    - partial_record_year: the year straddles the sensor's record start or end.
    - required_year_invalid: a required year lacks data or support (P2 r9 required change 2);
      the baseline is then unavailable, never shortened, and no other year replaces it.
    """

    year: int = Field(ge=2000, le=2100)
    reason: Literal["sealed_evaluation_window", "partial_record_year", "required_year_invalid"]
    detail: str | None = None


class SeasonalBaselineInfo(StrictContractModel):
    sensor: SensorType
    policy_id: str = Field(min_length=1)
    status: Literal["available", "insufficient_baseline", "unavailable"]
    reference_start_year: int = Field(ge=2000, le=2100)
    reference_end_year: int = Field(ge=2000, le=2100)
    eligible_prior_years: list[int]
    # Required key; may be empty. Years of the span that are not eligible, each with a reason.
    excluded_years: list[BaselineYearExclusion]
    # Required key: set exactly when status is "unavailable".
    unavailable_reason: Literal["required_year_invalid"] | None
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
        excluded = [e.year for e in self.excluded_years]
        if len(set(excluded)) != len(excluded):
            raise ValueError("a baseline year can be excluded only once")
        span = set(range(self.reference_start_year, self.reference_end_year + 1))
        if set(self.eligible_prior_years) & set(excluded):
            raise ValueError("a baseline year cannot be both eligible and excluded")
        if set(self.eligible_prior_years) | set(excluded) != span:
            raise ValueError("every year of the registered baseline span must be eligible or excluded with a "
                             "reason; a baseline is never shortened silently")
        required_invalid = any(e.reason == "required_year_invalid" for e in self.excluded_years)
        if required_invalid != (self.status == "unavailable"):
            raise ValueError("a baseline is unavailable exactly when a required year is invalid")
        if (self.status == "unavailable") != (self.unavailable_reason is not None):
            raise ValueError("an unavailable baseline needs its reason, and only it has one")
        season_values = (
            self.normal_season_start_month,
            self.normal_season_end_month,
            self.peak_median_month,
        )
        if self.status == "available":
            if len(self.eligible_prior_years) < self.minimum_year_count or any(v is None for v in season_values):
                raise ValueError("available baseline requires minimum years and complete season fields")
        elif any(v is not None for v in season_values):
            raise ValueError("an insufficient or unavailable baseline cannot publish a normal season")
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


class Week53PriorObservation(StrictContractModel):
    """One prior ISO week-53 observation offered to a week-53 baseline (same series)."""

    iso_year: int = Field(ge=2000, le=2100)
    period_complete: bool
    support_ok: bool


class Week53Baseline(StrictContractModel):
    """Baseline for a target ISO week 53. Lives inside one series, so same sensor and policy."""

    target_year: int = Field(ge=2000, le=2100)
    status: Literal["available", "insufficient_baseline"]
    prior_observations: list[Week53PriorObservation]

    @model_validator(mode="after")
    def validate_baseline(self) -> "Week53Baseline":
        if not has_iso_week_53(self.target_year):
            raise ValueError(f"{self.target_year} has no ISO week 53")
        years = [p.iso_year for p in self.prior_observations]
        if len(years) != len(set(years)):
            raise ValueError("prior week-53 years must be unique")
        for year in years:
            if year >= self.target_year:
                raise ValueError("prior week-53 observations must precede the target year")
            if not has_iso_week_53(year):
                raise ValueError(f"{year} has no ISO week 53 and cannot be a prior week-53 observation")
        return self

    def eligible_count(self) -> int:
        return sum(1 for p in self.prior_observations if p.period_complete and p.support_ok)


class WeeklyCalendarSeries(StrictContractModel):
    sensor: SensorType
    policy_id: str = Field(min_length=1)
    week_definition: WeekDefinition
    records: list[WeekRecord] = Field(min_length=1)
    # Required key; may be empty. One entry per target ISO week 53 in this series.
    week_53_baselines: list[Week53Baseline]

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
    # P2 r8 item 3: every sensor's coverage is declared; NOAA-20/21 stay reserved_inactive in
    # the current phase. The S-NPP cutoff fields are inactive unless S-NPP data reach the cutoff.
    sensor_coverage: list[SensorCoverage]
    snpp_cutoff_status: Literal["active", "reserved_inactive"]
    annual_coverage: list[AnnualCoverage]

    @model_validator(mode="after")
    def validate_calendar(self) -> "CalendarArtifact":
        if self.snpp_delivery_end_at != SNPP_CESSATION_AT:
            raise ValueError("S-NPP cessation timestamp must be 2026-11-02T15:40:00Z")
        coverage = self._validate_coverage()
        self._validate_annual_coverage(coverage)
        self._validate_record_coverage(coverage)
        self._validate_pairing()
        for series in [*self.monthly_series, *self.weekly_series]:
            if series.policy_id != self.policy_id:
                raise ValueError("calendar series policy must match artifact identity")
        window = self.sealed_window
        if self.data_classification == "production":
            # P5 binding decision (handoff d0b8c90): sealed years stay out of baselines.
            # Exclusion is only enforceable against a declared window, so production must declare one.
            if window is None or window.registration_status != "registered":
                raise ValueError("production artifacts require a declared, registered sealed window")
        periods: list[tuple[str, date, date, str | None, int | None]] = []
        if window is not None:
            # P2 r11 (handoff 8f67011) section 3: a period lying entirely inside the sealed window is
            # never read or emitted. It is excluded from the artifact: no record at all, so it is
            # never shown as missing data, as unavailable/no_file or with partition_boundary.
            for label, rec in self._labelled_records():
                start, end = (month_bounds(rec.year, rec.month) if isinstance(rec, MonthRecord)
                              else (rec.start_date, rec.end_date))
                if sealed_window_period_status(start, end, window.start, window.end) == "inside":
                    raise ValueError(f"{label}: lies wholly inside the sealed window; such periods are "
                                     "excluded from artifacts, not represented")
        for m_series in self.monthly_series:
            for m in m_series.records:
                first, last = month_bounds(m.year, m.month)
                periods.append((f"{m.year}-{m.month:02d} month", first, last, m.partial_period_reason,
                                m.included_day_count))
        for w_series in self.weekly_series:
            for w in w_series.records:
                periods.append((f"{w.year}-W{w.week_number} week", w.start_date, w.end_date,
                                w.partial_period_reason, w.included_day_count))
        for label, start, end, reason, included in periods:
            if reason != SEALED_BOUNDARY_REASON and included is not None:
                raise ValueError(f"{label}: included_day_count is only valid on sealed-boundary partials")
            if window is None:
                if reason == SEALED_BOUNDARY_REASON:
                    raise ValueError(f"{label}: sealed-boundary partial without a declared sealed window")
                continue
            status = sealed_window_period_status(start, end, window.start, window.end)
            if status == "partial" and reason != SEALED_BOUNDARY_REASON:
                raise ValueError(f"{label}: period straddles the sealed window and must be sealed-boundary partial")
            if status != "partial" and reason == SEALED_BOUNDARY_REASON:
                raise ValueError(f"{label}: sealed-boundary reason on a period that does not straddle the window")
            if status == "partial":
                permitted = days_outside_window(start, end, window.start, window.end)
                if included != permitted:
                    raise ValueError(
                        f"{label}: sealed-boundary partial must use only its {permitted} permitted day(s); "
                        f"included_day_count={included}"
                    )

        # Baseline years must be declared, non-partial years of that sensor's record.
        declared = {(a.sensor, a.year): a for a in self.annual_coverage}
        for baseline in self.seasonal_baselines:
            for year in baseline.eligible_prior_years:
                entry = declared.get((baseline.sensor, year))
                if entry is None:
                    raise ValueError(f"baseline year {year} has no declared {baseline.sensor} annual coverage")
                if entry.is_partial_period:
                    raise ValueError(f"baseline year {year} is a partial {baseline.sensor} year and cannot be a prior year")
                if entry.days_with_file != entry.days_in_period:
                    # Until P1 registers a year-validity rule (P2 proposes >= 9 of 12 months kept and
                    # an O floor), a year with any missing file day cannot be used. It must be listed
                    # as required_year_invalid, which makes the baseline unavailable.
                    raise ValueError(f"baseline year {year} has missing {baseline.sensor} file days; list it as "
                                     "required_year_invalid instead of using or dropping it")
            for exclusion in baseline.excluded_years:
                entry = declared.get((baseline.sensor, exclusion.year))
                if exclusion.reason == "partial_record_year" and (entry is None or not entry.is_partial_period):
                    raise ValueError(f"baseline year {exclusion.year}: partial_record_year needs a declared "
                                     f"partial {baseline.sensor} year")
                if exclusion.reason == "sealed_evaluation_window":
                    if window is None or sealed_window_period_status(
                        date(exclusion.year, 1, 1), date(exclusion.year, 12, 31), window.start, window.end
                    ) == "outside":
                        raise ValueError(f"baseline year {exclusion.year}: sealed_evaluation_window exclusion "
                                         "needs a declared sealed window overlapping that year")

        self._validate_coverage_reasons(coverage, window)

        # Sealed years never feed later baselines.
        if window is not None:
            for baseline in self.seasonal_baselines:
                for year in baseline.eligible_prior_years:
                    if sealed_window_period_status(date(year, 1, 1), date(year, 12, 31), window.start, window.end) != "outside":
                        raise ValueError(f"baseline year {year} overlaps the sealed window and cannot be a prior year")

        # ISO week 53: decisions need a registered rule and enough complete, supported,
        # eligible prior week-53 observations from the same series (same sensor and policy).
        rule = self.week_53_rule
        rule_registered = rule is not None and rule.registration_status == "registered"
        minimum = rule.minimum_year_count if rule_registered else None
        decisions = {"critical", "not_critical", "unusual", "not_unusual"}
        for w_series in self.weekly_series:
            by_target: dict[int, Week53Baseline] = {}
            for baseline in w_series.week_53_baselines:
                if baseline.target_year in by_target:
                    raise ValueError(f"duplicate week-53 baseline for {baseline.target_year}")
                by_target[baseline.target_year] = baseline
                for prior in baseline.prior_observations:
                    if window is not None and sealed_window_period_status(
                        date(prior.iso_year, 12, 28), date(prior.iso_year, 12, 28), window.start, window.end
                    ) != "outside":
                        raise ValueError(f"prior week-53 year {prior.iso_year} lies in the sealed window")
                sufficient = minimum is not None and baseline.eligible_count() >= minimum
                if (baseline.status == "available") != sufficient:
                    raise ValueError(
                        f"{baseline.target_year}-W53 baseline status must be available only with a registered "
                        f"rule and at least the registered minimum of complete, supported prior observations"
                    )
            for w in w_series.records:
                if w.week_number != 53:
                    continue
                baseline = by_target.get(w.year)
                usable = baseline is not None and baseline.status == "available"
                # P1 decision 2026-11-14T23:19:58Z (handoff bb1bf4c): week-53 critical ranking is
                # OPEN, so week 53 is unranked and never carries a critical-week label.
                if w.critical_status is not None:
                    raise ValueError(f"{w.year}-W53: week 53 is unranked for critical weeks; critical_status must be null")
                # Same decision, rule B3: without an available week-53 baseline the unusual label
                # is withheld (null), never inferred from weeks 52 or 1.
                if not usable and w.unusual_status is not None:
                    raise ValueError(f"{w.year}-W53: insufficient week-53 baseline; the unusual label is withheld (null)")
                if usable and w.unusual_status not in decisions and w.availability == "available" \
                        and not w.is_partial_period:
                    raise ValueError(f"{w.year}-W53: an available week-53 baseline requires an unusual decision")

        # Whole-footprint completeness is conditional on documented certification.
        cert = self.footprint_certification
        if cert is not None and cert.geometry_id != self.geometry_id:
            raise ValueError("footprint certification must be for this artifact's geometry")
        any_eligible = any(r.comparison_eligible for s in self.monthly_series for r in s.records) or any(
            r.comparison_eligible for s in self.weekly_series for r in s.records
        )
        if any_eligible:
            # Fail closed for every artifact class: only a P2-certified complete footprint, backed
            # by cell-level evidence, supports comparison-eligible whole-area periods (P2 r9 Q3).
            if cert is None or cert.status != "complete":
                status = "missing" if cert is None else cert.status
                raise ValueError(f"comparison-eligible whole-area periods need a P2-certified complete "
                                 f"footprint; certification is {status}")
            if self.data_classification == "production" and "synthetic" in (cert.certification_ref or "").lower():
                raise ValueError("production artifacts cannot rely on a synthetic footprint certification")
        return self

    # ---------------------------------------------------------------- helpers

    def _validate_coverage_reasons(self, coverage: dict[str, SensorCoverage], window: SealedWindow | None) -> None:
        """Every P2 coverage reason is present exactly when the period's dates and files call for it."""
        for label, rec in self._labelled_records():
            cov = coverage[rec.sensor]
            if isinstance(rec, MonthRecord):
                start, end = month_bounds(rec.year, rec.month)
            else:
                start, end = rec.start_date, rec.end_date
            inside_record = days_within(start, end, cov.record_start, cov.record_end)  # type: ignore[arg-type]
            permitted = inside_record
            if window is not None and inside_record:
                rs = max(start, cov.record_start)  # type: ignore[type-var]
                re_ = min(end, cov.record_end)  # type: ignore[type-var]
                permitted = days_outside_window(rs, re_, window.start, window.end)
            expected: set[str] = set()
            if rec.partial_period_reason is not None:
                expected.add(PARTIAL_REASON_TO_P2[rec.partial_period_reason])
            if inside_record == 0:
                expected.add("sensor_not_operating")
            elif rec.days_with_file == 0 and permitted > 0:
                expected.add("no_file")
            elif 0 < rec.days_with_file < permitted:
                expected.add(MISSING_DAYS_REASON)
            if rec.processed_coverage is not None and rec.processed_coverage < 1.0:
                expected.add(LOW_COVERAGE_REASON)
            if set(rec.coverage_reasons) != expected:
                raise ValueError(f"{label}: coverage reasons must be {sorted(expected)}, got "
                                 f"{sorted(rec.coverage_reasons)}")
            boundary = rec.partial_period_reason in ARTIFACT_BOUNDARY_REASONS | {SNPP_CESSATION_REASON}
            if not boundary and rec.days_with_file > 0:
                gap = (MISSING_DAYS_REASON if MISSING_DAYS_REASON in expected
                       else LOW_COVERAGE_REASON if LOW_COVERAGE_REASON in expected else None)
                if rec.partial_period_reason != gap:
                    raise ValueError(f"{label}: a period with coverage gaps inside the record must be partial "
                                     f"({gap}); without gaps it is not partial")

    def _labelled_records(self):
        for m_series in self.monthly_series:
            for m in m_series.records:
                yield f"{m.year}-{m.month:02d} month", m
        for w_series in self.weekly_series:
            for w in w_series.records:
                yield f"{w.year}-W{w.week_number} week", w

    def _validate_coverage(self) -> dict[str, SensorCoverage]:
        coverage: dict[str, SensorCoverage] = {}
        for entry in self.sensor_coverage:
            if entry.sensor in coverage:
                raise ValueError(f"duplicate sensor coverage for {entry.sensor}")
            coverage[entry.sensor] = entry
        missing = set(get_args(SensorType)) - set(coverage)
        if missing:
            raise ValueError(f"sensor coverage must be declared for every sensor; missing {sorted(missing)}")
        snpp = coverage["VIIRS_SNPP"]
        reaches_cutoff = snpp.status == "active" and snpp.record_end >= SNPP_LAST_RECORD_DATE  # type: ignore[operator]
        expected = "active" if reaches_cutoff else "reserved_inactive"
        if self.snpp_cutoff_status != expected:
            raise ValueError(f"snpp_cutoff_status must be {expected} for the declared S-NPP coverage")
        return coverage

    @staticmethod
    def _boundary_reason(sensor: str, start: date, end: date) -> str:
        if sensor == "VIIRS_SNPP" and snpp_period_status(start, end) == "partial":
            return SNPP_CESSATION_REASON
        return SENSOR_RECORD_BOUNDARY_REASON

    def _validate_annual_coverage(self, coverage: dict[str, SensorCoverage]) -> None:
        seen: set[tuple[str, int]] = set()
        for entry in self.annual_coverage:
            key = (entry.sensor, entry.year)
            if key in seen:
                raise ValueError(f"duplicate annual coverage for {entry.sensor} {entry.year}")
            seen.add(key)
            cov = coverage[entry.sensor]
            if cov.status != "active":
                raise ValueError(f"{entry.sensor} is reserved_inactive and cannot declare annual coverage")
            start, end = year_bounds(entry.year)
            inside = days_within(start, end, cov.record_start, cov.record_end)  # type: ignore[arg-type]
            if inside == 0:
                raise ValueError(f"{entry.sensor} {entry.year} lies outside the declared record")
            if entry.days_with_file > inside:
                raise ValueError(f"{entry.sensor} {entry.year}: days_with_file exceeds days inside the record")
            straddles = inside < entry.days_in_period
            if straddles != entry.is_partial_period:
                raise ValueError(f"{entry.sensor} {entry.year}: partial exactly when the year straddles the record")
            if straddles and entry.partial_period_reason != self._boundary_reason(entry.sensor, start, end):
                raise ValueError(f"{entry.sensor} {entry.year}: wrong partial reason for its record boundary")

    def _validate_record_coverage(self, coverage: dict[str, SensorCoverage]) -> None:
        for label, rec in self._labelled_records():
            cov = coverage[rec.sensor]
            if cov.status != "active":
                raise ValueError(f"{label}: {rec.sensor} is reserved_inactive; its data do not exist in this phase")
            if isinstance(rec, MonthRecord):
                start, end = month_bounds(rec.year, rec.month)
            else:
                start, end = rec.start_date, rec.end_date
            inside = days_within(start, end, cov.record_start, cov.record_end)  # type: ignore[arg-type]
            if inside == 0:
                # P2 r9 Q5: a period wholly outside an active record is unavailable, not rejected.
                if rec.unavailable_reason != "sensor_not_operating" or rec.days_with_file != 0:
                    raise ValueError(f"{label}: lies outside the declared {rec.sensor} record and can only be "
                                     "unavailable (sensor_not_operating) with no file days")
                continue
            if rec.unavailable_reason == "sensor_not_operating":
                raise ValueError(f"{label}: sensor_not_operating on a period inside the {rec.sensor} record")
            if rec.days_with_file > inside:
                raise ValueError(f"{label}: days_with_file exceeds days inside the declared {rec.sensor} record")
            reason = rec.partial_period_reason
            if inside < rec.days_in_period:
                expected = self._boundary_reason(rec.sensor, start, end)
                if reason != expected:
                    raise ValueError(f"{label}: straddles the {rec.sensor} record boundary and must be partial ({expected})")
            elif reason == SENSOR_RECORD_BOUNDARY_REASON:
                raise ValueError(f"{label}: outside_sensor_record on a period wholly inside the record")

    def _validate_pairing(self) -> None:
        index: dict[tuple, MonthRecord | WeekRecord] = {}
        for m_series in self.monthly_series:
            for m in m_series.records:
                index[("month", m.sensor, m.year, m.month)] = m
        for w_series in self.weekly_series:
            for w in w_series.records:
                index[("week", w_series.week_definition, w.sensor, w.start_date)] = w
        for key, rec in index.items():
            if not rec.paired_comparison_eligible:
                continue
            other = PAIRED_SENSOR.get(rec.sensor)
            if other is None:
                raise ValueError(f"{rec.sensor} has no MODIS/VIIRS pair in the current phase")
            if key[0] == "month":
                twin = index.get(("month", other, key[2], key[3]))
            else:
                twin = index.get(("week", key[1], other, key[3]))
            if twin is None or not twin.paired_comparison_eligible:
                raise ValueError(
                    f"{rec.sensor} {key[-2:] if key[0] == 'month' else key[-1]}: paired comparison needs a complete, "
                    f"paired {other} record for the same period"
                )
