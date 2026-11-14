"""Shared, frozen contract primitives for THE THIRD EYE."""

from __future__ import annotations

import hashlib
import json
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

CONTRACT_VERSION = "1.3.0"
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

    contract_version: Literal["1.3.0"] = CONTRACT_VERSION
    artifact_version: str = Field(min_length=1)
    geometry_id: str = Field(min_length=1)
    period_spec: str = Field(min_length=1)
    method_id: str = Field(min_length=1)
    policy_id: str = Field(min_length=1)
    data_classification: DataClassification
    fixture_label: Literal["[SYNTHETIC DEV FIXTURE]"] | None = None

    def cache_key(self) -> CacheKey:
        return CacheKey(**{name: getattr(self, name) for name in CACHE_KEY_FIELDS})

    @model_validator(mode="after")
    def require_visible_synthetic_label(self) -> "ArtifactIdentity":
        if self.data_classification == "synthetic_dev_fixture":
            if self.fixture_label != SYNTHETIC_FIXTURE_LABEL:
                raise ValueError("synthetic fixtures require the visible synthetic fixture label")
        elif self.fixture_label is not None:
            raise ValueError("production artifacts cannot carry a synthetic fixture label")
        return self


CACHE_KEY_FIELDS = ("artifact_version", "geometry_id", "period_spec", "method_id", "policy_id")
CACHE_KEY_PREFIX = "tte-cache-v1:"


class CacheKey(StrictContractModel):
    """The five-field compound identity. Equality of ALL five fields is required for reuse."""

    artifact_version: str = Field(min_length=1)
    geometry_id: str = Field(min_length=1)
    period_spec: str = Field(min_length=1)
    method_id: str = Field(min_length=1)
    policy_id: str = Field(min_length=1)

    def canonical(self) -> str:
        # JSON array of the fields in fixed order: unambiguous even if a value contains
        # delimiters such as "|" or ":".
        values = [getattr(self, name) for name in CACHE_KEY_FIELDS]
        return json.dumps(values, ensure_ascii=True, separators=(",", ":"))

    def digest(self) -> str:
        return CACHE_KEY_PREFIX + hashlib.sha256(self.canonical().encode("utf-8")).hexdigest()


class CacheKeyMismatch(ValueError):
    """Raised when a cached artifact is offered for a request with a different key."""


def assert_cache_key_match(requested: CacheKey, artifact: "ArtifactIdentity") -> None:
    """Reference enforcement for cache consumers (P4-A pipeline, P3 loader).

    Never reuse a factor, baseline, mask, or cache entry unless all five fields match.
    """
    actual = artifact.cache_key()
    if actual != requested:
        differing = [n for n in CACHE_KEY_FIELDS if getattr(actual, n) != getattr(requested, n)]
        raise CacheKeyMismatch(f"cache key mismatch on: {', '.join(differing)}")