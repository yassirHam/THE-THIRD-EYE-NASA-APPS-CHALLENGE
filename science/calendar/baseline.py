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
    years never enter.  Years in excluded_years are removed from the span and
    reported (never silently); sealed years must be excluded and their records
    are refused (P5 decision d0b8c90: never reuse holdouts).  If the remaining
    span has fewer than min_years years the baseline is INSUFFICIENT_BASELINE.
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
from typing import Literal, Optional

from science.calendar.rates import (
    PeriodObs, PolicyID, SensorID, block_problems, pooled_rate,
)


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
    # Years inside [eligible_start_year, eligible_end_year] that never enter the
    # baseline, listed explicitly (P5 binding decision, handoff d0b8c90 and
    # 0a49cbb: sealed 2020-2021 are excluded everywhere; never reuse holdouts).
    # Required, may be empty.  Excluded years are reported, never silently dropped.
    excluded_years: tuple[int, ...]
    # Years of the sealed evaluation window.  Every sealed year inside the span
    # must be in excluded_years, and records from sealed years are refused: they
    # must never reach a development baseline.  Required, may be empty.
    sealed_years: tuple[int, ...]
    policy: PolicyID = "own_support"

    def __post_init__(self) -> None:
        if self.eligible_end_year < self.eligible_start_year:
            raise ValueError("eligible_end_year must be >= eligible_start_year.")
        for name in ("excluded_years", "sealed_years"):
            years = getattr(self, name)
            if (not isinstance(years, tuple) or len(set(years)) != len(years)
                    or not all(isinstance(y, int) and not isinstance(y, bool) for y in years)):
                raise ValueError(f"{name} must be a tuple of unique integer years.")
        outside = [y for y in self.excluded_years
                   if not (self.eligible_start_year <= y <= self.eligible_end_year)]
        if outside:
            raise ValueError(f"excluded_years {outside} lie outside the registered span.")
        unexcluded = [y for y in self.sealed_years
                      if self.eligible_start_year <= y <= self.eligible_end_year
                      and y not in self.excluded_years]
        if unexcluded:
            raise ValueError(
                f"Sealed years {unexcluded} lie inside the baseline span and are not "
                "excluded; holdouts are never reused (P5 decision d0b8c90)."
            )
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
    excluded_years: list[int] = field(default_factory=list)  # registered exclusions in span


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
# Required years (shared by monthly and weekly baselines)
# ---------------------------------------------------------------------------
def _required_years(target_year: int, config: BaselineConfig) -> tuple[list[int], list[int]]:
    """(required years, registered exclusions inside the target's span)."""
    last_year = min(target_year - 1, config.eligible_end_year)
    span = list(range(config.eligible_start_year, last_year + 1))
    excluded = [y for y in span if y in config.excluded_years]
    return [y for y in span if y not in config.excluded_years], excluded


def _refuse_sealed(all_obs: list[PeriodObs], config: BaselineConfig) -> None:
    sealed = sorted({o.year for o in all_obs if o.year in config.sealed_years})
    if sealed:
        raise ValueError(
            f"Records from sealed years {sealed} were supplied to a baseline; sealed "
            "evaluation data must not reach development code (P5 decision d0b8c90)."
        )


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
    _refuse_sealed(all_obs, config)
    required, excluded = _required_years(target_year, config)

    def _result(status, median=None, p90=None, used=None, missing=None, reasons=None):
        used = used or []
        return MonthBaseline(
            calendar_month=calendar_month, target_year=target_year,
            sensor=config.sensor, policy=config.policy,
            min_support_O=config.min_support_O,
            median_rate=median, p90_rate=p90, n_years=len(used),
            eligible_years=used, required_years=required,
            missing_years=missing or [], status=status, reasons=reasons or [],
            excluded_years=excluded,
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
        
        recs_available = [r for r in recs if r.is_available]
        blk = block_problems(recs, required_blocks)
        if blk:
            missing.append(yr)
            reasons.extend(f"{yr}: {b}" for b in blk)
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
    
    blk = block_problems(relevant, required_blocks)
    if blk:
        return _label("target_unavailable", p90=baseline.p90_rate,
                      reason="; ".join(blk))
    
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
    
    _refuse_sealed(all_obs, config)
    required, excluded = _required_years(target_year, config)

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
            excluded_years=excluded,
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
        
        recs_available = [r for r in recs if r.is_available]
        blk = block_problems(recs, required_blocks)
        if blk:
            missing.append(yr)
            reasons.extend(f"{yr}: {b}" for b in blk)
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
# Critical weeks of the typical year (plan Section 3A)
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class CriticalWeekConfig:
    """
    Registered critical-week rules.  No field has a default.

    n_busiest_weeks: how many busiest weeks of the typical year are critical.
    ranked_weeks: the ISO week numbers that are ranked (e.g. 1..52).  Every
        listed week must have an available weekly baseline.
    tie_rule: how ties at the cut-off are handled.
        "include_all_tied": weeks tied with the last selected week are also
            critical, so more than n_busiest_weeks may be returned.
        "lower_week_number_first": exactly n_busiest_weeks; ties go to the
            lower ISO week number.
    The typical-year value of a week is its baseline median rate across the
    registered prior years (same sensor and policy).
    """
    n_busiest_weeks: int
    ranked_weeks: tuple[int, ...]
    tie_rule: Literal["include_all_tied", "lower_week_number_first"]

    def __post_init__(self) -> None:
        if (not isinstance(self.ranked_weeks, tuple) or not self.ranked_weeks
                or len(set(self.ranked_weeks)) != len(self.ranked_weeks)
                or not all(isinstance(w, int) and not isinstance(w, bool)
                           and 1 <= w <= 53 for w in self.ranked_weeks)):
            raise ValueError("ranked_weeks must be a non-empty tuple of unique ISO weeks 1-53.")
        if (isinstance(self.n_busiest_weeks, bool) or not isinstance(self.n_busiest_weeks, int)
                or not (1 <= self.n_busiest_weeks <= len(self.ranked_weeks))):
            raise ValueError("n_busiest_weeks must be an integer in 1..len(ranked_weeks).")
        if self.tie_rule not in ("include_all_tied", "lower_week_number_first"):
            raise ValueError(f"Unknown tie_rule {self.tie_rule!r}.")


@dataclass
class CriticalWeeks:
    """
    status: 'available' | 'insufficient_baseline' | 'no_detected_activity'
    critical_weeks: selected weeks in rank order (busiest first).
    ranking: (week, typical_rate, rank) for every ranked week; rank uses
        competition ranking (tied weeks share a rank).
    cutoff_rate: typical rate of the last selected week.
    tied_at_cutoff: weeks whose typical rate equals cutoff_rate.
    """
    target_year: int
    sensor: SensorID
    policy: PolicyID
    status: str
    critical_weeks: list[int] = field(default_factory=list)
    ranking: list[tuple[int, float, int]] = field(default_factory=list)
    cutoff_rate: Optional[float] = None
    tied_at_cutoff: list[int] = field(default_factory=list)
    missing_weeks: list[int] = field(default_factory=list)
    reasons: list[str] = field(default_factory=list)


@dataclass
class CriticalWeekLabel:
    """status: 'labeled' | 'not_ranked' | 'unavailable'"""
    week_number: int
    target_year: int
    sensor: SensorID
    policy: PolicyID
    is_critical: bool
    rank: Optional[int]
    typical_rate: Optional[float]
    status: str
    reason: str = ""


def compute_critical_weeks(
    target_year: int,
    all_obs: list[PeriodObs],
    config: BaselineConfig,
    cw_config: CriticalWeekConfig,
    required_blocks: Optional[tuple[str, ...]] = None,
) -> CriticalWeeks:
    """
    Busiest weeks of the typical year from registered prior years only.

    Each ranked week needs an AVAILABLE weekly baseline (all required years
    present with registered support and complete blocks).  If any ranked week
    is unavailable, no critical weeks are returned: the set is not computed
    over a silently reduced list of weeks.  The target year's own outcomes
    never enter.
    """
    def _out(status, **kw):
        return CriticalWeeks(target_year=target_year, sensor=config.sensor,
                             policy=config.policy, status=status, **kw)

    medians: dict[int, float] = {}
    missing: list[int] = []
    reasons: list[str] = []
    for w in cw_config.ranked_weeks:
        bl = compute_week_baseline(w, target_year, all_obs, config, required_blocks)
        if bl.status != BaselineStatus.AVAILABLE or bl.median_rate is None:
            missing.append(w)
            reasons.append(f"week {w}: baseline {bl.status.value}.")
        else:
            medians[w] = bl.median_rate

    if missing:
        reasons.insert(0, f"Ranked weeks {missing} lack an available baseline; "
                          "critical weeks are not computed.")
        return _out("insufficient_baseline", missing_weeks=missing, reasons=reasons)

    if max(medians.values()) <= 0.0:
        return _out("no_detected_activity",
                    reasons=["Every ranked week has a typical rate of 0."])

    ordered = sorted(medians.items(), key=lambda kv: (-kv[1], kv[0]))
    ranking: list[tuple[int, float, int]] = []
    for i, (w, r) in enumerate(ordered):
        rank = i + 1 if i == 0 or r != ordered[i - 1][1] else ranking[-1][2]
        ranking.append((w, r, rank))

    n = cw_config.n_busiest_weeks
    cutoff_rate = ordered[n - 1][1]
    tied = sorted(w for w, r in ordered if r == cutoff_rate)
    if cw_config.tie_rule == "include_all_tied":
        selected = [w for w, r in ordered if r >= cutoff_rate]
    else:
        selected = [w for w, _ in ordered[:n]]

    if len(tied) > 1:
        reasons.append(f"Weeks {tied} tie at the cut-off rate {cutoff_rate}; "
                       f"tie rule '{cw_config.tie_rule}' applied.")
    return _out("available", critical_weeks=selected, ranking=ranking,
                cutoff_rate=cutoff_rate, tied_at_cutoff=tied, reasons=reasons)


def label_critical_week(week_number: int, result: CriticalWeeks) -> CriticalWeekLabel:
    """Whether a week belongs to the registered critical weeks of the typical year."""
    def _lab(is_critical, rank, rate, status, reason=""):
        return CriticalWeekLabel(week_number=week_number, target_year=result.target_year,
                                 sensor=result.sensor, policy=result.policy,
                                 is_critical=is_critical, rank=rank, typical_rate=rate,
                                 status=status, reason=reason)

    if result.status != "available":
        return _lab(False, None, None, "unavailable",
                    f"Critical weeks status is {result.status}.")
    for w, r, rank in result.ranking:
        if w == week_number:
            return _lab(w in result.critical_weeks, rank, r, "labeled")
    return _lab(False, None, None, "not_ranked",
                f"Week {week_number} is not in the registered ranked weeks.")


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
    
    blk = block_problems(relevant, required_blocks)
    if blk:
        return _label("target_unavailable", p90=baseline.p90_rate,
                      reason="; ".join(blk))
    
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
