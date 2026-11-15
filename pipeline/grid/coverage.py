"""Per-sensor period coverage state and footprint evidence (P2 r9 rule, contract 1.6.0).

Reference implementation of the rule P2 wrote in its Round 9 review of the P4 contract
(origin/handoff b18ed3e, handoff/verdicts/P4/P4-B-001/r9-P2.md, sections 1, 3 and 5),
in the vocabulary of contract 1.6.0 (`coverage_state`, `coverage_reasons`,
contracts/schemas/calendar.py). pipeline/grid/COVERAGE_RULE.md documents it.

Rules:
- Expected days = UTC calendar days of the period inside the sensor record and outside the
  sealed set. The sealed set is the union of the fixed sealed holdout years
  [2020-01-01, 2021-12-31] and any caller-supplied `sealed_window`, each excluded on its own
  (never merged into one min(start)..max(end) span). Sealed days are never read; they are only
  counted from dates, and any sealed day reported present raises.
- A day is present only if a granule exists for every expected tile (the caller passes one
  bool per expected day, already reduced over tiles). Non-bool values raise.
- complete    : every expected day present, period not clipped, no sealed day excluded, and
                processed coverage, when measured at cell level, equals 1.0.
- partial     : at least one day present, with one or more reasons
                period_clipped / partition_boundary / missing_days_or_tiles /
                low_processed_coverage.
- unavailable : no day present. Reasons: sensor_not_operating (period wholly outside the
                record), partition_boundary alone (every in-record day sealed), or no_file
                (at least one permitted day, none with a file), plus partition_boundary when
                some in-record days are sealed.
- partition_boundary means "sealed days were excluded" and nothing else: a period that
  crosses a non-sealed year or split boundary (for example 2024-12-30..2025-01-05) gets no
  partition_boundary.
- coverage = P / (N_fp x days_with_file), P = processed footprint cell-days.
- C_MIN is fixed at 1.0 (contract 1.6.0 lists low_processed_coverage exactly when processed
  coverage < 1.0). `c_min` accepts only None or 1.0; any other value raises.
- record_end may not be later than 2025-12-31 (the current record). A period may run past
  record_end when it starts on or before it; it is then partial with period_clipped.
- footprint_evidence is cell_level only when processed and footprint cell counts are
  supplied; otherwise day_level. Day-level evidence never yields a certifiable footprint,
  and an untagged aggregate is never certified complete.

Values from missing days are never filled: the caller keeps them null.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Mapping, Optional

__all__ = [
    "PeriodCoverage",
    "period_coverage",
    "footprint_evidence_summary",
    "HOLDOUT_SEALED_WINDOW",
    "MAX_RECORD_END",
    "C_MIN",
]

# Sealed holdout years: always excluded, whatever sealed_window the caller passes.
HOLDOUT_SEALED_WINDOW: tuple[date, date] = (date(2020, 1, 1), date(2021, 12, 31))
# Latest record end this module accepts (current record through 2025).
MAX_RECORD_END = date(2025, 12, 31)
# Contract 1.6.0: any processed coverage below 1.0 is low; nothing below it counts as complete.
C_MIN = 1.0


@dataclass(frozen=True)
class PeriodCoverage:
    state: str                      # complete | partial | unavailable
    reasons: tuple[str, ...]        # P2 r9 vocabulary, sorted
    days_in_period: int
    expected_days: int              # inside record and outside the sealed set
    days_with_file: int
    coverage: Optional[float]       # P / (N_fp x days_with_file), cell level only
    footprint_evidence: str         # cell_level | day_level
    certifiable_complete: bool      # True only for complete + cell-level evidence
    missing_days: tuple[date, ...] = field(default_factory=tuple)


def _days(start: date, end: date) -> list[date]:
    return [start + timedelta(days=i) for i in range((end - start).days + 1)]


def _sealed_windows(sealed_window: Optional[tuple[date, date]]) -> tuple[tuple[date, date], ...]:
    windows = [HOLDOUT_SEALED_WINDOW]
    if sealed_window is not None:
        ws, we = sealed_window
        if ws > we:
            raise ValueError("sealed_window start must not be later than its end")
        windows.append((ws, we))
    return tuple(windows)


def _is_sealed(d: date, windows: tuple[tuple[date, date], ...]) -> bool:
    # Union membership: each window is tested on its own, never merged into one span.
    return any(ws <= d <= we for ws, we in windows)


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
    if record_end > MAX_RECORD_END:
        raise ValueError(f"record_end {record_end} is later than {MAX_RECORD_END}")
    if c_min is not None and c_min != C_MIN:
        raise ValueError("c_min must be 1.0 (contract 1.6.0); coverage below 1.0 is never complete")
    if (processed_cell_days is None) != (footprint_cells is None):
        raise ValueError("processed_cell_days and footprint_cells are supplied together")
    windows = _sealed_windows(sealed_window)

    non_bool = [d for d, v in day_present.items() if not isinstance(v, bool)]
    if non_bool:
        raise ValueError(f"day_present values must be bool; non-bool for {non_bool[:3]}")
    sealed_read = sorted(d for d, v in day_present.items() if v and _is_sealed(d, windows))
    if sealed_read:
        raise ValueError(f"sealed days were reported present {sealed_read[:3]}; sealed days are never read")

    all_days = _days(period_start, period_end)
    inside = [d for d in all_days if record_start <= d <= record_end]
    expected = [d for d in inside if not _is_sealed(d, windows)]
    unknown = [d for d in expected if d not in day_present]
    if unknown:
        raise ValueError(f"day_present lacks expected days {unknown[:3]}...; absent is not the same as unknown")

    present = [d for d in expected if day_present[d]]
    missing = tuple(d for d in expected if not day_present[d])
    reasons: set[str] = set()
    if 0 < len(inside) < len(all_days):  # wholly outside is sensor_not_operating only
        reasons.add("period_clipped")
    if len(expected) < len(inside):  # sealed exclusions only
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
        state = "unavailable"
        if not inside:
            reasons.add("sensor_not_operating")
        elif expected:  # permitted days exist but none has a file
            reasons.add("no_file")
        # else: every in-record day is sealed; partition_boundary alone
    else:
        if missing:
            reasons.add("missing_days_or_tiles")
        if coverage is not None and coverage < C_MIN:
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
    human to add. `supports_status` is the strongest status the evidence allows, using the
    FootprintCertification vocabulary (contracts/schemas/calendar.py):
    - complete   : every period is complete with cell-level evidence (coverage_fraction 1.0
                   here; FootprintCertification itself carries no fraction for complete);
    - partial    : cell-level evidence exists for every period, some are not complete, and
                   0.0 < coverage_fraction < 1.0 (processed / expected over all periods),
                   matching the contract's gt=0.0, lt=1.0 bound;
    - unverified : any period lacks cell-level evidence, there are no periods, or the
                   fraction is None (no expected days), 0.0 or not below 1.0 while some
                   period is not complete. coverage_fraction is then None.
    """
    if not results:
        return {"geometry_id": geometry_id, "supports_status": "unverified", "footprint_evidence": "none",
                "periods": 0, "periods_certifiable": 0, "coverage_fraction": None,
                "note": "no period evidence supplied"}
    cell = all(r.footprint_evidence == "cell_level" for r in results)
    certifiable = sum(r.certifiable_complete for r in results)
    fraction: Optional[float] = None
    status = "unverified"
    note = "evidence summary only; certification needs P2's reference and UTC timestamp"
    if cell:
        processed = sum((r.coverage or 0.0) * r.days_with_file for r in results)
        expected = sum(r.expected_days for r in results)
        measured = processed / expected if expected else None
        if certifiable == len(results):
            status, fraction = "complete", measured
        elif measured is not None and 0.0 < measured < 1.0:
            status, fraction = "partial", measured
        else:
            note = (f"cell-level fraction {measured!r} cannot support partial (needs 0 < f < 1); "
                    + note)
    return {
        "geometry_id": geometry_id,
        "supports_status": status,
        "footprint_evidence": "cell_level" if cell else "day_level",
        "periods": len(results),
        "periods_certifiable": certifiable,
        "coverage_fraction": fraction,
        "note": note,
    }
