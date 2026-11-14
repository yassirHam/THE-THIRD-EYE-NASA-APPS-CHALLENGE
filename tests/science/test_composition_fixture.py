"""
P1-C Independent Fixture: Sums-Before-Division & Block Composition

Equation source: THE_THIRD_EYE_FINAL_PLAN_GEOGRAPHIC_ACCESS_UPDATED.txt

The plan defines pooled-rate ratios (a_H, a_C) as sums-before-division:

    pooled_rate = sum(D_i) / sum(O_i)

NOT the average of per-cell rates:

    WRONG: (1/N) * sum(D_i / O_i)

Fixture: two blocks with opposite weighting:
  Block A: 80% observation support on high-rate cells (rate=10/unit-O)
           20% observation support on low-rate cells (rate=1/unit-O)
    -> pooled = (0.8*10 + 0.2*1) / (0.8+0.2) = 8.2  FAI = 8200
  Block B: 20% observation support on high-rate cells (rate=10/unit-O)
           80% observation support on low-rate cells (rate=1/unit-O)
    -> pooled = (0.2*10 + 0.8*1) / (0.2+0.8) = 2.8  FAI = 2800

  Naive (unweighted) average: (10+1)/2 = 5.5 -> FAI = 5500 for both
"""

import pytest

UNAVAILABLE = "unavailable"


# ---------------------------------------------------------------------------
# Core pooling helper (sums-before-division)
# ---------------------------------------------------------------------------

def pool_fai(cells: list[tuple[float, float]]) -> object:
    """
    cells: list of (D_i, O_i) tuples.
    Returns FAI = sum(D) / sum(O) * 1000, excluding O=0 cells.
    Returns UNAVAILABLE if no usable cells.
    """
    total_D = sum(d for d, o in cells if o > 0)
    total_O = sum(o for d, o in cells if o > 0)
    if total_O == 0:
        return UNAVAILABLE
    return (total_D / total_O) * 1000


def naive_average_fai(cells: list[tuple[float, float]]) -> float:
    """
    WRONG method: arithmetic mean of per-cell rates * 1000.
    Included only to prove the two methods diverge on imbalanced data.
    """
    rates = [(d / o) * 1000 for d, o in cells if o > 0]
    return sum(rates) / len(rates)


BLOCK_A_CELLS = [
    (8.0, 0.8),   # high-rate cell: D=8, O=0.8  -> rate=10 /unit-O
    (0.2, 0.2),   # low-rate cell:  D=0.2, O=0.2 -> rate=1  /unit-O
]

BLOCK_B_CELLS = [
    (2.0, 0.2),   # high-rate cell: D=2, O=0.2  -> rate=10 /unit-O
    (0.8, 0.8),   # low-rate cell:  D=0.8, O=0.8 -> rate=1  /unit-O
]

EXPECTED_A = 8200.0   # (8.0+0.2)/(0.8+0.2) * 1000 = 8.2 * 1000
EXPECTED_B = 2800.0   # (2.0+0.8)/(0.2+0.8) * 1000 = 2.8 * 1000
EXPECTED_NAIVE = 5500.0  # (10+1)/2 * 1000
EXPECTED_SHIFT_PCT = -65.85   # (2.8 - 8.2) / 8.2 * 100


class TestSumsBeforeDivision:
    """The pooled rate must use sums-before-division, not averaged per-cell rates."""

    def test_block_a_pooled_fai(self):
        result = pool_fai(BLOCK_A_CELLS)
        assert result == pytest.approx(EXPECTED_A, rel=1e-9), (
            f"Block A pooled FAI should be {EXPECTED_A}, got {result}"
        )

    def test_block_b_pooled_fai(self):
        result = pool_fai(BLOCK_B_CELLS)
        assert result == pytest.approx(EXPECTED_B, rel=1e-9), (
            f"Block B pooled FAI should be {EXPECTED_B}, got {result}"
        )

    def test_naive_average_gives_equal_wrong_result(self):
        """Naive averaging yields 5500 for both blocks -- proves it is wrong."""
        a_naive = naive_average_fai(BLOCK_A_CELLS)
        b_naive = naive_average_fai(BLOCK_B_CELLS)
        assert a_naive == pytest.approx(EXPECTED_NAIVE, rel=1e-9)
        assert b_naive == pytest.approx(EXPECTED_NAIVE, rel=1e-9)
        assert a_naive == pytest.approx(b_naive, rel=1e-9), (
            "Naive method must incorrectly equate the two blocks"
        )

    def test_pooled_blocks_are_not_equal(self):
        """The correct pooled method must distinguish the two blocks."""
        a = pool_fai(BLOCK_A_CELLS)
        b = pool_fai(BLOCK_B_CELLS)
        assert a != pytest.approx(b, rel=1e-6), (
            "Pooled FAI must differ between Block A and Block B"
        )

    def test_pooled_shift_percent(self):
        """Verify the plan-stated -65.85 % shift from Block A to Block B."""
        a = pool_fai(BLOCK_A_CELLS)
        b = pool_fai(BLOCK_B_CELLS)
        shift_pct = (b - a) / a * 100
        assert shift_pct == pytest.approx(EXPECTED_SHIFT_PCT, abs=0.01), (
            f"Shift should be approx {EXPECTED_SHIFT_PCT} %, got {shift_pct:.4f} %"
        )

    def test_sums_before_division_identity(self):
        """Direct arithmetic verification: sum(D)/sum(O)*1000."""
        total_D_a = sum(d for d, o in BLOCK_A_CELLS)
        total_O_a = sum(o for d, o in BLOCK_A_CELLS)
        assert total_D_a == pytest.approx(8.2, rel=1e-9)
        assert total_O_a == pytest.approx(1.0, rel=1e-9)
        assert (total_D_a / total_O_a) * 1000 == pytest.approx(EXPECTED_A)

        total_D_b = sum(d for d, o in BLOCK_B_CELLS)
        total_O_b = sum(o for d, o in BLOCK_B_CELLS)
        assert total_D_b == pytest.approx(2.8, rel=1e-9)
        assert total_O_b == pytest.approx(1.0, rel=1e-9)
        assert (total_D_b / total_O_b) * 1000 == pytest.approx(EXPECTED_B)


class TestCompositionInvariance:
    """
    Adding a third region: pooled result must equal sums-before-division
    across all three, not an average of pairwise results.

    Region C uses O=3.0 (not 1.0) so its observation weight differs from
    Block A and Block B (both O=1.0 total), breaking the accidental equality
    between pooled and naive-average that arises when all weights are equal.
    """

    # Region C: D=15.0, O=3.0 -> rate = 5000 FAI
    # Total across all: D = 8.2 + 2.8 + 15.0 = 26.0
    #                   O = 1.0 + 1.0 +  3.0  =  5.0
    # Combined pool = (26.0 / 5.0) * 1000 = 5200.0
    # Naive average = (8200 + 2800 + 5000) / 3 = 5333.33  <-- differs
    REGION_C_CELLS = [(15.0, 3.0)]  # rate = 5000 FAI, O=3.0

    def test_three_region_pool_is_not_average_of_pairwise(self):
        all_cells = BLOCK_A_CELLS + BLOCK_B_CELLS + self.REGION_C_CELLS
        combined = pool_fai(all_cells)

        fai_a = pool_fai(BLOCK_A_CELLS)
        fai_b = pool_fai(BLOCK_B_CELLS)
        fai_c = pool_fai(self.REGION_C_CELLS)
        wrong = (fai_a + fai_b + fai_c) / 3

        assert combined != pytest.approx(wrong, rel=1e-4), (
            "Combined pool must differ from naive average of sub-region FAIs"
        )

    def test_three_region_pool_exact(self):
        all_cells = BLOCK_A_CELLS + BLOCK_B_CELLS + self.REGION_C_CELLS
        combined = pool_fai(all_cells)
        # D total = 8.2 + 2.8 + 15.0 = 26.0; O total = 1.0 + 1.0 + 3.0 = 5.0
        expected = (26.0 / 5.0) * 1000  # = 5200.0
        assert combined == pytest.approx(expected, rel=1e-9)
