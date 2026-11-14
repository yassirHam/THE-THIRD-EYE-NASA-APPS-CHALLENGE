"""
Historical fire-activity rate calculation — same-sensor calendar.

Scientific authority:
  THE_THIRD_EYE_FINAL_PLAN_GEOGRAPHIC_ACCESS_UPDATED.txt  §3A, §4
  contracts/schemas/calendar.py

GUARDRAILS (non-negotiable):
- R = 1000 * sum(D) / sum(O).  Sums of D and O BEFORE division.
- O = 0 is UNAVAILABLE; never coerced to zero fire.
- Monthly and weekly rates are SAME-SENSOR ONLY.  MODIS Aqua and
  VIIRS S-NPP / NOAA-20 are never joined into one rate series without
  a separately evaluated mapping at that resolution.
- S-NPP (VNP14A1) archive ends at 2026-11-02T15:40:00Z.  No S-NPP
  month after that cutoff may be computed as a normal or complete value.
  November 2026 is a partial month and is never presented as a full
  normal month.
- A partial month (is_partial_month=True) is always is_unavailable=True
  for rate purposes; it may show raw D/O counts but not a comparable rate.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from enum import Enum
from typing import Literal, Optional

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
SCALE: float = 1000.0

# Exact S-NPP cessation timestamp (UTC).
SNPP_CESSATION_UTC: str = "2026-11-02T15:40:00Z"
# No S-NPP data covers any date after this calendar month is partial.
SNPP_LAST_COMPLETE_MONTH: tuple[int, int] = (2026, 10)  # October 2026

SensorID = Literal["MODIS_Aqua", "VIIRS_SNPP", "VIIRS_NOAA20"]


# ---------------------------------------------------------------------------
# Input record
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class PeriodObs:
    """
    Aggregate D and O for one sensor in one calendar period (year/month or
    year/week).

    D: detected fire-cell-days (non-negative integer).
    O: usable land-cell-days denominator.
        O = 0 means the period is UNAVAILABLE; D must be 0.
    sensor: one of the three named platforms.
    year / month / week_number: calendar address.  week_number is None
        for monthly records; month is None for weekly records.
    is_partial: True when the period is known to be incomplete — specifically,
        any S-NPP period that overlaps the 2026-11-02 cessation, or any
        in-progress period where only part of the calendar window was observed.
        A partial period is always treated as unavailable for rate comparison.
    """

    sensor: SensorID
    year: int
    D: int
    O: int
    month: Optional[int] = None       # 1-12; None for weekly records
    week_number: Optional[int] = None  # 1-53; None for monthly records
    is_partial: bool = False

    def __post_init__(self) -> None:
        if self.D < 0:
            raise ValueError(f"D must be >= 0, got {self.D}")
        if self.O < 0:
            raise ValueError(f"O must be >= 0, got {self.O}")
        if self.O == 0 and self.D > 0:
            raise ValueError(
                "O = 0 (unavailable period) cannot have D > 0.  "
                "If the period was unobserved set both D = 0 and O = 0."
            )
        if self.month is None and self.week_number is None:
            raise ValueError("At least one of month or week_number must be set.")
        if self.month is not None and self.week_number is not None:
            raise ValueError("Set month OR week_number, not both.")
        if self.month is not None and not (1 <= self.month <= 12):
            raise ValueError(f"month must be 1-12, got {self.month}")
        if self.week_number is not None and not (1 <= self.week_number <= 53):
            raise ValueError(f"week_number must be 1-53, got {self.week_number}")

    @property
    def is_available(self) -> bool:
        """True when the period has usable observations and is not partial."""
        return self.O > 0 and not self.is_partial

    @staticmethod
    def snpp_month_is_partial(year: int, month: int) -> bool:
        """
        Return True when a VIIRS_SNPP monthly record is for a partial month.

        November 2026 is partial because S-NPP data ceased on 2026-11-02.
        No SNPP month after October 2026 is complete.
        """
        # S-NPP last complete month is October 2026 (year=2026, month=10).
        # November 2026 (2026, 11) is partial.
        # Any month in 2027+ would also be partial (no data), but those
        # records should not exist in the VNP14A1 archive.
        if year > 2026:
            return True
        if year == 2026 and month >= 11:
            return True
        return False


# ---------------------------------------------------------------------------
# Rate calculation
# ---------------------------------------------------------------------------
class RateStatus(str, Enum):
    AVAILABLE = "available"          # R computed from O > 0
    UNAVAILABLE = "unavailable"      # O = 0 or period is partial
    PARTIAL_MONTH = "partial_month"  # specifically the S-NPP Nov-2026 case


@dataclass
class RateResult:
    """
    Fire-activity rate for one sensor/period.

    fire_activity_index: 1000 * D / O when status == AVAILABLE; else None.
    status: AVAILABLE, UNAVAILABLE, or PARTIAL_MONTH.
    D, O: raw counts as supplied.
    reasons: human-readable explanations for non-AVAILABLE status.
    """

    sensor: SensorID
    year: int
    month: Optional[int]
    week_number: Optional[int]
    D: int
    O: int
    fire_activity_index: Optional[float]
    status: RateStatus
    reasons: list[str] = field(default_factory=list)


def compute_rate(obs: PeriodObs) -> RateResult:
    """
    Compute R = 1000 * D / O for a single period observation.

    Returns RateResult with fire_activity_index = None when O = 0 or the
    period is partial.  Partial S-NPP months produce status = PARTIAL_MONTH.
    """
    reasons: list[str] = []

    # Partial-month guard (highest priority — applies before O check)
    if obs.is_partial:
        if obs.sensor == "VIIRS_SNPP" and obs.month is not None:
            status = RateStatus.PARTIAL_MONTH
            reasons.append(
                f"VIIRS_SNPP month {obs.year}-{obs.month:02d} is a partial "
                f"month (S-NPP data ceased {SNPP_CESSATION_UTC}).  "
                "This month is never shown as a complete normal value."
            )
        else:
            status = RateStatus.UNAVAILABLE
            reasons.append(
                f"Period {obs.year} month={obs.month} week={obs.week_number} "
                "is marked partial; rate is unavailable."
            )
        return RateResult(
            sensor=obs.sensor,
            year=obs.year,
            month=obs.month,
            week_number=obs.week_number,
            D=obs.D,
            O=obs.O,
            fire_activity_index=None,
            status=status,
            reasons=reasons,
        )

    # Missing observation guard
    if obs.O == 0:
        reasons.append(
            f"O = 0 for {obs.sensor} {obs.year} "
            f"month={obs.month} week={obs.week_number}: "
            "period is unavailable (no usable land-cell-days)."
        )
        return RateResult(
            sensor=obs.sensor,
            year=obs.year,
            month=obs.month,
            week_number=obs.week_number,
            D=obs.D,
            O=obs.O,
            fire_activity_index=None,
            status=RateStatus.UNAVAILABLE,
            reasons=reasons,
        )

    r = SCALE * obs.D / obs.O
    return RateResult(
        sensor=obs.sensor,
        year=obs.year,
        month=obs.month,
        week_number=obs.week_number,
        D=obs.D,
        O=obs.O,
        fire_activity_index=r,
        status=RateStatus.AVAILABLE,
        reasons=[],
    )


def pooled_rate(observations: list[PeriodObs]) -> Optional[float]:
    """
    1000 * sum(D) / sum(O) across all available observations.

    Returns None when no available observations exist.

    All observations must be from the same sensor.  The caller is responsible
    for filtering; this function does not enforce sensor homogeneity.
    """
    total_D: int = 0
    total_O: int = 0
    for obs in observations:
        if obs.is_available:
            total_D += obs.D
            total_O += obs.O
    if total_O == 0:
        return None
    return SCALE * total_D / total_O
