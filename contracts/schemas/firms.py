"""FIRMS link and point contracts, isolated from gridded D/O science."""

from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Literal

from pydantic import Field, HttpUrl, model_validator

from .common import ArtifactIdentity, StrictContractModel

FirmsPlatform = Literal["MODIS", "VIIRS_SNPP", "VIIRS_NOAA20", "VIIRS_NOAA21"]


class BoundingBox(StrictContractModel):
    west: float = Field(ge=-180.0, le=180.0)
    south: float = Field(ge=-90.0, le=90.0)
    east: float = Field(ge=-180.0, le=180.0)
    north: float = Field(ge=-90.0, le=90.0)

    @model_validator(mode="after")
    def validate_bounds(self) -> "BoundingBox":
        if self.west >= self.east or self.south >= self.north:
            raise ValueError("bounding box edges must be ordered")
        return self


class FirmsHotspotLink(StrictContractModel):
    url: HttpUrl
    selected_area: BoundingBox
    start_date: date
    end_date: date
    manual_selection_required: bool
    limitation: str = Field(min_length=1)

    @model_validator(mode="after")
    def validate_dates(self) -> "FirmsHotspotLink":
        if self.end_date < self.start_date:
            raise ValueError("FIRMS link end date must not precede start date")
        return self


class FirmsHotspotPoint(StrictContractModel):
    point_id: str = Field(min_length=1)
    latitude: float = Field(ge=-90.0, le=90.0)
    longitude: float = Field(ge=-180.0, le=180.0)
    acquired_at: datetime
    platform: FirmsPlatform
    confidence_label: str = Field(min_length=1)
    source_product: str = Field(min_length=1)

    @model_validator(mode="after")
    def require_utc_timestamp(self) -> "FirmsHotspotPoint":
        if self.acquired_at.tzinfo is None or self.acquired_at.utcoffset() != timezone.utc.utcoffset(self.acquired_at):
            raise ValueError("FIRMS acquisition timestamp must be UTC")
        return self


class FirmsHotspotArtifact(ArtifactIdentity):
    view_name: Literal["Reported hotspots"] = "Reported hotspots"
    measurement_unit: Literal["reported_detection_points"] = "reported_detection_points"
    processing_level: Literal["standard_archive"] = "standard_archive"
    confidence_filter: str = Field(min_length=1)
    firms_link: FirmsHotspotLink
    points: list[FirmsHotspotPoint]
    feeds_grid_math: Literal[False] = False
    inherits_grid_calibration: Literal[False] = False
    cross_sensor_trend_allowed: Literal[False] = False
    isolation_notice: Literal[
        "FIRMS points are separate from D, O, baselines, factors, and verdicts."
    ] = "FIRMS points are separate from D, O, baselines, factors, and verdicts."
