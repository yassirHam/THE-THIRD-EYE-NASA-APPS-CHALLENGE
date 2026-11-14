"""
THE THIRD EYE — Provenance & Data Manifest Schema Contract
"""
from typing import List, Dict, Optional
from pydantic import BaseModel, Field

class PartitionFileRecord(BaseModel):
    file_path: str
    sensor: str
    year: int
    row_count: int
    file_size_bytes: int
    sha256_checksum: str
    coverage_status: str

class ProvenanceManifest(BaseModel):
    manifest_version: str
    generated_at: str
    snpp_cessation_date: str = "2026-11-02T15:40:00Z"
    primary_region_id: str
    canonical_boundaries: Dict[str, Any]
    gee_collections: List[str]
    total_file_size_bytes: int
    compressed_bundle_size_bytes: int
    partitions: List[PartitionFileRecord]
