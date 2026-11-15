"""
eval/baselines.py — Baseline A–D predictors for the held-out sensor-switch
experiment (Section 9A, THE_THIRD_EYE_FINAL_PLAN_GEOGRAPHIC_ACCESS_UPDATED.txt).

BASELINE DEFINITIONS (frozen, do not retune on holdouts):
  A — Raw sensor handover: apply VIIRS R directly with no calibration.
      Always issues a decision (abstention_rate=0 when O>0).
  B — Point a_H harmonization: multiply VIIRS R by the full-training a_H
      factor (Aqua own-support pooled rate / VIIRS own-support pooled rate).
      Always issues a decision (same coverage as A).
  C — Uncertainty-aware baseline: block-bootstrap confidence interval at a
      registered confidence level around the a_H-adjusted estimate.  Abstains
      when the interval straddles ±tau (within-margin) or when minimum
      independent blocks cannot be formed.
  D — Stage A finite registered-factor audit: applies each leave-one-year-out
      factor variant; abstains (unresolved) when variants disagree on direction
      beyond tau.

RULES:
- Baselines use the same eligible cases, same registered support thresholds,
  same train/test split and same tau as Stage A.
- Baselines are computed from frozen method artifacts; this module never reads
  sealed holdout data directly.  The runner (run_eval.py) loads the data
  and calls these functions.
- O=0 → unavailable; CaseResult.has_usable_prediction=False;
  predicted_value=None; is_abstention stays False (unavailable ≠ abstention).
- FIRMS hotspot points never enter D, O, baselines or verdicts.
"""

from __future__ import annotations

import random
import math
from typing import Sequence

from eval.metrics import CaseResult


# ---------------------------------------------------------------------------
# Baseline A — Raw sensor handover
# ---------------------------------------------------------------------------

def predict_baseline_a(
    viirs_r: float | None,
    has_usable_obs: bool,
    case_id: str,
    year: int,
    block_id: str,
    region_id: str,
    reference_value: float | None,
    reference_direction: int | None,
    has_usable_reference: bool,
    outage_flag: bool,
    practical_margin_tau: float,
) -> CaseResult:
    """
    Baseline A: raw VIIRS R, no calibration applied.

    Issues a decision whenever VIIRS O>0 (has_usable_obs=True).
    Predicted direction is sign(viirs_r - baseline_reference_period_r); the caller
    must supply pre-computed reference_direction from the REGISTERED rule.
    """
    if not has_usable_obs or viirs_r is None:
        return CaseResult(
            case_id=case_id,
            reference_value=reference_value,
            predicted_value=None,
            is_abstention=False,        # unavailable ≠ abstention
            reference_direction=reference_direction,
            predicted_direction=None,   # cannot determine without usable obs
            practical_margin_tau=practical_margin_tau,
            has_usable_reference=has_usable_reference,
            has_usable_prediction=False,
            outage_flag=outage_flag,
            year=year,
            block_id=block_id,
            region_id=region_id,
        )
    pred_dir = _direction(viirs_r, reference_value, practical_margin_tau)
    return CaseResult(
        case_id=case_id,
        reference_value=reference_value,
        predicted_value=viirs_r,
        is_abstention=False,
        reference_direction=reference_direction,
        predicted_direction=pred_dir,
        practical_margin_tau=practical_margin_tau,
        has_usable_reference=has_usable_reference,
        has_usable_prediction=True,
        outage_flag=outage_flag,
        year=year,
        block_id=block_id,
        region_id=region_id,
    )


# ---------------------------------------------------------------------------
# Baseline B — Point a_H harmonization
# ---------------------------------------------------------------------------

def predict_baseline_b(
    viirs_r: float | None,
    a_h: float,
    has_usable_obs: bool,
    case_id: str,
    year: int,
    block_id: str,
    region_id: str,
    reference_value: float | None,
    reference_direction: int | None,
    has_usable_reference: bool,
    outage_flag: bool,
    practical_margin_tau: float,
) -> CaseResult:
    """
    Baseline B: apply the full-training a_H factor to VIIRS R.

    a_H = pooled_aqua_own_support_rate / pooled_viirs_own_support_rate,
    computed on training years only, frozen before holdout inspection.

    Raises ValueError if a_H <= 0 (plan §6: 'nonpositive factor → unavailable').
    """
    if a_h <= 0:
        raise ValueError(
            f"Baseline B: a_H must be > 0; got {a_h}. "
            "A nonpositive factor means the baseline is unavailable."
        )
    if not has_usable_obs or viirs_r is None:
        return CaseResult(
            case_id=case_id,
            reference_value=reference_value,
            predicted_value=None,
            is_abstention=False,
            reference_direction=reference_direction,
            predicted_direction=None,
            practical_margin_tau=practical_margin_tau,
            has_usable_reference=has_usable_reference,
            has_usable_prediction=False,
            outage_flag=outage_flag,
            year=year,
            block_id=block_id,
            region_id=region_id,
        )
    adjusted = viirs_r * a_h
    pred_dir = _direction(adjusted, reference_value, practical_margin_tau)
    return CaseResult(
        case_id=case_id,
        reference_value=reference_value,
        predicted_value=adjusted,
        is_abstention=False,
        reference_direction=reference_direction,
        predicted_direction=pred_dir,
        practical_margin_tau=practical_margin_tau,
        has_usable_reference=has_usable_reference,
        has_usable_prediction=True,
        outage_flag=outage_flag,
        year=year,
        block_id=block_id,
        region_id=region_id,
    )


# ---------------------------------------------------------------------------
# Baseline C — Block-bootstrap uncertainty-aware interval
# ---------------------------------------------------------------------------

def predict_baseline_c(
    block_viirs_d: Sequence[int],
    block_viirs_o: Sequence[int],
    block_aqua_d_baseline: Sequence[int],
    block_aqua_o_baseline: Sequence[int],
    a_h: float,
    n_replicates: int,
    confidence_level: float,
    min_independent_blocks: int,
    practical_margin_tau: float,
    rng_seed: int,
    case_id: str,
    year: int,
    block_id: str,
    region_id: str,
    reference_value: float | None,
    reference_direction: int | None,
    has_usable_reference: bool,
    outage_flag: bool,
) -> CaseResult:
    """
    Baseline C: block-bootstrap CI on the a_H-adjusted period effect.

    Resamples registered geographic blocks jointly across both periods.
    Abstains when:
    - fewer than min_independent_blocks usable blocks exist, OR
    - the interval straddles both sides of ±tau (within-margin undecidable).

    Parameters
    ----------
    block_viirs_d / block_viirs_o  : per-block VIIRS D and O for the target period
    block_aqua_d_baseline / ...o   : per-block Aqua D and O for the baseline period
    a_h                            : frozen full-training own-support factor
    n_replicates                   : bootstrap replicate count (frozen at kickoff)
    confidence_level               : e.g. 0.90 (frozen at kickoff)
    min_independent_blocks         : minimum block count to run bootstrap (frozen)
    practical_margin_tau           : pre-registered margin (same units as R = 1000*D/O)
    rng_seed                       : frozen random seed
    """
    if a_h <= 0:
        raise ValueError(f"Baseline C: a_H must be > 0; got {a_h}.")

    n_blocks = len(block_viirs_d)
    if n_blocks != len(block_viirs_o) or n_blocks != len(block_aqua_d_baseline) or \
            n_blocks != len(block_aqua_o_baseline):
        raise ValueError("Baseline C: block arrays must all have the same length.")

    # Identify usable blocks: both periods must have O>0
    usable_idx = [
        i for i in range(n_blocks)
        if block_viirs_o[i] > 0 and block_aqua_o_baseline[i] > 0
    ]
    n_usable = len(usable_idx)

    # --- Branch 1: truly unavailable (zero usable blocks, O=0 on all blocks) ---
    # unavailable ≠ abstention: the method cannot issue any prediction at all.
    if n_usable == 0:
        return CaseResult(
            case_id=case_id,
            reference_value=reference_value,
            predicted_value=None,
            is_abstention=False,        # unavailable, not an abstention
            reference_direction=reference_direction,
            predicted_direction=None,
            practical_margin_tau=practical_margin_tau,
            has_usable_reference=has_usable_reference,
            has_usable_prediction=False,
            outage_flag=outage_flag,
            year=year,
            block_id=block_id,
            region_id=region_id,
        )

    # --- Branch 2: data exists but insufficient independent blocks to run bootstrap ---
    # Enough O>0 blocks exist, so we have usable predictions in principle, but the
    # bootstrap requires at least min_independent_blocks to form a valid CI.
    # This IS an abstention: the method has data but cannot issue a confident answer.
    if n_usable < min_independent_blocks:
        return CaseResult(
            case_id=case_id,
            reference_value=reference_value,
            predicted_value=None,
            is_abstention=True,         # method withholds answer due to insufficient blocks
            reference_direction=reference_direction,
            predicted_direction=None,
            practical_margin_tau=practical_margin_tau,
            has_usable_reference=has_usable_reference,
            has_usable_prediction=True, # data present, but bootstrap cannot run
            outage_flag=outage_flag,
            year=year,
            block_id=block_id,
            region_id=region_id,
        )

    rng = random.Random(rng_seed)
    alpha = 1.0 - confidence_level
    lower_pct = alpha / 2.0
    upper_pct = 1.0 - alpha / 2.0

    bootstrap_effects: list[float] = []
    for _ in range(n_replicates):
        sample_idx = [rng.choice(usable_idx) for _ in range(n_usable)]
        viirs_d_sum = sum(block_viirs_d[i] for i in sample_idx)
        viirs_o_sum = sum(block_viirs_o[i] for i in sample_idx)
        aqua_d_sum = sum(block_aqua_d_baseline[i] for i in sample_idx)
        aqua_o_sum = sum(block_aqua_o_baseline[i] for i in sample_idx)
        if viirs_o_sum == 0 or aqua_o_sum == 0:
            continue
        viirs_r_rep = 1000.0 * viirs_d_sum / viirs_o_sum
        aqua_r_base = 1000.0 * aqua_d_sum / aqua_o_sum
        effect = viirs_r_rep * a_h - aqua_r_base
        bootstrap_effects.append(effect)

    if len(bootstrap_effects) < 2:
        # Bootstrap produced too few non-zero-O resamples to form a CI.
        # This is an abstention (data present, CI not computable), not unavailable.
        return CaseResult(
            case_id=case_id,
            reference_value=reference_value,
            predicted_value=None,
            is_abstention=True,
            reference_direction=reference_direction,
            predicted_direction=None,
            practical_margin_tau=practical_margin_tau,
            has_usable_reference=has_usable_reference,
            has_usable_prediction=True,  # blocks exist; bootstrap itself failed
            outage_flag=outage_flag,
            year=year,
            block_id=block_id,
            region_id=region_id,
        )

    bootstrap_effects.sort()
    n_eff = len(bootstrap_effects)
    lo = bootstrap_effects[max(0, math.ceil(lower_pct * n_eff) - 1)]
    hi = bootstrap_effects[min(n_eff - 1, math.ceil(upper_pct * n_eff) - 1)]
    point_effect = sum(bootstrap_effects) / n_eff   # bootstrap mean as point estimate

    # Decision rule: abstain unless CI lies wholly above +tau or wholly below -tau
    if lo > practical_margin_tau:
        pred_dir = 1
        is_abs = False
    elif hi < -practical_margin_tau:
        pred_dir = -1
        is_abs = False
    else:
        # Straddles margin → abstain (within-margin undecidable)
        pred_dir = None
        is_abs = True

    return CaseResult(
        case_id=case_id,
        reference_value=reference_value,
        predicted_value=point_effect if not is_abs else None,
        is_abstention=is_abs,
        reference_direction=reference_direction,
        predicted_direction=pred_dir,
        practical_margin_tau=practical_margin_tau,
        has_usable_reference=has_usable_reference,
        has_usable_prediction=True,
        outage_flag=outage_flag,
        year=year,
        block_id=block_id,
        region_id=region_id,
    )


# ---------------------------------------------------------------------------
# Baseline D — Stage A finite registered-factor audit
# ---------------------------------------------------------------------------

def predict_baseline_d(
    viirs_r: float | None,
    factor_variants: dict[str, float],
    has_usable_obs: bool,
    practical_margin_tau: float,
    case_id: str,
    year: int,
    block_id: str,
    region_id: str,
    reference_value: float | None,
    reference_direction: int | None,
    has_usable_reference: bool,
    outage_flag: bool,
) -> CaseResult:
    """
    Baseline D: Stage A finite registered-factor audit.

    Applies each leave-one-year-out factor variant (and the full-training variant)
    to VIIRS R, computes the effect against the reference, and checks directional
    agreement across variants.

    Abstains (unresolved) when:
    - variants disagree on direction (some above +tau, some below -tau, or some
      within-margin), OR
    - any required variant is missing (nonpositive factor → unavailable; a
      required undefined factor follows unresolved precedence per plan §7).

    factor_variants must be non-empty and all values > 0, registered before
    holdout inspection.
    """
    if not factor_variants:
        raise ValueError(
            "Baseline D: factor_variants must be non-empty. "
            "Register all leave-one-year-out variants before evaluation."
        )
    for vid, fv in factor_variants.items():
        if fv <= 0:
            raise ValueError(
                f"Baseline D: factor {vid!r} = {fv} is non-positive. "
                "Per plan §6, a nonpositive/undefined factor is unavailable; "
                "unresolved precedence applies."
            )

    if not has_usable_obs or viirs_r is None:
        return CaseResult(
            case_id=case_id,
            reference_value=reference_value,
            predicted_value=None,
            is_abstention=False,
            reference_direction=reference_direction,
            predicted_direction=None,
            practical_margin_tau=practical_margin_tau,
            has_usable_reference=has_usable_reference,
            has_usable_prediction=False,
            outage_flag=outage_flag,
            year=year,
            block_id=block_id,
            region_id=region_id,
        )

    # Apply each factor and collect directional outcomes
    dirs: set[int | None] = set()
    effects: list[float] = []
    for fv in factor_variants.values():
        effect = viirs_r * fv - (reference_value if reference_value is not None else 0.0)
        effects.append(viirs_r * fv)   # calibrated VIIRS, not the effect
        d = _direction_from_effect(effect, practical_margin_tau)
        dirs.add(d)

    # If reference is unavailable we cannot assess direction, but can still
    # record the calibrated prediction for MAE/Bias when reference arrives.
    point_pred = sum(viirs_r * fv for fv in factor_variants.values()) / len(factor_variants)

    if not has_usable_reference or reference_value is None:
        return CaseResult(
            case_id=case_id,
            reference_value=reference_value,
            predicted_value=point_pred,
            is_abstention=False,
            reference_direction=None,
            predicted_direction=None,
            practical_margin_tau=practical_margin_tau,
            has_usable_reference=False,
            has_usable_prediction=True,
            outage_flag=outage_flag,
            year=year,
            block_id=block_id,
            region_id=region_id,
        )

    # Check consensus
    unique_decisive = {d for d in dirs if d is not None and d != 0}
    has_within_margin = 0 in dirs
    is_unresolved = len(unique_decisive) > 1 or has_within_margin or len(dirs) > 1

    if is_unresolved:
        return CaseResult(
            case_id=case_id,
            reference_value=reference_value,
            predicted_value=point_pred,
            is_abstention=True,       # unresolved → abstain per plan §7
            reference_direction=reference_direction,
            predicted_direction=None,
            practical_margin_tau=practical_margin_tau,
            has_usable_reference=has_usable_reference,
            has_usable_prediction=True,
            outage_flag=outage_flag,
            year=year,
            block_id=block_id,
            region_id=region_id,
        )

    pred_dir = next(iter(dirs), None)
    return CaseResult(
        case_id=case_id,
        reference_value=reference_value,
        predicted_value=point_pred,
        is_abstention=False,
        reference_direction=reference_direction,
        predicted_direction=pred_dir,
        practical_margin_tau=practical_margin_tau,
        has_usable_reference=has_usable_reference,
        has_usable_prediction=True,
        outage_flag=outage_flag,
        year=year,
        block_id=block_id,
        region_id=region_id,
    )


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

def _direction(
    predicted: float | None,
    reference: float | None,
    tau: float,
) -> int | None:
    """
    Encode direction of (predicted − reference) relative to tau.

    Returns +1 (increase), -1 (decrease), 0 (within margin), or None when
    either value is missing.
    """
    if predicted is None or reference is None:
        return None
    return _direction_from_effect(predicted - reference, tau)


def _direction_from_effect(effect: float, tau: float) -> int | None:
    """Encode sign of effect relative to ±tau."""
    if effect > tau:
        return 1
    if effect < -tau:
        return -1
    return 0  # within practical margin
