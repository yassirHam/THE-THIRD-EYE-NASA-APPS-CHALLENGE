"""Shared, frozen contract primitives for THE THIRD EYE."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

CONTRACT_VERSION = "1.0.0"
SYNTHETIC_FIXTURE_LABEL = "[SYNTHETIC DEV FIXTURE]"

SensorType = Literal["MODIS_Aqua", "VIIRS_SNPP", "VIIRS_NOAA20", "VIIRS_NOAA21"]
DataClassification = Literal["production", "synthetic_dev_fixture"]


class StrictContractModel(BaseModel):
    """Reject coercion and unknown fields, and prevent post-validation mutation."""

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        strict=True,
        str_strip_whitespace=False,
    )


class ArtifactIdentity(StrictContractModel):
    """Identity fields that prevent cross-area, cross-period, or cross-policy reuse."""

    contract_version: Literal["1.0.0"] = CONTRACT_VERSION
    artifact_version: str = Field(min_length=1)
    geometry_id: str = Field(min_length=1)
    period_spec: str = Field(min_length=1)
    method_id: str = Field(min_length=1)
    policy_id: str = Field(min_length=1)
    data_classification: DataClassification
    fixture_label: Literal["[SYNTHETIC DEV FIXTURE]"] | None = None

    @model_validator(mode="after")
    def require_visible_synthetic_label(self) -> "ArtifactIdentity":
        if self.data_classification == "synthetic_dev_fixture":
            if self.fixture_label != SYNTHETIC_FIXTURE_LABEL:
                raise ValueError("synthetic fixtures require the visible synthetic fixture label")
        elif self.fixture_label is not None:
            raise ValueError("production artifacts cannot carry a synthetic fixture label")
        return self
