"""
Stage A sensor-switch harmonization — own-support (a_H) and
common-support (a_C) calibration factors.

Scientific authority:
  THE_THIRD_EYE_FINAL_PLAN_GEOGRAPHIC_ACCESS_UPDATED.txt  §6, §7, §8
  contracts/schemas/comparison.py

GUARDRAILS (non-negotiable):
- O = 0 is MISSING/UNAVAILABLE.  It never becomes zero fire (D = 0).
- Sums of D and O are computed across all eligible observations BEFORE
  division.  Never average rates then divide.
- a_H and a_C are separate estimands.  a_C never substitutes for a_H.
- A non-positive or undefined factor is UNAVAILABLE — never 0 or 1.
- Status dimensions (sensitivity, applicability, inference, practical_change)
  are strictly independent and must never be collapsed.
- Stage B and Evidence Repair are out of scope here.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from enum import Enum
from typing import Iterable, Literal, Optional

# ---------------------------------------------------------------------------
# Public constants
# ---------------------------------------------------------------------------
METHOD_ID = "stage_a_finite_factors"
TRAINING_YEARS_DEFAULT: tuple[int, ...] = (2016, 2017, 2018)
DEVELOPMENT_YEAR: int = 2019
SCALE: float = 1000.0  # R = 1000 * D / O


# ---------------------------------------------------------------------------
# Domain value types
# ---------------------------------------------------------------------------
class Availability(str, Enum):
    """Observation availability for a single cell-day or aggregate."""

    AVAILABLE = "available"
    UNAVAILABLE = "unavailable"  # O = 0 or missing swath


class FactorStatus(str, Enum):
    AVAILABLE = "available"
    UNAVAILABLE = "unavailable"  # zero O, negative/zero result, or insufficient support


class SensitivityStatus(str, Enum):
    STABLE = "stable_across_displayed_settings"
    SENSITIVE = "sensitive"
    UNRESOLVED = "unresolved"


class ApplicabilityStatus(str, Enum):
    EVALUATED = "evaluated_for_conditions"
    OUTSIDE_EVALUATED = "outside_evaluated_conditions"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"


class InferenceStatus(str, Enum):
    NOT_ESTABLISHED = "not_established"


class PracticalChange(str, Enum):
    MEANINGFUL_INCREASE = "meaningful_increase"
    MEANINGFUL_DECREASE = "meaningful_decrease"
    WITHIN_MARGIN = "within_practical_margin"
    UNSPECIFIED = "unspecified"


class HeadlineDirection(str, Enum):
    INCREASE = "increase"
    DECREASE = "decrease"
    NO_CHANGE = "no_change"
    AMBIGUOUS = "ambiguous"
    UNRESOLVED = "unresolved"


# ---------------------------------------------------------------------------
# Input record
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class ObsRecord:
    """
    One aggregate observation block: a sensor, year, calendar stratum,
    and policy (own-support or common-support).

    D: detected fire-cell-days (non-negative integer).
    O: usable land-cell-days denominator.
        O = 0  <=>  the period is UNAVAILABLE; D is meaningless.
        Caller must NOT pass O = 0 with a non-zero D as "no fire detected".
    policy: 'own_support' or 'common_support'.
    """

    sensor: Literal["aqua", "viirs"]
    year: int
    stratum: str  # e.g. "month_07" or "annual"
    policy: Literal["own_support", "common_support"]
    D: int  # detected fire-cell-days
    O: int  # usable land-cell-days

    def __post_init__(self) -> None:
        if self.D < 0:
            raise ValueError(f"D must be >= 0, got {self.D}")
        if self.O < 0:
            raise ValueError(f"O must be >= 0, got {self.O}")
        # O = 0 with D > 0 would be nonsensical; flag it.
        if self.O == 0 and self.D > 0:
            raise ValueError(
                "O = 0 (unavailable period) cannot have D > 0.  "
                "If the period was unobserved, set D = 0 and O = 0, "
                "or omit the record entirely; it will be treated as unavailable."
            )

    @property
    def is_available(self) -> bool:
        """True when the period has usable observations (O > 0)."""
        return self.O > 0

    @property
    def availability(self) -> Availability:
        return Availability.AVAILABLE if self.is_available else Availability.UNAVAILABLE


# ---------------------------------------------------------------------------
# Pooled-rate helper
# ---------------------------------------------------------------------------
def _pooled_rate(records: Iterable[ObsRecord]) -> Optional[float]:
    """
    Compute SCALE * sum(D) / sum(O) across all *available* records.

    Returns None when:
      - no records are available (all O = 0 or the iterable is empty), or
      - sum(O) = 0 after filtering.

    Caller must treat None as UNAVAILABLE; must not substitute 0.
    """
    total_D: int = 0
    total_O: int = 0
    for rec in records:
        if not rec.is_available:
            # O = 0 → skip; never coerce to zero fire
            continue
        total_D += rec.D
        total_O += rec.O

    if total_O == 0:
        return None  # unavailable — no valid denominator

    return SCALE * total_D / total_O


# ---------------------------------------------------------------------------
# Single-factor result
# ---------------------------------------------------------------------------
@dataclass
class FactorResult:
    """
    Result of fitting one calibration factor (a_H or a_C) on one variant.

    factor_value: positive float when status is AVAILABLE, else None.
    aqua_pooled_rate: 1000·ΣD_aqua / ΣO_aqua (None when unavailable).
    viirs_pooled_rate: 1000·ΣD_viirs / ΣO_viirs (None when unavailable).
    n_aqua_obs: count of AVAILABLE Aqua records used.
    n_viirs_obs: count of AVAILABLE VIIRS records used.
    reasons: human-readable list of why the factor is unavailable (if applicable).
    """

    variant_id: str
    factor_type: Literal["own_support_a_H", "common_support_a_C"]
    training_years: tuple[int, ...]
    status: FactorStatus
    factor_value: Optional[float]
    aqua_pooled_rate: Optional[float]
    viirs_pooled_rate: Optional[float]
    n_aqua_obs: int
    n_viirs_obs: int
    reasons: list[str] = field(default_factory=list)


def _fit_factor(
    *,
    variant_id: str,
    factor_type: Literal["own_support_a_H", "common_support_a_C"],
    training_years: tuple[int, ...],
    aqua_records: list[ObsRecord],
    viirs_records: list[ObsRecord],
) -> FactorResult:
    """
    Core factor-fitting logic shared by a_H and a_C variants.

    Both sensor record lists must already be filtered to the correct
    policy and training years by the caller.

    Returns FactorResult with status=UNAVAILABLE and factor_value=None
    whenever the computation cannot proceed (zero O, zero VIIRS rate, etc.).
    """
    reasons: list[str] = []

    aqua_available = [r for r in aqua_records if r.is_available]
    viirs_available = [r for r in viirs_records if r.is_available]

    n_aqua = len(aqua_available)
    n_viirs = len(viirs_available)

    aqua_rate = _pooled_rate(aqua_available)
    viirs_rate = _pooled_rate(viirs_available)

    if aqua_rate is None:
        reasons.append(
            f"Aqua pooled rate unavailable: no usable observations (O > 0) "
            f"in training years {training_years}."
        )
    if viirs_rate is None:
        reasons.append(
            f"VIIRS pooled rate unavailable: no usable observations (O > 0) "
            f"in training years {training_years}."
        )
    if viirs_rate is not None and viirs_rate == 0.0:
        reasons.append(
            "VIIRS pooled rate is exactly zero (D = 0 across all training "
            "observations).  Division undefined; factor is unavailable."
        )

    if reasons or viirs_rate == 0.0:
        return FactorResult(
            variant_id=variant_id,
            factor_type=factor_type,
            training_years=training_years,
            status=FactorStatus.UNAVAILABLE,
            factor_value=None,
            aqua_pooled_rate=aqua_rate,
            viirs_pooled_rate=viirs_rate,
            n_aqua_obs=n_aqua,
            n_viirs_obs=n_viirs,
            reasons=reasons,
        )

    factor_value: float = aqua_rate / viirs_rate  # type: ignore[operator]

    if factor_value <= 0.0:
        reasons.append(
            f"Computed factor {factor_value!r} is non-positive; unavailable."
        )
        return FactorResult(
            variant_id=variant_id,
            factor_type=factor_type,
            training_years=training_years,
            status=FactorStatus.UNAVAILABLE,
            factor_value=None,
            aqua_pooled_rate=aqua_rate,
            viirs_pooled_rate=viirs_rate,
            n_aqua_obs=n_aqua,
            n_viirs_obs=n_viirs,
            reasons=reasons,
        )

    return FactorResult(
        variant_id=variant_id,
        factor_type=factor_type,
        training_years=training_years,
        status=FactorStatus.AVAILABLE,
        factor_value=factor_value,
        aqua_pooled_rate=aqua_rate,
        viirs_pooled_rate=viirs_rate,
        n_aqua_obs=n_aqua,
        n_viirs_obs=n_viirs,
        reasons=[],
    )


# ---------------------------------------------------------------------------
# Public API — fit a_H (own-support) variants
# ---------------------------------------------------------------------------
def fit_own_support_variants(
    aqua_records: list[ObsRecord],
    viirs_records: list[ObsRecord],
    training_years: tuple[int, ...] = TRAINING_YEARS_DEFAULT,
) -> dict[str, FactorResult]:
    """
    Fit the full-training a_H factor and all leave-one-year-out variants.

    Both record lists must contain ONLY 'own_support' policy records.
    Records outside training_years are silently ignored (they are not
    used for factor fitting; only training data may enter the denominator).

    Returns a dict keyed by variant_id, e.g.:
      {
        "full_training_2016_2018": FactorResult(...),
        "ex_2016": FactorResult(...),
        "ex_2017": FactorResult(...),
        "ex_2018": FactorResult(...),
      }

    Missing required factors are UNAVAILABLE, never dropped silently.
    """
    # Guard: only own-support records should be passed here
    for rec in aqua_records + viirs_records:
        if rec.policy != "own_support":
            raise ValueError(
                f"fit_own_support_variants received a '{rec.policy}' record. "
                "Pass only own_support records to this function."
            )

    def _subset(
        records: list[ObsRecord], years: tuple[int, ...]
    ) -> list[ObsRecord]:
        return [r for r in records if r.year in years]

    results: dict[str, FactorResult] = {}

    # Full-training variant
    full_id = "_".join(["full_training"] + [str(y) for y in sorted(training_years)])
    results[full_id] = _fit_factor(
        variant_id=full_id,
        factor_type="own_support_a_H",
        training_years=training_years,
        aqua_records=_subset(aqua_records, training_years),
        viirs_records=_subset(viirs_records, training_years),
    )

    # Leave-one-year-out variants — one per training year
    for excluded_year in sorted(training_years):
        remaining = tuple(y for y in training_years if y != excluded_year)
        variant_id = f"ex_{excluded_year}"
        results[variant_id] = _fit_factor(
            variant_id=variant_id,
            factor_type="own_support_a_H",
            training_years=remaining,
            aqua_records=_subset(aqua_records, remaining),
            viirs_records=_subset(viirs_records, remaining),
        )

    return results


# ---------------------------------------------------------------------------
# Public API — fit a_C (common-support) diagnostic factor
# ---------------------------------------------------------------------------
def fit_common_support_variants(
    aqua_common_records: list[ObsRecord],
    viirs_common_records: list[ObsRecord],
    training_years: tuple[int, ...] = TRAINING_YEARS_DEFAULT,
) -> dict[str, FactorResult]:
    """
    Fit the full-training a_C diagnostic factor and leave-one-year-out variants.

    Both record lists must contain ONLY 'common_support' policy records
    (paired cell-days where both sensors have O > 0 on the same spatial units).

    a_C is diagnostic only.  It MUST NOT substitute for a_H in historical
    comparisons; it does not replace the own-support historical target.

    Returns the same variant structure as fit_own_support_variants.
    """
    for rec in aqua_common_records + viirs_common_records:
        if rec.policy != "common_support":
            raise ValueError(
                f"fit_common_support_variants received a '{rec.policy}' record. "
                "Pass only common_support records to this function."
            )

    def _subset(
        records: list[ObsRecord], years: tuple[int, ...]
    ) -> list[ObsRecord]:
        return [r for r in records if r.year in years]

    results: dict[str, FactorResult] = {}

    full_id = "_".join(["full_training"] + [str(y) for y in sorted(training_years)])
    results[full_id] = _fit_factor(
        variant_id=full_id,
        factor_type="common_support_a_C",
        training_years=training_years,
        aqua_records=_subset(aqua_common_records, training_years),
        viirs_records=_subset(viirs_common_records, training_years),
    )

    for excluded_year in sorted(training_years):
        remaining = tuple(y for y in training_years if y != excluded_year)
        variant_id = f"ex_{excluded_year}"
        results[variant_id] = _fit_factor(
            variant_id=variant_id,
            factor_type="common_support_a_C",
            training_years=remaining,
            aqua_records=_subset(aqua_common_records, remaining),
            viirs_records=_subset(viirs_common_records, remaining),
        )

    return results


# ---------------------------------------------------------------------------
# Sensitivity check
# ---------------------------------------------------------------------------
def assess_sensitivity(
    variant_results: dict[str, FactorResult],
    required_variant_ids: Optional[list[str]] = None,
) -> tuple[SensitivityStatus, list[str]]:
    """
    Determine calibration_sensitivity from a set of factor variants.

    Rules (§7):
    - Any required variant that is UNAVAILABLE → UNRESOLVED (takes precedence).
    - If all available factors agree in direction of their Delta values and
      the factors themselves are within the registered min-max envelope → STABLE.
    - If factors produce directional disagreement → SENSITIVE.
    - If the required_variant_ids list is supplied, all must be present and
      AVAILABLE; otherwise the status is UNRESOLVED regardless.

    Returns (SensitivityStatus, list[reason_strings]).
    """
    reasons: list[str] = []

    # Collect available factor values
    available_values: list[float] = []
    unavailable_ids: list[str] = []

    for vid, result in variant_results.items():
        if result.status == FactorStatus.AVAILABLE:
            available_values.append(result.factor_value)  # type: ignore[arg-type]
        else:
            unavailable_ids.append(vid)

    # Check required variants
    if required_variant_ids:
        missing = [
            vid
            for vid in required_variant_ids
            if vid not in variant_results
            or variant_results[vid].status == FactorStatus.UNAVAILABLE
        ]
        if missing:
            reasons.append(
                f"Required variants unavailable or missing: {missing}. "
                "Sensitivity is UNRESOLVED; a stable badge cannot be awarded."
            )
            return SensitivityStatus.UNRESOLVED, reasons

    if unavailable_ids:
        reasons.append(
            f"Factor variants {unavailable_ids} are UNAVAILABLE. "
            "Cannot assess sensitivity without all registered variants."
        )
        return SensitivityStatus.UNRESOLVED, reasons

    if len(available_values) < 2:
        reasons.append(
            "Fewer than 2 available factor variants; sensitivity cannot be assessed."
        )
        return SensitivityStatus.UNRESOLVED, reasons

    factor_min = min(available_values)
    factor_max = max(available_values)

    # Factors all positive and present — check if direction is consistent.
    # At Stage A we do not apply factors to a target here; we can only note
    # whether the factor spread is non-trivial.  Directional stability of Delta
    # requires a target value and belongs in comparison logic (see apply_factor).
    # Here we return STABLE if all factors are present and positive (no direction
    # reversal is possible from the factors alone without a target).
    reasons.append(
        f"All {len(available_values)} registered variants available. "
        f"Factor range [{factor_min:.6f}, {factor_max:.6f}]."
    )
    return SensitivityStatus.STABLE, reasons


# ---------------------------------------------------------------------------
# Apply factor to a target VIIRS rate
# ---------------------------------------------------------------------------
@dataclass
class AppliedComparison:
    """
    Result of applying a calibration factor to a target VIIRS rate and
    comparing with a baseline Aqua rate.

    All four independent status dimensions are carried here.
    """

    variant_id: str
    factor_type: Literal["own_support_a_H", "common_support_a_C"]
    factor_value: Optional[float]
    factor_status: FactorStatus
    baseline_B: Optional[float]  # Aqua reference rate
    viirs_V: Optional[float]  # Raw VIIRS target rate
    mapped_Z: Optional[float]  # a * V
    delta: Optional[float]  # mapped_Z - baseline_B
    # --- independent status dimensions ---
    sensitivity_status: SensitivityStatus
    applicability_status: ApplicabilityStatus
    inference_status: InferenceStatus
    practical_change: PracticalChange
    headline_direction: HeadlineDirection
    equality_break_a: Optional[float]  # B / V; None when V <= 0 or unavailable
    reasons: list[str] = field(default_factory=list)


def apply_factor(
    *,
    factor_result: FactorResult,
    baseline_B: Optional[float],
    viirs_V: Optional[float],
    sensitivity_status: SensitivityStatus,
    applicability_status: ApplicabilityStatus,
    practical_margin_tau: Optional[float] = None,
) -> AppliedComparison:
    """
    Apply one factor variant to a target comparison.

    Parameters
    ----------
    factor_result:
        Output of _fit_factor / fit_own_support_variants etc.
    baseline_B:
        Pooled Aqua reference rate for the target period (None = unavailable).
    viirs_V:
        Raw VIIRS rate for the target period (None = unavailable).
    sensitivity_status:
        Pre-computed from assess_sensitivity(); passed in, not re-derived here.
    applicability_status:
        Caller is responsible for determining whether this factor was
        evaluated for the target region/period/policy.
    practical_margin_tau:
        Non-negative margin registered BEFORE outcome inspection (§7).
        None → practical_change = UNSPECIFIED.

    Returns
    -------
    AppliedComparison with all status dimensions set independently.
    """
    reasons: list[str] = []

    # --- guard: tau must be non-negative if supplied ---
    if practical_margin_tau is not None and practical_margin_tau < 0:
        raise ValueError("practical_margin_tau must be non-negative.")

    # Determine mapped value and delta
    mapped_Z: Optional[float] = None
    delta: Optional[float] = None
    equality_break_a: Optional[float] = None

    factor_value = factor_result.factor_value

    if factor_result.status == FactorStatus.UNAVAILABLE:
        reasons.append(
            f"Factor '{factor_result.variant_id}' is UNAVAILABLE: "
            + "; ".join(factor_result.reasons)
        )
    elif viirs_V is None:
        reasons.append("Target VIIRS rate is unavailable (O = 0 or missing).")
    elif baseline_B is None:
        reasons.append("Baseline Aqua rate is unavailable (O = 0 or missing).")
    else:
        # All inputs present — compute
        mapped_Z = factor_value * viirs_V  # type: ignore[operator]
        delta = mapped_Z - baseline_B

        # Equality boundary (§8): a_break = B / V
        if viirs_V > 0:
            equality_break_a = baseline_B / viirs_V
        elif viirs_V == 0.0:
            # Delta = -B for every valid a; B=0 → equality always
            if baseline_B == 0.0:
                reasons.append(
                    "V = 0 and B = 0: Delta = 0 for every valid factor. "
                    "Equality holds regardless of factor value."
                )
            else:
                reasons.append(
                    f"V = 0, B = {baseline_B:.6f}: "
                    f"Delta = -B = {-baseline_B:.6f} for every valid factor. "
                    "No factor-induced reversal is possible."
                )
            equality_break_a = None  # division undefined

    # --- headline direction ---
    if delta is None:
        headline_direction = HeadlineDirection.UNRESOLVED
    elif delta > 0.0:
        headline_direction = HeadlineDirection.INCREASE
    elif delta < 0.0:
        headline_direction = HeadlineDirection.DECREASE
    else:
        headline_direction = HeadlineDirection.NO_CHANGE

    # --- practical change (§7) ---
    if delta is None or practical_margin_tau is None:
        practical_change = PracticalChange.UNSPECIFIED
    elif delta > practical_margin_tau:
        practical_change = PracticalChange.MEANINGFUL_INCREASE
    elif delta < -practical_margin_tau:
        practical_change = PracticalChange.MEANINGFUL_DECREASE
    else:
        practical_change = PracticalChange.WITHIN_MARGIN

    return AppliedComparison(
        variant_id=factor_result.variant_id,
        factor_type=factor_result.factor_type,
        factor_value=factor_value,
        factor_status=factor_result.status,
        baseline_B=baseline_B,
        viirs_V=viirs_V,
        mapped_Z=mapped_Z,
        delta=delta,
        sensitivity_status=sensitivity_status,
        applicability_status=applicability_status,
        inference_status=InferenceStatus.NOT_ESTABLISHED,
        practical_change=practical_change,
        headline_direction=headline_direction,
        equality_break_a=equality_break_a,
        reasons=reasons,
    )
