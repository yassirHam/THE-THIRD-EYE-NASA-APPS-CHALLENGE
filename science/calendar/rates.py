"""
Historical fire-activity rate calculation - same-sensor calendar.

Scientific authority:
  THE_THIRD_EYE_FINAL_PLAN_GEOGRAPHIC_ACCESS_UPDATED.txt  Sections 3A, 4
  contracts/schemas/calendar.py

GUARDRAILS (enforced in this module, not delegated to callers):
- R = 1000 * sum(D) / sum(O).  Sums of D and O BEFORE division.
- O = 0 is UNAVAILABLE; never coerced to zero fire.
- Rates are same-sensor and same-policy.  pooled_rate() raises if records
  from different sensors, policies or period types are passed together.
- S-NPP cutoff.  Every VIIRS_SNPP record is classified against the
  cessation instant from its own calendar bounds, whatever the caller sets
  in is_partial:
    complete         period ends at or before the cutoff
    partial          period straddles the cutoff (November 2026; ISO week
                     45 of 2026)
    after_cessation  period starts at or after the cutoff
  Partial and after-cessation periods never produce a comparable rate.
- Period boundaries (frozen):
    monthly: first day 00:00 UTC to first day of next month 00:00 UTC
    weekly:  ISO 8601 weeks in UTC, Monday 00:00 to next Monday 00:00;
             PeriodObs.year is the ISO week-year for weekly records.

Limit: SNPP_CESSATION is the NOAA/NESDIS notice time.  The plan requires P2 to
confirm the last VNP14A1 date in the actual collection; if that date is
earlier, this constant must be updated in a reviewed commit.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from enum import Enum
from typing import Literal, Optional

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
SCALE: float = 1000.0

SNPP_CESSATION: datetime = datetime(2026, 11, 2, 15, 40, tzinfo=timezone.utc)
SNPP_CESSATION_UTC: str = "2026-11-02T15:40:00Z"
SNPP_LAST_COMPLETE_MONTH: tuple[int, int] = (2026, 10)
WEEK_DEFINITION: str = "iso_8601_utc"

SensorID = Literal["MODIS_Aqua", "VIIRS_SNPP", "VIIRS_NOAA20"]
PolicyID = Literal["own_support", "common_support"]


class CutoffStatus(str, Enum):
    COMPLETE = "complete"
    PARTIAL = "partial"
    AFTER_CESSATION = "after_cessation"
    NOT_APPLICABLE = "not_applicable"  # sensor has no registered cessation


def period_bounds_utc(
    year: int, month: Optional[int] = None, week_number: Optional[int] = None
) -> tuple[datetime, datetime]:
    """Return [start, end) of a monthly or ISO-week period in UTC."""
    if month is not None:
        start = datetime(year, month, 1, tzinfo=timezone.utc)
        if month == 12:
            end = datetime(year + 1, 1, 1, tzinfo=timezone.utc)
        else:
            end = datetime(year, month + 1, 1, tzinfo=timezone.utc)
        return start, end
    if week_number is not None:
        monday = date.fromisocalendar(year, week_number, 1)
        start = datetime(monday.year, monday.month, monday.day, tzinfo=timezone.utc)
        return start, start + timedelta(days=7)
    raise ValueError("period_bounds_utc needs month or week_number.")


def snpp_cutoff_status(start: datetime, end: datetime) -> CutoffStatus:
    """Classify a [start, end) period against the S-NPP cessation instant."""
    if end <= SNPP_CESSATION:
        return CutoffStatus.COMPLETE
    if start >= SNPP_CESSATION:
        return CutoffStatus.AFTER_CESSATION
    return CutoffStatus.PARTIAL


# ---------------------------------------------------------------------------
# Input record
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class PeriodObs:
    """
    Aggregate D and O for one sensor, policy and calendar period.

    D: detected fire-cell-days (non-negative integer).
    O: usable land-cell-days.  O = 0 means unavailable; D must then be 0.
    month / week_number: exactly one must be set.  For weekly records, year
        is the ISO week-year.
    is_partial: caller flag for periods known to be incomplete for reasons
        other than the S-NPP cutoff (e.g. an in-progress month).  It can mark
        a period partial; it cannot mark an S-NPP period complete.
    policy: support policy; rates never mix policies.
    block_id: optional identifier for geographic block/footprint; used for
        whole-area baseline calculations to verify all required blocks are present.
    """

    sensor: SensorID
    year: int
    D: int
    O: int
    month: Optional[int] = None
    week_number: Optional[int] = None
    is_partial: bool = False
    policy: PolicyID = "own_support"
    block_id: Optional[str] = None

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
        if self.week_number is not None:
            try:
                date.fromisocalendar(self.year, self.week_number, 1)
            except ValueError as exc:
                raise ValueError(
                    f"week_number {self.week_number} is not a valid ISO week "
                    f"for ISO week-year {self.year}."
                ) from exc

    @property
    def period_type(self) -> str:
        return "month" if self.month is not None else "week"

    @property
    def bounds_utc(self) -> tuple[datetime, datetime]:
        return period_bounds_utc(self.year, self.month, self.week_number)

    @property
    def cutoff_status(self) -> CutoffStatus:
        if self.sensor != "VIIRS_SNPP":
            return CutoffStatus.NOT_APPLICABLE
        return snpp_cutoff_status(*self.bounds_utc)

    @property
    def is_after_cessation(self) -> bool:
        return self.cutoff_status == CutoffStatus.AFTER_CESSATION

    @property
    def is_period_partial(self) -> bool:
        """Partial by caller flag or by straddling the S-NPP cutoff."""
        return self.is_partial or self.cutoff_status == CutoffStatus.PARTIAL

    @property
    def is_available(self) -> bool:
        """Usable for a comparable rate: O > 0, complete and before cessation."""
        return (
            self.O > 0
            and not self.is_period_partial
            and not self.is_after_cessation
        )


# ---------------------------------------------------------------------------
# Rate calculation
# ---------------------------------------------------------------------------
class RateStatus(str, Enum):
    AVAILABLE = "available"
    UNAVAILABLE = "unavailable"          # O = 0
    PARTIAL_MONTH = "partial_month"
    PARTIAL_WEEK = "partial_week"
    AFTER_CESSATION = "after_cessation"  # S-NPP record has ended


@dataclass
class RateResult:
    sensor: SensorID
    policy: PolicyID
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
    R = 1000 * D / O for one period.  Status precedence:
    after_cessation > partial > O = 0 > available.
    """
    def _result(rate: Optional[float], status: RateStatus, reasons: list[str]) -> RateResult:
        return RateResult(
            sensor=obs.sensor, policy=obs.policy, year=obs.year,
            month=obs.month, week_number=obs.week_number,
            D=obs.D, O=obs.O, fire_activity_index=rate,
            status=status, reasons=reasons,
        )

    label = (
        f"{obs.sensor} {obs.year}-{obs.month:02d}" if obs.month is not None
        else f"{obs.sensor} {obs.year}-W{obs.week_number:02d}"
    )

    if obs.is_after_cessation:
        return _result(None, RateStatus.AFTER_CESSATION, [
            f"{label} starts after the S-NPP cessation ({SNPP_CESSATION_UTC}). "
            "S-NPP record ends; no value is shown for this period."
        ])

    if obs.is_period_partial:
        status = RateStatus.PARTIAL_MONTH if obs.month is not None else RateStatus.PARTIAL_WEEK
        if obs.cutoff_status == CutoffStatus.PARTIAL:
            reason = (
                f"{label} straddles the S-NPP cessation ({SNPP_CESSATION_UTC}); "
                "it is a partial period and never a complete normal value."
            )
        else:
            reason = f"{label} is flagged partial; no comparable rate is shown."
        return _result(None, status, [reason])

    if obs.O == 0:
        return _result(None, RateStatus.UNAVAILABLE, [
            f"O = 0 for {label}: no usable land-cell-days; unavailable, not zero."
        ])

    return _result(SCALE * obs.D / obs.O, RateStatus.AVAILABLE, [])


def block_problems(
    observations: list[PeriodObs],
    required_blocks: Optional[tuple[str, ...]],
) -> list[str]:
    """
    Single block-completeness check used by every rate and baseline function.

    Raises ValueError for invalid input (cannot be fixed by marking unavailable):
      - required_blocks is not a non-empty tuple of unique non-empty strings;
      - required_blocks is None but some record carries a block_id
        (block-level records need a registered block list);
      - a record has no block_id or an unregistered block_id
        (pooling it would silently change the analysed footprint);
      - two records share the same block and period (double counting).

    Returns a list of reasons the data are unavailable (empty means complete):
      - a required block has no record in a period present in the input;
      - a required block has no usable record (all O = 0, partial or after
        cessation) in that period.
    A block with O = 0 is not treated as zero activity and is not dropped:
    the period is unavailable for a whole-area value.
    """
    if required_blocks is None:
        tagged = sorted({o.block_id for o in observations if o.block_id is not None})
        if tagged:
            raise ValueError(
                f"Records carry block_ids {tagged} but no registered "
                "required_blocks were supplied."
            )
        return []

    if (not isinstance(required_blocks, tuple) or not required_blocks
            or len(set(required_blocks)) != len(required_blocks)
            or not all(isinstance(b, str) and b for b in required_blocks)):
        raise ValueError(
            "required_blocks must be a non-empty tuple of unique, non-empty "
            f"strings; got {required_blocks!r}."
        )
    registered = set(required_blocks)
    unregistered = sorted({str(o.block_id) for o in observations
                           if o.block_id not in registered})
    if unregistered:
        raise ValueError(
            f"Records with unregistered or missing block_id {unregistered}; "
            f"registered blocks are {list(required_blocks)}."
        )

    by_period: dict[tuple, dict[str, list[PeriodObs]]] = {}
    for o in observations:
        key = (o.year, o.month, o.week_number)
        by_period.setdefault(key, {}).setdefault(o.block_id, []).append(o)  # type: ignore[arg-type]

    problems: list[str] = []
    for key in sorted(by_period, key=lambda k: (k[0], k[1] or 0, k[2] or 0)):
        blocks = by_period[key]
        label = f"{key[0]}-{key[1]:02d}" if key[1] is not None else f"{key[0]}-W{key[2]:02d}"
        dupes = sorted(b for b, recs in blocks.items() if len(recs) > 1)
        if dupes:
            raise ValueError(f"Period {label}: more than one record for block(s) {dupes}.")
        for b in required_blocks:
            if b not in blocks:
                problems.append(f"{label}: required block {b} missing.")
            elif not blocks[b][0].is_available:
                problems.append(f"{label}: required block {b} has no usable observations.")
    return problems


def pooled_rate(
    observations: list[PeriodObs],
    required_blocks: Optional[tuple[str, ...]] = None,
) -> Optional[float]:
    """
    1000 * sum(D) / sum(O) across available observations.

    Raises ValueError when records mix sensors, policies or period types, or
    when block_problems() finds invalid block input.
    Returns None when no available observation exists or when any required
    block is missing or has no usable observations.
    """
    if not observations:
        return None
    sensors = {o.sensor for o in observations}
    policies = {o.policy for o in observations}
    period_types = {o.period_type for o in observations}
    if len(sensors) > 1:
        raise ValueError(f"pooled_rate received mixed sensors {sorted(sensors)}; "
                         "rates are same-sensor only.")
    if len(policies) > 1:
        raise ValueError(f"pooled_rate received mixed policies {sorted(policies)}.")
    if len(period_types) > 1:
        raise ValueError("pooled_rate received both monthly and weekly records.")

    if block_problems(observations, required_blocks):
        return None

    total_D = 0
    total_O = 0
    for obs in observations:
        if obs.is_available:
            total_D += obs.D
            total_O += obs.O
    if total_O == 0:
        return None
    return SCALE * total_D / total_O
