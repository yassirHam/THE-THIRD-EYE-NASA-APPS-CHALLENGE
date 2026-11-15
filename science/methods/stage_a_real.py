"""
Stage A real-data calibration on P2's non-sealed weekly California / British
Columbia export (focus_weekly_CA_BC.parquet).

Scientific authority: THE_THIRD_EYE_FINAL_PLAN_GEOGRAPHIC_ACCESS_UPDATED.txt
Sections 4B (composition), 6 (Stage A factor definition) and 7 (output logic).
Factor arithmetic is delegated to science.methods.stage_a; this module only
selects eligible weeks, aggregates D and O, and reports.

Splits: 2016-2018 training, 2019 development, 2022-2025 applicability.
2020-2021 is the sealed evaluation window and is never loaded: the parquet is
read with a row filter that drops ISO years 2020-2021, and every row that is
returned is checked again against the sealed calendar window
(2020-01-01..2021-12-31, contracts/config/pending_registrations.json).  A row
that overlaps it raises SealedDataError.

Week selection (stated assumptions, NOT registered P1 decisions):
- Weeks are UTC ISO weeks (registered); a week's year is its ISO year.
- A week enters pooling only when both sensors are 'complete', the row is
  comparison_eligible, and processed coverage for both sensors >= c_min.
  C_MIN is unregistered, so the default c_min = 1.0 fails closed (contract
  rule: any coverage < 1.0 is low_processed_coverage).  Excluded weeks are
  listed with their reasons; missing O is never turned into zero.
- One stratum, 'annual' (all eligible ISO weeks of the year).  Because only
  weeks where both sensors are complete are kept, Aqua and VIIRS pool over the
  identical set of weeks (matched calendar strata).
- min_support_O defaults to the region footprint size N_fp (one
  footprint-equivalent of usable land-cell-days per sensor-year).  It derives
  from geometry only, not from fire outcomes, and is PROPOSED, NOT REGISTERED.
- Regions are fitted separately.  No CA+BC union factor is fitted; a union
  needs its own applicability evidence (plan Section 5A).
- Common-support a_C needs an explicit pairing attestation from P2
  (attest_common_pairing=True).  Without it every a_C variant is unavailable.

Applicability (2022-2025) has no registered pass criterion, so its status is
insufficient_evidence with applicability_passed = None.  The reported
envelope check is descriptive only.

Usage:
    python -m science.methods.stage_a_real [--data-dir DIR] [--out PATH]
DIR defaults to $THE_THIRD_EYE_DATA_DIR.  Raw parquet files are never written
into the repository; only the compact JSON summary is.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import sys
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path
from typing import Any, Iterable, Mapping, Optional, Sequence

from science.methods.stage_a import (
    SCALE,
    ApplicabilityStatus,
    FactorResult,
    FactorStatus,
    ObsRecord,
    StageAConfig,
    fit_common_support_variants,
    fit_own_support_variants,
)

MODULE_VERSION = "stage_a_real/1.0.0"
PARQUET_NAME = "focus_weekly_CA_BC.parquet"
DATA_DIR_ENV = "THE_THIRD_EYE_DATA_DIR"

TRAINING_YEARS: tuple[int, ...] = (2016, 2017, 2018)
DEV_YEAR: int = 2019
APPLICABILITY_YEARS: tuple[int, ...] = (2022, 2023, 2024, 2025)
SEALED_YEARS: tuple[int, ...] = (2020, 2021)
SEALED_START = date(2020, 1, 1)
SEALED_END = date(2021, 12, 31)
ALLOWED_PARTITIONS: tuple[str, ...] = (
    "train_2016_2018", "dev_2019", "applicability_2022_2025",
)
PARTITION_YEARS: dict[str, tuple[int, ...]] = {
    "train_2016_2018": TRAINING_YEARS,
    "dev_2019": (DEV_YEAR,),
    "applicability_2022_2025": APPLICABILITY_YEARS,
}
REGIONS: dict[int, str] = {3218: "California", 826: "British Columbia"}
STRATUM = "annual"

REQUIRED_COLUMNS: tuple[str, ...] = (
    "ADM1_CODE", "week_start", "partition", "iso_year", "iso_week",
    "D_aqua", "O_aqua", "D_viirs", "O_viirs",
    "O_common", "D_aqua_common", "D_viirs_common",
    "state_aqua", "state_viirs", "coverage_aqua", "coverage_viirs",
    "comparison_eligible", "N_fp",
)

# (policy, sensor) -> (D column, O column)
POLICY_COLUMNS: dict[tuple[str, str], tuple[str, str]] = {
    ("own_support", "aqua"): ("D_aqua", "O_aqua"),
    ("own_support", "viirs"): ("D_viirs", "O_viirs"),
    ("common_support", "aqua"): ("D_aqua_common", "O_common"),
    ("common_support", "viirs"): ("D_viirs_common", "O_common"),
}


class SealedDataError(RuntimeError):
    """A row touching the sealed 2020-2021 evaluation window reached this module."""


# ---------------------------------------------------------------------------
# Loading
# ---------------------------------------------------------------------------
def default_parquet_path(data_dir: Optional[str] = None) -> Optional[Path]:
    """Return the parquet path under data_dir (or $THE_THIRD_EYE_DATA_DIR), else None."""
    base = data_dir if data_dir is not None else os.environ.get(DATA_DIR_ENV)
    if not base:
        return None
    return Path(base) / PARQUET_NAME


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def assert_no_sealed_rows(rows: Iterable[Mapping[str, Any]]) -> None:
    """Raise SealedDataError if any row's ISO year or 7-day week touches 2020-2021."""
    for r in rows:
        if int(r["iso_year"]) in SEALED_YEARS:
            raise SealedDataError(f"Sealed ISO year in row: {r['week_start']} ({r['iso_year']}).")
        start = date.fromisoformat(str(r["week_start"])[:10])
        end = start + timedelta(days=6)
        if start <= SEALED_END and end >= SEALED_START:
            raise SealedDataError(
                f"Week starting {start} overlaps the sealed window "
                f"{SEALED_START}..{SEALED_END}."
            )


def load_rows(path: Path) -> list[dict[str, Any]]:
    """
    Read the non-sealed development partitions of the weekly parquet.

    The row filter excludes ISO years 2020-2021 and any partition outside
    ALLOWED_PARTITIONS inside pyarrow, before rows reach Python.  Returned
    rows are re-checked by assert_no_sealed_rows.
    """
    import pyarrow.parquet as pq  # local import: tests without pyarrow still run

    if not path.is_file():
        raise FileNotFoundError(f"{path} not found.")
    schema_names = set(pq.read_schema(path).names)
    missing = [c for c in REQUIRED_COLUMNS if c not in schema_names]
    if missing:
        raise ValueError(f"{path.name} is missing required columns {missing}.")
    table = pq.read_table(
        path,
        columns=list(REQUIRED_COLUMNS),
        filters=[
            ("iso_year", "not in", list(SEALED_YEARS)),
            ("partition", "in", list(ALLOWED_PARTITIONS)),
        ],
    )
    rows = table.to_pylist()
    assert_no_sealed_rows(rows)
    return rows


# ---------------------------------------------------------------------------
# Week eligibility and aggregation
# ---------------------------------------------------------------------------
def _num(value: Any) -> Optional[float]:
    """None for null/NaN (missing stays missing, never zero)."""
    if value is None:
        return None
    v = float(value)
    return None if math.isnan(v) else v


def _count(value: Any, name: str) -> int:
    v = _num(value)
    if v is None:
        raise ValueError(f"{name} is missing on an otherwise eligible week.")
    if v < 0 or v != round(v):
        raise ValueError(f"{name} = {v!r} is not a non-negative integer count.")
    return int(round(v))


def week_exclusion_reasons(row: Mapping[str, Any], c_min: float) -> list[str]:
    """Empty list when the week is eligible for paired pooling."""
    reasons: list[str] = []
    for sensor in ("aqua", "viirs"):
        state = row.get(f"state_{sensor}")
        if state != "complete":
            reasons.append(f"{sensor}_state_{state}")
            continue
        cov = _num(row.get(f"coverage_{sensor}"))
        if cov is None or cov < c_min:
            reasons.append(f"{sensor}_coverage_below_c_min")
    if not bool(row.get("comparison_eligible")):
        reasons.append("not_comparison_eligible")
    years = PARTITION_YEARS.get(str(row.get("partition")))
    if years is None or int(row["iso_year"]) not in years:
        reasons.append("iso_year_outside_partition")
    return reasons


@dataclass(frozen=True)
class WeekObs:
    region: int
    iso_year: int
    week_start: str
    D: dict[tuple[str, str], int]  # (policy, sensor) -> D
    O: dict[tuple[str, str], int]  # (policy, sensor) -> O


def select_weeks(
    rows: Iterable[Mapping[str, Any]], c_min: float
) -> tuple[list[WeekObs], list[dict[str, Any]]]:
    """Split rows into eligible WeekObs and an exclusion log."""
    eligible: list[WeekObs] = []
    excluded: list[dict[str, Any]] = []
    seen: set[tuple[int, str]] = set()
    for r in rows:
        region = int(r["ADM1_CODE"])
        if region not in REGIONS:
            continue
        key = (region, str(r["week_start"]))
        reasons = week_exclusion_reasons(r, c_min)
        if reasons:
            excluded.append({"region": region, "week_start": key[1],
                             "iso_year": int(r["iso_year"]), "reasons": reasons})
            continue
        if key in seen:
            raise ValueError(f"Duplicate eligible week {key}.")
        seen.add(key)
        D = {k: _count(r[d], d) for k, (d, _) in POLICY_COLUMNS.items()}
        O = {k: _count(r[o], o) for k, (_, o) in POLICY_COLUMNS.items()}
        eligible.append(WeekObs(region, int(r["iso_year"]), key[1], D, O))
    eligible.sort(key=lambda w: (w.region, w.week_start))
    excluded.sort(key=lambda e: (e["region"], e["week_start"]))
    return eligible, excluded


def annual_records(
    weeks: Iterable[WeekObs], region: int, policy: str, years: Iterable[int]
) -> dict[str, list[ObsRecord]]:
    """Sum D and O per (sensor, ISO year) before any division."""
    wanted = set(years)
    sums: dict[tuple[str, int], list[int]] = {}
    for w in weeks:
        if w.region != region or w.iso_year not in wanted:
            continue
        for sensor in ("aqua", "viirs"):
            acc = sums.setdefault((sensor, w.iso_year), [0, 0])
            acc[0] += w.D[(policy, sensor)]
            acc[1] += w.O[(policy, sensor)]
    out: dict[str, list[ObsRecord]] = {"aqua": [], "viirs": []}
    for (sensor, year), (d, o) in sorted(sums.items()):
        out[sensor].append(ObsRecord(sensor=sensor, year=year, stratum=STRATUM,
                                     policy=policy, D=d, O=o))
    return out


def pooled(weeks: Iterable[WeekObs], region: int, policy: str, sensor: str,
           years: Iterable[int]) -> tuple[Optional[float], int, int]:
    """(1000*sumD/sumO or None, sumD, sumO) over the given ISO years."""
    wanted = set(years)
    d = o = 0
    for w in weeks:
        if w.region == region and w.iso_year in wanted:
            d += w.D[(policy, sensor)]
            o += w.O[(policy, sensor)]
    return (SCALE * d / o if o > 0 else None), d, o


# ---------------------------------------------------------------------------
# Development and applicability reporting
# ---------------------------------------------------------------------------
def _factor_json(fr: FactorResult) -> dict[str, Any]:
    return {
        "status": fr.status.value,
        "factor": fr.factor_value,
        "training_years": list(fr.training_years),
        "aqua_pooled_rate": fr.aqua_pooled_rate,
        "viirs_pooled_rate": fr.viirs_pooled_rate,
        "support_failures": [list(x) for x in fr.support_failures],
        "reasons": fr.reasons,
    }


def mapping_errors(
    weeks: Sequence[WeekObs], region: int, policy: str, years: Iterable[int],
    variants: Mapping[str, FactorResult],
) -> dict[str, Any]:
    """
    Pooled and weekly mapping errors of a*V against Aqua A over `years`.
    'raw' is the a = 1 baseline.  Weekly errors use each week's own rates.
    Descriptive only; nothing is tuned on these numbers.
    """
    years = list(years)
    A, dA, oA = pooled(weeks, region, policy, "aqua", years)
    V, dV, oV = pooled(weeks, region, policy, "viirs", years)
    wk = [w for w in weeks if w.region == region and w.iso_year in set(years)]
    wk_rates = [
        (SCALE * w.D[(policy, "aqua")] / w.O[(policy, "aqua")],
         SCALE * w.D[(policy, "viirs")] / w.O[(policy, "viirs")])
        for w in wk if w.O[(policy, "aqua")] > 0 and w.O[(policy, "viirs")] > 0
    ]
    factors: dict[str, Optional[float]] = {"raw": 1.0}
    for vid, fr in variants.items():
        factors[vid] = fr.factor_value if fr.status == FactorStatus.AVAILABLE else None
    by_variant: dict[str, Any] = {}
    for vid, a in factors.items():
        if a is None or A is None or V is None:
            by_variant[vid] = {"factor": a, "status": "unavailable"}
            continue
        err = a * V - A
        weekly_mae = (sum(abs(a * v - aq) for aq, v in wk_rates) / len(wk_rates)
                      if wk_rates else None)
        by_variant[vid] = {
            "factor": a,
            "status": "available",
            "mapped_rate": a * V,
            "pooled_error": err,
            "pooled_relative_error": (err / A) if A > 0 else None,
            "weekly_mae": weekly_mae,
        }
    return {
        "years": years,
        "aqua": {"rate": A, "D": dA, "O": oA},
        "viirs": {"rate": V, "D": dV, "O": oV},
        "observed_ratio_A_over_V": (A / V) if (A is not None and V) else None,
        "n_weeks": len(wk_rates),
        "by_variant": by_variant,
    }


def applicability_year(
    weeks: Sequence[WeekObs], region: int, policy: str, year: int,
    variants: Mapping[str, FactorResult], n_excluded: int,
) -> dict[str, Any]:
    """One applicability-year record.  No registered pass criterion exists."""
    rep = mapping_errors(weeks, region, policy, [year], variants)
    avail = [fr.factor_value for fr in variants.values()
             if fr.status == FactorStatus.AVAILABLE]
    all_avail = len(avail) == len(variants) and bool(avail)
    ratio = rep["observed_ratio_A_over_V"]
    if rep["n_weeks"] == 0 or ratio is None:
        status = ApplicabilityStatus.MISSING_REQUIRED_SUPPORT
    else:
        status = ApplicabilityStatus.INSUFFICIENT_EVIDENCE
    rep.update({
        "excluded_weeks": n_excluded,
        "applicability_status": status.value,
        "applicability_passed": None,
        "applicability_reason": (
            "No registered applicability pass criterion; the envelope check "
            "below is descriptive and is not a gate."
        ),
        "descriptive_ratio_inside_variant_envelope": (
            (min(avail) <= ratio <= max(avail)) if (all_avail and ratio is not None) else None
        ),
        "variant_envelope": [min(avail), max(avail)] if all_avail else None,
    })
    return rep


# ---------------------------------------------------------------------------
# Geographic composition (plan Section 4B)
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class Block:
    block_id: str
    D: float
    O: float


def observed_pooled_rate(blocks: Sequence[Block]) -> Optional[float]:
    """R_t = 1000*sum(D)/sum(O) over blocks with O > 0; None when no support."""
    d = sum(b.D for b in blocks if b.O > 0)
    o = sum(b.O for b in blocks if b.O > 0)
    return SCALE * d / o if o > 0 else None


def o_share_weighted_rate(blocks: Sequence[Block]) -> Optional[float]:
    """sum_b w_b * r_b with w_b = O_b / sum O; equals observed_pooled_rate."""
    o = sum(b.O for b in blocks if b.O > 0)
    if o <= 0:
        return None
    return sum((b.O / o) * (SCALE * b.D / b.O) for b in blocks if b.O > 0)


def fixed_weight_rate(
    blocks: Sequence[Block], weights: Mapping[str, float]
) -> tuple[Optional[float], list[str]]:
    """
    R_std = sum_b q_b * r_b with registered fixed weights q.

    Unavailable (None) when a weighted block is absent or has O = 0; the
    remaining weights are never renormalized.  Invalid weights raise.
    """
    if not weights:
        raise ValueError("weights must be non-empty.")
    if any((not math.isfinite(q)) or q < 0 for q in weights.values()):
        raise ValueError("weights must be finite and non-negative.")
    if abs(sum(weights.values()) - 1.0) > 1e-12:
        raise ValueError(f"weights must sum to 1, got {sum(weights.values())!r}.")
    by_id = {b.block_id: b for b in blocks}
    reasons: list[str] = []
    for bid, q in weights.items():
        b = by_id.get(bid)
        if b is None:
            reasons.append(f"required block {bid!r} is missing")
        elif b.O <= 0:
            reasons.append(f"required block {bid!r} has zero usable support (O = 0)")
    if reasons:
        return None, reasons
    return sum(q * SCALE * by_id[bid].D / by_id[bid].O for bid, q in weights.items()), []


def composition_counterexample() -> dict[str, Any]:
    """
    Plan Section 4B fixture.  Block rates 10 and 1 (per 1000 usable
    cell-days) are unchanged; O shares move from 0.8/0.2 to 0.2/0.8.
    """
    p1 = [Block("high", 80, 8000), Block("low", 2, 2000)]
    p2 = [Block("high", 20, 2000), Block("low", 8, 8000)]
    q = {"high": 0.5, "low": 0.5}
    r1, r2 = observed_pooled_rate(p1), observed_pooled_rate(p2)
    s1, _ = fixed_weight_rate(p1, q)
    s2, _ = fixed_weight_rate(p2, q)
    assert r1 is not None and r2 is not None and s1 is not None and s2 is not None
    missing, missing_reasons = fixed_weight_rate([Block("high", 80, 8000)], q)
    zero, zero_reasons = fixed_weight_rate([Block("high", 80, 8000), Block("low", 0, 0)], q)
    return {
        "observed": [r1, r2],
        "observed_pct_change": 100.0 * (r2 - r1) / r1,
        "fixed_weight_0.5_0.5": [s1, s2],
        "identity_holds": all(
            math.isclose(observed_pooled_rate(p), o_share_weighted_rate(p), rel_tol=1e-12)
            for p in (p1, p2)
        ),
        "missing_block_result": missing,
        "missing_block_reasons": missing_reasons,
        "zero_support_result": zero,
        "zero_support_reasons": zero_reasons,
    }


def composition_identity_real(weeks: Sequence[WeekObs], years: Iterable[int]) -> dict[str, Any]:
    """
    Real-data check of the Section 4B identity: CA+BC pooled rate equals the
    O-share-weighted sum of block rates, and block sums reconcile.  This is an
    accounting check, not a calibrated or evaluated union.
    """
    out: dict[str, Any] = {}
    for sensor in ("aqua", "viirs"):
        for y in years:
            blocks = []
            for region in sorted(REGIONS):
                _, d, o = pooled(weeks, region, "own_support", sensor, [y])
                blocks.append(Block(str(region), d, o))
            r = observed_pooled_rate(blocks)
            w = o_share_weighted_rate(blocks)
            total_o = sum(b.O for b in blocks)
            out[f"{sensor}_{y}"] = {
                "o_shares": {b.block_id: (b.O / total_o) if total_o else None for b in blocks},
                "blocks_sum_D": sum(b.D for b in blocks),
                "blocks_sum_O": total_o,
                # None = no usable support (unavailable), never a failed identity
                "identity_holds": (None if (r is None or w is None)
                                   else math.isclose(r, w, rel_tol=1e-12)),
            }
    return out


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------
def run_stage_a(
    rows: Sequence[Mapping[str, Any]],
    *,
    c_min: float = 1.0,
    min_support_O: Optional[Mapping[int, int]] = None,
    attest_common_pairing: bool = False,
    source: Optional[Mapping[str, Any]] = None,
) -> dict[str, Any]:
    """
    Build the full Stage A summary from already-loaded, non-sealed rows.

    min_support_O: per-region minimum summed O per sensor-year; defaults to
    the region's N_fp.  Pure Python; does not need pyarrow.
    """
    rows = list(rows)
    assert_no_sealed_rows(rows)
    weeks, excluded = select_weeks(rows, c_min)

    n_fp: dict[int, int] = {}
    for r in rows:
        reg = int(r["ADM1_CODE"])
        if reg in REGIONS and _num(r.get("N_fp")) is not None:
            n_fp.setdefault(reg, int(r["N_fp"]))
    support = dict(min_support_O) if min_support_O is not None else dict(n_fp)

    regions_out: dict[str, Any] = {}
    for region, name in REGIONS.items():
        if region not in support:
            regions_out[str(region)] = {"name": name, "status": "unavailable",
                                        "reason": "no rows or no N_fp for region"}
            continue
        excl_by_year: dict[int, int] = {}
        for e in excluded:
            if e["region"] == region:
                excl_by_year[e["iso_year"]] = excl_by_year.get(e["iso_year"], 0) + 1
        reg_out: dict[str, Any] = {
            "name": name,
            "N_fp": n_fp.get(region),
            "min_support_O": support[region],
            "eligible_weeks_by_year": {
                str(y): sum(1 for w in weeks if w.region == region and w.iso_year == y)
                for y in TRAINING_YEARS + (DEV_YEAR,) + APPLICABILITY_YEARS
            },
            "excluded_weeks_by_year": {str(y): n for y, n in sorted(excl_by_year.items())},
            "policies": {},
        }
        for policy in ("own_support", "common_support"):
            cfg = StageAConfig(policy=policy, strata=(STRATUM,),
                               min_support_O=int(support[region]))
            recs = annual_records(weeks, region, policy, TRAINING_YEARS)
            if policy == "own_support":
                variants = fit_own_support_variants(
                    recs["aqua"], recs["viirs"], TRAINING_YEARS, config=cfg)
            else:
                variants = fit_common_support_variants(
                    recs["aqua"], recs["viirs"], TRAINING_YEARS,
                    pairing_validated=attest_common_pairing, config=cfg)
            pol: dict[str, Any] = {
                "factor_name": "a_H" if policy == "own_support" else "a_C",
                "role": ("historical own-support factor" if policy == "own_support"
                         else "diagnostic only; never substitutes for a_H"),
                "variants": {vid: _factor_json(fr) for vid, fr in variants.items()},
                "development_2019": mapping_errors(weeks, region, policy, [DEV_YEAR], variants),
                "applicability": {
                    str(y): applicability_year(weeks, region, policy, y, variants,
                                               excl_by_year.get(y, 0))
                    for y in APPLICABILITY_YEARS
                },
            }
            avail = [fr.factor_value for fr in variants.values()
                     if fr.status == FactorStatus.AVAILABLE]
            pol["variant_envelope"] = ([min(avail), max(avail)]
                                       if len(avail) == len(variants) else None)
            pol["variant_envelope_note"] = (
                "Min-max of registered leave-one-year-out variants; not a confidence "
                "interval or physical bound."
            )
            reg_out["policies"][policy] = pol
        regions_out[str(region)] = reg_out

    years_used = sorted({w.iso_year for w in weeks})
    return {
        "summary_id": "stage_a_real_CA_BC_weekly",
        "module_version": MODULE_VERSION,
        "method": "stage_a_finite_factors (science.methods.stage_a)",
        "source": dict(source or {}),
        "splits": {
            "training": list(TRAINING_YEARS),
            "development": DEV_YEAR,
            "applicability": list(APPLICABILITY_YEARS),
            "sealed_not_read": list(SEALED_YEARS),
        },
        "iso_years_in_eligible_weeks": years_used,
        "selection": {
            "week_definition": "utc_iso_week (registered)",
            "stratum": STRATUM,
            "eligible_week_rule": ("both sensors state 'complete', comparison_eligible, "
                                   "processed coverage >= c_min for both sensors"),
            "c_min": c_min,
            "c_min_registered": False,
            "min_support_O_rule": "region N_fp per sensor-year",
            "min_support_O_registered": False,
            "strata_registered": False,
            "common_pairing_attested": attest_common_pairing,
            "regions_fitted_separately": True,
            "union_factor_fitted": False,
            "rows_loaded": len(rows),
            "eligible_weeks": len(weeks),
            "excluded_weeks": len(excluded),
        },
        "status_dimensions": {
            "inference_status": "not_established",
            "applicability_note": ("No registered applicability criterion; "
                                   "applicability_passed is null for every year."),
            "stability_note": ("Variants test training-year composition only, not every "
                               "plausible sensor bias or transfer failure."),
        },
        "regions": regions_out,
        "composition_fixture_section_4b": composition_counterexample(),
        "composition_identity_real_own_support": composition_identity_real(
            weeks, TRAINING_YEARS + (DEV_YEAR,) + APPLICABILITY_YEARS),
        "unit": "fire-cell-days per 1000 usable land-cell-days (not fire counts, not FIRMS points)",
    }


def write_summary(summary: Mapping[str, Any], out: Path) -> None:
    out.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(summary, indent=2, sort_keys=True, allow_nan=False)
    out.write_text(text + "\n", encoding="utf-8")


DEFAULT_OUT = Path(__file__).resolve().parent / "frozen" / "stage_a_real_CA_BC_summary.json"


def main(argv: Optional[Sequence[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    ap.add_argument("--data-dir", default=None,
                    help=f"Directory holding {PARQUET_NAME} (default ${DATA_DIR_ENV}).")
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    ap.add_argument("--c-min", type=float, default=1.0)
    ap.add_argument("--attest-common-pairing", action="store_true",
                    help="Only with a recorded P2 attestation that O_common is cell-day paired.")
    args = ap.parse_args(argv)

    path = default_parquet_path(args.data_dir)
    if path is None or not path.is_file():
        print(f"{PARQUET_NAME} not available (set ${DATA_DIR_ENV} or --data-dir); "
              "nothing written.", file=sys.stderr)
        return 2
    rows = load_rows(path)
    summary = run_stage_a(
        rows, c_min=args.c_min, attest_common_pairing=args.attest_common_pairing,
        source={"file": PARQUET_NAME, "sha256": sha256_file(path),
                "read_filter": "iso_year not in (2020, 2021); partition in "
                               + ", ".join(ALLOWED_PARTITIONS)},
    )
    write_summary(summary, args.out)
    print(f"wrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
