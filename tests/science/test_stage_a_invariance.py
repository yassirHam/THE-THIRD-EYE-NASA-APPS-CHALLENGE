"""
P1-C Independent Fixture: Stage A Invariance, a_H vs a_C, Applicability

Equation source: THE_THIRD_EYE_FINAL_PLAN_GEOGRAPHIC_ACCESS_UPDATED.txt

Covers:
  1. Scalar invariance: multiplying all D and O by the same scalar k must
     leave FAI unchanged (FAI is a rate, not a count).
  2. Equality-threshold edge cases: boundary values at exactly min_support.
  3. a_H (own-support) vs a_C (common-support) pooled-rate ratios must be
     computed separately and are not interchangeable.
  4. failed-applicability vs absent-data: distinct output states.
  5. Inference status: not_established unless criteria are met.
"""

import pytest
import math

UNAVAILABLE = "unavailable"
INSUFFICIENT_SUPPORT = "insufficient_support"
FAILED_APPLICABILITY = "failed_applicability"
NOT_ESTABLISHED = "not_established"


def fai(D: float, O: float) -> float:
    return (D / O) * 1000


def pooled_ratio(D_list: list[float], O_list: list[float]) -> float:
    total_D = sum(D_list)
    total_O = sum(O_list)
    if total_O == 0:
        raise ValueError("Cannot pool with total O = 0")
    return total_D / total_O


def a_H(sensor_D: list[float], sensor_O: list[float]) -> float:
    return pooled_ratio(sensor_D, sensor_O)


def a_C(
    sensor_D: list[float], sensor_O: list[float],
    ref_D: list[float], ref_O: list[float],
) -> float:
    sensor_rate = pooled_ratio(sensor_D, sensor_O)
    ref_rate = pooled_ratio(ref_D, ref_O)
    if ref_rate == 0:
        raise ValueError("Reference rate is zero; a_C undefined")
    return sensor_rate / ref_rate


def check_applicability(
    O: float,
    min_support: int = 5,
    in_domain: bool = True,
) -> str:
    if not in_domain:
        return FAILED_APPLICABILITY
    if O is None or O == 0:
        return UNAVAILABLE
    if O < min_support:
        return INSUFFICIENT_SUPPORT
    return "applicable"


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
        base = pooled_ratio(D_list, O_list)
        scaled = pooled_ratio([d * k for d in D_list], [o * k for o in O_list])
        assert scaled == pytest.approx(base, rel=1e-9)

    def test_zero_fires_valid_obs_gives_zero_fai(self):
        assert fai(0.0, 100.0) == pytest.approx(0.0)

    def test_full_saturation_gives_1000_fai(self):
        assert fai(50.0, 50.0) == pytest.approx(1000.0)


class TestEqualityThresholdEdgeCases:
    """Boundary conditions at min_support must be handled exactly."""

    @pytest.mark.parametrize("O,min_support,expected_state", [
        (0,   5, UNAVAILABLE),
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

    def test_none_obs_is_unavailable_not_insufficient(self):
        result = check_applicability(O=None, min_support=5)
        assert result == UNAVAILABLE
        assert result != INSUFFICIENT_SUPPORT

    def test_zero_obs_is_unavailable_not_insufficient(self):
        result = check_applicability(O=0, min_support=5)
        assert result == UNAVAILABLE
        assert result != INSUFFICIENT_SUPPORT


class TestAHvsACDivergence:
    """
    a_H and a_C are distinct quantities computed over different cell sets.
    """

    def test_a_H_own_support_computation(self):
        sensor_D = [4.0, 6.0, 2.0]
        sensor_O = [10.0, 20.0, 5.0]
        result = a_H(sensor_D, sensor_O)
        assert result == pytest.approx(12 / 35, rel=1e-9)

    def test_a_C_common_support_ratio(self):
        sensor_D = [3.0, 5.0]
        sensor_O = [10.0, 10.0]
        ref_D    = [4.0, 4.0]
        ref_O    = [10.0, 10.0]
        result = a_C(sensor_D, sensor_O, ref_D, ref_O)
        assert result == pytest.approx(1.0, rel=1e-9)

    def test_a_H_and_a_C_differ_on_imbalanced_data(self):
        sensor_own_D = [9.0, 8.0]
        sensor_own_O = [10.0, 10.0]
        aH = a_H(sensor_own_D, sensor_own_O)

        sensor_comm_D = [1.0, 2.0]
        sensor_comm_O = [10.0, 10.0]
        ref_comm_D    = [5.0, 6.0]
        ref_comm_O    = [10.0, 10.0]
        aC = a_C(sensor_comm_D, sensor_comm_O, ref_comm_D, ref_comm_O)

        assert aH != pytest.approx(aC, rel=1e-4)

    def test_a_H_uses_sums_not_averages(self):
        sensor_D = [9.0, 1.0]
        sensor_O = [1.0, 9.0]
        result = a_H(sensor_D, sensor_O)
        assert result == pytest.approx(1.0, rel=1e-9)
        naive_avg = sum(d / o for d, o in zip(sensor_D, sensor_O)) / 2
        assert result != pytest.approx(naive_avg, rel=1e-4)

    def test_a_C_ref_zero_raises(self):
        with pytest.raises(ValueError, match="zero"):
            a_C([1.0], [5.0], [0.0], [10.0])

    def test_a_H_own_support_cells_never_inherit_common_factor(self):
        aH = a_H([6.0], [10.0])
        aC = a_C([2.0], [10.0], [4.0], [10.0])

        assert aH == pytest.approx(0.6, rel=1e-9)
        assert aC == pytest.approx(0.5, rel=1e-9)
        assert aH != pytest.approx(aC, rel=1e-4)


class TestApplicabilitySeparation:
    def test_out_of_domain_is_failed_applicability(self):
        result = check_applicability(O=100, min_support=5, in_domain=False)
        assert result == FAILED_APPLICABILITY

    def test_out_of_domain_is_not_unavailable(self):
        result = check_applicability(O=100, min_support=5, in_domain=False)
        assert result != UNAVAILABLE

    def test_missing_data_is_unavailable_not_failed(self):
        result = check_applicability(O=0, min_support=5, in_domain=True)
        assert result == UNAVAILABLE
        assert result != FAILED_APPLICABILITY

    def test_all_four_states_are_distinct(self):
        states = {
            UNAVAILABLE,
            INSUFFICIENT_SUPPORT,
            FAILED_APPLICABILITY,
            NOT_ESTABLISHED,
        }
        assert len(states) == 4

    def test_failed_applicability_survives_high_obs_count(self):
        result = check_applicability(O=99999, min_support=5, in_domain=False)
        assert result == FAILED_APPLICABILITY


class TestInferenceStatus:
    def _infer_status(self, fai_value, n_years: int, threshold: float = 1.5) -> str:
        if isinstance(fai_value, str):
            return NOT_ESTABLISHED
        if n_years < threshold:
            return NOT_ESTABLISHED
        return "established"

    def test_unavailable_fai_gives_not_established(self):
        status = self._infer_status(UNAVAILABLE, n_years=10)
        assert status == NOT_ESTABLISHED

    def test_low_year_count_gives_not_established(self):
        status = self._infer_status(500.0, n_years=1)
        assert status == NOT_ESTABLISHED

    def test_sufficient_data_can_be_established(self):
        status = self._infer_status(500.0, n_years=5)
        assert status == "established"

    def test_sensitivity_label_is_independent_of_inference(self):
        fai_value = 300.0
        sensitivity = "sensitive_to_assumptions"
        inference = self._infer_status(fai_value, n_years=1)

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
