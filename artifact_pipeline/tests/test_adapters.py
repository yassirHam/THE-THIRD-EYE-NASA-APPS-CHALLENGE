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
    FootprintCertification.model_validate_json(json.dumps(cert))


# ---- P1 r3 F-01 (handoff 8f33ce4): complete / partial / unverified, synthetic evidence only

DOC = {"certification_ref": "p2-test-only", "certified_at": "2026-11-15T10:00:00Z"}


def certify(**p2: object) -> dict:
    cert = footprint_certification("g", p2)
    FootprintCertification.model_validate_json(json.dumps(cert))  # must be a valid contract object
    return cert


@pytest.mark.parametrize("extra", [{}, {"coverage_fraction": 1.0}, {"coverage": 1.0}])
def test_documented_complete_evidence_is_complete(extra: dict) -> None:
    cert = certify(footprint_evidence="cell_level", certifiable_complete=True, **DOC, **extra)
    assert cert["status"] == "complete" and cert["coverage_fraction"] is None
    assert (cert["certification_ref"], cert["certified_at"]) == (DOC["certification_ref"], DOC["certified_at"])


@pytest.mark.parametrize("key", ["coverage_fraction", "coverage"])
def test_documented_partial_evidence_keeps_partial_status_and_fraction(key: str) -> None:
    cert = certify(footprint_evidence="cell_level", certifiable_complete=False, **DOC, **{key: 0.83})
    assert cert["status"] == "partial" and cert["coverage_fraction"] == 0.83
    assert cert["certification_ref"] == DOC["certification_ref"] and cert["footprint_evidence"] == "cell_level"


def test_documented_partial_is_never_reported_as_complete() -> None:
    with pytest.raises(ValueError, match="complete"):
        footprint_certification("g", {"footprint_evidence": "cell_level", "certifiable_complete": True,
                                      "coverage_fraction": 0.83, **DOC})


def test_partial_certification_keeps_artifact_periods_comparison_ineligible() -> None:
    from contracts import build_fixtures as bf
    from contracts.schemas.calendar import CalendarArtifact
    from pydantic import ValidationError

    data = bf.calendar()
    data["footprint_certification"] = certify(footprint_evidence="cell_level", certifiable_complete=False,
                                              coverage_fraction=0.83, **DOC) | {"geometry_id": data["geometry_id"]}
    eligible = any(r["comparison_eligible"] for s in data["monthly_series"] + data["weekly_series"]
                   for r in s["records"])
    assert eligible  # the fixture has eligible periods, so a partial footprint must be refused
    with pytest.raises(ValidationError):
        CalendarArtifact.model_validate_json(json.dumps(data))


@pytest.mark.parametrize("p2", [
    {"footprint_evidence": "none"},
    {"footprint_evidence": "day_level", "certifiable_complete": False, "coverage_fraction": 0.83, **DOC},
    {"footprint_evidence": "cell_level", "certifiable_complete": False, "coverage_fraction": 0.83},
    {"footprint_evidence": "cell_level", "certifiable_complete": True, "certification_ref": "x"},
], ids=["no-evidence", "day-level", "cell-level-undocumented", "cell-level-no-timestamp"])
def test_absent_or_undocumented_evidence_is_unverified(p2: dict) -> None:
    cert = certify(**p2)
    assert cert["status"] == "unverified"
    assert cert["coverage_fraction"] is None and cert["certification_ref"] is None and cert["certified_at"] is None


@pytest.mark.parametrize("p2", [
    {"certifiable_complete": False},                                     # documented, no fraction
    {"certifiable_complete": False, "coverage_fraction": 0.0},
    {"certifiable_complete": False, "coverage_fraction": 1.0},
    {"certifiable_complete": False, "coverage_fraction": 1.2},
    {"certifiable_complete": False, "coverage_fraction": -0.1},
    {"certifiable_complete": False, "coverage_fraction": "0.8"},
    {"certifiable_complete": False, "coverage_fraction": 0.8, "coverage": 0.7},
], ids=["no-fraction", "zero", "one-not-complete", "above-one", "negative", "string", "keys-disagree"])
def test_contradictory_documented_evidence_raises_instead_of_downgrading(p2: dict) -> None:
    with pytest.raises(ValueError):
        footprint_certification("g", {"footprint_evidence": "cell_level", **DOC, **p2})


def test_unknown_evidence_kind_raises() -> None:
    with pytest.raises(ValueError):
        footprint_certification("g", {"footprint_evidence": "pixel_guess"})

