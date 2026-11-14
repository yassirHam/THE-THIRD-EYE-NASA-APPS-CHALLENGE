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
    "inconsistent_across_variants",
    "unspecified",
    "unavailable",
]
Direction = Literal["increase", "decrease", "no_change"]
HeadlineDirection = Literal[
    "increase",
    "decrease",
    "within_practical_margin",
    "no_change",
    "ambiguous",
    "unavailable",
]
ApplicabilityCheckStatus = Literal["passed", "failed", "missing", "out_of_domain"]
OutputCategory = Literal[
    "consistent_across_tested_corrections",
    "depends_on_the_correction",
    "not_enough_usable_evidence",
    "outside_evaluated_calibration",
    "calibration_check_failed",
    "calibration_check_failed_and_missing_evidence",
]
StatusLabel = Literal[
    "Consistent across tested corrections",
    "Depends on the correction",
    "Not enough usable evidence",
    "Outside evaluated calibration",
    "Calibration check failed",
    "Calibration check failed and required evidence missing",
]


SUMMARY_LABELS: dict[str, str] = {
    "consistent_across_tested_corrections": "Consistent across tested corrections",
    "depends_on_the_correction": "Depends on the correction",
    "not_enough_usable_evidence": "Not enough usable evidence",
    "outside_evaluated_calibration": "Outside evaluated calibration",
    "calibration_check_failed": "Calibration check failed",
    "calibration_check_failed_and_missing_evidence": "Calibration check failed and required evidence missing",
}
_CHECK_FOR_APPLICABILITY = {
    "applicable": "passed",
    "failed_applicability": "failed",
    "missing_required_support": "missing",
    "out_of_domain": "out_of_domain",
}


def expected_output_category(applicability: str, sensitivity: str, complete: bool = True) -> str:
    """Failed, missing, and out-of-domain stay distinct; none is hidden under sensitivity."""
    if applicability == "failed_applicability":
        if not complete:
            return "calibration_check_failed_and_missing_evidence"
        return "calibration_check_failed"
    if not complete:
        return "not_enough_usable_evidence"
    fixed = {
        "missing_required_support": "not_enough_usable_evidence",
        "out_of_domain": "outside_evaluated_calibration",
    }.get(applicability)
    if fixed is not None:
        return fixed
    return {
        "unavailable": "not_enough_usable_evidence",
        "sensitive_to_assumptions": "depends_on_the_correction",
        "stable_across_displayed_settings": "consistent_across_tested_corrections",
    }[sensitivity]


def is_conclusion_eligible(applicability: str, sensitivity: str, complete: bool = True) -> bool:
    return complete and applicability == "applicable" and sensitivity != "unavailable"


def check_applicability_consistency(status: str, checks: "list[ApplicabilityCheck]") -> None:
    states = {check.status for check in checks}
    if _CHECK_FOR_APPLICABILITY[status] not in states:
        raise ValueError("overall applicability must be supported by a matching check state")
    if status == "applicable" and states != {"passed"}:
        raise ValueError("applicable requires every applicability check to pass")


def effect_category(delta: float, tau: float | None) -> str:
    """Frozen Stage A rule: Delta > tau increase, Delta < -tau decrease, else within margin.

    With no registered margin, only the sign is compared (zero is no_change).
    """
    if tau is None:
        return "increase" if delta > 0 else "decrease" if delta < 0 else "no_change"
    return "increase" if delta > tau else "decrease" if delta < -tau else "within"


_DIRECTION_FOR = {
    "increase": "increase",
    "decrease": "decrease",
    "within": "within_practical_margin",
    "no_change": "no_change",
}
_PRACTICAL_FOR = {
    "increase": "meaningful_increase",
    "decrease": "meaningful_decrease",
    "within": "within_practical_margin",
}

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
        if self.status_label != SUMMARY_LABELS[self.output_category]:
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
        complete = required.issubset(supplied)

        check_applicability_consistency(self.applicability_status, self.applicability_checks)
        if self.reviewed_summary.output_category != expected_output_category(
            self.applicability_status, self.sensitivity_status, complete=complete
        ):
            raise ValueError("reviewed summary must preserve sensitivity and applicability status")
        eligible = is_conclusion_eligible(self.applicability_status, self.sensitivity_status, complete=complete)
        if self.conclusion_eligible != eligible:
            raise ValueError("conclusion eligibility must preserve missing/failed/out-of-domain distinctions")

        pc = self.practical_change
        available_variants = [v for v in self.registered_variants if v.variant_id in required]

        if not complete:
            if not self.missing_evidence_reasons:
                raise ValueError("a missing required variant requires a missing evidence reason")
            if self.sensitivity_status == "stable_across_displayed_settings":
                raise ValueError("missing required variants cannot be labelled stable")
            # When required variants are missing, preserve any sensitivity already observed
            # among the available variants, while keeping the overall result unavailable.
            available_cats = {v.direction for v in available_variants}
            observed_sensitive = len(available_cats) > 1
            if observed_sensitive:
                if self.sensitivity_status != "sensitive_to_assumptions":
                    raise ValueError("available variants exhibit sensitivity; preserve sensitive_to_assumptions")
            else:
                if self.sensitivity_status != "unavailable":
                    raise ValueError("without observed sensitivity among available variants, sensitivity must be unavailable")
            if pc.category != "unavailable" or self.headline_direction != "unavailable":
                raise ValueError("missing required variants cannot publish a practical category or direction")
            if pc.observed_signs and set(pc.observed_signs) != {v.direction for v in available_variants}:
                raise ValueError("observed signs must match available variants' directions")
            return self

        if self.sensitivity_status == "unavailable":
            raise ValueError("unavailable sensitivity requires a missing required variant")

        # Frozen sensitivity rule: recompute from full-precision effects.
        variants = available_variants
        tau = pc.practical_margin_tau
        cats = {effect_category(v.effect_delta, tau) for v in variants}
        stable = len(cats) == 1
        if stable != (self.sensitivity_status == "stable_across_displayed_settings"):
            raise ValueError("sensitivity label contradicts the registered effects under the frozen rule")

        if set(pc.observed_signs) != {v.direction for v in variants}:
            raise ValueError("observed signs must equal the registered variants' directions")
        magnitude = max(abs(v.effect_delta) for v in variants)
        if pc.magnitude is None or not math.isclose(pc.magnitude, magnitude, rel_tol=1e-12, abs_tol=1e-12):
            raise ValueError("magnitude must be the maximum absolute registered effect")
        if tau is None:
            expected_category = "unspecified"
        elif stable:
            expected_category = _PRACTICAL_FOR[next(iter(cats))]
        else:
            expected_category = "inconsistent_across_variants"
        if pc.category != expected_category:
            raise ValueError("practical category contradicts the registered effects and margin")

        if not eligible:
            if self.headline_direction not in {"ambiguous", "unavailable"}:
                raise ValueError("ineligible comparisons cannot publish a directional headline")
        elif stable:
            expected_direction = _DIRECTION_FOR[next(iter(cats))]
            if self.headline_direction != expected_direction:
                raise ValueError("directional headline contradicts the registered effects")
            if self.headline_direction == "no_change" and any(v.effect_delta != 0.0 for v in variants):
                raise ValueError("effects within the practical margin cannot be described as no_change; use within_practical_margin and preserve observed signs separately")
        elif self.headline_direction != "ambiguous":
            raise ValueError("conflicting registered effects require an ambiguous headline")
        return self