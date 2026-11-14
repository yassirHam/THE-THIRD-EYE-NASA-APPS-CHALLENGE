"""Downloadable claim audit record and deterministic summary contract."""

from __future__ import annotations

from pydantic import Field

from .common import ArtifactIdentity
from .comparison import (
    ApplicabilityStatus,
    InferenceStatus,
    PracticalChange,
    ReviewedTemplateSummary,
    SensitivityStatus,
)


class ClaimAuditRecord(ArtifactIdentity):
    record_id: str = Field(min_length=1)
    statement: str = Field(min_length=1)
    analyst_entity: str | None = None
    target_region: str = Field(min_length=1)
    date_range_tested: str = Field(min_length=1)
    dataset_versions: list[str] = Field(min_length=1)
    formulas_applied: list[str] = Field(min_length=1)
    sensitivity_status: SensitivityStatus
    applicability_status: ApplicabilityStatus
    inference_status: InferenceStatus = "not_established"
    practical_change: PracticalChange
    reviewed_summary: ReviewedTemplateSummary
    counterexample_interpretations: list[dict[str, object]] = Field(default_factory=list)
    reproducibility_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    verification_steps: list[str] = Field(min_length=1)
    evidence_artifact_versions: list[str] = Field(min_length=1)
