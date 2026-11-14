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

Changes v2 (review response):
  1. assess_sensitivity now requires a (baseline_B, viirs_V) target pair to
     evaluate whether all variant Deltas agree in sign.  Directional
     disagreement → SENSITIVE.  Stability is per the spec: "all required tested
     variants agree", not merely "all factors are present and positive".
  2. _fit_factor now verifies each required training year has at least one
     available record (O > 0) per sensor.  A year present in training_years
     but entirely absent or O=0 → UNAVAILABLE with an explicit year-missing
     reason.  Silently pooling over fewer years than registered is forbidden.
  3. ApplicabilityStatus gains FAILED_APPLICABILITY and MISSING_REQUIRED_SUPPORT,
     matching the spec's five named output categories (§8B):
       - evaluated_for_conditions      (evaluation performed)
       - failed_applicability          (evaluation performed but failed)
       - outside_evaluated_conditions  (domain not evaluated at all)
       - missing_required_support      (required observations absent)
       - insufficient_evidence         (checks incomplete/unavailable)

Changes v3 (review response — two remaining issues):
  Issue 1 — Headline direction withheld when applicability fails or is absent
    (stage_a.py:668 in v2):
    apply_factor now gates headline_direction on applicability_status.
    Only ApplicabilityStatus.EVALUATED permits INCREASE/DECREASE/NO_CHANGE.
    Any other status (FAILED_APPLICABILITY, MISSING_REQUIRED_SUPPORT,
    OUTSIDE_EVALUATED, INSUFFICIENT_EVIDENCE) → UNRESOLVED, with the reason
    recorded.  practical_change is similarly gated: a directional practical
    category requires both a numeric delta AND evaluated applicability.
    Spec §7: "do not collapse these dimensions into a reassuring single badge
    or report a directional conclusion when its mandatory applicability evidence
    fails or is absent."

  Issue 2 — Matched calendar strata required before making a factor available
    (stage_a.py:383 in v2):
    Added _check_stratum_match(aqua, viirs) which computes the symmetric
    difference of (year, stratum) key sets present in both sensor lists.
    Keys present in one sensor but absent in the other → factor UNAVAILABLE
    with the mismatched key list in a new FactorResult.mismatched_strata field.
    This applies to both own-support (a_H) and common-support (a_C) fits.
    Spec §6: "matched calendar strata"; a_C uses "identical paired
    common-support cell-days" — unverified pairing is now an error, not a
    silent assumption.
    Note: this check verifies (year, stratum) key presence, not sub-pixel
    spatial cell identity; spatial pairing of cell-days must be verified by
    the data layer before records are assembled and passed here.

Changes v4 (review response — two remaining safeguards):
  Issue 3 — evaluated_for_conditions does not mean the check passed
    (stage_a.py:843 in v3):
    apply_factor gains a required keyword parameter applicability_passed: bool.
    A directional conclusion now requires BOTH applicability_status == EVALUATED
    AND applicability_passed == True.  When EVALUATED but applicability_passed
    is False, direction is withheld with an explicit reason.  The existing gate
    for non-EVALUATED statuses remains; this is a second independent condition.
    Spec §7: 'Evaluated does NOT mean passed.'  Spec §8B output categories:
    'Consistent across tested corrections only when all required tested variants
    agree AND all applicability gates pass.'

  Issue 4 — a_C returns AVAILABLE without evidence that cell-pairing was
    validated upstream (stage_a.py:266 in v3):
    fit_common_support_variants gains a required keyword parameter
    pairing_validated: bool.  When False (the caller must opt in explicitly),
    every variant is UNAVAILABLE with an explicit reason.  The caller attests
    that the data layer has confirmed the common-support records represent the
    same spatial cell-days for both sensors (e.g. by joining on cell ID and
    verifying the join is complete and lossless).  Spec §6: a_C uses 'each
    sensor’s pooled rate on the identical paired common-support cell-days';
    key-matching alone cannot confirm identical pairing.
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
    """
    Five named categories from §8B of the scientific plan.

    evaluated_for_conditions    — the evaluation was performed and the domain
                                   conditions are met.  Does NOT mean "passed".
    failed_applicability        — the evaluation was performed but failed
                                   (e.g. support shifted, QA changed).  Preserve
                                   this separately; never collapse into out_of_domain.
    outside_evaluated_conditions— the requested domain was never evaluated.
                                   Raw observations may still be available.
    missing_required_support    — required observations (O > 0) are absent;
                                   the check cannot even be attempted.
    insufficient_evidence       — the applicability check is incomplete or its
                                   required preconditions are unavailable.
    """

    EVALUATED = "evaluated_for_conditions"
    FAILED_APPLICABILITY = "failed_applicability"
    OUTSIDE_EVALUATED = "outside_evaluated_conditions"
    MISSING_REQUIRED_SUPPORT = "missing_required_support"
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
        # O = 0 with D > 0 is nonsensical; flag it immediately.
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
    missing_aqua_years: training years with no available Aqua records.
    missing_viirs_years: training years with no available VIIRS records.
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
    missing_aqua_years: list[int] = field(default_factory=list)
    missing_viirs_years: list[int] = field(default_factory=list)
    mismatched_strata: list[tuple[int, str]] = field(default_factory=list)
    reasons: list[str] = field(default_factory=list)


def _check_year_support(
    records: list[ObsRecord],
    training_years: tuple[int, ...],
    sensor_label: str,
) -> list[int]:
    """
    Return the list of years in training_years that have NO available
    (O > 0) records in `records`.

    A required year with only O=0 records is treated the same as a year
    that is entirely absent — it contributes nothing to the pooled rate
    and must be flagged, not silently skipped.
    """
    years_with_support: set[int] = {
        r.year for r in records if r.is_available
    }
    return sorted(y for y in training_years if y not in years_with_support)


def _check_stratum_match(
    aqua_records: list[ObsRecord],
    viirs_records: list[ObsRecord],
) -> list[tuple[int, str]]:
    """
    Return the sorted list of (year, stratum) keys that are present in one
    sensor's available records but absent in the other's available records.

    Spec §6 requires "matched calendar strata" for a_H and "identical paired
    common-support cell-days" for a_C.  A (year, stratum) key present for Aqua
    but missing for VIIRS (or vice-versa) means the two pooled rates would not
    cover the same temporal domain — the factor would be computed on
    mismatched observations.

    Only available (O > 0) records are considered; O = 0 records carry no
    poolable information and are ignored here just as they are in _pooled_rate.

    Note: this verifies (year, stratum) key identity, not sub-pixel spatial
    cell membership.  Spatial cell pairing for a_C must be enforced by the
    data layer before records are assembled and passed to this module.
    """
    aqua_keys: set[tuple[int, str]] = {
        (r.year, r.stratum) for r in aqua_records if r.is_available
    }
    viirs_keys: set[tuple[int, str]] = {
        (r.year, r.stratum) for r in viirs_records if r.is_available
    }
    # Symmetric difference: keys in one set but not the other
    mismatched = aqua_keys.symmetric_difference(viirs_keys)
    return sorted(mismatched)


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

    Precondition check (v2): every year in training_years must have at least
    one available record (O > 0) for each sensor.  If any year is missing
    support for either sensor, the factor is UNAVAILABLE and the missing
    years are recorded explicitly.  Silently pooling over fewer years than
    registered is a scientific error (§6: "registered training years").

    Precondition check (v3): every (year, stratum) key present in available
    Aqua records must also be present in available VIIRS records, and vice
    versa.  Mismatched strata → UNAVAILABLE.  Spec §6 requires "matched
    calendar strata"; a_C additionally requires "identical paired
    common-support cell-days".

    Returns FactorResult with status=UNAVAILABLE and factor_value=None
    whenever the computation cannot proceed.
    """
    reasons: list[str] = []

    # --- (v2) Check that every registered year has support ---
    missing_aqua = _check_year_support(aqua_records, training_years, "Aqua")
    missing_viirs = _check_year_support(viirs_records, training_years, "VIIRS")

    if missing_aqua:
        reasons.append(
            f"Aqua has no usable observations (O > 0) in required training "
            f"year(s): {missing_aqua}.  Factor variant '{variant_id}' is "
            "UNAVAILABLE; cannot pool over fewer years than registered."
        )
    if missing_viirs:
        reasons.append(
            f"VIIRS has no usable observations (O > 0) in required training "
            f"year(s): {missing_viirs}.  Factor variant '{variant_id}' is "
            "UNAVAILABLE; cannot pool over fewer years than registered."
        )

    if reasons:
        return FactorResult(
            variant_id=variant_id,
            factor_type=factor_type,
            training_years=training_years,
            status=FactorStatus.UNAVAILABLE,
            factor_value=None,
            aqua_pooled_rate=None,
            viirs_pooled_rate=None,
            n_aqua_obs=0,
            n_viirs_obs=0,
            missing_aqua_years=missing_aqua,
            missing_viirs_years=missing_viirs,
            mismatched_strata=[],
            reasons=reasons,
        )

    # --- (v3) Check that (year, stratum) keys are matched across sensors ---
    mismatched = _check_stratum_match(aqua_records, viirs_records)
    if mismatched:
        reasons.append(
            f"Calendar strata are not matched between Aqua and VIIRS available "
            f"records.  Mismatched (year, stratum) keys: {mismatched}.  "
            f"Spec §6 requires matched strata; factor variant '{variant_id}' "
            "is UNAVAILABLE until the data layer supplies aligned records."
        )
        return FactorResult(
            variant_id=variant_id,
            factor_type=factor_type,
            training_years=training_years,
            status=FactorStatus.UNAVAILABLE,
            factor_value=None,
            aqua_pooled_rate=None,
            viirs_pooled_rate=None,
            n_aqua_obs=0,
            n_viirs_obs=0,
            missing_aqua_years=[],
            missing_viirs_years=[],
            mismatched_strata=mismatched,
            reasons=reasons,
        )

    # All years have support — now pool
    aqua_available = [r for r in aqua_records if r.is_available]
    viirs_available = [r for r in viirs_records if r.is_available]

    n_aqua = len(aqua_available)
    n_viirs = len(viirs_available)

    aqua_rate = _pooled_rate(aqua_available)
    viirs_rate = _pooled_rate(viirs_available)

    # These cases should be unreachable after the year-support check above,
    # but are kept as a defence-in-depth guard.
    if aqua_rate is None:
        reasons.append(
            f"Aqua pooled rate is None despite passing year-support check "
            f"(unexpected; variant '{variant_id}')."
        )
    if viirs_rate is None:
        reasons.append(
            f"VIIRS pooled rate is None despite passing year-support check "
            f"(unexpected; variant '{variant_id}')."
        )
    if viirs_rate is not None and viirs_rate == 0.0:
        reasons.append(
            "VIIRS pooled rate is exactly zero (D = 0 across all training "
            "observations with O > 0).  Division undefined; factor is unavailable."
        )

    if reasons or (viirs_rate is not None and viirs_rate == 0.0):
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
            missing_aqua_years=missing_aqua,
            missing_viirs_years=missing_viirs,
            mismatched_strata=[],
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
            missing_aqua_years=[],
            missing_viirs_years=[],
            mismatched_strata=[],
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
        missing_aqua_years=[],
        missing_viirs_years=[],
        mismatched_strata=[],
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

    Every variant is returned, even if UNAVAILABLE.  Missing required
    factors are UNAVAILABLE with explicit year-missing reasons, never dropped.

    Returns a dict keyed by variant_id, e.g.:
      {
        "full_training_2016_2017_2018": FactorResult(...),
        "ex_2016": FactorResult(...),
        "ex_2017": FactorResult(...),
        "ex_2018": FactorResult(...),
      }
    """
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

    full_id = "_".join(["full_training"] + [str(y) for y in sorted(training_years)])
    results[full_id] = _fit_factor(
        variant_id=full_id,
        factor_type="own_support_a_H",
        training_years=training_years,
        aqua_records=_subset(aqua_records, training_years),
        viirs_records=_subset(viirs_records, training_years),
    )

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
    *,
    pairing_validated: bool,
) -> dict[str, FactorResult]:
    """
    Fit the full-training a_C diagnostic factor and leave-one-year-out variants.

    Both record lists must contain ONLY 'common_support' policy records
    (paired cell-days where both sensors have O > 0 on the same spatial units).

    a_C is diagnostic only.  It MUST NOT substitute for a_H in historical
    comparisons; it does not replace the own-support historical target.

    pairing_validated must be True for any variant to be AVAILABLE.  Pass
    True only after the data layer has confirmed that every common-support
    record in both sensor lists covers the SAME spatial cell-days (e.g. by
    joining on a canonical cell ID and verifying the join is complete and
    lossless for every (year, stratum) key).  Passing False is the safe
    default: it makes the unverified-pairing assumption explicit and
    machine-checked rather than documented-only.

    Returns the same variant structure as fit_own_support_variants.
    """
    for rec in aqua_common_records + viirs_common_records:
        if rec.policy != "common_support":
            raise ValueError(
                f"fit_common_support_variants received a '{rec.policy}' record. "
                "Pass only common_support records to this function."
            )

    # (v4) Spatial cell-pairing attestation.
    # _check_stratum_match confirms (year, stratum) key presence but cannot
    # verify that records for each key cover the identical cell-days in both
    # sensors.  The caller must supply pairing_validated=True after the data
    # layer has confirmed complete, lossless spatial pairing for all keys.
    if not pairing_validated:
        _pairing_reason = (
            "fit_common_support_variants called with pairing_validated=False. "
            "All a_C variants are UNAVAILABLE until the data layer confirms "
            "that every common-support record covers the identical spatial "
            "cell-days for both sensors (spec \u00a76: 'identical paired "
            "common-support cell-days').  Pass pairing_validated=True after "
            "verifying the join on a canonical cell ID is complete and lossless."
        )
        results_unvalidated: dict[str, FactorResult] = {}
        full_id_u = "_".join(
            ["full_training"] + [str(y) for y in sorted(training_years)]
        )
        results_unvalidated[full_id_u] = FactorResult(
            variant_id=full_id_u,
            factor_type="common_support_a_C",
            training_years=training_years,
            status=FactorStatus.UNAVAILABLE,
            factor_value=None,
            aqua_pooled_rate=None,
            viirs_pooled_rate=None,
            n_aqua_obs=0,
            n_viirs_obs=0,
            mismatched_strata=[],
            reasons=[_pairing_reason],
        )
        for excluded_year in sorted(training_years):
            remaining = tuple(y for y in training_years if y != excluded_year)
            vid_u = f"ex_{excluded_year}"
            results_unvalidated[vid_u] = FactorResult(
                variant_id=vid_u,
                factor_type="common_support_a_C",
                training_years=remaining,
                status=FactorStatus.UNAVAILABLE,
                factor_value=None,
                aqua_pooled_rate=None,
                viirs_pooled_rate=None,
                n_aqua_obs=0,
                n_viirs_obs=0,
                mismatched_strata=[],
                reasons=[_pairing_reason],
            )
        return results_unvalidated

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
# Sensitivity check  (v2: requires a target to evaluate directional agreement)
# ---------------------------------------------------------------------------
def _delta_for_factor(
    factor_value: float,
    baseline_B: float,
    viirs_V: float,
) -> float:
    """Return Delta = factor * V - B.  Used only inside assess_sensitivity."""
    return factor_value * viirs_V - baseline_B


def assess_sensitivity(
    variant_results: dict[str, FactorResult],
    baseline_B: Optional[float],
    viirs_V: Optional[float],
    required_variant_ids: Optional[list[str]] = None,
) -> tuple[SensitivityStatus, list[str]]:
    """
    Determine calibration_sensitivity from a set of factor variants.

    Per §7: "Label agreement 'Stable across the registered calibration variants'"
    requires that all registered variants' Deltas (= a*V - B) agree in sign.
    Stability is a property of the variants applied to a specific target, not a
    property of the factor values in isolation.

    Parameters
    ----------
    variant_results:
        Output of fit_own_support_variants / fit_common_support_variants.
    baseline_B:
        Pooled Aqua reference rate for the target comparison period.
        None means the target is unavailable → UNRESOLVED.
    viirs_V:
        Raw VIIRS rate for the target comparison period.
        None means the target is unavailable → UNRESOLVED.
    required_variant_ids:
        If supplied, every listed variant must be present AND AVAILABLE.
        Any missing or UNAVAILABLE required variant → UNRESOLVED (takes
        precedence over all other checks; spec §7: "a required undefined
        factor remains unavailable and follows unresolved precedence; never
        drop it to get a stable badge").

    Returns (SensitivityStatus, list[reason_strings]).
    """
    reasons: list[str] = []

    # --- target unavailability takes precedence over everything else ---
    if baseline_B is None:
        reasons.append("Baseline (B) is unavailable; sensitivity cannot be assessed.")
        return SensitivityStatus.UNRESOLVED, reasons
    if viirs_V is None:
        reasons.append("Target VIIRS rate (V) is unavailable; sensitivity cannot be assessed.")
        return SensitivityStatus.UNRESOLVED, reasons

    # --- collect available factor values ---
    available: dict[str, float] = {}
    unavailable_ids: list[str] = []

    for vid, result in variant_results.items():
        if result.status == FactorStatus.AVAILABLE:
            available[vid] = result.factor_value  # type: ignore[assignment]
        else:
            unavailable_ids.append(vid)

    # --- check required variants (UNRESOLVED takes strict precedence) ---
    if required_variant_ids:
        missing_or_unavail = [
            vid
            for vid in required_variant_ids
            if vid not in variant_results
            or variant_results[vid].status == FactorStatus.UNAVAILABLE
        ]
        if missing_or_unavail:
            reasons.append(
                f"Required variants unavailable or missing: {missing_or_unavail}. "
                "Sensitivity is UNRESOLVED; a stable badge cannot be awarded "
                "(spec §7: required undefined factor follows unresolved precedence)."
            )
            return SensitivityStatus.UNRESOLVED, reasons

    # --- if any variant (not just required) is unavailable, cannot assess ---
    if unavailable_ids:
        reasons.append(
            f"Factor variants {unavailable_ids} are UNAVAILABLE. "
            "Cannot assess sensitivity without all registered variants."
        )
        return SensitivityStatus.UNRESOLVED, reasons

    if len(available) < 2:
        reasons.append(
            "Fewer than 2 available factor variants; sensitivity cannot be assessed."
        )
        return SensitivityStatus.UNRESOLVED, reasons

    # --- (v2) compute Deltas and check directional agreement ---
    deltas: dict[str, float] = {
        vid: _delta_for_factor(a, baseline_B, viirs_V)
        for vid, a in available.items()
    }

    # Classify each Delta: positive, negative, or zero.
    # Zero is compatible with either direction (no sign reversal).
    positive_ids = [vid for vid, d in deltas.items() if d > 0.0]
    negative_ids = [vid for vid, d in deltas.items() if d < 0.0]
    zero_ids     = [vid for vid, d in deltas.items() if d == 0.0]

    factor_min = min(available.values())
    factor_max = max(available.values())
    delta_min  = min(deltas.values())
    delta_max  = max(deltas.values())

    base_summary = (
        f"All {len(available)} registered variants available. "
        f"Factor range [{factor_min:.6f}, {factor_max:.6f}]. "
        f"Delta range [{delta_min:.6f}, {delta_max:.6f}] "
        f"(B={baseline_B:.6f}, V={viirs_V:.6f})."
    )

    if positive_ids and negative_ids:
        # Sign reversal across variants → SENSITIVE
        reasons.append(base_summary)
        reasons.append(
            f"Directional disagreement: variants {positive_ids} give Delta > 0 "
            f"(increase) while variants {negative_ids} give Delta < 0 (decrease). "
            "Result is SENSITIVE to calibration assumptions."
        )
        return SensitivityStatus.SENSITIVE, reasons

    # All non-zero Deltas share the same sign (some may be zero) → STABLE
    reasons.append(base_summary)
    if zero_ids:
        reasons.append(
            f"Variants {zero_ids} give Delta = 0 (equality); "
            "these are compatible with the dominant direction."
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
    viirs_V: Optional[float]     # Raw VIIRS target rate
    mapped_Z: Optional[float]    # a * V
    delta: Optional[float]       # mapped_Z - baseline_B
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
    applicability_passed: bool,
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
        The caller must supply the value from assess_sensitivity(B, V, ...) for
        this specific (baseline_B, viirs_V) pair.
    applicability_status:
        Caller is responsible for determining whether this factor was
        evaluated for the target region/period/policy.  Use FAILED_APPLICABILITY
        when an evaluation was performed and failed; MISSING_REQUIRED_SUPPORT
        when required observations are absent; INSUFFICIENT_EVIDENCE when
        checks are incomplete.  Do not collapse failed checks into OUTSIDE_EVALUATED.
    applicability_passed:
        True only when applicability_status == EVALUATED AND the applicability
        evaluation actually passed all required gates.  False in all other cases,
        including when status == EVALUATED but the evaluation found failures.
        Spec §7: 'Evaluated does NOT mean passed.'  When False, headline_direction
        is UNRESOLVED and practical_change is UNSPECIFIED regardless of delta.
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

    # --- headline direction (v3/v4: two independent applicability gates) ---
    # Gate A: applicability_status == EVALUATED  (check was performed)
    # Gate B: applicability_passed == True        (check actually passed)
    # Spec §7: 'Evaluated does NOT mean passed.'  Both gates must be
    # satisfied; failing either withholds the directional conclusion.
    applicability_status_ok = (
        applicability_status == ApplicabilityStatus.EVALUATED
    )
    applicability_permits_direction = applicability_status_ok and applicability_passed

    if delta is None:
        headline_direction = HeadlineDirection.UNRESOLVED
    elif not applicability_status_ok:
        # Gate A failed: check was not even performed for this domain
        headline_direction = HeadlineDirection.UNRESOLVED
        reasons.append(
            f"Headline direction withheld: applicability_status is "
            f"'{applicability_status.value}', not 'evaluated_for_conditions'. "
            "A directional conclusion requires passing applicability gates "
            "(spec §7)."
        )
    elif not applicability_passed:
        # Gate B failed: check was performed but did not pass
        headline_direction = HeadlineDirection.UNRESOLVED
        reasons.append(
            "Headline direction withheld: applicability_status is "
            "'evaluated_for_conditions' but applicability_passed=False. "
            "Spec §7: 'Evaluated does NOT mean passed'; a directional "
            "conclusion requires the evaluation to have actually passed."
        )
    elif delta > 0.0:
        headline_direction = HeadlineDirection.INCREASE
    elif delta < 0.0:
        headline_direction = HeadlineDirection.DECREASE
    else:
        headline_direction = HeadlineDirection.NO_CHANGE

    # --- practical change (§7) ---
    # Requires both gates: evaluated AND passed.
    if delta is None or practical_margin_tau is None or not applicability_permits_direction:
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
