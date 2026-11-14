"""
THE THIRD EYE — Claim Audit Record Contract
Standardized, downloadable, reproducible audit certificate.
"""
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field

class ClaimAuditRecord(BaseModel):
    """Reproducible audit record verifying an environmental assertion."""
    record_id: str = Field(..., description="SHA256 hash of query and inputs")
    statement: str = Field(..., description="Natural language environmental claim tested")
    analyst_entity: Optional[str] = None
    target_region: str
    geometry_id: str
    date_range_tested: str
    dataset_versions: List[str] = Field(
        default=["MODIS/061/MYD14A1", "NASA/VIIRS/002/VNP14A1"],
        description="Exact NASA Earth Engine collections utilized"
    )
    snpp_cessation_verified: bool = True
    formulas_applied: List[str]
    sensitivity_status: str
    applicability_status: str
    inference_status: str = "not_established"
    practical_margin_applied: Optional[float] = None
    counterexample_interpretations: Optional[List[Dict[str, Any]]] = None
    reproducibility_hash: str
    verification_steps: List[str]
