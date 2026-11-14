"""Package initialization."""
from science.calendar.baseline import (
    BaselineConfig,
    BaselineStatus,
    MonthBaseline,
    NormalSeason,
    UnusualLabel,
    compute_month_baseline,
    compute_week_baseline,
    derive_normal_season,
    label_unusual,
    label_unusual_week,
)
from science.calendar.rates import (
    CutoffStatus,
    PeriodObs,
    RateStatus,
    SNPP_CESSATION,
    SNPP_CESSATION_UTC,
    SNPP_LAST_COMPLETE_MONTH,
    SensorID,
    PolicyID,
    compute_rate,
    period_bounds_utc,
    pooled_rate,
)

__all__ = [
    # rates
    "CutoffStatus",
    "PeriodObs",
    "RateStatus",
    "SNPP_CESSATION",
    "SNPP_CESSATION_UTC",
    "SNPP_LAST_COMPLETE_MONTH",
    "SensorID",
    "PolicyID",
    "compute_rate",
    "period_bounds_utc",
    "pooled_rate",
    # baseline
    "BaselineConfig",
    "BaselineStatus",
    "MonthBaseline",
    "NormalSeason",
    "UnusualLabel",
    "compute_month_baseline",
    "compute_week_baseline",
    "derive_normal_season",
    "label_unusual",
    "label_unusual_week",
]
