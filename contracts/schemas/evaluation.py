"""Held-out sensor-switch evaluation summary contracts."""

from __future__ import annotations

from typing import Literal

from pydantic import Field, model_validator

from .common import ArtifactIdentity, StrictContractModel

MetricStatus = Literal["available", "unavailable"]


class BenchmarkBaselineMetrics(StrictContractModel):
    status: MetricStatus
    evaluated_case_count: int = Field(ge=0)
    answered_case_count: int = Field(ge=0)
    abstention_count: int = Field(ge=0)
    mean_reference_relative_error: float | None = Field(default=None, ge=0.0)
    directional_error_count: int | None = Field(default=None, ge=0)
    decision_coverage_percent: float | None = Field(default=None, ge=0.0, le=100.0)
    unavailable_reason: str | None = None

    @model_validator(mode="after")
    def validate_metrics(self) -> "BenchmarkBaselineMetrics":
        if self.answered_case_count + self.abstention_count != self.evaluated_case_count:
            raise ValueError("answered plus abstained cases must equal evaluated cases")
        metrics = (
            self.mean_reference_relative_error,
            self.directional_error_count,
            self.decision_coverage_percent,
        )
        if self.status == "available":
            if any(metric is None for metric in metrics) or self.unavailable_reason is not None:
                raise ValueError("available baseline requires metrics and no unavailable reason")
            if (self.directional_error_count or 0) > self.answered_case_count:
                raise ValueError("directional errors cannot exceed answered cases")
        elif any(metric is not None for metric in metrics) or not self.unavailable_reason:
            raise ValueError("unavailable baseline requires a reason and null metrics")
        return self


class IndependentUnits(StrictContractModel):
    blocks: int = Field(ge=0)
    regions: int = Field(ge=0)
    test_years: int = Field(ge=0)
    dependence_note: str = Field(min_length=1)


class LandingHeadlineMetric(StrictContractModel):
    status: MetricStatus
    description: str = Field(min_length=1)
    registered_case_count: int | None = Field(default=None, ge=0)
    raw_wrong_way_count: int | None = Field(default=None, ge=0)
    corrected_wrong_way_count: int | None = Field(default=None, ge=0)
    flagged_remaining_error_count: int | None = Field(default=None, ge=0)
    abstained_count: int | None = Field(default=None, ge=0)
    denominator_statement: str = Field(min_length=1)
    independent_units: IndependentUnits
    unavailable_reason: str | None = None

    @model_validator(mode="after")
    def validate_headline(self) -> "LandingHeadlineMetric":
        counts = (
            self.registered_case_count,
            self.raw_wrong_way_count,
            self.corrected_wrong_way_count,
            self.flagged_remaining_error_count,
            self.abstained_count,
        )
        if self.status == "available":
            if any(count is None for count in counts) or self.unavailable_reason is not None:
                raise ValueError("available headline requires all frozen counts")
            n = self.registered_case_count or 0
            if any((count or 0) > n for count in counts[1:]):
                raise ValueError("headline component counts cannot exceed the registered denominator")
        elif any(count is not None for count in counts) or not self.unavailable_reason:
            raise ValueError("unavailable headline requires null counts and an explicit reason")
        return self


class EvaluationSummary(ArtifactIdentity):
    eval_protocol_version: Literal["P0-held-out-sensor-switch-v1"]
    baseline_a_raw_handover: BenchmarkBaselineMetrics
    baseline_b_point_a_h: BenchmarkBaselineMetrics
    baseline_c_uncertainty_aware: BenchmarkBaselineMetrics
    baseline_d_stage_a_finite_audit: BenchmarkBaselineMetrics
    landing_headline_metric: LandingHeadlineMetric
    failures_and_limitations: list[str] = Field(min_length=1)
