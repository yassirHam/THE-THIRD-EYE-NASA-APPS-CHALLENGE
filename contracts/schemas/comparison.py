"""
THE THIRD EYE — Comparison & Harmonization Contract
Governs Stage A sensor-switch harmonization, sensitivity, applicability, and inference.
"""
from typing import List, Optional, Literal, Dict
from pydantic import BaseModel, Field

class CalibrationFactorVariant(BaseModel):
    """Registered calibration factor variant."""
    variant_id: str = Field(..., description="e.g., 'full_training_2016_2018', 'ex_2016', 'ex_2017', 'ex_2018'")
    factor_value: float = Field(..., gt=0.0, description="Scaling factor a_H or a_C")
    factor_type: Literal["own_support_a_H", "common_support_a_C"]
    training_years: List[int]
    delta_relative_to_reference: float = Field(..., description="Observed relative change in target period")

class ComparisonResult(BaseModel):
    """Evaluation result for a cross-era or sensor-switch claim."""
    artifact_version: str
    geometry_id: str
    target_period: str
    baseline_period: str
    method_id: Literal["stage_a_finite_factors", "stage_b_joint_constraints"] = "stage_a_finite_factors"
    policy_id: Literal["own_support_eligible", "common_support_paired"]

    # --- 4 Independent Status Dimensions ---
    sensitivity_status: Literal["stable_across_displayed_settings", "sensitive", "unresolved"]
    applicability_status: Literal["evaluated_for_conditions", "outside_evaluated_conditions", "insufficient_evidence"]
    inference_status: Literal["not_established", "statistically_supported"] = "not_established"
    practical_change: Literal["meaningful_increase", "meaningful_decrease", "within_practical_margin", "unspecified"]

    practical_margin_tau: Optional[float] = Field(None, description="Nonnegative practical margin registered before outcomes")
    headline_direction: Literal["increase", "decrease", "no_change", "ambiguous", "unresolved"]
    registered_variants: List[CalibrationFactorVariant]
    reasons_and_limits: List[str]
    plain_language_summary: str
