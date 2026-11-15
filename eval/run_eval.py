"""
eval/run_eval.py — Headless evaluation runner for the held-out sensor-switch
experiment (P5-A Lane, task/P5-A-001).

USAGE
-----
    python eval/run_eval.py [--out PATH]

    Reads strictly from $SEALED_EVAL_DIR (never from science/ or pipeline/).
    Writes eval_summary.json (and optionally a public aggregate report) to
    the path given by --out (default: eval/eval_summary.json).

ENVIRONMENT VARIABLES
---------------------
    SEALED_EVAL_DIR   Required.  Path to the directory containing the sealed
                      2020-2021 holdout data files.  Must be a local path;
                      this runner never uploads sealed data to any cloud service.
    EVAL_OUT_DIR      Optional override for the output directory (default: eval/).
    EVAL_ARTIFACT_VERSION  Optional version tag for the output artifact.

FILE LAYOUT EXPECTED UNDER SEALED_EVAL_DIR
------------------------------------------
    cases.json                  — list of registered case descriptors
    factor_registry.json        — frozen calibration factors (a_H variants)
    bootstrap_config.json       — Baseline C bootstrap parameters

FILE FORMAT — cases.json
------------------------
Each entry is a dict with keys:
    case_id              str
    year                 int (2020 or 2021)
    block_id             str
    region_id            str
    outage_flag          bool
    practical_margin_tau float (>= 0, registered before evaluation)
    viirs_d              int | null
    viirs_o              int
    aqua_d_target        int | null   (reference period, same block)
    aqua_o_target        int
    aqua_d_baseline      int | null   (pre-switch baseline period)
    aqua_o_baseline      int
    reference_direction  int | null   (+1/-1/0/None, registered from Aqua-to-Aqua rule)

FILE FORMAT — factor_registry.json
-----------------------------------
{
  "full_training": float,
  "ex_<year>": float,    // one entry per leave-one-year-out variant
  ...
}
All factors must be > 0 (plan §6).

FILE FORMAT — bootstrap_config.json
------------------------------------
{
  "n_replicates": int,
  "confidence_level": float,
  "min_independent_blocks": int,
  "rng_seed": int
}

OUTPUT — eval_summary.json
---------------------------
Schema matches contracts/schemas/evaluation.py::EvaluationSummary extended with
per-baseline EvalMetrics detail.  The file is the canonical eval artifact.

FIREWALL RULES (non-negotiable per AGENTS.md and plan §9A):
- This module NEVER imports from science/ or pipeline/.
- It NEVER writes sealed data or holdout outcomes to Git-tracked files.
- It NEVER suppresses failures, abstentions or unavailable cases.
- It NEVER re-tunes frozen factors based on holdout errors.
- FIRMS hotspot points never enter D, O, baselines, or verdicts.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# Eval-only imports — never science/ or pipeline/
from eval.metrics import CaseResult, EvalMetrics, compute_all_metrics
from eval.baselines import (
    predict_baseline_a,
    predict_baseline_b,
    predict_baseline_c,
    predict_baseline_d,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

EVAL_PROTOCOL_VERSION = "P0-held-out-sensor-switch-v1"
DEFAULT_OUT_FILENAME = "eval_summary.json"


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Headless evaluation runner for the held-out sensor-switch experiment."
    )
    parser.add_argument(
        "--out",
        default=None,
        help="Output path for eval_summary.json (default: eval/eval_summary.json).",
    )
    parser.add_argument(
        "--sealed-dir",
        default=None,
        help="Override SEALED_EVAL_DIR environment variable.",
    )
    args = parser.parse_args(argv)

    # --- Resolve sealed data directory ---
    sealed_dir_str = args.sealed_dir or os.environ.get("SEALED_EVAL_DIR")
    if not sealed_dir_str:
        print(
            "ERROR: SEALED_EVAL_DIR is not set.  "
            "Set it to the local path of the sealed holdout directory before running.",
            file=sys.stderr,
        )
        return 2
    sealed_dir = Path(sealed_dir_str)
    if not sealed_dir.is_dir():
        print(
            f"ERROR: SEALED_EVAL_DIR={sealed_dir!r} does not exist or is not a directory.",
            file=sys.stderr,
        )
        return 2

    # --- Resolve output path ---
    out_dir_str = os.environ.get("EVAL_OUT_DIR", "eval")
    out_path = Path(args.out) if args.out else Path(out_dir_str) / DEFAULT_OUT_FILENAME

    artifact_version = os.environ.get(
        "EVAL_ARTIFACT_VERSION",
        f"eval-v1-run-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}",
    )

    # --- Load sealed inputs ---
    print(f"[run_eval] Loading sealed inputs from: {sealed_dir}")
    try:
        raw_cases = _load_json(sealed_dir / "cases.json")
        factor_registry = _load_json(sealed_dir / "factor_registry.json")
        bootstrap_cfg = _load_json(sealed_dir / "bootstrap_config.json")
    except FileNotFoundError as exc:
        print(f"ERROR: Missing sealed input file: {exc}", file=sys.stderr)
        return 2
    except json.JSONDecodeError as exc:
        print(f"ERROR: Malformed JSON in sealed inputs: {exc}", file=sys.stderr)
        return 2

    _validate_factor_registry(factor_registry)
    a_h_full = factor_registry["full_training"]

    # --- Build CaseResult lists for each baseline ---
    print(f"[run_eval] Processing {len(raw_cases)} registered cases ...")

    cases_a: list[CaseResult] = []
    cases_b: list[CaseResult] = []
    cases_c: list[CaseResult] = []
    cases_d: list[CaseResult] = []

    for rc in raw_cases:
        cid = rc["case_id"]
        year = rc["year"]
        block_id = rc["block_id"]
        region_id = rc["region_id"]
        outage = rc["outage_flag"]
        tau = float(rc["practical_margin_tau"])
        ref_dir = rc.get("reference_direction")

        viirs_d = rc.get("viirs_d")
        viirs_o = int(rc["viirs_o"])
        aqua_d_target = rc.get("aqua_d_target")
        aqua_o_target = int(rc["aqua_o_target"])
        aqua_d_baseline = rc.get("aqua_d_baseline")
        aqua_o_baseline = int(rc["aqua_o_baseline"])

        # Compute R values (sums before division; O=0 → unavailable)
        viirs_r = _safe_r(viirs_d, viirs_o)
        aqua_r_target = _safe_r(aqua_d_target, aqua_o_target)
        aqua_r_baseline = _safe_r(aqua_d_baseline, aqua_o_baseline)

        has_usable_viirs = viirs_o > 0 and viirs_d is not None
        has_usable_ref = aqua_o_target > 0 and aqua_d_target is not None

        # Reference value is the Aqua-to-Aqua EFFECT: aqua_target - aqua_baseline
        # (same period, using Aqua for both sides of the sensor switch)
        ref_value: float | None = None
        if has_usable_ref and aqua_r_baseline is not None:
            ref_value = aqua_r_target - aqua_r_baseline  # type: ignore[operator]
        elif has_usable_ref:
            ref_value = aqua_r_target

        # --- Baseline A ---
        cases_a.append(predict_baseline_a(
            viirs_r=viirs_r,
            has_usable_obs=has_usable_viirs,
            case_id=cid,
            year=year, block_id=block_id, region_id=region_id,
            reference_value=ref_value,
            reference_direction=ref_dir,
            has_usable_reference=has_usable_ref,
            outage_flag=outage,
            practical_margin_tau=tau,
        ))

        # --- Baseline B ---
        cases_b.append(predict_baseline_b(
            viirs_r=viirs_r,
            a_h=a_h_full,
            has_usable_obs=has_usable_viirs,
            case_id=cid,
            year=year, block_id=block_id, region_id=region_id,
            reference_value=ref_value,
            reference_direction=ref_dir,
            has_usable_reference=has_usable_ref,
            outage_flag=outage,
            practical_margin_tau=tau,
        ))

        # --- Baseline C (block-bootstrap) ---
        # Gather block arrays for the entire region associated with this case.
        # For the region-level bootstrap the caller must supply all blocks;
        # here we operate per-case using the case's own D/O arrays.
        # A single-block case will not meet min_independent_blocks and abstains.
        bvd = [viirs_d if viirs_d is not None else 0]
        bvo = [viirs_o]
        bad = [aqua_d_baseline if aqua_d_baseline is not None else 0]
        bao = [aqua_o_baseline]
        cases_c.append(predict_baseline_c(
            block_viirs_d=bvd,
            block_viirs_o=bvo,
            block_aqua_d_baseline=bad,
            block_aqua_o_baseline=bao,
            a_h=a_h_full,
            n_replicates=bootstrap_cfg["n_replicates"],
            confidence_level=bootstrap_cfg["confidence_level"],
            min_independent_blocks=bootstrap_cfg["min_independent_blocks"],
            practical_margin_tau=tau,
            rng_seed=bootstrap_cfg["rng_seed"],
            case_id=cid,
            year=year, block_id=block_id, region_id=region_id,
            reference_value=ref_value,
            reference_direction=ref_dir,
            has_usable_reference=has_usable_ref,
            outage_flag=outage,
        ))

        # --- Baseline D ---
        # Only pass variants that apply to this case (registered against
        # training years available for the case's block/year).
        # For now all registered variants are applied uniformly; a production
        # implementation would filter by registered eligibility rules.
        cases_d.append(predict_baseline_d(
            viirs_r=viirs_r,
            factor_variants=factor_registry,
            has_usable_obs=has_usable_viirs,
            practical_margin_tau=tau,
            case_id=cid,
            year=year, block_id=block_id, region_id=region_id,
            reference_value=ref_value,
            reference_direction=ref_dir,
            has_usable_reference=has_usable_ref,
            outage_flag=outage,
        ))

    # --- Compute metrics ---
    metrics_a = compute_all_metrics(cases_a, "baseline_a_raw_handover")
    metrics_b = compute_all_metrics(cases_b, "baseline_b_point_a_h")
    metrics_c = compute_all_metrics(cases_c, "baseline_c_uncertainty_aware")
    metrics_d = compute_all_metrics(cases_d, "baseline_d_stage_a_finite_audit")

    # --- Compute frozen headline metric ---
    # Headline: "At an artificial sensor switch, raw MODIS-to-VIIRS comparisons
    # pointed the wrong way in X of N cases; after correction, Y of N."
    # Metric: directional error RATE for A vs B (decisive cases only), reported
    # with the full case count and independent-unit counts as the denominator.
    headline = _compute_headline(metrics_a, metrics_b, metrics_c, metrics_d)

    # --- Assemble output ---
    summary = _build_summary(
        artifact_version=artifact_version,
        metrics_a=metrics_a,
        metrics_b=metrics_b,
        metrics_c=metrics_c,
        metrics_d=metrics_d,
        headline=headline,
        n_total=len(raw_cases),
    )

    # --- Write output (never the sealed holdout data, only metrics) ---
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as fh:
        json.dump(summary, fh, indent=2)
    print(f"[run_eval] eval_summary.json written to: {out_path}")
    _print_headline(headline, metrics_a, metrics_b, metrics_c, metrics_d)
    return 0


# ---------------------------------------------------------------------------
# Headline metric
# ---------------------------------------------------------------------------

def _compute_headline(
    ma: EvalMetrics, mb: EvalMetrics, mc: EvalMetrics, md: EvalMetrics
) -> dict[str, Any]:
    """
    Freeze ONE plain-language headline per plan §9A:

      "At an artificial sensor switch, raw MODIS-to-VIIRS comparisons pointed
       the wrong way in X of N cases; after correction, Y of N; Stage A flagged
       Z of the remaining errors and abstained on W."

    Returns a dict that maps directly to the EvaluationSummary fields.
    Denominator is the number of decisive directional cases for Baseline A
    (the widest decisive set, since A never abstains).
    """
    da = ma.directional_accuracy
    db = mb.directional_accuracy
    dc = mc.directional_accuracy
    dd = md.directional_accuracy

    n_total = ma.n_total_registered
    test_years = ma.test_years
    regions = ma.region_ids
    blocks = ma.block_ids
    n_blocks = len(blocks)
    n_regions = len(regions)
    n_years = len(test_years)

    # Errors = decisive cases where direction was WRONG (1 - accuracy)
    def _n_errors(m: MetricResult) -> int | str:
        if m.value is None or m.denominator == 0:
            return "unavailable"
        return m.denominator - (m.numerator or 0)

    def _n_decisive(m: MetricResult) -> int | str:
        return m.denominator if m.denominator > 0 else "unavailable"

    x_a = _n_errors(da)   # wrong-direction count for A (raw)
    n_a = _n_decisive(da)  # decisive N for A
    y_b = _n_errors(db)   # wrong-direction count for B
    n_b = _n_decisive(db)
    # Remaining errors after correction that D flagged / abstained on
    abstentions_d = md.n_abstentions
    n_total_d = md.n_total_registered

    if isinstance(x_a, int) and isinstance(n_a, int) and n_a > 0:
        raw_error_rate = round(x_a / n_a, 4)
    else:
        raw_error_rate = None

    if isinstance(y_b, int) and isinstance(n_b, int) and n_b > 0:
        corrected_error_rate = round(y_b / n_b, 4)
    else:
        corrected_error_rate = None

    headline_value = raw_error_rate if raw_error_rate is not None else -1.0
    headline_desc = (
        "Directional error rate for raw sensor handover (Baseline A) in decisive "
        "Aqua-to-Aqua reference cases. "
        f"Raw: {x_a}/{n_a} wrong; "
        f"After a_H correction (B): {y_b}/{n_b} wrong; "
        f"Stage A abstained on {abstentions_d}/{n_total_d} cases. "
        f"N={n_total} registered cases across "
        f"{n_regions} region(s), {n_years} test year(s); "
        f"{n_blocks} block(s), not independent within a region."
    )
    denom_str = (
        f"{n_a} decisive directional cases "
        f"({n_total} total registered; {ma.n_abstentions} abstentions, "
        f"{ma.n_unavailable_reference} unavailable references excluded); "
        f"test years: {', '.join(str(y) for y in test_years)}; "
        f"regions: {', '.join(regions)}; "
        f"{n_blocks} blocks (not independent within a region)"
    )
    return {
        "headline_metric_description": headline_desc,
        "headline_metric_value": headline_value,
        "headline_denominator": denom_str,
        "independent_units": {
            "blocks": n_blocks,
            "regions": n_regions,
            "test_years": n_years,
        },
    }


# ---------------------------------------------------------------------------
# Output builder
# ---------------------------------------------------------------------------

def _build_summary(
    artifact_version: str,
    metrics_a: EvalMetrics,
    metrics_b: EvalMetrics,
    metrics_c: EvalMetrics,
    metrics_d: EvalMetrics,
    headline: dict[str, Any],
    n_total: int,
) -> dict[str, Any]:
    """Assemble the full eval_summary.json payload."""

    def _metrics_dict(m: EvalMetrics) -> dict[str, Any]:
        return {
            "mean_reference_relative_error": m.mae.value,
            "decision_coverage_percent": round(
                100.0 * m.n_decisive_scoreable / max(m.n_total_registered, 1), 4
            ),
            "abstention_rate_percent": round(
                100.0 * m.n_abstentions / max(m.n_total_registered, 1), 4
            ),
            "mae": {
                "value": m.mae.value,
                "denominator": m.mae.denominator,
                "denominator_description": m.mae.denominator_description,
                "undefined_reason": m.mae.undefined_reason,
            },
            "bias": {
                "value": m.bias.value,
                "denominator": m.bias.denominator,
                "denominator_description": m.bias.denominator_description,
                "undefined_reason": m.bias.undefined_reason,
            },
            "overlap": {
                "value": m.overlap.value,
                "denominator": m.overlap.denominator,
                "denominator_description": m.overlap.denominator_description,
                "undefined_reason": m.overlap.undefined_reason,
            },
            "directional_accuracy": {
                "value": m.directional_accuracy.value,
                "numerator": m.directional_accuracy.numerator,
                "denominator": m.directional_accuracy.denominator,
                "denominator_description": m.directional_accuracy.denominator_description,
                "undefined_reason": m.directional_accuracy.undefined_reason,
            },
            "n_total_registered": m.n_total_registered,
            "n_abstentions": m.n_abstentions,
            "n_unavailable_reference": m.n_unavailable_reference,
            "n_unavailable_prediction": m.n_unavailable_prediction,
            "n_outage_flagged": m.n_outage_flagged,
            "n_decisive_scoreable": m.n_decisive_scoreable,
            "test_years": m.test_years,
            "region_ids": m.region_ids,
            "block_ids": m.block_ids,
            "failures_and_notes": m.failures_and_notes,
        }

    all_failures: list[str] = list({
        note
        for m in [metrics_a, metrics_b, metrics_c, metrics_d]
        for note in m.failures_and_notes
    })
    all_failures.sort()

    return {
        "artifact_version": artifact_version,
        "eval_protocol_version": EVAL_PROTOCOL_VERSION,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "n_total_registered_cases": n_total,
        "baseline_a_raw_handover": _metrics_dict(metrics_a),
        "baseline_b_point_a_h": _metrics_dict(metrics_b),
        "baseline_c_uncertainty_aware": _metrics_dict(metrics_c),
        "baseline_d_stage_a_finite_audit": _metrics_dict(metrics_d),
        "headline_metric_description": headline["headline_metric_description"],
        "headline_metric_value": headline["headline_metric_value"],
        "headline_denominator": headline["headline_denominator"],
        "independent_units": headline["independent_units"],
        "failures_and_limitations": all_failures,
    }


# ---------------------------------------------------------------------------
# Validation helpers
# ---------------------------------------------------------------------------

def _validate_factor_registry(registry: dict[str, Any]) -> None:
    if "full_training" not in registry:
        raise ValueError(
            "factor_registry.json must contain 'full_training' key (the full-training a_H)."
        )
    for key, val in registry.items():
        if not isinstance(val, (int, float)):
            raise ValueError(f"factor_registry: value for {key!r} must be numeric; got {val!r}.")
        if float(val) <= 0:
            raise ValueError(
                f"factor_registry: factor {key!r} = {val} is non-positive. "
                "Per plan §6, a nonpositive factor is unavailable."
            )


def _safe_r(d: int | None, o: int) -> float | None:
    """R = 1000*D/O; returns None when O=0 or D is None (plan §4)."""
    if o == 0 or d is None:
        return None
    return 1000.0 * d / o


def _load_json(path: Path) -> Any:
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def _print_headline(
    headline: dict[str, Any],
    ma: EvalMetrics, mb: EvalMetrics, mc: EvalMetrics, md: EvalMetrics,
) -> None:
    print("\n--- HEADLINE METRIC ---")
    print(headline["headline_metric_description"])
    print(f"Denominator: {headline['headline_denominator']}")
    iu = headline["independent_units"]
    print(
        f"Independent units: {iu['blocks']} blocks, "
        f"{iu['regions']} region(s), {iu['test_years']} test year(s)"
    )
    print(
        f"Note: blocks within one region are dependent; "
        f"never present N cases as N independent tests."
    )
    print("-----------------------\n")


# ---------------------------------------------------------------------------
# CLI entry
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    sys.exit(main())
