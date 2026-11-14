"""P2 r9 period coverage and D <= O evidence per product and policy (synthetic only).

No sealed (2020-2021) observation is read: sealed dates appear only as calendar dates,
and the code refuses any sealed day reported present.
"""
from datetime import date, timedelta
from itertools import product as cartesian

import numpy as np
import pytest

from pipeline.grid.accounting import block_day_counts, check_row
from pipeline.grid.coverage import footprint_evidence_summary, period_coverage
from pipeline.masks.firemask import fire_mask, fire_nh_mask, usable_mask

PRODUCTS = ["MYD14A1.061", "VNP14A1.002"]
AQUA_START = date(2002, 7, 4)
VIIRS_START = date(2012, 1, 19)
RECORD_END = date(2025, 12, 31)
SEALED = (date(2020, 1, 1), date(2021, 12, 31))  # proposed window, dates only


def days(start, end):
    return [start + timedelta(days=i) for i in range((end - start).days + 1)]


def all_present(start, end, missing=()):
    return {d: d not in missing for d in days(start, end)}


def cov(start, end, rec_start=VIIRS_START, present=None, **kw):
    present = all_present(start, end) if present is None else present
    kw.setdefault("c_min", None)
    return period_coverage(period_start=start, period_end=end, record_start=rec_start,
                           record_end=RECORD_END, day_present=present, **kw)


# ------------------------------------------------------------------ states


def test_full_week_with_cell_level_full_coverage_is_certifiable():
    s, e = date(2023, 7, 3), date(2023, 7, 9)
    r = cov(s, e, processed_cell_days=700, footprint_cells=100)
    assert (r.state, r.reasons, r.coverage, r.footprint_evidence) == ("complete", (), 1.0, "cell_level")
    assert r.certifiable_complete


def test_day_level_evidence_is_never_certifiable():
    r = cov(date(2023, 7, 3), date(2023, 7, 9))
    assert r.state == "complete" and r.footprint_evidence == "day_level"
    assert not r.certifiable_complete and r.coverage is None


def test_mid_record_missing_day_is_partial_and_lists_the_day():
    s, e = date(2023, 7, 3), date(2023, 7, 9)
    gap = date(2023, 7, 5)
    r = cov(s, e, present=all_present(s, e, missing=[gap]))
    assert r.state == "partial" and r.reasons == ("missing_days_or_tiles",)
    assert r.days_with_file == 6 and r.missing_days == (gap,)


def test_no_file_inside_the_record_is_unavailable_no_file():
    s, e = date(2023, 7, 3), date(2023, 7, 9)
    r = cov(s, e, present={d: False for d in days(s, e)})
    assert r.state == "unavailable" and r.reasons == ("no_file",)


def test_before_the_record_is_unavailable_sensor_not_operating():
    r = cov(date(2011, 12, 1), date(2011, 12, 31), present={})
    assert r.state == "unavailable" and r.reasons == ("sensor_not_operating",)


@pytest.mark.parametrize("start,end,rec_start,days_inside", [
    (date(2012, 1, 16), date(2012, 1, 22), VIIRS_START, 4),   # 2012-W03
    (date(2002, 7, 1), date(2002, 7, 7), AQUA_START, 4),      # 2002-W27
    (date(2025, 12, 29), date(2026, 1, 4), AQUA_START, 3),    # 2026-W01
])
def test_record_boundary_weeks_are_partial_period_clipped(start, end, rec_start, days_inside):
    present = {d: True for d in days(start, end) if rec_start <= d <= RECORD_END}
    r = cov(start, end, rec_start=rec_start, present=present)
    assert r.state == "partial" and r.reasons == ("period_clipped",)
    assert r.expected_days == r.days_with_file == days_inside


def test_sealed_boundary_week_uses_permitted_days_only():
    s, e = date(2019, 12, 30), date(2020, 1, 5)  # 2020-W01
    present = {date(2019, 12, 30): True, date(2019, 12, 31): True}
    r = cov(s, e, present=present, sealed_window=SEALED)
    assert r.state == "partial" and r.reasons == ("partition_boundary",)
    assert r.expected_days == r.days_with_file == 2


def test_sealed_day_reported_present_is_refused():
    s, e = date(2019, 12, 30), date(2020, 1, 5)
    present = {d: True for d in days(s, e)}
    with pytest.raises(ValueError, match="sealed"):
        cov(s, e, present=present, sealed_window=SEALED)


def test_unknown_day_is_not_treated_as_absent():
    s, e = date(2023, 7, 3), date(2023, 7, 9)
    present = all_present(s, e)
    del present[date(2023, 7, 6)]
    with pytest.raises(ValueError, match="unknown"):
        cov(s, e, present=present)


@pytest.mark.parametrize("c_min,expect_low", [(None, True), (1.0, True), (0.99, False)])
def test_low_processed_coverage_against_c_min(c_min, expect_low):
    s, e = date(2023, 7, 3), date(2023, 7, 9)
    r = cov(s, e, processed_cell_days=695, footprint_cells=100, c_min=c_min)  # 695/700 = 0.9929
    assert ("low_processed_coverage" in r.reasons) is expect_low
    assert r.state == ("partial" if expect_low else "complete")
    assert r.certifiable_complete is (not expect_low)


def test_unregistered_c_min_never_relaxes():
    s, e = date(2023, 7, 3), date(2023, 7, 9)
    r = cov(s, e, processed_cell_days=699, footprint_cells=100, c_min=None)
    assert r.state == "partial" and not r.certifiable_complete


@pytest.mark.parametrize("bad", [
    dict(processed_cell_days=10, footprint_cells=None),
    dict(processed_cell_days=800, footprint_cells=100),
    dict(c_min=0.0),
    dict(c_min=1.5),
])
def test_invalid_inputs_raise(bad):
    with pytest.raises(ValueError):
        cov(date(2023, 7, 3), date(2023, 7, 9), **bad)


# --------------------------------------------- D <= O per product and policy


@pytest.mark.parametrize("product", PRODUCTS)
def test_d_le_o_for_every_class_and_qa_state_and_policy(product):
    """Exhaustive over FireMask 0-9 x QA land/water bits: all, nh and common policies."""
    classes = list(range(10))
    qa_states = [0, 1, 2, 3]
    pairs = list(cartesian(classes, qa_states))
    fm = np.array([c for c, _ in pairs], dtype=np.uint8)
    qa = np.array([q for _, q in pairs], dtype=np.uint8)
    fire = fire_mask(fm, qa, product)
    fire_nh = fire_nh_mask(fm, qa, product)
    usable = usable_mask(fm, qa, product)
    assert np.all(~fire | usable)            # D subset of O, per cell
    assert np.all(~fire_nh | fire)           # D_nh subset of D
    o_nh = usable & ~(fire & ~fire_nh)       # O_nh = O - (D - D_nh)
    assert np.all(~fire_nh | o_nh)           # D_nh subset of O_nh
    assert int(o_nh.sum()) - int(fire_nh.sum()) == int(usable.sum()) - int(fire.sum())


def test_block_rows_from_random_grids_satisfy_every_le_pair():
    rng = np.random.default_rng(20261114)  # synthetic grids only
    for _ in range(50):
        ids = rng.choice([101, 102, -1], size=(12, 12))
        a = (rng.integers(0, 10, (12, 12)).astype(np.uint8), rng.integers(0, 4, (12, 12)).astype(np.uint8))
        v = (rng.integers(0, 10, (12, 12)).astype(np.uint8), rng.integers(0, 4, (12, 12)).astype(np.uint8))
        for row in block_day_counts(ids, [101, 102], aqua=a, viirs=v).values():
            assert check_row(row) == []


# --------------------------------------------- footprint evidence summary (Q3)


def _week(n_days_present=7, processed=None, fp=None):
    s, e = date(2023, 7, 3), date(2023, 7, 9)
    present = {d: i < n_days_present for i, d in enumerate(days(s, e))}
    return cov(s, e, present=present, processed_cell_days=processed, footprint_cells=fp)


def test_summary_without_cell_level_evidence_is_unverified():
    s = footprint_evidence_summary("g", [_week(), _week()])
    assert s["supports_status"] == "unverified" and s["footprint_evidence"] == "day_level"
    assert footprint_evidence_summary("g", [])["supports_status"] == "unverified"


def test_summary_all_cell_level_complete_supports_complete_but_does_not_certify():
    s = footprint_evidence_summary("g", [_week(processed=700, fp=100)] * 2)
    assert s["supports_status"] == "complete" and s["coverage_fraction"] == 1.0
    assert "certification_ref" not in s and "certified_at" not in s


def test_summary_with_a_shortfall_supports_partial_with_fraction():
    s = footprint_evidence_summary("g", [_week(processed=700, fp=100), _week(processed=350, fp=100)])
    assert s["supports_status"] == "partial"
    assert s["coverage_fraction"] == pytest.approx(0.75)


def test_one_day_level_period_makes_the_whole_summary_unverified():
    s = footprint_evidence_summary("g", [_week(processed=700, fp=100), _week()])
    assert s["supports_status"] == "unverified"
