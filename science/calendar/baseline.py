"""
Seasonal baseline, unusual-month labels and normal season - same sensor
and same policy.

Scientific authority:
  THE_THIRD_EYE_FINAL_PLAN_GEOGRAPHIC_ACCESS_UPDATED.txt
    WEEKEND BUILD BRIEF (registered prior years "must be present with minimum
    support or the baseline is unavailable") and Section 3A.

Rules implemented:
  - Required years for a target year T are every year from
    eligible_start_year through min(T - 1, eligible_end_year).  T and later
    years never enter.  If that span has fewer than min_years years the
    baseline is INSUFFICIENT_BASELINE.
  - Every required year must be present with complete, pre-cessation records
    whose summed O meets min_support_O.  One missing, partial or
    under-supported year makes the baseline MISSING_REQUIRED_YEARS; years are
    never silently dropped.
  - Each year's rate is 1000 * sum(D) / sum(O) over that year's records.
  - Median: conventional median (mean of the two middle values for even n).
  - 90th percentile: nearest rank, rank = ceil(0.90 * n), 1-indexed.
  - Unusual: strictly above the 90th percentile; ties are not unusual.
  - Normal season: needs an AVAILABLE baseline for all 12 months, otherwise
    insufficient baseline.  Season start/end are the first and last
    qualifying months in the frozen season-year order (starting at
    season_year_start_month).  Non-qualifying months inside the span are
    reported, not hidden.  Peak ties go to the earliest month in that order.
    A peak median of 0 yields no season.

All BaselineConfig parameters except policy are required so they must be
registered explicitly before outcomes are inspected; none has a code default.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import date
from enum import Enum
from typing import Optional

from science.calendar.rates import PeriodObs, PolicyID, SensorID, pooled_rate


# ---------------------------------------------------------------------------
# Configuration - frozen before outcome inspection
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class BaselineConfig:
    sensor: SensorID
    eligible_start_year: int
    eligible_end_year: int
    min_years: int
    min_support_O: int
    normal_season_threshold_fraction: float
    season_year_start_month: int
    policy: PolicyID = "own_support"

    def __post_init__(self) -> None:
        if self.eligible_end_year < self.eligible_start_year:
            raise ValueError("eligible_end_year must be >= eligible_start_year.")
        if self.min_years < 1:
            raise ValueError("min_years must be >= 1.")
        if self.min_support_O < 1:
            raise ValueError("min_support_O must be >= 1 (O = 0 is never support).")
        if not (0.0 < self.normal_season_threshold_fraction <= 1.0):
            raise ValueError("normal_season_threshold_fraction must be in (0, 1].")
        if not (1 <= self.season_year_start_month <= 12):
            raise ValueError("season_year_start_month must be 1-12.")


# ---------------------------------------------------------------------------
# Result types
# ---------------------------------------------------------------------------
class BaselineStatus(str, Enum):
    AVAILABLE = "available"
    INSUFFICIENT_BASELINE = "insufficient_baseline"    # span shorter than min_years
    MISSING_REQUIRED_YEARS = "missing_required_years"  # a required year lacks support


@dataclass
class MonthBaseline:
    calendar_month: int
    target_year: int
    sensor: SensorID
    policy: PolicyID
    min_support_O: int
    median_rate: Optional[float]
    p90_rate: Optional[float]
    n_years: int
    eligible_years: list[int]   # years whose rates entered the statistics
    required_years: list[int]
    missing_years: list[int]
    status: BaselineStatus
    reasons: list[str] = field(default_factory=list)


@dataclass
class UnusualLabel:
    """
    status: 'labeled' | 'baseline_unavailable' | 'target_unavailable' |
            'target_partial' | 'target_insufficient_support'
    is_unusual is True only when status == 'labeled' and rate > p90.
    """
    calendar_month: int
    target_year: int
    sensor: SensorID
    policy: PolicyID
    is_unusual: bool
    target_rate: Optional[float]
    p90_rate: Optional[float]
    status: str
    reason: str = ""


@dataclass
class NormalSeason:
    """status: 'available' | 'insufficient_baseline' | 'no_detected_activity'"""
    sensor: SensorID
    policy: PolicyID
    start_month: Optional[int]
    end_month: Optional[int]
    peak_month: Optional[int]
    status: str
    threshold_rate: Optional[float] = None
    tied_peak_months: list[int] = field(default_factory=list)
    interior_nonqualifying_months: list[int] = field(default_factory=list)
    missing_months: list[int] = field(default_factory=list)
    reasons: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Statistics
# ---------------------------------------------------------------------------
def _median(sorted_values: list[float]) -> float:
    """Conventional median of a non-empty sorted list."""
    n = len(sorted_values)
    mid = n // 2
    if n % 2 == 1:
        return sorted_values[mid]
    return (sorted_values[mid - 1] + sorted_values[mid]) / 2.0


def _nearest_rank_percentile(sorted_values: list[float], p: float) -> float:
    """Nearest-rank percentile: sorted_values[ceil(p/100 * n) - 1]."""
    n = len(sorted_values)
    rank = max(1, min(math.ceil(p / 100.0 * n), n))
    return sorted_values[rank - 1]


# ---------------------------------------------------------------------------
# Monthly baseline
# ---------------------------------------------------------------------------
def compute_month_baseline(
    calendar_month: int,
    target_year: int,
    all_obs: list[PeriodObs],
    config: BaselineConfig,
    required_blocks: Optional[tuple[str, ...]] = None,
) -> MonthBaseline:
    """Baseline for one calendar month and target year under a frozen config."""
    last_year = min(target_year - 1, config.eligible_end_year)
    required = list(range(config.eligible_start_year, last_year + 1))

    def _result(status, median=None, p90=None, used=None, missing=None, reasons=None):
        used = used or []
        return MonthBaseline(
            calendar_month=calendar_month, target_year=target_year,
            sensor=config.sensor, policy=config.policy,
            min_support_O=config.min_support_O,
            median_rate=median, p90_rate=p90, n_years=len(used),
            eligible_years=used, required_years=required,
            missing_years=missing or [], status=status, reasons=reasons or [],
        )

    if len(required) < config.min_years:
        return _result(BaselineStatus.INSUFFICIENT_BASELINE, reasons=[
            f"Registered span gives {len(required)} prior year(s) "
            f"({required}) for target {target_year}; minimum is "
            f"{config.min_years}.  Insufficient baseline."
        ])

    required_set = set(required)
    by_year: dict[int, list[PeriodObs]] = {}
    for o in all_obs:
        if (o.sensor == config.sensor and o.policy == config.policy
                and o.month == calendar_month and o.year in required_set):
            by_year.setdefault(o.year, []).append(o)

    missing: list[int] = []
    reasons: list[str] = []
    rates: dict[int, float] = {}
    for yr in required:
        recs = by_year.get(yr, [])
        if not recs:
            missing.append(yr)
            reasons.append(f"{yr}: no records.")
            continue
        if any(r.is_period_partial or r.is_after_cessation for r in recs):
            missing.append(yr)
            reasons.append(f"{yr}: partial or after-cessation record present.")
            continue
        
        # Check block completeness if required_blocks is provided
        recs_available = [r for r in recs if r.is_available]
        if required_blocks is not None:
            # Group by block_id
            blocks_present = {r.block_id for r in recs_available if r.block_id is not None}
            missing_blocks = set(required_blocks) - blocks_present
            if missing_blocks:
                missing.append(yr)
                reasons.append(f"{yr}: missing blocks {sorted(missing_blocks)}.")
                continue
            
            # Check each required block has O > 0
            blocks_ok = True
            for block in required_blocks:
                block_recs = [r for r in recs_available if r.block_id == block]
                total_block_O = sum(r.O for r in block_recs)
                if total_block_O == 0:
                    missing.append(yr)
                    reasons.append(f"{yr}: block {block} has O=0.")
                    blocks_ok = False
                    break
            
            if not blocks_ok:
                continue
        
        total_O = sum(r.O for r in recs_available)
        if total_O < config.min_support_O:
            missing.append(yr)
            reasons.append(
                f"{yr}: summed O = {total_O} below registered minimum "
                f"{config.min_support_O}."
            )
            continue
        rate = pooled_rate(recs_available, required_blocks=required_blocks)
        if rate is None:  # Can happen if required_blocks check failed in pooled_rate
            missing.append(yr)
            reasons.append(f"{yr}: no available records after block check.")
            continue
        rates[yr] = rate

    if missing:
        reasons.insert(0, (
            f"Required prior years {missing} lack complete records with "
            f"registered support for {config.sensor}/{config.policy} month "
            f"{calendar_month}, target {target_year}.  Baseline unavailable; "
            "remaining years are not used on their own."
        ))
        return _result(BaselineStatus.MISSING_REQUIRED_YEARS,
                       used=sorted(rates), missing=missing, reasons=reasons)

    sorted_rates = sorted(rates.values())
    return _result(
        BaselineStatus.AVAILABLE,
        median=_median(sorted_rates),
        p90=_nearest_rank_percentile(sorted_rates, 90.0),
        used=sorted(rates),
    )


# ---------------------------------------------------------------------------
# Unusual-month label
# ---------------------------------------------------------------------------
def label_unusual(
    target_obs: list[PeriodObs],
    target_year: int,
    calendar_month: int,
    baseline: MonthBaseline,
    required_blocks: Optional[tuple[str, ...]] = None,
) -> UnusualLabel:
    """Unusual = target rate strictly above the baseline's 90th percentile."""
    if baseline.target_year != target_year or baseline.calendar_month != calendar_month:
        raise ValueError(
            f"Baseline was computed for {baseline.target_year}-"
            f"{baseline.calendar_month:02d}, not {target_year}-{calendar_month:02d}."
        )

    def _label(status, rate=None, p90=None, unusual=False, reason=""):
        return UnusualLabel(
            calendar_month=calendar_month, target_year=target_year,
            sensor=baseline.sensor, policy=baseline.policy,
            is_unusual=unusual, target_rate=rate, p90_rate=p90,
            status=status, reason=reason,
        )

    if baseline.status != BaselineStatus.AVAILABLE:
        return _label("baseline_unavailable",
                      reason=f"Baseline status is {baseline.status.value}.")

    relevant = [
        o for o in target_obs
        if o.sensor == baseline.sensor and o.policy == baseline.policy
        and o.year == target_year and o.month == calendar_month
    ]
    if not relevant:
        return _label("target_unavailable", p90=baseline.p90_rate,
                      reason="No target records.")
    if any(o.is_period_partial or o.is_after_cessation for o in relevant):
        return _label("target_partial", p90=baseline.p90_rate,
                      reason="Target month is partial or after S-NPP cessation.")
    
    # Verify block completeness if required_blocks is provided
    if required_blocks is not None:
        available_blocks = {o.block_id for o in relevant if o.block_id is not None}
        missing_blocks = set(required_blocks) - available_blocks
        if missing_blocks:
            return _label("target_unavailable", p90=baseline.p90_rate,
                          reason=f"Missing required blocks: {sorted(missing_blocks)}")
        
        # Check each required block has O > 0
        for block in required_blocks:
            block_recs = [o for o in relevant if o.block_id == block]
            total_block_O = sum(o.O for o in block_recs)
            if total_block_O == 0:
                return _label("target_unavailable", p90=baseline.p90_rate,
                              reason=f"Block {block} has O=0.")
    
    total_O = sum(o.O for o in relevant)
    if total_O == 0:
        return _label("target_unavailable", p90=baseline.p90_rate,
                      reason="Target O = 0; unavailable, not zero.")
    if total_O < baseline.min_support_O:
        return _label("target_insufficient_support", p90=baseline.p90_rate,
                      reason=f"Target O = {total_O} below registered minimum "
                             f"{baseline.min_support_O}.")

    rate = pooled_rate(relevant, required_blocks=required_blocks)
    p90 = baseline.p90_rate
    return _label("labeled", rate=rate, p90=p90,
                  unusual=rate > p90)  # type: ignore[operator]


# ---------------------------------------------------------------------------
# Normal season
# ---------------------------------------------------------------------------
def derive_normal_season(
    all_baselines: dict[int, MonthBaseline],
    config: BaselineConfig,
) -> NormalSeason:
    """Normal season from 12 monthly baselines under the frozen rules above."""
    target_years = set()
    for m, bl in all_baselines.items():
        if bl.sensor != config.sensor or bl.policy != config.policy:
            raise ValueError(f"Baseline for month {m} is {bl.sensor}/{bl.policy}, "
                             f"config is {config.sensor}/{config.policy}.")
        if bl.calendar_month != m:
            raise ValueError(f"Baseline keyed {m} is for month {bl.calendar_month}.")
        target_years.add(bl.target_year)
    if len(target_years) > 1:
        raise ValueError(f"Baselines mix target years {sorted(target_years)}.")

    def _none(status, reasons, missing=None):
        return NormalSeason(sensor=config.sensor, policy=config.policy,
                            start_month=None, end_month=None, peak_month=None,
                            status=status, missing_months=missing or [],
                            reasons=reasons)

    missing = [
        m for m in range(1, 13)
        if m not in all_baselines
        or all_baselines[m].status != BaselineStatus.AVAILABLE
    ]
    if missing:
        return _none("insufficient_baseline", [
            f"Months {missing} lack an available baseline; first and last "
            "qualifying months cannot be determined."
        ], missing)

    order = [((config.season_year_start_month - 1 + i) % 12) + 1 for i in range(12)]
    medians = {m: all_baselines[m].median_rate for m in order}
    peak_median = max(medians.values())  # type: ignore[type-var]
    if peak_median <= 0.0:  # type: ignore[operator]
        return _none("no_detected_activity", [
            "Every monthly median rate is 0; no fire season is defined."
        ])

    tied = [m for m in order if medians[m] == peak_median]
    threshold = config.normal_season_threshold_fraction * peak_median  # type: ignore[operator]
    qualifying = [m for m in order if medians[m] >= threshold]  # type: ignore[operator]
    start, end = qualifying[0], qualifying[-1]
    span = order[order.index(start): order.index(end) + 1]
    interior = [m for m in span if m not in qualifying]

    reasons: list[str] = []
    if len(tied) > 1:
        reasons.append(f"Peak median tied across months {tied}; earliest in "
                       "season-year order selected.")
    if interior:
        reasons.append(f"Months {interior} inside the season fall below the "
                       "qualifying threshold.")
    return NormalSeason(
        sensor=config.sensor, policy=config.policy,
        start_month=start, end_month=end, peak_month=tied[0],
        status="available", threshold_rate=threshold,
        tied_peak_months=tied, interior_nonqualifying_months=interior,
        missing_months=[], reasons=reasons,
    )


# ---------------------------------------------------------------------------
# Weekly baseline
# ---------------------------------------------------------------------------
def compute_week_baseline(
    week_number: int,
    target_year: int,
    all_obs: list[PeriodObs],
    config: BaselineConfig,
    required_blocks: Optional[tuple[str, ...]] = None,
) -> MonthBaseline:
    """
    Weekly baseline following the same rules as monthly baselines.
    
    Week number is an ISO week (1-53). For weekly records, PeriodObs.year
    is the ISO week-year.
    
    Returns MonthBaseline for consistency (same structure, different semantics).
    The calendar_month field in the result contains the week number (1-53).
    """
    # Validate week_number
    if not (1 <= week_number <= 53):
        raise ValueError(f"week_number must be 1-53, got {week_number}")
    
    # Validate target_year is valid for ISO week-year
    try:
        date.fromisocalendar(target_year, week_number, 1)
    except ValueError as exc:
        raise ValueError(
            f"week_number {week_number} is not a valid ISO week "
            f"for ISO week-year {target_year}."
        ) from exc
    
    last_year = min(target_year - 1, config.eligible_end_year)
    required = list(range(config.eligible_start_year, last_year + 1))

    def _result(status, median=None, p90=None, used=None, missing=None, reasons=None):
        used = used or []
        return MonthBaseline(
            calendar_month=week_number,  # Store week number in calendar_month
            target_year=target_year,
            sensor=config.sensor, policy=config.policy,
            min_support_O=config.min_support_O,
            median_rate=median, p90_rate=p90, n_years=len(used),
            eligible_years=used, required_years=required,
            missing_years=missing or [], status=status, reasons=reasons or [],
        )

    if len(required) < config.min_years:
        return _result(BaselineStatus.INSUFFICIENT_BASELINE, reasons=[
            f"Registered span gives {len(required)} prior year(s) "
            f"({required}) for target {target_year}; minimum is "
            f"{config.min_years}.  Insufficient baseline."
        ])

    required_set = set(required)
    by_year: dict[int, list[PeriodObs]] = {}
    for o in all_obs:
        if (o.sensor == config.sensor and o.policy == config.policy
                and o.week_number == week_number and o.year in required_set):
            by_year.setdefault(o.year, []).append(o)

    missing: list[int] = []
    reasons: list[str] = []
    rates: dict[int, float] = {}
    for yr in required:
        recs = by_year.get(yr, [])
        if not recs:
            missing.append(yr)
            reasons.append(f"{yr}: no records.")
            continue
        if any(r.is_period_partial or r.is_after_cessation for r in recs):
            missing.append(yr)
            reasons.append(f"{yr}: partial or after-cessation record present.")
            continue
        
        # Check block completeness if required_blocks is provided
        recs_available = [r for r in recs if r.is_available]
        if required_blocks is not None:
            # Group by block_id
            blocks_present = {r.block_id for r in recs_available if r.block_id is not None}
            missing_blocks = set(required_blocks) - blocks_present
            if missing_blocks:
                missing.append(yr)
                reasons.append(f"{yr}: missing blocks {sorted(missing_blocks)}.")
                continue
            
            # Check each required block has O > 0
            blocks_ok = True
            for block in required_blocks:
                block_recs = [r for r in recs_available if r.block_id == block]
                total_block_O = sum(r.O for r in block_recs)
                if total_block_O == 0:
                    missing.append(yr)
                    reasons.append(f"{yr}: block {block} has O=0.")
                    blocks_ok = False
                    break
            
            if not blocks_ok:
                continue
        
        total_O = sum(r.O for r in recs_available)
        if total_O < config.min_support_O:
            missing.append(yr)
            reasons.append(
                f"{yr}: summed O = {total_O} below registered minimum "
                f"{config.min_support_O}."
            )
            continue
        rate = pooled_rate(recs_available, required_blocks=required_blocks)
        if rate is None:  # Can happen if required_blocks check failed in pooled_rate
            missing.append(yr)
            reasons.append(f"{yr}: no available records after block check.")
            continue
        rates[yr] = rate

    if missing:
        reasons.insert(0, (
            f"Required prior years {missing} lack complete records with "
            f"registered support for {config.sensor}/{config.policy} week "
            f"{week_number}, target {target_year}.  Baseline unavailable; "
            "remaining years are not used on their own."
        ))
        return _result(BaselineStatus.MISSING_REQUIRED_YEARS,
                       used=sorted(rates), missing=missing, reasons=reasons)

    sorted_rates = sorted(rates.values())
    return _result(
        BaselineStatus.AVAILABLE,
        median=_median(sorted_rates),
        p90=_nearest_rank_percentile(sorted_rates, 90.0),
        used=sorted(rates),
    )


# ---------------------------------------------------------------------------
# Critical week functions (P1-B-R2-03)
# ---------------------------------------------------------------------------
@dataclass
class CriticalWeekLabel:
    """
    Label for a critical/busiest week.
    
    status: 'labeled' | 'baseline_unavailable' | 'target_unavailable' |
            'target_partial' | 'target_insufficient_support'
    is_critical is True only when status == 'labeled' and week is in top busiest.
    rank: 1-indexed rank among all weeks (lower = busier)
    tied_with: list of other week numbers that have the same rate (sorted)
    """
    calendar_month: int  # Week number (1-53)
    target_year: int
    sensor: SensorID
    policy: PolicyID
    is_critical: bool
    target_rate: Optional[float]
    threshold_rate: Optional[float]
    rank: Optional[int]
    tied_with: list[int]
    status: str
    reason: str = ""


def compute_weekly_rates(
    target_obs: list[PeriodObs],
    target_year: int,
    baseline: MonthBaseline,
    required_blocks: Optional[tuple[str, ...]] = None,
) -> dict[int, float]:
    """
    Compute rates for all weeks in a target year from available observations.
    
    Returns a dict mapping week_number -> rate for weeks that have sufficient support.
    """
    relevant = [
        o for o in target_obs
        if o.sensor == baseline.sensor and o.policy == baseline.policy
        and o.year == target_year
    ]
    
    if not relevant:
        return {}
    
    if any(o.is_period_partial or o.is_after_cessation for o in relevant):
        return {}
    
    # Group by week_number
    from collections import defaultdict
    by_week: dict[int, list[PeriodObs]] = defaultdict(list)
    for o in relevant:
        if o.week_number is not None:
            by_week[o.week_number].append(o)
    
    rates: dict[int, float] = {}
    for week_num, obs_list in by_week.items():
        # Verify block completeness if required_blocks is provided
        if required_blocks is not None:
            available_blocks = {o.block_id for o in obs_list if o.block_id is not None}
            missing_blocks = set(required_blocks) - available_blocks
            if missing_blocks:
                continue  # Skip this week
            
            # Check each required block has O > 0
            blocks_ok = True
            for block in required_blocks:
                block_recs = [o for o in obs_list if o.block_id == block]
                total_block_O = sum(o.O for o in block_recs)
                if total_block_O == 0:
                    blocks_ok = False
                    break
            
            if not blocks_ok:
                continue
        
        total_O = sum(o.O for o in obs_list)
        if total_O == 0:
            continue  # O = 0 is unavailable
        if total_O < baseline.min_support_O:
            continue
        
        rate = pooled_rate(obs_list, required_blocks=required_blocks)
        if rate is not None:
            rates[week_num] = rate
    
    return rates


def compute_critical_weeks(
    target_obs: list[PeriodObs],
    target_year: int,
    baseline: MonthBaseline,
    top_n: int = 3,
    required_blocks: Optional[tuple[str, ...]] = None,
) -> list[CriticalWeekLabel]:
    """
    Identify the top busiest weeks by rate for a target year.
    
    Returns a sorted list (busiest first) of CriticalWeekLabel objects.
    Ties are broken deterministically by week_number (lower week_number wins).
    
    Args:
        target_obs: Target year observations
        target_year: Target year for analysis
        baseline: MonthBaseline from which to derive threshold (p90_rate)
        top_n: Number of top weeks to identify
        required_blocks: Optional tuple of required block IDs for spatial filtering
    """
    # Get all weekly rates
    rates = compute_weekly_rates(target_obs, target_year, baseline, required_blocks)
    
    if not rates:
        return []
    
    # Sort by rate descending, then by week_number ascending for deterministic tie-breaking
    sorted_weeks = sorted(rates.items(), key=lambda x: (-x[1], x[0]))
    
    # Determine threshold: use p90 rate from baseline if available
    threshold_rate = baseline.p90_rate if baseline.p90_rate is not None else None
    
    # Compute ranks with tie handling
    result: list[CriticalWeekLabel] = []
    i = 0
    while i < len(sorted_weeks):
        # Find all weeks with the same rate (ties)
        current_rate = sorted_weeks[i][1]
        tied_weeks = [w for w, r in sorted_weeks if r == current_rate]
        tied_weeks.sort()  # Deterministic ordering
        
        rank = i + 1  # 1-indexed rank
        
        for week_num in tied_weeks:
            rate = rates[week_num]
            is_critical = rank <= top_n
            status = "labeled" if is_critical else "not_in_top_n"
            
            # Check if unusual (rate > p90 threshold)
            unusual = False
            if threshold_rate is not None and rate > threshold_rate:
                unusual = True
                status = "unusual" if is_critical else "unusual_not_in_top_n"
            
            reason_parts = []
            if unusual:
                reason_parts.append(f"Rate {rate:.1f} exceeds p90 threshold {threshold_rate:.1f}")
            if len(tied_weeks) > 1:
                reason_parts.append(f"Tied with weeks {tied_weeks}")
            if is_critical:
                reason_parts.append(f"Ranked #{rank} of {len(sorted_weeks)} weeks")
            
            result.append(CriticalWeekLabel(
                calendar_month=week_num,
                target_year=target_year,
                sensor=baseline.sensor,
                policy=baseline.policy,
                is_critical=is_critical,
                target_rate=rate,
                threshold_rate=threshold_rate,
                rank=rank,
                tied_with=[w for w in tied_weeks if w != week_num],
                status=status,
                reason=". ".join(reason_parts) if reason_parts else "",
            ))
        
        i += len(tied_weeks)
    
    # Sort by rank to ensure proper ordering
    result.sort(key=lambda x: (x.rank or 999, x.calendar_month))
    
    return result


def label_critical_week(
    target_obs: list[PeriodObs],
    target_year: int,
    week_number: int,
    baseline: MonthBaseline,
    top_n: int = 3,
    required_blocks: Optional[tuple[str, ...]] = None,
) -> CriticalWeekLabel:
    """
    Label a specific week as critical/busiest if it falls within the top N busiest weeks.
    
    Returns a CriticalWeekLabel with status and rank information.
    """
    # Validate week_number
    if not (1 <= week_number <= 53):
        raise ValueError(f"week_number must be 1-53, got {week_number}")
    
    # Verify baseline.target_year matches target_year (P1-B-R2-02)
    if baseline.target_year != target_year:
        raise ValueError(
            f"Baseline was computed for target year {baseline.target_year}, "
            f"not {target_year}."
        )
    
    baseline_week = baseline.calendar_month
    if baseline_week != week_number:
        raise ValueError(
            f"Baseline was computed for week {baseline_week}, not {week_number}."
        )

    # Compute all critical weeks
    critical_weeks = compute_critical_weeks(
        target_obs, target_year, baseline, top_n, required_blocks
    )
    
    # Find the label for the specified week
    for cw in critical_weeks:
        if cw.calendar_month == week_number:
            return cw
    
    # Week not in top N, return with is_critical=False
    return CriticalWeekLabel(
        calendar_month=week_number,
        target_year=target_year,
        sensor=baseline.sensor,
        policy=baseline.policy,
        is_critical=False,
        target_rate=None,
        threshold_rate=baseline.p90_rate,
        rank=None,
        tied_with=[],
        status="not_in_top_n",
        reason=f"Week {week_number} is not among the top {top_n} busiest weeks.",
    )


def label_unusual_week(
    target_obs: list[PeriodObs],
    target_year: int,
    week_number: int,
    baseline: MonthBaseline,
    required_blocks: Optional[tuple[str, ...]] = None,
) -> UnusualLabel:
    """
    Label a week as unusual if its rate is strictly above the baseline's 90th percentile.
    
    Follows the same rules as label_unusual but operates on ISO weeks.
    The baseline.calendar_month field contains the week number (1-53).
    """
    # Validate week_number
    if not (1 <= week_number <= 53):
        raise ValueError(f"week_number must be 1-53, got {week_number}")
    
    # Verify baseline.target_year matches target_year (P1-B-R2-02)
    if baseline.target_year != target_year:
        raise ValueError(
            f"Baseline was computed for target year {baseline.target_year}, "
            f"not {target_year}."
        )
    
    baseline_week = baseline.calendar_month
    if baseline_week != week_number:
        raise ValueError(
            f"Baseline was computed for week {baseline_week}, not {week_number}."
        )

    def _label(status, rate=None, p90=None, unusual=False, reason=""):
        return UnusualLabel(
            calendar_month=week_number,  # Store week number in calendar_month
            target_year=target_year,
            sensor=baseline.sensor, policy=baseline.policy,
            is_unusual=unusual, target_rate=rate, p90_rate=p90,
            status=status, reason=reason,
        )

    if baseline.status != BaselineStatus.AVAILABLE:
        return _label("baseline_unavailable",
                      reason=f"Baseline status is {baseline.status.value}.")

    relevant = [
        o for o in target_obs
        if o.sensor == baseline.sensor and o.policy == baseline.policy
        and o.year == target_year and o.week_number == week_number
    ]
    if not relevant:
        return _label("target_unavailable", p90=baseline.p90_rate,
                      reason="No target records.")
    if any(o.is_period_partial or o.is_after_cessation for o in relevant):
        return _label("target_partial", p90=baseline.p90_rate,
                      reason="Target week is partial or after S-NPP cessation.")
    
    # Verify block completeness if required_blocks is provided
    if required_blocks is not None:
        available_blocks = {o.block_id for o in relevant if o.block_id is not None}
        missing_blocks = set(required_blocks) - available_blocks
        if missing_blocks:
            return _label("target_unavailable", p90=baseline.p90_rate,
                          reason=f"Missing required blocks: {sorted(missing_blocks)}")
        
        # Check each required block has O > 0
        for block in required_blocks:
            block_recs = [o for o in relevant if o.block_id == block]
            total_block_O = sum(o.O for o in block_recs)
            if total_block_O == 0:
                return _label("target_unavailable", p90=baseline.p90_rate,
                              reason=f"Block {block} has O=0.")
    
    total_O = sum(o.O for o in relevant)
    if total_O == 0:
        return _label("target_unavailable", p90=baseline.p90_rate,
                      reason="Target O = 0; unavailable, not zero.")
    if total_O < baseline.min_support_O:
        return _label("target_insufficient_support", p90=baseline.p90_rate,
                      reason=f"Target O = {total_O} below registered minimum "
                             f"{baseline.min_support_O}.")

    rate = pooled_rate(relevant, required_blocks=required_blocks)
    p90 = baseline.p90_rate
    return _label("labeled", rate=rate, p90=p90,
                  unusual=rate > p90)  # type: ignore[operator]
