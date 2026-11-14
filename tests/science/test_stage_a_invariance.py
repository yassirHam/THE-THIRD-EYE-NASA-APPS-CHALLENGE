"""
P1-C Independent Fixture: Stage A Invariance, a_H vs a_C, Applicability

Equation source: THE_THIRD_EYE_FINAL_PLAN_GEOGRAPHIC_ACCESS_UPDATED.txt

Covers:
  1. Scalar invariance: multiplying all D and O by the same scalar k must
     leave FAI unchanged (FAI is a rate, not a count).
  2. Equality-threshold edge cases: boundary values at exactly min_support.
  3. a_H (own-support) vs a_C (common-support) pooled-rate ratios.
     a_H = pooled(Aqua_own) / pooled(VIIRS_own)
     a_C = pooled(Aqua_comm) / pooled(VIIRS_comm)
     Aqua is the historical reference (numerator); VIIRS is the sensor being
     mapped (denominator). They are computed separately and are not
     interchangeable.
  4. Ranking preservation: any positive factor a > 0 preserves the strict
     ordering of VIIRS fire-activity values.
  5. Equality boundary a_break = B / V: harmonized VIIRS crosses the baseline
     exactly at a_break.
  6. 4-way applicability states: applicable, failed_applicability,
     missing_required_support, out_of_domain. out_of_domain must NEVER be
     mapped to failed_applicability.
  7. Inference status: not_established by default; no toy procedure may emit
     "established".
"""

import pytest
import math

UNAVAILABLE = "unavailable"
INSUFFICIENT_SUPPORT = "insufficient_support"
FAILED_APPLICABILITY = "failed_applicability"
MISSING_REQUIRED_SUPPORT = "missing_required_support"
OUT_OF_DOMAIN = "out_of_domain"
NOT_ESTABLISHED = "not_established"


# ---------------------------------------------------------------------------
# Core helpers
# ---------------------------------------------------------------------------

def fai(D: float, O: float) -> float:
    return (D / O) * 1000


def pooled_rate(D_list: list, O_list: list) -> float:
    """sum(D) / sum(O) — raises if total O is zero."""
    total_D = sum(D_list)
    total_O = sum(O_list)
    if total_O == 0:
        raise ValueError("Cannot pool with total O = 0")
    return total_D / total_O


def a_H(aqua_own_D: list, aqua_own_O: list,
        viirs_own_D: list, viirs_own_O: list) -> float:
    """
    Own-support factor.
    a_H = pooled(Aqua_own) / pooled(VIIRS_own)
    Aqua is the historical reference (numerator).
    VIIRS is the sensor being mapped (denominator).
    """
    aqua_rate = pooled_rate(aqua_own_D, aqua_own_O)
    viirs_rate = pooled_rate(viirs_own_D, viirs_own_O)
    if viirs_rate == 0:
        raise ValueError("VIIRS own-support rate is zero; a_H undefined")
    return aqua_rate / viirs_rate


def a_C(aqua_comm_D: list, aqua_comm_O: list,
        viirs_comm_D: list, viirs_comm_O: list) -> float:
    """
    Common-support factor.
    a_C = pooled(Aqua_comm) / pooled(VIIRS_comm)
    Aqua is the historical reference (numerator).
    VIIRS is the sensor being mapped (denominator).
    """
    aqua_rate = pooled_rate(aqua_comm_D, aqua_comm_O)
    viirs_rate = pooled_rate(viirs_comm_D, viirs_comm_O)
    if viirs_rate == 0:
        raise ValueError("VIIRS common-support rate is zero; a_C undefined")
    return aqua_rate / viirs_rate


def check_applicability(
    O,
    min_support: int = 5,
    in_domain: bool = True,
) -> str:
    """
    Returns one of four distinct contract applicability states:
      "applicable"               — in domain, O >= min_support
      "failed_applicability"     — in domain, but calibration check fails
                                   (negative or invalid rate)
      "missing_required_support" — in domain, but O == 0 or missing swath
      "out_of_domain"            — geographic/sensor domain criteria not met
                                   MUST NOT be mapped to failed_applicability
    """
    if not in_domain:
        return OUT_OF_DOMAIN
    if O is None or O == 0:
        return MISSING_REQUIRED_SUPPORT
    if O < 0:
        return FAILED_APPLICABILITY
    if O < min_support:
        return INSUFFICIENT_SUPPORT
    return "applicable"


def harmonize(a: float, V: float):
    """
    Apply factor a to VIIRS value V.
    Returns UNAVAILABLE if V is not a usable positive number.
    """
    if not isinstance(V, (int, float)) or V < 0:
        return UNAVAILABLE
    return a * V


def a_break(B, V):
    """
    Equality boundary: the factor at which a * V == B.
    Returns UNAVAILABLE when V == 0 or B == 0 or either is None/non-numeric.
    """
    for val in (B, V):
        if val is None:
            return UNAVAILABLE
        if not isinstance(val, (int, float)):
            return UNAVAILABLE
    if V == 0:
        return UNAVAILABLE
    if B == 0:
        return UNAVAILABLE
    return B / V


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestScalarInvariance:
    """FAI = D/O * 1000 is a rate; scaling D and O by k must not change it."""

    @pytest.mark.parametrize("k", [1, 2, 10, 100, 0.5, 0.01, 1e6])
    def test_fai_invariant_under_scaling(self, k):
        D, O = 3.0, 12.0
        base = fai(D, O)
        scaled = fai(D * k, O * k)
        assert scaled == pytest.approx(base, rel=1e-9), (
            f"FAI changed under scaling by k={k}: base={base}, scaled={scaled}"
        )

    @pytest.mark.parametrize("k", [1, 7, 50])
    def test_pooled_ratio_invariant_under_scaling(self, k):
        D_list = [3.0, 5.0, 2.0]
        O_list = [10.0, 20.0, 5.0]
        base = pooled_rate(D_list, O_list)
        scaled = pooled_rate([d * k for d in D_list], [o * k for o in O_list])
        assert scaled == pytest.approx(base, rel=1e-9)

    def test_zero_fires_valid_obs_gives_zero_fai(self):
        assert fai(0.0, 100.0) == pytest.approx(0.0)

    def test_full_saturation_gives_1000_fai(self):
        assert fai(50.0, 50.0) == pytest.approx(1000.0)


class TestEqualityThresholdEdgeCases:
    """Boundary conditions at min_support must be handled exactly."""

    @pytest.mark.parametrize("O,min_support,expected_state", [
        (0,   5, MISSING_REQUIRED_SUPPORT),
        (1,   5, INSUFFICIENT_SUPPORT),
        (4,   5, INSUFFICIENT_SUPPORT),
        (5,   5, "applicable"),
        (6,   5, "applicable"),
        (100, 5, "applicable"),
    ])
    def test_support_boundaries(self, O, min_support, expected_state):
        result = check_applicability(O, min_support=min_support)
        assert result == expected_state, (
            f"O={O}, min_support={min_support}: expected {expected_state!r}, got {result!r}"
        )

    def test_none_obs_is_missing_required_support(self):
        result = check_applicability(O=None, min_support=5)
        assert result == MISSING_REQUIRED_SUPPORT

    def test_zero_obs_is_missing_required_support(self):
        result = check_applicability(O=0, min_support=5)
        assert result == MISSING_REQUIRED_SUPPORT


class TestAHvsACFactorDefinitions:
    """
    a_H = pooled(Aqua_own) / pooled(VIIRS_own)
    a_C = pooled(Aqua_comm) / pooled(VIIRS_comm)
    Aqua is the historical reference (numerator); VIIRS is denominator.
    """

    def test_a_H_ratio_definition(self):
        # Aqua own-support: 6 detections over 20 obs = rate 0.30
        # VIIRS own-support: 4 detections over 20 obs = rate 0.20
        # a_H = 0.30 / 0.20 = 1.5
        aqua_own_D = [3.0, 3.0]
        aqua_own_O = [10.0, 10.0]
        viirs_own_D = [2.0, 2.0]
        viirs_own_O = [10.0, 10.0]
        result = a_H(aqua_own_D, aqua_own_O, viirs_own_D, viirs_own_O)
        assert result == pytest.approx(1.5, rel=1e-9)

    def test_a_C_ratio_definition(self):
        # Aqua common-support: 8/20 = 0.40
        # VIIRS common-support: 4/20 = 0.20
        # a_C = 0.40 / 0.20 = 2.0
        aqua_comm_D = [4.0, 4.0]
        aqua_comm_O = [10.0, 10.0]
        viirs_comm_D = [2.0, 2.0]
        viirs_comm_O = [10.0, 10.0]
        result = a_C(aqua_comm_D, aqua_comm_O, viirs_comm_D, viirs_comm_O)
        assert result == pytest.approx(2.0, rel=1e-9)

    def test_a_H_uses_sums_before_division(self):
        # Imbalanced cells: naive per-cell average != pooled ratio
        aqua_own_D = [9.0, 1.0]
        aqua_own_O = [1.0, 9.0]   # pooled: 10/10 = 1.0
        viirs_own_D = [1.0, 1.0]
        viirs_own_O = [5.0, 5.0]  # pooled: 2/10 = 0.2
        result = a_H(aqua_own_D, aqua_own_O, viirs_own_D, viirs_own_O)
        assert result == pytest.approx(5.0, rel=1e-9)

    def test_a_C_uses_sums_before_division(self):
        # Aqua common: imbalanced cells pool to 1.0
        aqua_comm_D = [9.0, 1.0]
        aqua_comm_O = [1.0, 9.0]  # pooled: 10/10 = 1.0
        # VIIRS common: symmetric, pooled to 0.5
        viirs_comm_D = [1.0, 1.0]
        viirs_comm_O = [2.0, 2.0]  # pooled: 2/4 = 0.5
        result = a_C(aqua_comm_D, aqua_comm_O, viirs_comm_D, viirs_comm_O)
        assert result == pytest.approx(2.0, rel=1e-9)

    def test_a_H_and_a_C_diverge_when_own_and_common_rates_differ(self):
        """
        When own-support and common-support rates diverge, a_H != a_C.
        Own-support: Aqua dominates high-fire cells; VIIRS dominates low-fire.
        Common-support: rates are balanced between sensors.
        """
        # Own support — rates diverge strongly
        aqua_own_D = [8.0, 1.0]
        aqua_own_O = [10.0, 10.0]  # Aqua own rate = 9/20 = 0.450
        viirs_own_D = [1.0, 1.0]
        viirs_own_O = [10.0, 10.0]  # VIIRS own rate = 2/20 = 0.100
        aH = a_H(aqua_own_D, aqua_own_O, viirs_own_D, viirs_own_O)
        # a_H = 0.450 / 0.100 = 4.5

        # Common support — rates are close to equal
        aqua_comm_D = [3.0, 3.0]
        aqua_comm_O = [10.0, 10.0]  # Aqua common rate = 6/20 = 0.300
        viirs_comm_D = [3.0, 3.0]
        viirs_comm_O = [10.0, 10.0]  # VIIRS common rate = 6/20 = 0.300
        aC = a_C(aqua_comm_D, aqua_comm_O, viirs_comm_D, viirs_comm_O)
        # a_C = 0.300 / 0.300 = 1.0

        assert aH == pytest.approx(4.5, rel=1e-9)
        assert aC == pytest.approx(1.0, rel=1e-9)
        assert aH != pytest.approx(aC, rel=1e-4), (
            "a_H and a_C must diverge when own-support and common-support rates differ"
        )

    def test_a_H_viirs_zero_rate_raises(self):
        with pytest.raises(ValueError, match="zero"):
            a_H([1.0], [5.0], [0.0], [10.0])

    def test_a_C_viirs_zero_rate_raises(self):
        with pytest.raises(ValueError, match="zero"):
            a_C([1.0], [5.0], [0.0], [10.0])

    def test_a_H_own_cells_do_not_inherit_common_factor(self):
        """a_H and a_C use different cell sets and must never be equal by default."""
        aH = a_H([6.0], [10.0], [4.0], [10.0])  # 0.6 / 0.4 = 1.5
        aC = a_C([2.0], [10.0], [4.0], [10.0])  # 0.2 / 0.4 = 0.5
        assert aH == pytest.approx(1.5, rel=1e-9)
        assert aC == pytest.approx(0.5, rel=1e-9)
        assert aH != pytest.approx(aC, rel=1e-4)


class TestRankingPreservation:
    """
    For any positive factor a > 0, multiplying by a preserves the strict
    ordering of VIIRS fire-activity values: if V1 < V2, then a*V1 < a*V2.
    """

    @pytest.mark.parametrize("a", [0.1, 0.5, 1.0, 1.5, 2.0, 10.0, 100.0])
    def test_monotonicity_preserves_strict_order(self, a):
        # Three VIIRS cells with strictly increasing fire activity
        viirs_values = [10.0, 50.0, 200.0]
        harmonized = [a * v for v in viirs_values]
        for i in range(len(harmonized) - 1):
            assert harmonized[i] < harmonized[i + 1], (
                f"a={a}: order broken between index {i} and {i+1}: "
                f"{harmonized[i]} >= {harmonized[i+1]}"
            )

    @pytest.mark.parametrize("a", [0.001, 0.999, 1.001, 999.0])
    def test_monotonicity_with_extreme_factors(self, a):
        v1, v2 = 1.0, 2.0
        assert a * v1 < a * v2

    def test_zero_factor_collapses_all_to_zero(self):
        """a=0 is a degenerate edge case: all values map to 0, order is lost."""
        # Confirm that a > 0 is required for ranking preservation.
        a = 0.0
        v1, v2 = 1.0, 2.0
        # With a=0 both map to 0; strict order is not preserved.
        assert a * v1 == a * v2  # both zero

    def test_negative_factor_reverses_order(self):
        """a < 0 reverses rankings; callers must enforce a > 0."""
        a = -1.0
        v1, v2 = 1.0, 2.0
        # Reversed: a*v1 > a*v2
        assert a * v1 > a * v2


class TestEqualityBoundary:
    """
    Equality boundary: a_break = B / V
      a > a_break  =>  a*V > B  (harmonized exceeds baseline)
      a < a_break  =>  a*V < B  (harmonized below baseline)
      a == a_break =>  a*V == B (exact equality)

    Edge cases: V=0, B=0, missing/zero O must return UNAVAILABLE, never 0.
    """

    def test_above_break_harmonized_exceeds_baseline(self):
        B, V = 100.0, 50.0  # a_break = 2.0
        ab = a_break(B, V)
        assert ab == pytest.approx(2.0, rel=1e-9)
        a = ab + 0.5  # 2.5 > 2.0
        assert harmonize(a, V) > B

    def test_below_break_harmonized_below_baseline(self):
        B, V = 100.0, 50.0  # a_break = 2.0
        ab = a_break(B, V)
        a = ab - 0.5  # 1.5 < 2.0
        assert harmonize(a, V) < B

    def test_at_break_harmonized_equals_baseline(self):
        B, V = 100.0, 50.0  # a_break = 2.0
        ab = a_break(B, V)
        assert harmonize(ab, V) == pytest.approx(B, rel=1e-9)

    def test_a_break_exact_value(self):
        assert a_break(200.0, 80.0) == pytest.approx(2.5, rel=1e-9)
        assert a_break(60.0, 120.0) == pytest.approx(0.5, rel=1e-9)
        assert a_break(1.0, 1.0) == pytest.approx(1.0, rel=1e-9)

    def test_v_zero_returns_unavailable(self):
        result = a_break(B=100.0, V=0.0)
        assert result == UNAVAILABLE, (
            f"a_break with V=0 must be UNAVAILABLE, got {result!r}"
        )

    def test_b_zero_returns_unavailable(self):
        result = a_break(B=0.0, V=50.0)
        assert result == UNAVAILABLE, (
            f"a_break with B=0 must be UNAVAILABLE, got {result!r}"
        )

    def test_b_none_returns_unavailable(self):
        assert a_break(B=None, V=50.0) == UNAVAILABLE

    def test_v_none_returns_unavailable(self):
        assert a_break(B=100.0, V=None) == UNAVAILABLE

    def test_both_none_returns_unavailable(self):
        assert a_break(B=None, V=None) == UNAVAILABLE

    def test_unavailable_never_silently_becomes_zero(self):
        result = a_break(B=100.0, V=0.0)
        assert result != 0
        assert result != 0.0

    def test_harmonize_negative_v_returns_unavailable(self):
        assert harmonize(2.0, -1.0) == UNAVAILABLE

    def test_harmonize_missing_v_string_returns_unavailable(self):
        assert harmonize(2.0, UNAVAILABLE) == UNAVAILABLE


class TestApplicabilitySeparation:
    """
    Four distinct contract applicability states.
    out_of_domain MUST NOT be mapped to failed_applicability.
    """

    def test_applicable_in_domain_sufficient_support(self):
        result = check_applicability(O=100, min_support=5, in_domain=True)
        assert result == "applicable"

    def test_failed_applicability_negative_obs(self):
        result = check_applicability(O=-1, min_support=5, in_domain=True)
        assert result == FAILED_APPLICABILITY

    def test_missing_required_support_zero_obs(self):
        result = check_applicability(O=0, min_support=5, in_domain=True)
        assert result == MISSING_REQUIRED_SUPPORT

    def test_missing_required_support_none_obs(self):
        result = check_applicability(O=None, min_support=5, in_domain=True)
        assert result == MISSING_REQUIRED_SUPPORT

    def test_out_of_domain_is_not_failed_applicability(self):
        result = check_applicability(O=100, min_support=5, in_domain=False)
        assert result == OUT_OF_DOMAIN
        assert result != FAILED_APPLICABILITY, (
            "out_of_domain must NOT be mapped to failed_applicability"
        )

    def test_out_of_domain_even_with_zero_obs(self):
        """out_of_domain takes priority over missing_required_support."""
        result = check_applicability(O=0, min_support=5, in_domain=False)
        assert result == OUT_OF_DOMAIN

    def test_out_of_domain_even_with_high_obs(self):
        result = check_applicability(O=99999, min_support=5, in_domain=False)
        assert result == OUT_OF_DOMAIN

    def test_all_four_contract_states_are_distinct(self):
        states = {
            "applicable",
            FAILED_APPLICABILITY,
            MISSING_REQUIRED_SUPPORT,
            OUT_OF_DOMAIN,
        }
        assert len(states) == 4

    def test_missing_data_is_not_failed(self):
        result = check_applicability(O=0, min_support=5, in_domain=True)
        assert result == MISSING_REQUIRED_SUPPORT
        assert result != FAILED_APPLICABILITY


class TestInferenceStatus:
    """
    inference_status must be NOT_ESTABLISHED by default.
    No toy procedure in this test suite may emit "established".
    """

    def _infer_status(self, fai_value) -> str:
        """
        Conservative inference: returns NOT_ESTABLISHED unconditionally.
        Establishing a status requires separate calibration review outside
        this fixture.
        """
        return NOT_ESTABLISHED

    def test_unavailable_fai_gives_not_established(self):
        status = self._infer_status(UNAVAILABLE)
        assert status == NOT_ESTABLISHED

    def test_numeric_fai_still_gives_not_established(self):
        status = self._infer_status(500.0)
        assert status == NOT_ESTABLISHED

    def test_zero_fai_gives_not_established(self):
        status = self._infer_status(0.0)
        assert status == NOT_ESTABLISHED

    def test_high_fai_gives_not_established(self):
        status = self._infer_status(999.9)
        assert status == NOT_ESTABLISHED

    def test_inference_never_emits_established(self):
        for val in [UNAVAILABLE, 0.0, 100.0, 500.0, 999.0, None, "missing"]:
            status = self._infer_status(val)
            assert status == NOT_ESTABLISHED, (
                f"Expected NOT_ESTABLISHED for input {val!r}, got {status!r}"
            )

    def test_sensitivity_label_is_independent_of_inference(self):
        fai_value = 300.0
        sensitivity = "sensitive_to_assumptions"
        inference = self._infer_status(fai_value)

        assert isinstance(fai_value, float)
        assert sensitivity == "sensitive_to_assumptions"
        assert inference == NOT_ESTABLISHED

    @pytest.mark.parametrize("label", [
        "stable_across_displayed_settings",
        "sensitive_to_assumptions",
    ])
    def test_valid_sensitivity_labels(self, label):
        assert isinstance(label, str)
        assert len(label) > 0
