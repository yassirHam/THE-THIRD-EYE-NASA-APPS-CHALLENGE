"""
Seasonal baseline computation — same-sensor, same-calendar-month.

Scientific authority:
  THE_THIRD_EYE_FINAL_PLAN_GEOGRAPHIC_ACCESS_UPDATED.txt  §3A

Spec rules implemented here:
  - Eligible prior years: same sensor, years strictly before the target
    year, within the registered start/end span, excluding the target year
    and all later years.
  - Per-year monthly rate R_y = 1000 * sum(D) / sum(O) for each eligible
    year y.  Missing (O = 0) years contribute no rate — they are not
    counted in n and do not enter the sorted array.  Partially observed
    months are also excluded.
  - Median: nearest-rank, middle value of sorted array (len // 2 for even
    n; (len-1)//2 for odd n, i.e. lower median).  Spec says "median";
    we use the standard lower-median nearest-rank: sorted[n//2] for even,
    sorted[(n-1)//2] for odd.  For n=1 the median equals the single value.
  - 90th percentile: nearest-rank, rank = ceil(0.90 * n), 1-indexed.
    Value is sorted_values[rank - 1].
  - Unusual: strictly above the 90th percentile.  A value equal to the
    percentile is NOT unusual.
  - If the median rate is zero, the absolute difference is the only valid
    comparison; percentage change is undefined.
  - No baseline crosses sensors.
  - Minimum eligible-year count is registered before outcome inspection;
    if n < min_years the baseline is INSUFFICIENT.
  - Normal season: for each calendar month compute the median rate across
    eligible prior years.  The normal season is the contiguous run
    containing the peak-median month, bounded by months whose median
    crosses the registered threshold fraction of the peak median.
    All season parameters are frozen before outcome inspection.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

from science.calendar.rates import PeriodObs, pooled_rate, SCALE


# ---------------------------------------------------------------------------
# Configuration — frozen before outcome inspection
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class BaselineConfig:
    """
    Parameters frozen before any outcomes are inspected.

    sensor: which platform these baselines apply to.
    eligible_start_year: earliest year that may enter the baseline.
    eligible_end_year: last year that may enter the baseline (inclusive).
        For the VIIRS era, 2016 is the first usable year; for Aqua, 2003.
    min_years: minimum number of years with available rates required to
        produce a baseline; if n < min_years → INSUFFICIENT_BASELINE.
    normal_season_threshold_fraction: fraction of peak-month median that
        a month's median must meet or exceed to qualify as part of the
        normal season.  Frozen before outcomes.
    """

    sensor: str
    eligible_start_year: int
    eligible_end_year: int
    min_years: int = 3
    normal_season_threshold_fraction: float = 0.25


# ---------------------------------------------------------------------------
# Result types
# ---------------------------------------------------------------------------
class BaselineStatus(str, Enum):
    AVAILABLE = "available"
    INSUFFICIENT_BASELINE = "insufficient_baseline"  # n < min_years
    NO_AVAILABLE_YEARS = "no_available_years"         # all prior years O=0


@dataclass
class MonthBaseline:
    """
    Baseline statistics for one calendar month within one sensor era.

    median_rate: lower-median of per-year rates.  None when status != AVAILABLE.
    p90_rate: 90th-percentile nearest-rank rate.  None when status != AVAILABLE.
    n_years: count of eligible years with available rates.
    eligible_years: sorted list of years that contributed rates.
    status: AVAILABLE, INSUFFICIENT_BASELINE, or NO_AVAILABLE_YEARS.
    reasons: human-readable explanations for non-AVAILABLE status.
    """

    calendar_month: int   # 1-12
    sensor: str
    median_rate: Optional[float]
    p90_rate: Optional[float]
    n_years: int
    eligible_years: list[int]
    status: BaselineStatus
    reasons: list[str] = field(default_factory=list)


@dataclass
class UnusualLabel:
    """
    Unusual-period label for one target year/month.

    is_unusual: True when the target rate is STRICTLY above p90_rate.
                False when equal to or below p90_rate, or when
                baseline/target are unavailable.
    target_rate: the rate being tested.  None when unavailable.
    p90_rate: the threshold.  None when baseline unavailable.
    status: 'labeled' | 'insufficient_baseline' | 'target_unavailable' |
            'baseline_unavailable'
    """

    calendar_month: int
    target_year: int
    sensor: str
    is_unusual: bool
    target_rate: Optional[float]
    p90_rate: Optional[float]
    status: str
    reason: str = ""


@dataclass
class NormalSeason:
    """
    Normal season definition — frozen before outcome inspection.

    start_month / end_month: first and last calendar months of the season
        (inclusive, 1-indexed), or None when the season cannot be determined.
    peak_month: calendar month with the highest median rate, or None.
    status: 'available' | 'insufficient_baseline' | 'no_peak'
    """

    sensor: str
    start_month: Optional[int]
    end_month: Optional[int]
    peak_month: Optional[int]
    status: str
    reasons: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _nearest_rank_percentile(sorted_values: list[float], p: float) -> float:
    """
    Nearest-rank percentile.  p in [0, 100].
    rank = ceil(p/100 * n), 1-indexed; return sorted_values[rank-1].
    Requires len(sorted_values) >= 1.
    """
    n = len(sorted_values)
    rank = math.ceil(p / 100.0 * n)
    rank = max(1, min(rank, n))  # clamp to valid range
    return sorted_values[rank - 1]


def _lower_median(sorted_values: list[float]) -> float:
    """
    Lower median of a non-empty sorted list.
    For even n: sorted[(n//2) - 1]  (lower of the two middle values).
    For odd  n: sorted[n//2].
    For n=1:    sorted[0].
    """
    n = len(sorted_values)
    if n == 1:
        return sorted_values[0]
    if n % 2 == 0:
        return sorted_values[n // 2 - 1]
    return sorted_values[n // 2]


# ---------------------------------------------------------------------------
# Core baseline computation
# ---------------------------------------------------------------------------
def compute_month_baseline(
    calendar_month: int,
    target_year: int,
    all_obs: list[PeriodObs],
    config: BaselineConfig,
) -> MonthBaseline:
    """
    Compute the seasonal baseline for one calendar month in one sensor era.

    Parameters
    ----------
    calendar_month:
        Calendar month (1-12) for which to compute the baseline.
    target_year:
        The year being assessed.  Excluded from the baseline along with
        all later years.
    all_obs:
        All monthly PeriodObs for this sensor, any year, any month.
        The function filters to the correct month and eligible years.
    config:
        Frozen baseline parameters.

    Returns
    -------
    MonthBaseline with status AVAILABLE when n >= config.min_years,
    INSUFFICIENT_BASELINE when 0 < n < min_years, or NO_AVAILABLE_YEARS
    when no eligible year has usable observations for this month.
    """
    reasons: list[str] = []

    # Filter: correct sensor, correct month, eligible year range, before target
    eligible_obs = [
        o for o in all_obs
        if o.sensor == config.sensor
        and o.month == calendar_month
        and config.eligible_start_year <= o.year < target_year
        and o.year <= config.eligible_end_year
    ]

    # Group by year — one rate per eligible year
    years_seen: dict[int, list[PeriodObs]] = {}
    for o in eligible_obs:
        years_seen.setdefault(o.year, []).append(o)

    # Compute per-year pooled rate; skip years with no available obs
    per_year_rates: list[tuple[int, float]] = []
    for yr, yr_obs in sorted(years_seen.items()):
        r = pooled_rate(yr_obs)
        if r is not None:
            per_year_rates.append((yr, r))
        # Years where every obs has O=0 or is_partial are silently skipped;
        # they are not counted in n and do not widen the baseline.

    n = len(per_year_rates)
    eligible_years = [yr for yr, _ in per_year_rates]
    rates = [r for _, r in per_year_rates]

    if n == 0:
        reasons.append(
            f"No eligible years with usable observations (O > 0) for "
            f"sensor={config.sensor}, month={calendar_month}, "
            f"target_year={target_year}."
        )
        return MonthBaseline(
            calendar_month=calendar_month,
            sensor=config.sensor,
            median_rate=None,
            p90_rate=None,
            n_years=0,
            eligible_years=[],
            status=BaselineStatus.NO_AVAILABLE_YEARS,
            reasons=reasons,
        )

    if n < config.min_years:
        reasons.append(
            f"Only {n} eligible year(s) available; minimum required is "
            f"{config.min_years}.  Baseline is INSUFFICIENT for "
            f"sensor={config.sensor}, month={calendar_month}, "
            f"target_year={target_year}.  "
            f"Available years: {eligible_years}."
        )
        return MonthBaseline(
            calendar_month=calendar_month,
            sensor=config.sensor,
            median_rate=None,
            p90_rate=None,
            n_years=n,
            eligible_years=eligible_years,
            status=BaselineStatus.INSUFFICIENT_BASELINE,
            reasons=reasons,
        )

    sorted_rates = sorted(rates)
    median = _lower_median(sorted_rates)
    p90 = _nearest_rank_percentile(sorted_rates, 90.0)

    return MonthBaseline(
        calendar_month=calendar_month,
        sensor=config.sensor,
        median_rate=median,
        p90_rate=p90,
        n_years=n,
        eligible_years=eligible_years,
        status=BaselineStatus.AVAILABLE,
        reasons=[],
    )


# ---------------------------------------------------------------------------
# Unusual-period labeling
# ---------------------------------------------------------------------------
def label_unusual(
    target_obs: list[PeriodObs],
    target_year: int,
    calendar_month: int,
    baseline: MonthBaseline,
) -> UnusualLabel:
    """
    Label whether a target year/month is unusual relative to its baseline.

    Unusual means the target rate is STRICTLY above the 90th-percentile
    threshold.  A rate equal to the threshold is NOT unusual (spec §3A).

    If the baseline is unavailable or the target has O = 0, the label
    is not assigned and the status explains why.

    Parameters
    ----------
    target_obs:
        Monthly PeriodObs for the target year and month (same sensor).
        May be a list with multiple spatial blocks (they will be pooled).
    target_year:
        Year being assessed.
    calendar_month:
        Month being assessed.
    baseline:
        Pre-computed MonthBaseline for this month/sensor.
    """
    sensor = baseline.sensor

    # Filter target obs to available records for this year/month/sensor
    relevant = [
        o for o in target_obs
        if o.sensor == sensor
        and o.year == target_year
        and o.month == calendar_month
    ]

    target_rate = pooled_rate(relevant)

    # Baseline must be available
    if baseline.status != BaselineStatus.AVAILABLE:
        return UnusualLabel(
            calendar_month=calendar_month,
            target_year=target_year,
            sensor=sensor,
            is_unusual=False,
            target_rate=target_rate,
            p90_rate=None,
            status="baseline_unavailable",
            reason=(
                f"Baseline is {baseline.status.value} for "
                f"sensor={sensor}, month={calendar_month}.  "
                "Cannot assign unusual label."
            ),
        )

    # Target must be available
    if target_rate is None:
        return UnusualLabel(
            calendar_month=calendar_month,
            target_year=target_year,
            sensor=sensor,
            is_unusual=False,
            target_rate=None,
            p90_rate=baseline.p90_rate,
            status="target_unavailable",
            reason=(
                f"Target rate for {sensor} {target_year}-{calendar_month:02d} "
                "is unavailable (O = 0 or no usable observations).  "
                "Cannot assign unusual label."
            ),
        )

    p90 = baseline.p90_rate  # type: ignore[assignment]
    is_unusual = target_rate > p90  # strictly above; ties are not unusual

    return UnusualLabel(
        calendar_month=calendar_month,
        target_year=target_year,
        sensor=sensor,
        is_unusual=is_unusual,
        target_rate=target_rate,
        p90_rate=p90,
        status="labeled",
        reason="",
    )


# ---------------------------------------------------------------------------
# Normal-season derivation
# ---------------------------------------------------------------------------
def derive_normal_season(
    all_baselines: dict[int, MonthBaseline],
    config: BaselineConfig,
) -> NormalSeason:
    """
    Derive the normal season from the 12 monthly baselines.

    Algorithm (frozen, applied before outcome inspection):
      1. Find the calendar month with the highest median rate among
         months whose baseline is AVAILABLE.  That is the peak month.
      2. Months qualify for the normal season if their median rate is
         >= config.normal_season_threshold_fraction * peak_median.
      3. The normal season is the contiguous run of qualifying months
         that includes the peak month.  Month adjacency wraps around
         the year end (month 12 is adjacent to month 1).
      4. If no peak can be identified, or no qualifying run includes the
         peak, status is 'no_peak'.

    Parameters
    ----------
    all_baselines:
        Dict mapping calendar_month (1-12) to MonthBaseline for this sensor.
        May be incomplete; missing months are treated as unavailable.
    config:
        Frozen parameters including normal_season_threshold_fraction.

    Returns
    -------
    NormalSeason with start_month, end_month, peak_month when available.
    """
    reasons: list[str] = []

    # Collect available median rates
    available: dict[int, float] = {}
    for m in range(1, 13):
        bl = all_baselines.get(m)
        if bl is not None and bl.status == BaselineStatus.AVAILABLE and bl.median_rate is not None:
            available[m] = bl.median_rate

    if not available:
        reasons.append(
            "No calendar month has an available baseline; "
            "normal season cannot be determined."
        )
        return NormalSeason(
            sensor=config.sensor,
            start_month=None,
            end_month=None,
            peak_month=None,
            status="insufficient_baseline",
            reasons=reasons,
        )

    # Find peak month (highest median; ties broken by lower month number)
    peak_month = min(available, key=lambda m: (-available[m], m))
    peak_median = available[peak_month]

    threshold = config.normal_season_threshold_fraction * peak_median

    # Qualifying months: median >= threshold
    qualifying: set[int] = {m for m, r in available.items() if r >= threshold}

    if peak_month not in qualifying:
        reasons.append(
            f"Peak month {peak_month} does not meet its own threshold "
            "(threshold fraction may be > 1.0, which is a configuration error)."
        )
        return NormalSeason(
            sensor=config.sensor,
            start_month=None,
            end_month=None,
            peak_month=peak_month,
            status="no_peak",
            reasons=reasons,
        )

    # Find the contiguous run including peak_month (wrap-around allowed)
    # Walk outward from peak_month in both directions
    season_months: set[int] = {peak_month}
    # Walk backward
    m = peak_month
    for _ in range(11):
        prev = 12 if m == 1 else m - 1
        if prev in qualifying:
            season_months.add(prev)
            m = prev
        else:
            break
    # Walk forward
    m = peak_month
    for _ in range(11):
        nxt = 1 if m == 12 else m + 1
        if nxt in qualifying:
            season_months.add(nxt)
            m = nxt
        else:
            break

    # Express as start/end month (non-wrapping if possible; wrap if season
    # crosses year boundary).
    sorted_months = sorted(season_months)
    # Check for year-boundary wrap: gaps in sorted list indicate a wrap
    is_contiguous = all(
        sorted_months[i + 1] - sorted_months[i] == 1
        for i in range(len(sorted_months) - 1)
    )
    if is_contiguous:
        start_month = sorted_months[0]
        end_month = sorted_months[-1]
    else:
        # Wrap: season straddles Dec→Jan
        # start = first month after the gap, end = last month before the gap
        gaps = [
            i for i in range(len(sorted_months) - 1)
            if sorted_months[i + 1] - sorted_months[i] > 1
        ]
        # There should be exactly one gap for a simple wrap
        if len(gaps) == 1:
            g = gaps[0]
            start_month = sorted_months[g + 1]
            end_month = sorted_months[g]
        else:
            # Multiple gaps — season is fragmented; take the run containing peak
            start_month = peak_month
            end_month = peak_month
            reasons.append(
                "Season months are non-contiguous with multiple gaps; "
                "season reduced to peak month only."
            )

    return NormalSeason(
        sensor=config.sensor,
        start_month=start_month,
        end_month=end_month,
        peak_month=peak_month,
        status="available",
        reasons=reasons,
    )
