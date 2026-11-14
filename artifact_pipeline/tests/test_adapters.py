"""Export-boundary adapters (synthetic values only)."""
from __future__ import annotations

import json

import pytest

from artifact_pipeline.adapters import footprint_certification, p1a_statuses, record_coverage_fields
from contracts.schemas.calendar import FootprintCertification
from contracts.schemas.status_mapping import UnmappedStatusError, UnregisteredMappingError

P1A = dict(sensitivity="stable_across_displayed_settings", applicability="outside_evaluated_conditions",
           headline="unresolved", practical_change="unspecified")


def test_synthetic_export_uses_the_proposed_mapping() -> None:
    m = p1a_statuses("synthetic_dev_fixture", **P1A)
    assert (m.applicability_status, m.headline_direction) == ("out_of_domain", "unavailable")


def test_production_export_refuses_the_unregistered_mapping() -> None:
    with pytest.raises(UnregisteredMappingError):
        p1a_statuses("production", **P1A)


def test_insufficient_evidence_is_never_folded_into_another_state() -> None:
    with pytest.raises(UnmappedStatusError):
        p1a_statuses("synthetic_dev_fixture", **{**P1A, "applicability": "insufficient_evidence"})


def test_p2_coverage_maps_to_record_fields() -> None:
    fields = record_coverage_fields({"state": "partial", "reasons": ("missing_days_or_tiles",),
                                     "days_in_period": 7, "days_with_file": 6, "coverage": None})
    assert fields == {"coverage_state": "partial", "coverage_reasons": ["missing_days_or_tiles"],
                      "days_in_period": 7, "days_with_file": 6, "processed_coverage": None}


@pytest.mark.parametrize("bad", [
    {"state": "mostly", "reasons": ()},
    {"state": "complete", "reasons": ("no_file",)},
    {"state": "partial", "reasons": ()},
    {"state": "partial", "reasons": ("guess",)},
])
def test_p2_coverage_rejects_inconsistent_input(bad: dict) -> None:
    with pytest.raises(ValueError):
        record_coverage_fields({**bad, "days_in_period": 7, "days_with_file": 7})


def test_day_level_evidence_gives_an_unverified_certification() -> None:
    cert = footprint_certification("g", {"footprint_evidence": "day_level", "certifiable_complete": True,
                                         "certification_ref": "x", "certified_at": "2026-11-15T10:00:00Z"})
    assert cert["status"] == "unverified"
    FootprintCertification.model_validate_json(json.dumps(cert))


def test_cell_level_certified_period_gives_a_complete_certification() -> None:
    cert = footprint_certification("g", {"footprint_evidence": "cell_level", "certifiable_complete": True,
                                         "certification_ref": "p2-test-only", "certified_at": "2026-11-15T10:00:00Z"})
    assert cert["status"] == "complete"
    FootprintCertification.model_validate_json(json.dumps(cert))


def test_cell_level_without_p2_reference_stays_unverified() -> None:
    cert = footprint_certification("g", {"footprint_evidence": "cell_level", "certifiable_complete": True})
    assert cert["status"] == "unverified"
