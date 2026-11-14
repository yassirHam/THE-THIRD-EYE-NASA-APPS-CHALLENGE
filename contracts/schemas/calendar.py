"""
THE THIRD EYE — Calendar Schema Contract
Governs monthly & weekly same-sensor fire calendar, seasonal baseline,
and observation accounting per THE_THIRD_EYE_FINAL_PLAN_GEOGRAPHIC_ACCESS_UPDATED.txt.
"""
from typing import List, Optional, Literal
from pydantic import BaseModel, Field

class DayCellRecord(BaseModel):
    """Daily 1-km cell observation state."""
    date: str = Field(..., description="UTC ISO date YYYY-MM-DD")
    detected_fire_cell_days: float = Field(..., ge=0.0, description="D: fire-cell-days count")
    usable_land_cell_days: float = Field(..., ge=0.0, description="O: usable clear land cell-days count")
    fire_activity_index: Optional[float] = Field(None, description="(D / O) * 1000 if O > 0, else None")
    is_missing_observation: bool = Field(False, description="True if O == 0 or satellite swath omitted")
    sensor: Literal["MODIS_Aqua", "VIIRS_SNPP", "VIIRS_NOAA20"]

class WeekRecord(BaseModel):
    """Weekly same-sensor record."""
    year: int
    week_number: int = Field(..., ge=1, le=53, description="ISO week number or fixed 7-day bin")
    start_date: str
    end_date: str
    detected_fire_cell_days: float
    usable_land_cell_days: float
    fire_activity_index: Optional[float]
    is_critical_week: bool = Field(False, description="Registered busiest week of typical year")
    is_unusual_week: bool = Field(False, description="Above registered same-calendar-window percentile")
    sensor: Literal["MODIS_Aqua", "VIIRS_SNPP", "VIIRS_NOAA20"]

class MonthRecord(BaseModel):
    """Monthly same-sensor record."""
    year: int
    month: int = Field(..., ge=1, le=12)
    detected_fire_cell_days: float
    usable_land_cell_days: float
    fire_activity_index: Optional[float]
    baseline_median: Optional[float] = Field(None, description="Same-month historical reference median rate")
    baseline_p90: Optional[float] = Field(None, description="Same-month 90th percentile threshold")
    is_unusual_month: bool = Field(False, description="Rate strictly above 90th percentile threshold")
    is_partial_month: bool = Field(False, description="True for Nov 2026 due to S-NPP cessation on Nov 2, 2026")
    is_unavailable: bool = Field(False, description="True if usable support O is insufficient")
    sensor: Literal["MODIS_Aqua", "VIIRS_SNPP", "VIIRS_NOAA20"]

class SeasonalBaselineInfo(BaseModel):
    """Registered seasonal baseline metadata."""
    reference_start_year: int
    reference_end_year: int
    eligible_prior_years_count: int
    normal_season_start_month: int
    normal_season_end_month: int
    peak_median_month: int

class CalendarArtifact(BaseModel):
    """Root calendar schema exported as versioned JSON."""
    artifact_version: str = Field(..., description="Semantic or content-addressed artifact hash")
    geometry_id: str = Field(..., description="Immutable canonical region hash")
    region_name: str
    start_year: int = 2003
    end_year: int = 2026
    snpp_cessation_date: str = "2026-11-02T15:40:00Z"
    seasonal_baseline: SeasonalBaselineInfo
    monthly_records: List[MonthRecord]
    weekly_records: Optional[List[WeekRecord]] = None
