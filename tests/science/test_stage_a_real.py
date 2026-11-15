"""
Synthetic tests for science.methods.stage_a_real.

No external parquet is needed: rows are built in memory, and the loader test
writes a tiny synthetic parquet to tmp_path (skipped when pyarrow is absent).
Expected values are hand-computed from the plan's definitions (Section 4B,
Section 6), not copied from module output.
"""
from __future__ import annotations

import json
import math
from datetime import date, timedelta

import pytest

from science.methods import stage_a_real as sar
from science.methods.stage_a import FactorStatus

CA, BC = 3218, 826
FULL = "full_training_2016_2017_2018"


def _iso_monday(year: int, week: int) -> str:
    return date.fromisocalendar(year, week, 1).isoformat()


def _partition(year: int) -> str:
    if year in sar.TRAINING_YEARS:
        return "train_2016_2018"
    if year == sar.DEV_YEAR:
        return "dev_2019"
    return "applicability_2022_2025"


def row(region: int, year: int, week: int, *, Da=1, Oa=1000, Dv=1, Ov=1000,
        Oc=900, Dac=1, Dvc=1, state_a="complete", state_v="complete",
        cov_a=1.0, cov_v=1.0, eligible=True, n_fp=10, partition=None) -> dict:
    return {
        "ADM1_CODE": region, "week_start": _iso_monday(year, week),
        "partition": partition or _partition(year), "iso_year": year, "iso_week": week,
        "D_aqua": float(Da), "O_aqua": None if Oa is None else float(Oa),
        "D_viirs": float(Dv), "O_viirs": None if Ov is None else float(Ov),
        "O_common": float(Oc), "D_aqua_common": float(Dac), "D_viirs_common": float(Dvc),
        "state_aqua": state_a, "state_viirs": state_v,
        "coverage_aqua": cov_a, "coverage_viirs": cov_v,
        "comparison_eligible": eligible, "N_fp": n_fp,
    }


# Per-year weekly counts for one region.  Two weeks per training year with
# deliberately unequal O so pooled and averaged rates differ.
#   year: [(Da, Oa, Dv, Ov), (Da, Oa, Dv, Ov)]
TRAIN = {
    2016: [(30, 1000, 10, 1000), (2, 4000, 2, 4000)],
    2017: [(20, 2000, 10, 2000), (6, 3000, 3, 3000)],
    2018: [(10, 1000, 5, 1000), (8, 4000, 4, 4000)],
}


def _rows_for(region: int, data=TRAIN, extra=()) -> list[dict]:
    out = []
    for y, wks in data.items():
        for i, (Da, Oa, Dv, Ov) in enumerate(wks, start=1):
            out.append(row(region, y, i, Da=Da, Oa=Oa, Dv=Dv, Ov=Ov,
                           Oc=min(Oa, Ov), Dac=Da, Dvc=Dv))
    return out + list(extra)


def _hand_factor(years) -> float:
    da = sum(w[0] for y in years for w in TRAIN[y])
    oa = sum(w[1] for y in years for w in TRAIN[y])
    dv = sum(w[2] for y in years for w in TRAIN[y])
    ov = sum(w[3] for y in years for w in TRAIN[y])
    return (da / oa) / (dv / ov)


# ---------------------------------------------------------------------------
# Sealed-window guard
# ---------------------------------------------------------------------------
class TestSealedGuard:
    def test_sealed_iso_year_raises(self):
        with pytest.raises(sar.SealedDataError):
            sar.assert_no_sealed_rows([row(CA, 2020, 10)])

    def test_week_straddling_into_2020_raises(self):
        # ISO 2019 has 52 weeks; a week starting 2019-12-30 is ISO 2020 W1,
        # so build the straddle explicitly with an inconsistent iso_year label.
        r = row(CA, 2019, 52)
        r["week_start"] = "2019-12-30"
        with pytest.raises(sar.SealedDataError):
            sar.assert_no_sealed_rows([r])

    def test_week_ending_2019_12_31_is_allowed_but_2020_01_01_is_not(self):
        ok = row(CA, 2019, 52)
        ok["week_start"] = (date(2019, 12, 31) - timedelta(days=6)).isoformat()
        sar.assert_no_sealed_rows([ok])
        bad = dict(ok, week_start=(date(2020, 1, 1) - timedelta(days=6)).isoformat())
        with pytest.raises(sar.SealedDataError):
            sar.assert_no_sealed_rows([bad])

    def test_run_stage_a_rejects_sealed_rows(self):
        with pytest.raises(sar.SealedDataError):
            sar.run_stage_a(_rows_for(CA) + [row(CA, 2021, 5)])

    def test_loader_filters_sealed_years_and_partitions(self, tmp_path):
        pa = pytest.importorskip("pyarrow")
        pq = pytest.importorskip("pyarrow.parquet")
        rows = _rows_for(CA) + [row(CA, 2020, 3, partition="sealed_2020_2021"),
                                row(CA, 2021, 7, partition="applicability_2022_2025"),
                                row(CA, 2010, 3, partition="history_2002_2015")]
        p = tmp_path / sar.PARQUET_NAME
        pq.write_table(pa.Table.from_pylist(rows), p)
        loaded = sar.load_rows(p)
        assert len(loaded) == 6
        assert {r["iso_year"] for r in loaded} == {2016, 2017, 2018}

    def test_loader_missing_file(self, tmp_path):
        pytest.importorskip("pyarrow")
        with pytest.raises(FileNotFoundError):
            sar.load_rows(tmp_path / "absent.parquet")

    def test_cli_without_data_writes_nothing(self, tmp_path, monkeypatch):
        monkeypatch.delenv(sar.DATA_DIR_ENV, raising=False)
        out = tmp_path / "s.json"
        assert sar.main(["--out", str(out)]) == 2
        assert not out.exists()
        assert sar.main(["--data-dir", str(tmp_path), "--out", str(out)]) == 2
        assert not out.exists()


# ---------------------------------------------------------------------------
# Week eligibility: missing is never zero
# ---------------------------------------------------------------------------
class TestWeekSelection:
    def test_partial_unavailable_low_coverage_and_ineligible_excluded(self):
        rows = [
            row(CA, 2016, 1),
            row(CA, 2016, 2, state_v="partial"),
            row(CA, 2016, 3, state_a="unavailable", Oa=None),
            row(CA, 2016, 4, cov_v=0.99999),
            row(CA, 2016, 5, eligible=False),
            row(CA, 2019, 6, partition="train_2016_2018"),
        ]
        weeks, excluded = sar.select_weeks(rows, c_min=1.0)
        assert [w.week_start for w in weeks] == [_iso_monday(2016, 1)]
        reasons = {e["week_start"]: e["reasons"] for e in excluded}
        assert reasons[_iso_monday(2016, 2)] == ["viirs_state_partial"]
        assert reasons[_iso_monday(2016, 3)] == ["aqua_state_unavailable"]
        assert reasons[_iso_monday(2016, 4)] == ["viirs_coverage_below_c_min"]
        assert reasons[_iso_monday(2016, 5)] == ["not_comparison_eligible"]
        assert reasons[_iso_monday(2019, 6)] == ["iso_year_outside_partition"]

    def test_c_min_is_a_parameter(self):
        weeks, _ = sar.select_weeks([row(CA, 2016, 4, cov_v=0.995)], c_min=0.99)
        assert len(weeks) == 1

    def test_missing_O_on_eligible_week_raises_not_zero(self):
        with pytest.raises(ValueError):
            sar.select_weeks([row(CA, 2016, 1, Ov=None)], c_min=1.0)

    def test_zero_detection_week_is_kept_as_zero(self):
        weeks, _ = sar.select_weeks([row(CA, 2016, 1, Da=0, Dv=0)], c_min=1.0)
        assert weeks[0].D[("own_support", "aqua")] == 0
        assert weeks[0].O[("own_support", "aqua")] == 1000

    def test_non_integer_count_rejected(self):
        r = row(CA, 2016, 1)
        r["D_aqua"] = 1.5
        with pytest.raises(ValueError):
            sar.select_weeks([r], c_min=1.0)

    def test_duplicate_week_rejected(self):
        with pytest.raises(ValueError):
            sar.select_weeks([row(CA, 2016, 1), row(CA, 2016, 1)], c_min=1.0)


# ---------------------------------------------------------------------------
# Factor fitting
# ---------------------------------------------------------------------------
class TestFactors:
    def test_full_and_leave_one_year_out_hand_values(self):
        s = sar.run_stage_a(_rows_for(CA), min_support_O={CA: 1})
        v = s["regions"][str(CA)]["policies"]["own_support"]["variants"]
        # 2016-2018: sumDa=76, sumOa=15000; sumDv=34, sumOv=15000 -> 76/34
        assert v[FULL]["factor"] == pytest.approx(76 / 34)
        assert v[FULL]["factor"] == pytest.approx(_hand_factor((2016, 2017, 2018)))
        assert v["ex_2016"]["factor"] == pytest.approx((44 / 10000) / (22 / 10000))
        assert v["ex_2017"]["factor"] == pytest.approx((50 / 10000) / (21 / 10000))
        assert v["ex_2018"]["factor"] == pytest.approx((58 / 10000) / (25 / 10000))

    def test_sums_before_division_differs_from_mean_of_weekly_ratios(self):
        s = sar.run_stage_a(_rows_for(CA), min_support_O={CA: 1})
        a = s["regions"][str(CA)]["policies"]["own_support"]["variants"][FULL]["factor"]
        ratios = [(w[0] / w[1]) / (w[2] / w[3]) for y in TRAIN for w in TRAIN[y]]
        assert not math.isclose(a, sum(ratios) / len(ratios), rel_tol=1e-6)

    def test_regions_fitted_separately(self):
        bc_data = {y: [(2 * Da, Oa, Dv, Ov) for Da, Oa, Dv, Ov in wks]
                   for y, wks in TRAIN.items()}
        s = sar.run_stage_a(_rows_for(CA) + _rows_for(BC, bc_data),
                            min_support_O={CA: 1, BC: 1})
        ca = s["regions"][str(CA)]["policies"]["own_support"]["variants"][FULL]["factor"]
        bc = s["regions"][str(BC)]["policies"]["own_support"]["variants"][FULL]["factor"]
        assert ca == pytest.approx(76 / 34)
        assert bc == pytest.approx(152 / 34)
        assert s["selection"]["union_factor_fitted"] is False

    def test_min_support_defaults_to_n_fp_and_fails_closed(self):
        # Drop 2016 week 2: 2016 O = 1000 < N_fp = 2000, other years O = 5000.
        # Every variant containing 2016 is unavailable; ex_2016 survives.
        data = {**TRAIN, 2016: TRAIN[2016][:1]}
        rows = [dict(r, N_fp=2000) for r in _rows_for(CA, data)]
        s = sar.run_stage_a(rows)
        reg = s["regions"][str(CA)]
        assert reg["min_support_O"] == 2000
        v = reg["policies"]["own_support"]["variants"]
        assert v[FULL]["status"] == "unavailable" and v[FULL]["factor"] is None
        assert v["ex_2017"]["status"] == "unavailable"
        assert v["ex_2016"]["status"] == "available"
        assert reg["policies"]["own_support"]["variant_envelope"] is None

    def test_zero_viirs_rate_is_unavailable_not_zero_or_one(self):
        data = {y: [(Da, Oa, 0, Ov) for Da, Oa, _, Ov in wks] for y, wks in TRAIN.items()}
        s = sar.run_stage_a(_rows_for(CA, data), min_support_O={CA: 1})
        v = s["regions"][str(CA)]["policies"]["own_support"]["variants"]
        assert all(x["status"] == "unavailable" and x["factor"] is None for x in v.values())

    def test_missing_training_year_makes_variants_unavailable(self):
        data = {2016: TRAIN[2016], 2017: TRAIN[2017]}
        s = sar.run_stage_a(_rows_for(CA, data), min_support_O={CA: 1})
        v = s["regions"][str(CA)]["policies"]["own_support"]["variants"]
        assert v[FULL]["status"] == "unavailable"
        assert v["ex_2018"]["status"] == "available"
        assert v["ex_2016"]["status"] == "unavailable"

    def test_common_support_unavailable_without_attestation(self):
        s = sar.run_stage_a(_rows_for(CA), min_support_O={CA: 1})
        v = s["regions"][str(CA)]["policies"]["common_support"]["variants"]
        assert all(x["status"] == "unavailable" for x in v.values())
        assert s["selection"]["common_pairing_attested"] is False

    def test_common_support_uses_common_columns_when_attested(self):
        rows = _rows_for(CA)
        for r in rows:
            r["D_aqua_common"], r["D_viirs_common"], r["O_common"] = 3.0, 2.0, 500.0
        s = sar.run_stage_a(rows, min_support_O={CA: 1}, attest_common_pairing=True)
        pol = s["regions"][str(CA)]["policies"]
        assert pol["common_support"]["variants"][FULL]["factor"] == pytest.approx(1.5)
        assert pol["own_support"]["variants"][FULL]["factor"] == pytest.approx(76 / 34)


# ---------------------------------------------------------------------------
# Development and applicability
# ---------------------------------------------------------------------------
class TestDevAndApplicability:
    def _rows(self):
        dev = [row(CA, 2019, 1, Da=12, Oa=2000, Dv=4, Ov=2000),
               row(CA, 2019, 2, Da=0, Oa=2000, Dv=2, Ov=2000)]
        app = [row(CA, 2022, 1, Da=9, Oa=1000, Dv=3, Ov=1000)]
        return _rows_for(CA) + dev + app

    def test_dev_errors_hand_values(self):
        s = sar.run_stage_a(self._rows(), min_support_O={CA: 1})
        d = s["regions"][str(CA)]["policies"]["own_support"]["development_2019"]
        A, V = 1000 * 12 / 4000, 1000 * 6 / 4000  # 3.0, 1.5
        assert d["aqua"]["rate"] == pytest.approx(A)
        assert d["viirs"]["rate"] == pytest.approx(V)
        a = 76 / 34
        assert d["by_variant"][FULL]["pooled_error"] == pytest.approx(a * V - A)
        assert d["by_variant"]["raw"]["pooled_error"] == pytest.approx(V - A)
        # weekly rates: (6, 2) and (0, 1)
        assert d["by_variant"][FULL]["weekly_mae"] == pytest.approx(
            (abs(a * 2 - 6) + abs(a * 1 - 0)) / 2)
        assert d["n_weeks"] == 2

    def test_applicability_never_passes_without_registered_criterion(self):
        s = sar.run_stage_a(self._rows(), min_support_O={CA: 1})
        app = s["regions"][str(CA)]["policies"]["own_support"]["applicability"]
        y22 = app["2022"]
        assert y22["applicability_status"] == "insufficient_evidence"
        assert y22["applicability_passed"] is None
        assert y22["observed_ratio_A_over_V"] == pytest.approx(3.0)
        # envelope: min/max of the full and leave-one-year-out hand values
        env = [min(_hand_factor(ys) for ys in ((2016, 2017, 2018), (2017, 2018),
                                                (2016, 2018), (2016, 2017))),
               max(_hand_factor(ys) for ys in ((2016, 2017, 2018), (2017, 2018),
                                                (2016, 2018), (2016, 2017)))]
        assert y22["variant_envelope"] == pytest.approx(env)
        assert y22["descriptive_ratio_inside_variant_envelope"] is False

    def test_applicability_year_without_weeks_is_missing_support(self):
        s = sar.run_stage_a(self._rows(), min_support_O={CA: 1})
        y23 = s["regions"][str(CA)]["policies"]["own_support"]["applicability"]["2023"]
        assert y23["applicability_status"] == "missing_required_support"
        assert y23["aqua"]["rate"] is None and y23["n_weeks"] == 0
        assert y23["applicability_passed"] is None


# ---------------------------------------------------------------------------
# Composition counterexample (plan Section 4B)
# ---------------------------------------------------------------------------
class TestComposition:
    def test_counterexample_values(self):
        c = sar.composition_counterexample()
        # 1000*(80+2)/10000 = 8.2 ; 1000*(20+8)/10000 = 2.8
        assert c["observed"] == pytest.approx([8.2, 2.8])
        assert c["observed_pct_change"] == pytest.approx(-65.85, abs=0.005)
        assert c["fixed_weight_0.5_0.5"] == pytest.approx([5.5, 5.5])
        assert c["identity_holds"] is True
        assert c["missing_block_result"] is None and c["missing_block_reasons"]
        assert c["zero_support_result"] is None and c["zero_support_reasons"]

    def test_weighted_sum_identity_on_unequal_blocks(self):
        blocks = [sar.Block("a", 7, 3000), sar.Block("b", 1, 500), sar.Block("c", 0, 1500)]
        # 1000*8/5000 = 1.6 ; shares .6/.1/.3 * rates 7/3, 2, 0
        assert sar.observed_pooled_rate(blocks) == pytest.approx(1.6)
        assert sar.o_share_weighted_rate(blocks) == pytest.approx(0.6 * 7 / 3 + 0.1 * 2)

    def test_no_silent_renormalization(self):
        q = {"a": 0.25, "b": 0.75}
        val, reasons = sar.fixed_weight_rate([sar.Block("a", 1, 100)], q)
        assert val is None and "missing" in reasons[0]

    def test_invalid_weights_raise(self):
        with pytest.raises(ValueError):
            sar.fixed_weight_rate([sar.Block("a", 1, 1)], {"a": 0.9})
        with pytest.raises(ValueError):
            sar.fixed_weight_rate([sar.Block("a", 1, 1)], {"a": 1.5, "b": -0.5})

    def test_no_support_is_none_not_zero(self):
        assert sar.observed_pooled_rate([sar.Block("a", 0, 0)]) is None
        assert sar.o_share_weighted_rate([]) is None

    def test_real_identity_check_on_synthetic_two_region_rows(self):
        s = sar.run_stage_a(_rows_for(CA) + _rows_for(BC), min_support_O={CA: 1, BC: 1})
        ident = s["composition_identity_real_own_support"]
        assert ident["aqua_2016"]["identity_holds"] is True
        assert ident["aqua_2016"]["o_shares"] == pytest.approx({str(BC): 0.5, str(CA): 0.5})
        # 2016 sums: two regions x (D 32, O 5000)
        assert ident["aqua_2016"]["blocks_sum_D"] == 64
        assert ident["aqua_2016"]["blocks_sum_O"] == 10000
        assert ident["viirs_2019"]["identity_holds"] is None  # no 2019 weeks: unavailable


# ---------------------------------------------------------------------------
# Summary output
# ---------------------------------------------------------------------------
class TestSummary:
    def test_summary_is_deterministic_json_without_row_data(self, tmp_path):
        rows = _rows_for(CA) + _rows_for(BC)
        s1 = sar.run_stage_a(rows, min_support_O={CA: 1, BC: 1})
        s2 = sar.run_stage_a(list(reversed(rows)), min_support_O={CA: 1, BC: 1})
        p1, p2 = tmp_path / "a.json", tmp_path / "b.json"
        sar.write_summary(s1, p1)
        sar.write_summary(s2, p2)
        assert p1.read_text() == p2.read_text()
        text = p1.read_text()
        assert "week_start" not in text  # no row-level records
        loaded = json.loads(text)
        assert loaded["splits"]["sealed_not_read"] == [2020, 2021]
        assert loaded["status_dimensions"]["inference_status"] == "not_established"
        assert 2020 not in loaded["iso_years_in_eligible_weeks"]
        assert loaded["selection"]["min_support_O_registered"] is False
        assert loaded["selection"]["c_min_registered"] is False

    def test_committed_frozen_summary_if_present_is_consistent(self):
        path = sar.DEFAULT_OUT
        if not path.is_file():
            pytest.skip("frozen summary not generated")
        s = json.loads(path.read_text(encoding="utf-8"))
        assert s["splits"]["sealed_not_read"] == [2020, 2021]
        assert not set(s["iso_years_in_eligible_weeks"]) & {2020, 2021}
        fx = s["composition_fixture_section_4b"]
        assert fx["observed"] == pytest.approx([8.2, 2.8])
        assert fx["fixed_weight_0.5_0.5"] == pytest.approx([5.5, 5.5])
        for reg in s["regions"].values():
            for pol in reg["policies"].values():
                for vr in pol["variants"].values():
                    assert (vr["status"] == FactorStatus.AVAILABLE.value) == (vr["factor"] is not None)
                    if vr["factor"] is not None:
                        assert vr["factor"] > 0
                for yr in pol["applicability"].values():
                    assert yr["applicability_passed"] is None
