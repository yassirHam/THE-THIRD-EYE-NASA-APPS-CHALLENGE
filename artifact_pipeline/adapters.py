"""Export-boundary adapters from P1/P2 outputs to contract 1.4.0 fields.

They take plain values so this lane does not import P1/P2 code from other branches.
- P1-A statuses go through the PROPOSED mapping in contracts/config/p1a_status_mapping.json.
  While it is unregistered, only synthetic artifacts may use it; production export raises.
- P2 coverage results (pipeline/grid/coverage.py, P2 r9 rule) become record coverage fields.
  Day-level evidence never yields a complete footprint certification.
"""
from __future__ import annotations

from typing import Mapping

from contracts.schemas.status_mapping import MappedStatuses, map_p1a_statuses

P2_STATES = {"complete", "partial", "unavailable"}
P2_REASONS = {"period_clipped", "sensor_not_operating", "partition_boundary",
              "missing_days_or_tiles", "low_processed_coverage", "no_file"}


def p1a_statuses(data_classification: str, **p1a: object) -> MappedStatuses:
    """Map P1-A status names; refuse production use of an unregistered mapping."""
    if data_classification not in ("production", "synthetic_dev_fixture"):
        raise ValueError(f"unknown data classification {data_classification!r}")
    return map_p1a_statuses(**p1a, allow_unregistered=data_classification == "synthetic_dev_fixture")  # type: ignore[arg-type]


def record_coverage_fields(p2: Mapping[str, object]) -> dict:
    """Contract record fields from one P2 period-coverage result (state, reasons, days, coverage)."""
    state = p2["state"]
    reasons = list(p2["reasons"])  # type: ignore[arg-type]
    if state not in P2_STATES or not set(reasons) <= P2_REASONS:
        raise ValueError(f"unknown P2 coverage state or reason: {state!r} {reasons!r}")
    if (state == "complete") != (not reasons):
        raise ValueError("a complete P2 period has no reasons; every other state has at least one")
    return {
        "coverage_state": state,
        "coverage_reasons": reasons,
        "days_in_period": p2["days_in_period"],
        "days_with_file": p2["days_with_file"],
        "processed_coverage": p2.get("coverage"),
    }


def _coverage_fraction(p2: Mapping[str, object]) -> float | None:
    """P2's documented coverage fraction, from `coverage_fraction` or `coverage` (must agree)."""
    values = [p2[k] for k in ("coverage_fraction", "coverage") if p2.get(k) is not None]
    if not values:
        return None
    if any(isinstance(v, bool) or not isinstance(v, (int, float)) for v in values):
        raise ValueError(f"coverage fraction must be a number, got {values!r}")
    if len(values) == 2 and values[0] != values[1]:
        raise ValueError(f"coverage_fraction and coverage disagree: {values[0]!r} vs {values[1]!r}")
    return float(values[0])


def footprint_certification(geometry_id: str, p2: Mapping[str, object]) -> dict:
    """Footprint certification from P2's footprint evidence (P1 r3 F-01, handoff 8f33ce4).

    - complete: cell-level evidence, P2 reference and UTC timestamp, certifiable_complete true,
      and no coverage fraction below 1.
    - partial: cell-level evidence, P2 reference and UTC timestamp, certifiable_complete false and
      a documented coverage fraction in (0, 1). The fraction is kept; partial is never complete.
    - unverified: no P2 documentation, or day-level / no evidence. Day-level file presence and
      available data never certify footprint coverage.
    Contradictory documented input raises instead of being reported as complete or unverified, so
    a documented adverse finding is never lost.
    """
    evidence = p2.get("footprint_evidence")
    if evidence not in ("cell_level", "day_level", "none"):
        raise ValueError(f"unknown footprint evidence {evidence!r}")
    fraction = _coverage_fraction(p2)
    documented = bool(p2.get("certification_ref")) and bool(p2.get("certified_at"))
    if evidence == "cell_level" and documented:
        base = {"geometry_id": geometry_id, "footprint_evidence": "cell_level",
                "certification_ref": p2["certification_ref"], "certified_at": p2["certified_at"]}
        if p2.get("certifiable_complete"):
            if fraction is not None and fraction != 1.0:
                raise ValueError(f"P2 marked the footprint complete but documented coverage {fraction!r}")
            return {**base, "status": "complete", "coverage_fraction": None}
        if fraction is None:
            raise ValueError("documented cell-level footprint is neither complete nor carries a coverage "
                             "fraction; cannot be reported as partial or unverified without losing the finding")
        if not 0.0 < fraction < 1.0:
            raise ValueError(f"documented partial footprint needs a coverage fraction in (0, 1), got {fraction!r}")
        return {**base, "status": "partial", "coverage_fraction": fraction}
    return {"geometry_id": geometry_id, "status": "unverified", "footprint_evidence": evidence,
            "certification_ref": None, "certified_at": None, "coverage_fraction": None}
