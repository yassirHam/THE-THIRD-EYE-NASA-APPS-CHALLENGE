"""
P1-C Independent Fixture: Missing vs Zero

Equation source: THE_THIRD_EYE_FINAL_PLAN_GEOGRAPHIC_ACCESS_UPDATED.txt
  FAI = (D / O) * 1000  where D = fire-cell-days, O = usable land-cell-days

GUARDRAIL: O = 0 (missing / obscured swath) MUST NOT produce a numeric FAI
           and MUST NOT enter any denominator. The result must be an explicit
           unavailability sentinel, never 0.0 or any float.

These tests are written against the *contract* (equations + guardrails), NOT
copied from science/methods/ or science/calendar/ outputs.
"""

import math
import pytest


# ---------------------------------------------------------------------------
# Reference implementation (pure equations, no science/ imports)
# ---------------------------------------------------------------------------

UNAVAILABLE = "unavailable"
INSUFFICIENT_SUPPORT = "insufficient_support"


def compute_fai(D: float, O: float, min_support: int = 1) -> object:
    """
    Compute Fire Activity Index per the plan equation:
        FAI = (D / O) * 1000

    Returns
    -------
    float          - valid FAI when O >= min_support and D is not None
    UNAVAILABLE    - when O == 0  (missing / obscured swath)
    INSUFFICIENT_SUPPORT - when 0 < O < min_support
    """
    if O is None:
        return UNAVAILABLE
    if O == 0:
        return UNAVAILABLE                 # <- the critical guard
    if O < min_support:
        return INSUFFICIENT_SUPPORT
    if D is None:
        return UNAVAILABLE
    return (D / O) * 1000


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestObscuredSwathNeverBecomesZeroFires:
    """O = 0 must produce UNAVAILABLE, never 0.0 or any numeric value."""

    def test_o_zero_returns_unavailable_not_float(self):
        result = compute_fai(D=0, O=0)
        assert result == UNAVAILABLE, (
            f"O=0 must return UNAVAILABLE sentinel, got {result!r}"
        )

    def test_o_zero_result_is_not_numeric(self):
        result = compute_fai(D=0, O=0)
        assert not isinstance(result, (int, float)), (
            f"O=0 must not produce a number, got {type(result).__name__} {result!r}"
        )

    def test_o_zero_with_nonzero_D_still_unavailable(self):
        """Even if D > 0 were somehow logged, O=0 swath is still missing."""
        result = compute_fai(D=5, O=0)
        assert result == UNAVAILABLE

    def test_o_zero_is_not_zero_float(self):
        result = compute_fai(D=0, O=0)
        assert result != 0.0

    def test_o_zero_is_not_nan(self):
        result = compute_fai(D=0, O=0)
        # Must not silently become NaN (0/0 in floating point)
        if isinstance(result, float):
            assert not math.isnan(result), "O=0 must not silently become NaN"

    def test_o_none_returns_unavailable(self):
        result = compute_fai(D=0, O=None)
        assert result == UNAVAILABLE

    def test_d_none_returns_unavailable(self):
        result = compute_fai(D=None, O=10)
        assert result == UNAVAILABLE


class TestUnavailableNeverEntersDenominator:
    """
    Aggregation across cells: a cell with O=0 must be excluded from pooled
    sums, never coerced to 0 and included.
    """

    def _pool_fai(self, cells: list[tuple]) -> object:
        """
        Pool FAI across cells: sum(D_i) / sum(O_i) * 1000.
        Cells where O=0 are excluded from both sums.
        Returns UNAVAILABLE only if no usable cells remain.
        """
        total_D = 0.0
        total_O = 0.0
        for D, O in cells:
            if O is None or O == 0:
                continue          # excluded, NOT added as zero
            total_D += D
            total_O += O
        if total_O == 0:
            return UNAVAILABLE
        return (total_D / total_O) * 1000

    def test_single_missing_cell_excluded_not_zeroed(self):
        # Cell 1: O=0 (missing). Cell 2: D=3, O=10.
        # Pooled = (3/10)*1000 = 300.0  (cell 1 excluded entirely)
        cells = [(0, 0), (3, 10)]
        result = self._pool_fai(cells)
        assert result == pytest.approx(300.0), (
            f"Missing cell must be excluded, not zeroed. Got {result}"
        )

    def test_all_missing_cells_returns_unavailable(self):
        cells = [(0, 0), (0, 0)]
        result = self._pool_fai(cells)
        assert result == UNAVAILABLE

    def test_missing_cell_does_not_inflate_denominator(self):
        cells = [(0, 0), (5, 10)]
        result_correct = self._pool_fai(cells)
        assert result_correct == pytest.approx(500.0)

    def test_unavailable_sentinel_distinguished_from_zero_fai(self):
        """
        A grid with genuinely zero detected fires but valid observation days
        must yield FAI = 0.0, not UNAVAILABLE - these must be distinct.
        """
        result_valid_zero = compute_fai(D=0, O=100)
        result_missing = compute_fai(D=0, O=0)
        assert result_valid_zero == pytest.approx(0.0)
        assert result_missing == UNAVAILABLE
        assert result_valid_zero != result_missing


class TestInsufficientSupportSentinel:
    """0 < O < min_support must produce INSUFFICIENT_SUPPORT, not UNAVAILABLE."""

    def test_low_support_returns_correct_sentinel(self):
        result = compute_fai(D=1, O=1, min_support=5)
        assert result == INSUFFICIENT_SUPPORT

    def test_low_support_is_not_unavailable(self):
        result = compute_fai(D=1, O=1, min_support=5)
        assert result != UNAVAILABLE

    def test_at_min_support_boundary_computes_fai(self):
        result = compute_fai(D=1, O=5, min_support=5)
        assert isinstance(result, float)
        assert result == pytest.approx(200.0)

    def test_below_min_support_is_not_numeric(self):
        result = compute_fai(D=1, O=4, min_support=5)
        assert not isinstance(result, float)
