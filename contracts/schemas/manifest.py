"""Static artifact provenance and partition manifest contracts."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal

from pydantic import Field, model_validator

from .common import CACHE_KEY_FIELDS, ArtifactIdentity, CacheKeyMismatch, SensorType, StrictContractModel

# The artifact family a manifest describes. The manifest's five-field identity IS the described
# artifact's identity (P3 concern on calendar vs manifest method_id): a manifest for a calendar
# carries the calendar's method_id, never a separate "artifact_manifest" method.
DescribedArtifactType = Literal[
    "calendar",
    "comparison",
    "claim_audit",
    "evaluation",
    "region_selector",
    "firms_hotspots",
]


class GeoJsonPolygon(StrictContractModel):
    type: Literal["Polygon"] = "Polygon"
    coordinates: list[list[list[float]]] = Field(min_length=1)


class SourceCollection(StrictContractModel):
    collection_id: str = Field(min_length=1)
    sensor: SensorType
    source_version: str = Field(min_length=1)
    record_end_date: str | None = None


class PartitionFileRecord(StrictContractModel):
    """One file of the described artifact, relative to the bundle root.

    sensor: the single sensor of a per-sensor file, or null (required key) when the file
    holds several same-sensor series (a calendar) or is not sensor data (comparison,
    evaluation, selector, FIRMS view). Null never means a merged cross-sensor series.
    coverage_status: footprint coverage of the data in this file. "unverified" (1.5.0) is
    used whenever P2 has not certified the footprint; it is never upgraded to complete.
    """

    file_path: str = Field(min_length=1)
    geometry_id: str = Field(min_length=1)
    period_spec: str = Field(min_length=1)
    method_id: str = Field(min_length=1)
    policy_id: str = Field(min_length=1)
    sensor: SensorType | None
    row_count: int = Field(ge=0)
    file_size_bytes: int = Field(ge=0)
    cache_key_sha256: str = Field(pattern=r"^tte-cache-v1:[0-9a-f]{64}$")
    sha256_checksum: str = Field(pattern=r"^[0-9a-f]{64}$")
    coverage_status: Literal["complete", "partial", "unavailable", "unverified"]


class ProvenanceManifest(ArtifactIdentity):
    manifest_version: str = Field(min_length=1)
    described_artifact_type: DescribedArtifactType
    generated_at: datetime
    snpp_cessation_date: Literal["2026-11-02"] = "2026-11-02"
    # P2 r8 item 3: inactive unless a listed S-NPP source reaches the cessation date.
    snpp_cutoff_status: Literal["active", "reserved_inactive"]
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
        reaches = any(
            c.sensor == "VIIRS_SNPP" and c.record_end_date is not None and c.record_end_date >= self.snpp_cessation_date
            for c in self.source_collections
        )
        if self.snpp_cutoff_status != ("active" if reaches else "reserved_inactive"):
            raise ValueError("snpp_cutoff_status must reflect whether listed S-NPP data reach the cessation date")
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


class ManifestBindingError(CacheKeyMismatch):
    """Raised when a manifest is offered for an artifact it does not describe."""


def assert_manifest_describes(
    manifest: ProvenanceManifest, artifact: ArtifactIdentity, artifact_type: str
) -> None:
    """Bind a manifest to one artifact: same family and all five identity fields equal.

    A manifest whose partitions list a calendar file but whose method_id differs from the
    calendar's method_id does not describe that calendar and must not be used for it.
    """
    if manifest.described_artifact_type != artifact_type:
        raise ManifestBindingError(
            f"manifest describes {manifest.described_artifact_type}, not {artifact_type}"
        )
    differing = [n for n in CACHE_KEY_FIELDS if getattr(manifest, n) != getattr(artifact, n)]
    if differing:
        raise ManifestBindingError(f"manifest identity differs from the artifact on: {', '.join(differing)}")
    if manifest.data_classification != artifact.data_classification:
        raise ManifestBindingError("manifest and artifact differ in data classification")
    # A manifest cannot claim more coverage than the calendar's own footprint certification.
    cert = getattr(artifact, "footprint_certification", None)
    if artifact_type == "calendar":
        allowed = {"complete": "complete", "partial": "partial"}.get(cert.status if cert else "", "unverified")
        for part in manifest.partitions:
            if part.coverage_status != allowed:
                raise ManifestBindingError(
                    f"partition {part.file_path} claims {part.coverage_status}; the calendar's footprint "
                    f"certification allows only {allowed}")
