"""Per-sensor period coverage state and footprint evidence (P2 r9 rule).

Reference implementation of the rule P2 wrote in its Round 9 review of the P4 contract
(origin/handoff b18ed3e, handoff/verdicts/P4/P4-B-001/r9-P2.md, sections 1, 3 and 5),
in the vocabulary of contract 1.4.0 (`coverage_state`, `coverage_reasons`).

Rules:
- Expected days = UTC calendar days of the period inside the sensor record and outside
  the sealed window. Sealed days are never read; they are only counted from dates.
- A day is present only if a granule exists for every expected tile (the caller passes
  one boolean per expected day, already reduced over tiles).
- complete    : every expected day present, period not clipped, and processed coverage
                verified at cell level >= C_MIN.
- partial     : at least one day present, with one or more reasons
                period_clipped / partition_boundary / missing_days_or_tiles /
                low_processed_coverage.
- unavailable : no day present: no_file (inside the record) or sensor_not_operating.
- coverage = P / (N_fp x days_with_file), P = processed footprint cell-days.
- C_MIN is NOT registered (P2 proposes 0.99, alternative 1.0). It is a required argument;
  passing None applies the strictest reading (1.0), so nothing is relaxed by default.
- footprint_evidence is cell_level only when processed and footprint cell counts are
  supplied; otherwise day_level. Day-level evidence never yields a certifiable footprint,
  and an untagged aggregate is never certified complete.

Values from missing days are never filled: the caller keeps them null.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Mapping, Optional

__all__ = ["PeriodCoverage", "period_coverage", "footprint_evidence_summary"]


@dataclass(frozen=True)
class PeriodCoverage:
    state: str                      # complete | partial | unavailable
    reasons: tuple[str, ...]        # P2 r9 vocabulary, sorted
    days_in_period: int
    expected_days: int              # inside record and outside the sealed window
    days_with_file: int
    coverage: Optional[float]       # P / (N_fp x days_with_file), cell level only
    footprint_evidence: str         # cell_level | day_level
    certifiable_complete: bool      # True only for complete + cell-level evidence
    missing_days: tuple[date, ...] = field(default_factory=tuple)


def _days(start: date, end: date) -> list[date]:
    return [start + timedelta(days=i) for i in range((end - start).days + 1)]


def period_coverage(
    *,
    period_start: date,
    period_end: date,
    record_start: date,
    record_end: date,
    day_present: Mapping[date, bool],
    c_min: Optional[float],
    sealed_window: Optional[tuple[date, date]] = None,
    processed_cell_days: Optional[int] = None,
    footprint_cells: Optional[int] = None,
) -> PeriodCoverage:
    """Classify one sensor-period. `day_present` must cover every expected day."""
    if period_end < period_start or record_end < record_start:
        raise ValueError("period and record ends must not precede their starts")
    if c_min is not None and not (0.0 < c_min <= 1.0):
        raise ValueError("c_min must be in (0, 1]")
    if (processed_cell_days is None) != (footprint_cells is None):
        raise ValueError("processed_cell_days and footprint_cells are supplied together")
    threshold = 1.0 if c_min is None else c_min

    all_days = _days(period_start, period_end)
    inside = [d for d in all_days if record_start <= d <= record_end]
    if sealed_window is not None:
        ws, we = sealed_window
        expected = [d for d in inside if not (ws <= d <= we)]
    else:
        expected = inside
    unknown = [d for d in expected if d not in day_present]
    if unknown:
        raise ValueError(f"day_present lacks expected days {unknown[:3]}...; absent is not the same as unknown")
    sealed_read = [d for d in inside if d not in expected and day_present.get(d)]
    if sealed_read:
        raise ValueError("sealed days were reported present; sealed days are never read")

    present = [d for d in expected if day_present[d]]
    missing = tuple(d for d in expected if not day_present[d])
    reasons: set[str] = set()
    if 0 < len(inside) < len(all_days):  # wholly outside is sensor_not_operating only
        reasons.add("period_clipped")
    if len(expected) < len(inside):
        reasons.add("partition_boundary")

    coverage: Optional[float] = None
    evidence = "day_level"
    if footprint_cells is not None:
        if footprint_cells <= 0 or processed_cell_days < 0:  # type: ignore[operator]
            raise ValueError("footprint_cells must be positive and processed_cell_days non-negative")
        evidence = "cell_level"
        if present:
            cap = footprint_cells * len(present)
            if processed_cell_days > cap:  # type: ignore[operator]
                raise ValueError("processed cell-days exceed footprint cells x days with file")
            coverage = processed_cell_days / cap  # type: ignore[operator]

    if not present:
        reasons.add("sensor_not_operating" if not inside else "no_file")
        state = "unavailable"
    else:
        if missing:
            reasons.add("missing_days_or_tiles")
        if coverage is not None and coverage < threshold:
            reasons.add("low_processed_coverage")
        state = "partial" if reasons else "complete"

    return PeriodCoverage(
        state=state,
        reasons=tuple(sorted(reasons)),
        days_in_period=len(all_days),
        expected_days=len(expected),
        days_with_file=len(present),
        coverage=coverage,
        footprint_evidence=evidence,
        certifiable_complete=state == "complete" and evidence == "cell_level",
        missing_days=missing,
    )


def footprint_evidence_summary(geometry_id: str, results: list[PeriodCoverage]) -> dict:
    """Reproducible evidence summary for P2's footprint certification decision.

    It never certifies by itself: `certification_ref` and `certified_at` stay for the P2
    human to add. `supports_status` is the strongest status the evidence allows:
    - complete   : every period is complete with cell-level evidence;
    - partial    : cell-level evidence exists for every period but some are not complete
                   (coverage_fraction = processed / expected over all periods);
    - unverified : any period lacks cell-level evidence, or there are no periods.
    """
    if not results:
        return {"geometry_id": geometry_id, "supports_status": "unverified", "footprint_evidence": "none",
                "periods": 0, "periods_certifiable": 0, "coverage_fraction": None,
                "note": "no period evidence supplied"}
    cell = all(r.footprint_evidence == "cell_level" for r in results)
    certifiable = sum(r.certifiable_complete for r in results)
    fraction = None
    status = "unverified"
    if cell:
        processed = sum((r.coverage or 0.0) * r.days_with_file for r in results)
        expected = sum(r.expected_days for r in results)
        fraction = processed / expected if expected else None
        status = "complete" if certifiable == len(results) else "partial"
    return {
        "geometry_id": geometry_id,
        "supports_status": status,
        "footprint_evidence": "cell_level" if cell else "day_level",
        "periods": len(results),
        "periods_certifiable": certifiable,
        "coverage_fraction": fraction,
        "note": "evidence summary only; certification needs P2's reference and UTC timestamp",
    }
