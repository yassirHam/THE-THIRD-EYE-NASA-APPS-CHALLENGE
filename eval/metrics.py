"""
eval/metrics.py — Frozen benchmark metrics for the held-out sensor-switch experiment.

Implements the four pre-registered evaluation metrics per Section 9A of
THE_THIRD_EYE_FINAL_PLAN_GEOGRAPHIC_ACCESS_UPDATED.txt:

  MAE        — Mean Absolute Error (reference-relative, absolute-indicator units)
  Bias       — Signed mean error (positive = overcount vs reference)
  Overlap    — Fraction of predictions within practical margin tau of the reference
  DirectionalAccuracy — Fraction of decisive predictions whose sign matches the
                        Aqua-to-Aqua reference direction

RULES (non-negotiable):
- O=0 cases are UNAVAILABLE; they never enter an error calculation as zero.
- Missing reference periods cannot score directional accuracy; they are counted
  separately in the availability table.
- Abstentions are excluded from error denominators but reported in coverage
  tallies alongside decisive answers.
- Never suppress failures, abstentions or unavailable cases to improve metrics.
- FIRMS hotspot points are a separate view and never enter D, O or these metrics.
- These functions own no data; callers supply pre-validated arrays.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Sequence


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class CaseResult:
    """
    One registered evaluation case (a block × period pair).

    Fields
    ------
    case_id          : Unique identifier, e.g. "BLK-04:2020-JUL"
    reference_value  : Aqua-to-Aqua reference R (may be None when unavailable)
    predicted_value  : Method output R on the same period (may be None for abstention)
    is_abstention    : True when the method withheld a decisive answer
    reference_direction : +1 (increase vs baseline), -1 (decrease), 0 (no change),
                          or None when the reference itself is unavailable.
                          Computed by the caller from the REGISTERED direction rule
                          BEFORE holdout inspection.
    predicted_direction : Same encoding from the method output.  None for abstentions
                          or when the method could not determine direction.
    practical_margin_tau : Non-negative margin registered before evaluation (plan §9A).
    has_usable_reference : False when O_reference=0 or the reference period is absent.
    has_usable_prediction: False when O_predicted=0.
    outage_flag      : True when this case touches the 2020 Aqua FMU/SSR outage
                       interval; counted separately, never silently dropped.
    year             : Test year (e.g. 2020 or 2021).
    block_id         : Geographic block identifier.
    region_id        : Region the block belongs to.
    """
    case_id: str
    reference_value: float | None
    predicted_value: float | None
    is_abstention: bool
    reference_direction: int | None        # +1, -1, 0, or None
    predicted_direction: int | None        # +1, -1, 0, or None
    practical_margin_tau: float            # registered before evaluation; >= 0
    has_usable_reference: bool             # False → O_ref=0 or missing
    has_usable_prediction: bool            # False → O_pred=0
    outage_flag: bool
    year: int
    block_id: str
    region_id: str


@dataclass
class MetricResult:
    """
    Container for a single metric computed over a list of CaseResults.

    Every metric carries its own denominator string so callers can include it
    verbatim in the headline table, as required by the plan.
    """
    metric_name: str
    value: float | None           # None when computation is undefined
    numerator: int | None         # count feeding the metric (optional)
    denominator: int              # total cases considered (explicit, never hidden)
    denominator_description: str  # e.g. "24 decisive cases across 1 region, 2 test years"
    undefined_reason: str | None  # populated when value is None


@dataclass
class EvalMetrics:
    """All four frozen benchmark metrics for one baseline, plus availability counts."""
    baseline_id: str
    mae: MetricResult
    bias: MetricResult
    overlap: MetricResult
    directional_accuracy: MetricResult
    # Case accounting (never rolled into metric denominators)
    n_total_registered: int
    n_abstentions: int
    n_unavailable_reference: int   # O_ref=0 or missing; never scored
    n_unavailable_prediction: int  # O_pred=0; never scored
    n_outage_flagged: int
    n_decisive_scoreable: int      # cases that enter error metrics
    # Year and region breakdown (must be reported alongside headline)
    test_years: list[int] = field(default_factory=list)
    region_ids: list[str] = field(default_factory=list)
    block_ids: list[str] = field(default_factory=list)
    failures_and_notes: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Metric 1: MAE
# ---------------------------------------------------------------------------

def compute_mae(cases: Sequence[CaseResult], baseline_id: str) -> MetricResult:
    """
    Mean Absolute Error relative to the Aqua-to-Aqua reference.

    Denominator: decisive, scoreable cases (reference available, prediction
    available, not an abstention, not O=0 on either side).

    Returns MetricResult with value=None and undefined_reason if no scoreable
    cases exist.
    """
    scoreable = _scoreable(cases)
    n = len(scoreable)
    if n == 0:
        return MetricResult(
            metric_name="MAE",
            value=None,
            numerator=None,
            denominator=0,
            denominator_description=_denom_description(cases, n, "MAE"),
            undefined_reason="No scoreable cases (all abstentions or unavailable references).",
        )
    total_ae = sum(abs(c.predicted_value - c.reference_value) for c in scoreable)  # type: ignore[operator]
    return MetricResult(
        metric_name="MAE",
        value=round(total_ae / n, 6),
        numerator=n,
        denominator=n,
        denominator_description=_denom_description(cases, n, "MAE"),
        undefined_reason=None,
    )


# ---------------------------------------------------------------------------
# Metric 2: Bias
# ---------------------------------------------------------------------------

def compute_bias(cases: Sequence[CaseResult], baseline_id: str) -> MetricResult:
    """
    Signed mean error (predicted − reference).

    Positive values indicate the baseline systematically overcounts relative
    to the Aqua-to-Aqua reference; negative indicates undercounting.

    Same denominator rule as MAE.
    """
    scoreable = _scoreable(cases)
    n = len(scoreable)
    if n == 0:
        return MetricResult(
            metric_name="Bias",
            value=None,
            numerator=None,
            denominator=0,
            denominator_description=_denom_description(cases, n, "Bias"),
            undefined_reason="No scoreable cases (all abstentions or unavailable references).",
        )
    total_err = sum(c.predicted_value - c.reference_value for c in scoreable)  # type: ignore[operator]
    return MetricResult(
        metric_name="Bias",
        value=round(total_err / n, 6),
        numerator=n,
        denominator=n,
        denominator_description=_denom_description(cases, n, "Bias"),
        undefined_reason=None,
    )


# ---------------------------------------------------------------------------
# Metric 3: Overlap  (within practical margin tau)
# ---------------------------------------------------------------------------

def compute_overlap(cases: Sequence[CaseResult], baseline_id: str) -> MetricResult:
    """
    Fraction of scoreable predictions within ±tau of the reference.

    tau is per-case (registered before evaluation, may differ by block/season).
    Cases with tau < 0 are a contract violation; this function raises ValueError
    so the caller cannot silently ignore a bad pre-registered margin.

    Returns proportion [0, 1]; multiply by 100 for percentage if needed.
    """
    scoreable = _scoreable(cases)
    n = len(scoreable)
    if n == 0:
        return MetricResult(
            metric_name="Overlap",
            value=None,
            numerator=None,
            denominator=0,
            denominator_description=_denom_description(cases, n, "Overlap"),
            undefined_reason="No scoreable cases.",
        )
    within = 0
    for c in scoreable:
        if c.practical_margin_tau < 0:
            raise ValueError(
                f"Case {c.case_id!r}: practical_margin_tau must be >= 0; "
                f"got {c.practical_margin_tau}. Register the margin before evaluation."
            )
        diff = abs(c.predicted_value - c.reference_value)  # type: ignore[operator]
        if diff <= c.practical_margin_tau:
            within += 1
    return MetricResult(
        metric_name="Overlap",
        value=round(within / n, 6),
        numerator=within,
        denominator=n,
        denominator_description=_denom_description(cases, n, "Overlap"),
        undefined_reason=None,
    )


# ---------------------------------------------------------------------------
# Metric 4: Directional Accuracy
# ---------------------------------------------------------------------------

def compute_directional_accuracy(
    cases: Sequence[CaseResult], baseline_id: str
) -> MetricResult:
    """
    Fraction of decisive predictions whose direction matches the reference.

    Decisive here means:
    - reference_direction is not None (reference available and unambiguous)
    - predicted_direction is not None (method issued a direction, not abstained)
    - both reference and prediction have usable support (O > 0)
    - not flagged as abstention

    Cases with reference_direction=0 (tied/within-margin at the reference) are
    ambiguous direction cases; they are excluded from this metric and tallied
    separately to avoid masking genuine disagreements.

    Returns proportion [0, 1]; returns None with undefined_reason when the
    decisive directional set is empty.
    """
    directional_cases = [
        c for c in cases
        if (
            not c.is_abstention
            and c.has_usable_reference
            and c.has_usable_prediction
            and c.reference_direction is not None
            and c.reference_direction != 0      # skip tied-at-reference cases
            and c.predicted_direction is not None
        )
    ]
    n = len(directional_cases)
    if n == 0:
        return MetricResult(
            metric_name="DirectionalAccuracy",
            value=None,
            numerator=None,
            denominator=0,
            denominator_description=_denom_description(cases, n, "DirectionalAccuracy"),
            undefined_reason=(
                "No decisive directional cases "
                "(all abstentions, unavailable references, or tied reference directions)."
            ),
        )
    correct = sum(
        1 for c in directional_cases if c.predicted_direction == c.reference_direction
    )
    return MetricResult(
        metric_name="DirectionalAccuracy",
        value=round(correct / n, 6),
        numerator=correct,
        denominator=n,
        denominator_description=_denom_description(cases, n, "DirectionalAccuracy"),
        undefined_reason=None,
    )


# ---------------------------------------------------------------------------
# Convenience: compute all four metrics at once
# ---------------------------------------------------------------------------

def compute_all_metrics(cases: Sequence[CaseResult], baseline_id: str) -> EvalMetrics:
    """
    Compute all four frozen metrics and populate availability accounting.

    This is the primary entry point for run_eval.py and the test harness.
    """
    n_total = len(cases)
    n_abstentions = sum(1 for c in cases if c.is_abstention)
    n_unavail_ref = sum(1 for c in cases if not c.has_usable_reference)
    n_unavail_pred = sum(1 for c in cases if not c.has_usable_prediction and not c.is_abstention)
    n_outage = sum(1 for c in cases if c.outage_flag)
    n_decisive = len(_scoreable(cases))

    test_years = sorted({c.year for c in cases})
    region_ids = sorted({c.region_id for c in cases})
    block_ids = sorted({c.block_id for c in cases})

    failures: list[str] = []
    if n_unavail_ref > 0:
        failures.append(
            f"{n_unavail_ref} case(s) had unavailable reference (O_ref=0 or missing); "
            "excluded from error metrics, retained in availability table."
        )
    if n_outage > 0:
        failures.append(
            f"{n_outage} case(s) flagged for 2020 Aqua FMU/SSR outage interval "
            "(Aug 16 – Sep 2 2020); reported separately."
        )
    if n_abstentions > 0:
        failures.append(
            f"{n_abstentions} abstention(s); excluded from error denominators, "
            "reported in coverage tally."
        )
    # Always emit at least one entry so failures_and_limitations is never empty.
    # An empty list would be rejected by any schema that enforces min_length=1,
    # and a clean run is itself a scope/limitation note worth recording.
    if not failures:
        failures.append(
            "Evaluation scope: primary region only; "
            "transferability to other biomes and sensor eras is unvalidated."
        )

    return EvalMetrics(
        baseline_id=baseline_id,
        mae=compute_mae(cases, baseline_id),
        bias=compute_bias(cases, baseline_id),
        overlap=compute_overlap(cases, baseline_id),
        directional_accuracy=compute_directional_accuracy(cases, baseline_id),
        n_total_registered=n_total,
        n_abstentions=n_abstentions,
        n_unavailable_reference=n_unavail_ref,
        n_unavailable_prediction=n_unavail_pred,
        n_outage_flagged=n_outage,
        n_decisive_scoreable=n_decisive,
        test_years=test_years,
        region_ids=region_ids,
        block_ids=block_ids,
        failures_and_notes=failures,
    )


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

def _scoreable(cases: Sequence[CaseResult]) -> list[CaseResult]:
    """
    Cases that enter error metric denominators:
    - not an abstention
    - reference available and usable (O_ref > 0)
    - prediction available and usable (O_pred > 0)
    - both reference_value and predicted_value are finite floats
    """
    result = []
    for c in cases:
        if c.is_abstention:
            continue
        if not c.has_usable_reference or c.reference_value is None:
            continue
        if not c.has_usable_prediction or c.predicted_value is None:
            continue
        if not (math.isfinite(c.reference_value) and math.isfinite(c.predicted_value)):
            continue
        result.append(c)
    return result


def _denom_description(
    cases: Sequence[CaseResult], n_scoreable: int, metric_name: str
) -> str:
    """Human-readable denominator string for the headline table.

    Per Section 9A, blocks, regions, and test years must all appear alongside
    case counts.  Blocks are listed explicitly; callers must never present N
    cases as N independent tests when multiple blocks share a region.
    """
    n_total = len(cases)
    years = sorted({c.year for c in cases})
    regions = sorted({c.region_id for c in cases})
    blocks = sorted({c.block_id for c in cases})
    n_abs = sum(1 for c in cases if c.is_abstention)
    n_no_ref = sum(1 for c in cases if not c.has_usable_reference)
    year_str = ", ".join(str(y) for y in years) if years else "none"
    region_str = ", ".join(regions) if regions else "none"
    block_str = ", ".join(blocks) if blocks else "none"
    return (
        f"{n_scoreable} of {n_total} registered cases "
        f"({metric_name}; {n_abs} abstentions, {n_no_ref} unavailable references excluded); "
        f"test years: {year_str}; regions: {region_str}; "
        f"blocks: {block_str} (not independent within a region)"
    )
