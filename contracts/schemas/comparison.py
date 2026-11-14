"""Stage A calibration comparison and independent status dimensions."""

from __future__ import annotations

import math
from typing import Literal

from pydantic import Field, model_validator

from .common import ArtifactIdentity, StrictContractModel

SensitivityStatus = Literal[
    "stable_across_displayed_settings",
    "sensitive_to_assumptions",
    "unavailable",
]
ApplicabilityStatus = Literal[
    "applicable",
    "failed_applicability",
    "missing_required_support",
    "out_of_domain",
]
InferenceStatus = Literal["not_established"]
PracticalChangeCategory = Literal[
    "meaningful_increase",
    "meaningful_decrease",
    "within_practical_margin",
    "unspecified",
    "unavailable",
]
Direction = Literal["increase", "decrease", "no_change"]
HeadlineDirection = Literal["increase", "decrease", "no_change", "ambiguous", "unavailable"]
ApplicabilityCheckStatus = Literal["passed", "failed", "missing", "out_of_domain"]
OutputCategory = Literal[
    "consistent_across_tested_corrections",
    "depends_on_the_correction",
    "not_enough_usable_evidence",
    "outside_evaluated_calibration",
    "calibration_check_failed",
]
StatusLabel = Literal[
    "Consistent across tested corrections",
    "Depends on the correction",
    "Not enough usable evidence",
    "Outside evaluated calibration",
    "Calibration check failed",
]


class CalibrationFactorVariant(StrictContractModel):
    variant_id: str = Field(min_length=1)
    factor_value: float = Field(gt=0.0)
    factor_type: Literal["own_support_a_H", "common_support_a_C"]
    training_years: list[int] = Field(min_length=1)
    effect_delta: float
    direction: Direction

    @model_validator(mode="after")
    def validate_direction(self) -> "CalibrationFactorVariant":
        expected: Direction = "increase" if self.effect_delta > 0 else "decrease" if self.effect_delta < 0 else "no_change"
        if self.direction != expected:
            raise ValueError("variant direction must match the full-precision effect delta")
        if len(set(self.training_years)) != len(self.training_years):
            raise ValueError("training years must be unique")
        return self


class ApplicabilityCheck(StrictContractModel):
    check_id: str = Field(min_length=1)
    status: ApplicabilityCheckStatus
    detail: str = Field(min_length=1)
    evidence_version: str | None = None


class PracticalChange(StrictContractModel):
    category: PracticalChangeCategory
    magnitude: float | None = Field(default=None, ge=0.0)
    effect_units: str | None = None
    practical_margin_tau: float | None = Field(default=None, ge=0.0)
    observed_signs: list[Direction] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_practical_change(self) -> "PracticalChange":
        if self.category in {"unavailable"}:
            if self.magnitude is not None or self.effect_units is not None or self.practical_margin_tau is not None:
                raise ValueError("unavailable practical change cannot publish magnitude, units, or margin")
            return self
        if self.magnitude is None or self.effect_units is None:
            raise ValueError("available practical change requires magnitude and effect units")
        if self.category == "unspecified" and self.practical_margin_tau is not None:
            raise ValueError("unspecified practical importance cannot carry a margin")
        if self.category != "unspecified" and self.practical_margin_tau is None:
            raise ValueError("practical categories require a preregistered nonnegative margin")
        return self


class ReviewedTemplateSummary(StrictContractModel):
    template_id: str = Field(min_length=1)
    template_version: str = Field(min_length=1)
    generated_by: Literal["reviewed_deterministic_template"] = "reviewed_deterministic_template"
    output_category: OutputCategory
    status_label: StatusLabel
    finding_sentence: str = Field(min_length=1)
    limit_sentence: str = Field(min_length=1)

    @model_validator(mode="after")
    def validate_label_pair(self) -> "ReviewedTemplateSummary":
        expected = {
            "consistent_across_tested_corrections": "Consistent across tested corrections",
            "depends_on_the_correction": "Depends on the correction",
            "not_enough_usable_evidence": "Not enough usable evidence",
            "outside_evaluated_calibration": "Outside evaluated calibration",
            "calibration_check_failed": "Calibration check failed",
        }[self.output_category]
        if self.status_label != expected:
            raise ValueError("plain status label must match the deterministic output category")
        return self


class ComparisonResult(ArtifactIdentity):
    sensitivity_status: SensitivityStatus
    applicability_status: ApplicabilityStatus
    inference_status: InferenceStatus = "not_established"
    practical_change: PracticalChange
    headline_direction: HeadlineDirection
    required_variant_ids: list[str] = Field(min_length=1)
    registered_variants: list[CalibrationFactorVariant]
    applicability_checks: list[ApplicabilityCheck] = Field(min_length=1)
    missing_evidence_reasons: list[str] = Field(default_factory=list)
    conclusion_eligible: bool
    reviewed_summary: ReviewedTemplateSummary

    @model_validator(mode="after")
    def validate_independent_statuses(self) -> "ComparisonResult":
        required = set(self.required_variant_ids)
        if len(required) != len(self.required_variant_ids):
            raise ValueError("required variant IDs must be unique")
        supplied_ids = [variant.variant_id for variant in self.registered_variants]
        if len(supplied_ids) != len(set(supplied_ids)):
            raise ValueError("registered variant IDs must be unique")
        supplied = set(supplied_ids)

        if self.sensitivity_status == "unavailable":
            if not self.missing_evidence_reasons or required.issubset(supplied):
                raise ValueError("unavailable sensitivity requires a missing required variant and reason")
        elif not required.issubset(supplied):
            raise ValueError("available sensitivity requires every registered variant")

        check_states = {check.status for check in self.applicability_checks}
        expected_check = {
            "applicable": "passed",
            "failed_applicability": "failed",
            "missing_required_support": "missing",
            "out_of_domain": "out_of_domain",
        }[self.applicability_status]
        if expected_check not in check_states:
            raise ValueError("overall applicability must be supported by a matching check state")
        if self.applicability_status == "applicable" and check_states != {"passed"}:
            raise ValueError("applicable requires every applicability check to pass")

        expected_output = {
            "failed_applicability": "calibration_check_failed",
            "missing_required_support": "not_enough_usable_evidence",
            "out_of_domain": "outside_evaluated_calibration",
        }.get(self.applicability_status)
        if expected_output is None:
            expected_output = (
                "not_enough_usable_evidence"
                if self.sensitivity_status == "unavailable"
                else "depends_on_the_correction"
                if self.sensitivity_status == "sensitive_to_assumptions"
                else "consistent_across_tested_corrections"
            )
        if self.reviewed_summary.output_category != expected_output:
            raise ValueError("reviewed summary must preserve sensitivity and applicability status")

        eligible = self.applicability_status == "applicable" and self.sensitivity_status != "unavailable"
        if self.conclusion_eligible != eligible:
            raise ValueError("conclusion eligibility must preserve missing/failed/out-of-domain distinctions")
        if not eligible and self.headline_direction not in {"ambiguous", "unavailable"}:
            raise ValueError("ineligible comparisons cannot publish a directional headline")

        if self.practical_change.category == "within_practical_margin":
            tau = self.practical_change.practical_margin_tau
            if tau is None or any(abs(v.effect_delta) > tau for v in self.registered_variants):
                raise ValueError("within-margin requires every supplied variant to fall within tau")
            expected_magnitude = max((abs(v.effect_delta) for v in self.registered_variants), default=0.0)
            if not math.isclose(self.practical_change.magnitude or 0.0, expected_magnitude, rel_tol=1e-12, abs_tol=1e-12):
                raise ValueError("within-margin magnitude must be the maximum absolute supplied effect")
        return self
