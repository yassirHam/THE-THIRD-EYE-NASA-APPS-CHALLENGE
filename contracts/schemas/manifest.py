"""Static artifact provenance and partition manifest contracts."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal

from pydantic import Field, model_validator

from .common import ArtifactIdentity, SensorType, StrictContractModel


class GeoJsonPolygon(StrictContractModel):
    type: Literal["Polygon"] = "Polygon"
    coordinates: list[list[list[float]]] = Field(min_length=1)


class SourceCollection(StrictContractModel):
    collection_id: str = Field(min_length=1)
    sensor: SensorType
    source_version: str = Field(min_length=1)
    record_end_date: str | None = None


class PartitionFileRecord(StrictContractModel):
    file_path: str = Field(min_length=1)
    geometry_id: str = Field(min_length=1)
    period_spec: str = Field(min_length=1)
    method_id: str = Field(min_length=1)
    policy_id: str = Field(min_length=1)
    sensor: SensorType
    row_count: int = Field(ge=0)
    file_size_bytes: int = Field(ge=0)
    cache_key_sha256: str = Field(pattern=r"^tte-cache-v1:[0-9a-f]{64}$")
    sha256_checksum: str = Field(pattern=r"^[0-9a-f]{64}$")
    coverage_status: Literal["complete", "partial", "unavailable"]


class ProvenanceManifest(ArtifactIdentity):
    manifest_version: str = Field(min_length=1)
    generated_at: datetime
    snpp_cessation_date: Literal["2026-11-02"] = "2026-11-02"
    canonical_boundary: GeoJsonPolygon
    boundary_source: str = Field(min_length=1)
    boundary_version: str = Field(min_length=1)
    crs: str = Field(min_length=1)
    grid_inclusion_rule: str = Field(min_length=1)
    source_collections: list[SourceCollection] = Field(min_length=1)
    total_file_size_bytes: int = Field(ge=0)
    compressed_bundle_size_bytes: int = Field(ge=0)
    partitions: list[PartitionFileRecord] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_manifest(self) -> "ProvenanceManifest":
        if self.generated_at.tzinfo is None or self.generated_at.utcoffset() != timezone.utc.utcoffset(self.generated_at):
            raise ValueError("manifest timestamp must be UTC")
        if self.compressed_bundle_size_bytes > self.total_file_size_bytes:
            raise ValueError("compressed size cannot exceed total uncompressed size")
        for partition in self.partitions:
            key = (
                partition.geometry_id,
                partition.period_spec,
                partition.method_id,
                partition.policy_id,
            )
            expected = (self.geometry_id, self.period_spec, self.method_id, self.policy_id)
            if key != expected:
                raise ValueError("partition identity must match manifest compound identity")
            if partition.cache_key_sha256 != self.cache_key().digest():
                raise ValueError("partition cache key must be the digest of the five-field identity")
        return self
