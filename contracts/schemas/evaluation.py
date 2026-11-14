"""
THE THIRD EYE — Evaluation Benchmark Schema Contract
Governs held-out sensor-switch benchmark outputs per Section 9A.
"""
from typing import List, Dict, Optional
from pydantic import BaseModel, Field

class BenchmarkBaselineMetrics(BaseModel):
    mean_reference_relative_error: float
    decision_coverage_percent: float
    abstention_rate_percent: float

class IndependentUnits(BaseModel):
    blocks: int
    regions: int
    test_years: int

class EvaluationSummary(BaseModel):
    artifact_version: str
    eval_protocol_version: str = "P0-held-out-sensor-switch-v1"
    baseline_a_raw_handover: BenchmarkBaselineMetrics
    baseline_b_point_a_h: BenchmarkBaselineMetrics
    baseline_c_uncertainty_aware: BenchmarkBaselineMetrics
    baseline_d_stage_a_finite_audit: BenchmarkBaselineMetrics

    # Frozen headline metric paired with independent units and explicit denominator
    headline_metric_description: str
    headline_metric_value: float
    headline_denominator: str
    independent_units: IndependentUnits
    failures_and_limitations: List[str]
