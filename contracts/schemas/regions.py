"""Selectable geography and geographic-access contracts."""

from __future__ import annotations

from typing import Literal

from pydantic import Field, model_validator

from .common import ArtifactIdentity, StrictContractModel

RawDataStatus = Literal["available", "unavailable"]
ComparisonAccessStatus = Literal[
    "raw_only",
    "candidate_calibration",
    "evaluated_comparison",
    "unavailable",
]
GeometryRole = Literal["primary_region", "backup_region", "predeclared_sub_area"]
GeometryUnavailableReason = Literal[
    "no_complete_extract",
    "unsupported_geometry",
    "incomplete_footprint",
    "qa_unusable",
    "request_limit",
]


class RegionSelectorOption(StrictContractModel):
    geometry_id: str = Field(min_length=1)
    display_name: str = Field(min_length=1)
    geometry_role: GeometryRole
    boundary_source: str = Field(min_length=1)
    boundary_version: str = Field(min_length=1)
    crs: str = Field(min_length=1)
    grid_inclusion_rule: str = Field(min_length=1)
    raw_data_status: RawDataStatus
    comparison_access_status: ComparisonAccessStatus
    unavailable_reason: GeometryUnavailableReason | None = None
    evaluated_method_id: str | None = None
    evaluated_policy_id: str | None = None
    evaluated_period_spec: str | None = None

    @model_validator(mode="after")
    def validate_access_state(self) -> "RegionSelectorOption":
        evaluated_fields = (
            self.evaluated_method_id,
            self.evaluated_policy_id,
            self.evaluated_period_spec,
        )
        if self.raw_data_status == "unavailable":
            if self.comparison_access_status != "unavailable" or self.unavailable_reason is None:
                raise ValueError("unavailable raw data requires an unavailable comparison and reason")
        elif self.unavailable_reason is not None:
            raise ValueError("available raw data cannot carry a geometry unavailable reason")
        if self.comparison_access_status == "evaluated_comparison":
            if any(value is None for value in evaluated_fields):
                raise ValueError("evaluated comparison access requires its exact method, policy, and period")
        elif any(value is not None for value in evaluated_fields):
            raise ValueError("only evaluated comparison access may reference evaluated contract identity")
        return self


class RegionSelectorArtifact(ArtifactIdentity):
    options: list[RegionSelectorOption] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_options(self) -> "RegionSelectorArtifact":
        ids = [option.geometry_id for option in self.options]
        if len(ids) != len(set(ids)):
            raise ValueError("selector geometry IDs must be unique")
        if self.geometry_id not in ids:
            raise ValueError("artifact geometry must be one of the selector options")
        return self
