"""Downloadable claim audit record and deterministic summary contract."""

from __future__ import annotations

from pydantic import Field, model_validator

from .common import ArtifactIdentity
from .comparison import (
    ApplicabilityCheck,
    ApplicabilityStatus,
    InferenceStatus,
    PracticalChange,
    ReviewedTemplateSummary,
    SensitivityStatus,
    check_applicability_consistency,
    expected_output_category,
    is_conclusion_eligible,
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
    applicability_checks: list[ApplicabilityCheck] = Field(min_length=1)
    missing_evidence_reasons: list[str] = Field(default_factory=list)
    conclusion_eligible: bool
    reviewed_summary: ReviewedTemplateSummary
    counterexample_interpretations: list[dict[str, object]] = Field(default_factory=list)
    reproducibility_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    verification_steps: list[str] = Field(min_length=1)
    evidence_artifact_versions: list[str] = Field(min_length=1)

    @model_validator(mode="after")
    def preserve_applicability_distinctions(self) -> "ClaimAuditRecord":
        check_applicability_consistency(self.applicability_status, self.applicability_checks)
        complete = not bool(self.missing_evidence_reasons) and self.applicability_status != "missing_required_support"
        if self.reviewed_summary.output_category != expected_output_category(
            self.applicability_status, self.sensitivity_status, complete=complete
        ):
            raise ValueError(
                "summary must preserve failed, missing, and out-of-domain applicability states"
            )
        if self.conclusion_eligible != is_conclusion_eligible(
            self.applicability_status, self.sensitivity_status, complete=complete
        ):
            raise ValueError("conclusion eligibility must follow applicability and sensitivity")
        if self.sensitivity_status == "unavailable":
            if not self.missing_evidence_reasons or self.practical_change.category != "unavailable":
                raise ValueError("unavailable sensitivity requires reasons and no practical category")
        elif self.practical_change.category == "unavailable":
            if not self.missing_evidence_reasons:
                raise ValueError("practical change cannot be unavailable when sensitivity is available unless evidence is missing")
        return self
