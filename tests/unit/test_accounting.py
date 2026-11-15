"""P2-A D/O accounting and pooled-rate reference tests (synthetic fixtures only)."""
import math

import numpy as np
import pytest

from pipeline.grid.accounting import (
    COMMON_COLUMNS,
    COUNT_COLUMNS,
    block_day_counts,
    check_row,
    pooled_rate,
    pooled_rate_from_rows,
    sum_column,
)
from tests.unit.fixtures import (
    AQUA_FM, AQUA_QA, BLOCK_A, BLOCK_B, BLOCK_IDS, EXPECTED_BOTH,
    VIIRS_FM, VIIRS_QA, all_cloud,
)

BLOCKS = [BLOCK_A, BLOCK_B]
AQ, VI = (AQUA_FM, AQUA_QA), (VIIRS_FM, VIIRS_QA)


# ----------------------------------------------------------------- block counts
def test_hand_computed_block_counts_both_sensors():
    rows = block_day_counts(BLOCK_IDS, BLOCKS, aqua=AQ, viirs=VI)
    for code in BLOCKS:
        assert rows[code]["aqua_file_present"] == 1
        assert rows[code]["viirs_file_present"] == 1
        for col, val in EXPECTED_BOTH[code].items():
            assert rows[code][col] == val, (code, col)
        assert check_row(rows[code]) == []


def test_outside_domain_and_coast_water_fires_are_not_counted():
    rows = block_day_counts(BLOCK_IDS, BLOCKS, aqua=AQ, viirs=VI)
    # Aqua has 6 fire-class pixels in total; only 3 are land pixels inside a block.
    assert int(np.isin(AQUA_FM, [7, 8, 9]).sum()) == 6
    assert rows[BLOCK_A]["D_aqua"] + rows[BLOCK_B]["D_aqua"] == 3


def test_block_counts_reconcile_with_region_total():
    """Block counts must sum exactly to the counts of their union (plan 4B)."""
    rows = block_day_counts(BLOCK_IDS, BLOCKS, aqua=AQ, viirs=VI)
    union_ids = np.where(BLOCK_IDS >= 0, 999, BLOCK_IDS).astype(np.int32)
    region = block_day_counts(union_ids, [999], aqua=AQ, viirs=VI)[999]
    for col in COUNT_COLUMNS:
        assert sum_column(rows.values(), col) == region[col], col


def test_file_absent_is_null_not_zero():
    rows = block_day_counts(BLOCK_IDS, BLOCKS, aqua=None, viirs=VI)
    r = rows[BLOCK_A]
    assert r["aqua_file_present"] == 0 and r["viirs_file_present"] == 1
    assert r["D_aqua"] is None and r["O_aqua"] is None and r["D_aqua_nh"] is None
    assert all(r[c] is None for c in COMMON_COLUMNS)   # common needs both files
    assert r["O_viirs"] == EXPECTED_BOTH[BLOCK_A]["O_viirs"]
    assert check_row(r) == []


def test_both_files_absent_all_null():
    r = block_day_counts(BLOCK_IDS, BLOCKS)[BLOCK_B]
    assert all(r[c] is None for c in COUNT_COLUMNS)
    assert check_row(r) == []


def test_empty_day_is_zero_support_not_missing():
    """A processed all-cloud day: O = 0 is a real value; the rate is unavailable."""
    rows = block_day_counts(BLOCK_IDS, BLOCKS, aqua=all_cloud(), viirs=all_cloud())
    r = rows[BLOCK_A]
    assert r["O_aqua"] == 0 and r["D_aqua"] == 0 and r["O_common"] == 0
    res = pooled_rate_from_rows(rows.values(), "D_aqua", "O_aqua")
    assert res.value is None and res.status == "zero_support" and res.o_sum == 0


def test_registered_block_without_pixels_gets_zero_rows():
    rows = block_day_counts(BLOCK_IDS, BLOCKS + [303], aqua=AQ, viirs=VI)
    assert rows[303]["O_aqua"] == 0 and rows[303]["D_aqua"] == 0


def test_unregistered_or_reserved_codes_raise():
    with pytest.raises(ValueError, match="unregistered"):
        block_day_counts(BLOCK_IDS, [BLOCK_A], aqua=AQ, viirs=VI)
    with pytest.raises(ValueError, match="reserved"):
        block_day_counts(BLOCK_IDS, BLOCKS + [-1], aqua=AQ)
    with pytest.raises(ValueError, match="duplicate"):
        block_day_counts(BLOCK_IDS, [BLOCK_A, BLOCK_A, BLOCK_B], aqua=AQ)


def test_misaligned_grid_raises():
    with pytest.raises(ValueError):
        block_day_counts(BLOCK_IDS, BLOCKS, aqua=(AQUA_FM[:, :3], AQUA_QA[:, :3]))


# -------------------------------------------------------------------- check_row
def test_check_row_flags_contract_violations():
    good = block_day_counts(BLOCK_IDS, BLOCKS, aqua=AQ, viirs=VI)[BLOCK_A]
    assert check_row({**good, "D_aqua": 10}) != []                 # D > O
    assert check_row({**good, "D_aqua_nh": 3}) != []               # D_nh > D
    assert check_row({**good, "O_common": 4}) != []                # common > own
    assert check_row({**good, "aqua_file_present": 0}) != []       # values with absent file
    absent = block_day_counts(BLOCK_IDS, BLOCKS, viirs=VI)[BLOCK_A]
    assert check_row({**absent, "O_aqua": 0}) != []                # missing coded as zero
    assert check_row({**good, "O_viirs": None}) != []              # present file, null value


# ------------------------------------------------------------------ pooled rate
def test_sum_before_divide_differs_from_average_of_rates():
    # Block 1: big, quiet; block 2: small, busy.
    d, o = [1, 50], [1000, 100]
    res = pooled_rate(d, o)
    assert res.status == "available"
    assert res.value == pytest.approx(1000 * 51 / 1100)            # 46.36...
    mean_of_rates = (1000 * 1 / 1000 + 1000 * 50 / 100) / 2         # 250.5 (wrong)
    assert not math.isclose(res.value, mean_of_rates)
    # Pooled rate equals the O-weighted mean of block rates (plan 4B identity).
    w = [oi / sum(o) for oi in o]
    assert res.value == pytest.approx(sum(wi * 1000 * di / oi for wi, di, oi in zip(w, d, o)))


def test_pooling_over_days_and_blocks_from_rows():
    day1 = block_day_counts(BLOCK_IDS, BLOCKS, aqua=AQ, viirs=VI)
    day2 = block_day_counts(BLOCK_IDS, BLOCKS, aqua=all_cloud(), viirs=VI)
    rows = list(day1.values()) + list(day2.values())
    res = pooled_rate_from_rows(rows, "D_aqua", "O_aqua")
    assert (res.d_sum, res.o_sum) == (3, 5)
    assert res.value == pytest.approx(600.0)
    common = pooled_rate_from_rows(rows, "D_viirs_common", "O_common")
    assert (common.d_sum, common.o_sum) == (2, 4)


def test_valid_zero_detection_is_available_zero():
    res = pooled_rate([0, 0], [10, 5])
    assert res.status == "available" and res.value == 0.0


def test_zero_support_is_null():
    res = pooled_rate([0, 0], [0, 0])
    assert res.value is None and res.status == "zero_support"


def test_missing_unit_makes_rate_incomplete_not_renormalised():
    res = pooled_rate([1, None, 2], [100, None, 100])
    assert res.value is None and res.status == "incomplete"
    assert res.n_missing == 1 and res.n_units == 3
    assert res.d_sum is None and res.o_sum is None


def test_missing_file_day_in_rows_is_incomplete():
    day1 = block_day_counts(BLOCK_IDS, BLOCKS, aqua=AQ, viirs=VI)
    day2 = block_day_counts(BLOCK_IDS, BLOCKS, aqua=None, viirs=VI)
    rows = list(day1.values()) + list(day2.values())
    assert pooled_rate_from_rows(rows, "D_aqua", "O_aqua").status == "incomplete"
    assert pooled_rate_from_rows(rows, "D_aqua_common", "O_common").status == "incomplete"
    assert pooled_rate_from_rows(rows, "D_viirs", "O_viirs").status == "available"
    assert sum_column(rows, "O_aqua") is None


def test_no_units_is_no_data():
    res = pooled_rate([], [])
    assert res.value is None and res.status == "no_data"


@pytest.mark.parametrize("d, o, msg", [
    ([1, None], [10, 5], "null together"),
    ([5], [4], "subset of usable"),
    ([-1], [4], "non-negative"),
    ([float("nan")], [4.0], "not NaN"),
    ([1, 2], [3], "one value per unit"),
])
def test_invalid_inputs_raise(d, o, msg):
    with pytest.raises(ValueError, match=msg):
        pooled_rate(d, o)
