"""Monthly and weekly same-sensor calendar contracts."""

from __future__ import annotations

import math
from datetime import date, datetime, timezone
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


class ObservationRecord(StrictContractModel):
    """D/O accounting with an explicit distinction between zero and unavailable."""

    detected_fire_cell_days: float = Field(ge=0.0)
    usable_land_cell_days: float = Field(ge=0.0)
    fire_activity_index: float | None = Field(
        default=None,
        ge=0.0,
        description="R = 1000 * D / O; null only when O is zero.",
    )
    availability: ObservationAvailability
    unavailable_reason: UnavailableReason | None = None

    @model_validator(mode="after")
    def validate_observation_accounting(self) -> "ObservationRecord":
        d = self.detected_fire_cell_days
        o = self.usable_land_cell_days
        if d > o:
            raise ValueError("D cannot exceed usable support O")
        if o == 0.0:
            if d != 0.0:
                raise ValueError("D must be zero when O is zero")
            if self.fire_activity_index is not None:
                raise ValueError("R must be null when O is zero")
            if self.availability != "unavailable" or self.unavailable_reason != "zero_usable_support":
                raise ValueError("O=0 requires unavailable/zero_usable_support")
            return self

        expected = 1000.0 * d / o
        if self.fire_activity_index is None:
            raise ValueError("R is required when O is positive, including a valid 0.0")
        if not math.isclose(self.fire_activity_index, expected, rel_tol=1e-12, abs_tol=1e-12):
            raise ValueError("R must equal 1000 * D / O at full artifact precision")
        if self.availability != "available" or self.unavailable_reason is not None:
            raise ValueError("positive usable support requires available with no unavailable reason")
        return self


class MonthRecord(ObservationRecord):
    sensor: SensorType
    year: int = Field(ge=2000, le=2100)
    month: int = Field(ge=1, le=12)
    baseline_median: float | None = Field(default=None, ge=0.0)
    baseline_p90: float | None = Field(default=None, ge=0.0)
    unusual_status: Literal["unusual", "not_unusual", "insufficient_baseline", "not_applicable"]
    is_partial_period: bool = False
    comparison_eligible: bool
    partial_period_reason: Literal["snpp_record_ended_2026_11_02"] | None = None

    @model_validator(mode="after")
    def validate_month_labels(self) -> "MonthRecord":
        baseline_missing = self.baseline_median is None or self.baseline_p90 is None
        if self.unusual_status in {"unusual", "not_unusual"}:
            if baseline_missing or self.fire_activity_index is None:
                raise ValueError("an unusual-month decision requires baseline values and available R")
            above = self.fire_activity_index > self.baseline_p90  # type: ignore[operator]
            if above != (self.unusual_status == "unusual"):
                raise ValueError("unusual means R strictly above p90; ties are not unusual")
        elif self.unusual_status == "insufficient_baseline" and not baseline_missing:
            raise ValueError("insufficient baseline cannot carry baseline thresholds")
        if self.sensor == "VIIRS_SNPP" and (self.year, self.month) > (2026, 11):
            raise ValueError("S-NPP records cannot extend beyond November 2026")
        if self.sensor == "VIIRS_SNPP" and (self.year, self.month) == (2026, 11):
            if not self.is_partial_period or self.comparison_eligible:
                raise ValueError("November 2026 S-NPP must be partial and comparison-ineligible")
            if self.partial_period_reason != "snpp_record_ended_2026_11_02":
                raise ValueError("November 2026 S-NPP requires its cessation reason")
        elif self.partial_period_reason is not None or self.is_partial_period:
            raise ValueError("partial-period flags are only valid for November 2026 S-NPP")
        return self

class WeekRecord(ObservationRecord):
    sensor: SensorType
    year: int = Field(ge=2000, le=2100)
    week_number: int = Field(ge=1, le=53)
    start_date: date
    end_date: date
    critical_status: Literal["critical", "not_critical", "insufficient_baseline", "not_applicable"]
    unusual_status: Literal["unusual", "not_unusual", "insufficient_baseline", "not_applicable"]
    comparison_eligible: bool

    @model_validator(mode="after")
    def validate_week(self) -> "WeekRecord":
        if self.end_date < self.start_date:
            raise ValueError("week end date must not precede start date")
        if (self.end_date - self.start_date).days != 6:
            raise ValueError("weekly records must cover exactly seven inclusive UTC dates")
        if self.sensor == "VIIRS_SNPP" and self.end_date > date(2026, 11, 2):
            raise ValueError("S-NPP weekly records cannot extend past the confirmed record end")
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
        return self


class CalendarArtifact(ArtifactIdentity):
    region_name: str = Field(min_length=1)
    measurement_name: Literal["fire_activity_index"] = "fire_activity_index"
    measurement_unit: Literal["detected_fire_cell_days_per_1000_usable_land_cell_days"]
    snpp_delivery_end_at: datetime
    monthly_series: list[MonthlyCalendarSeries] = Field(min_length=1)
    weekly_series: list[WeeklyCalendarSeries] = Field(min_length=1)
    seasonal_baselines: list[SeasonalBaselineInfo] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_calendar(self) -> "CalendarArtifact":
        expected = datetime(2026, 11, 2, 15, 40, tzinfo=timezone.utc)
        if self.snpp_delivery_end_at != expected:
            raise ValueError("S-NPP cessation timestamp must be 2026-11-02T15:40:00Z")
        for series in [*self.monthly_series, *self.weekly_series]:
            if series.policy_id != self.policy_id:
                raise ValueError("calendar series policy must match artifact identity")
        return self

