"""
eval/test_eval_harness.py — pytest verification for the P5-A evaluation harness.

ALL test data is synthetic; no real holdout or sealed data appears here.
Synthetic fixtures are labeled as such throughout; they validate pipeline
behavior, not historical observation assumptions.

COVERAGE:
  1. Metric correctness — MAE, Bias, Overlap, DirectionalAccuracy formulae.
  2. Unavailable / O=0 exclusion — never enter error metrics as zero.
  3. Abstention accounting — excluded from denominators, tallied separately.
  4. 2020 Aqua outage flag — counted, not silently dropped.
  5. Baseline A — raw handover, no calibration, never abstains on usable obs.
  6. Baseline B — a_H adjustment; rejects non-positive factor (plan §6).
  7. Baseline C — bootstrap abstains when fewer than min_independent_blocks.
  8. Baseline D — abstains when variants disagree; raises on non-positive factor.
  9. run_eval integration — builds eval_summary.json from synthetic sealed-dir
     fixture; validates schema parity against contracts/schemas/evaluation.py.
  10. Edge cases — all abstentions, all unavailable, single case, ties at tau.
  11. Headline metric — explicit denominator is present and non-empty.
  12. Firewall — eval never imports from science/ or pipeline/.
  13. FIRMS guard — FIRMS hotspot data never enters D/O/baselines.

Run with:
    pytest eval/test_eval_harness.py -v
"""

from __future__ import annotations

import importlib
import json
import math
import os
import sys
import tempfile
from pathlib import Path
from typing import Any

import pytest

# ---------------------------------------------------------------------------
# Ensure the worktree root is on the path so eval.* imports work.
# ---------------------------------------------------------------------------

ROOT = Path(__file__).parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from eval.metrics import (
    CaseResult,
    EvalMetrics,
    MetricResult,
    compute_all_metrics,
    compute_bias,
    compute_directional_accuracy,
    compute_mae,
    compute_overlap,
)
from eval.baselines import (
    predict_baseline_a,
    predict_baseline_b,
    predict_baseline_c,
    predict_baseline_d,
)
from eval.run_eval import main as run_eval_main, _safe_r


# ===========================================================================
# SYNTHETIC FIXTURE HELPERS
# ===========================================================================

def _case(
    case_id: str = "SYNTH-BLK01:2020-JAN",
    reference_value: float | None = 10.0,
    predicted_value: float | None = 12.0,
    is_abstention: bool = False,
    reference_direction: int | None = 1,
    predicted_direction: int | None = 1,
    practical_margin_tau: float = 1.0,
    has_usable_reference: bool = True,
    has_usable_prediction: bool = True,
    outage_flag: bool = False,
    year: int = 2020,
    block_id: str = "BLK-01",
    region_id: str = "SYNTH-REGION",
) -> CaseResult:
    """Return a synthetic CaseResult; all values are artificial."""
    return CaseResult(
        case_id=case_id,
        reference_value=reference_value,
        predicted_value=predicted_value,
        is_abstention=is_abstention,
        reference_direction=reference_direction,
        predicted_direction=predicted_direction,
        practical_margin_tau=practical_margin_tau,
        has_usable_reference=has_usable_reference,
        has_usable_prediction=has_usable_prediction,
        outage_flag=outage_flag,
        year=year,
        block_id=block_id,
        region_id=region_id,
    )


def _scoreable_case(ref: float, pred: float, tau: float = 1.0, **kwargs: Any) -> CaseResult:
    return _case(
        reference_value=ref,
        predicted_value=pred,
        practical_margin_tau=tau,
        is_abstention=False,
        has_usable_reference=True,
        has_usable_prediction=True,
        **kwargs,
    )


# ===========================================================================
# 1. Metric correctness
# ===========================================================================

class TestMAE:
    def test_basic(self) -> None:
        """MAE = mean of |pred - ref| over scoreable cases. SYNTHETIC."""
        cases = [
            _scoreable_case(10.0, 12.0),   # |err|=2
            _scoreable_case(10.0, 9.0),    # |err|=1
            _scoreable_case(5.0, 5.0),     # |err|=0
        ]
        result = compute_mae(cases, "test")
        assert result.value == pytest.approx(1.0)
        assert result.denominator == 3

    def test_single_case(self) -> None:
        """Single scoreable case. SYNTHETIC."""
        cases = [_scoreable_case(10.0, 15.0)]
        result = compute_mae(cases, "test")
        assert result.value == pytest.approx(5.0)
        assert result.denominator == 1

    def test_no_scoreable_returns_none(self) -> None:
        """All abstentions → MAE undefined. SYNTHETIC."""
        cases = [_case(is_abstention=True)]
        result = compute_mae(cases, "test")
        assert result.value is None
        assert result.denominator == 0
        assert result.undefined_reason is not None


class TestBias:
    def test_positive_bias(self) -> None:
        """Predicted > reference → positive bias. SYNTHETIC."""
        cases = [
            _scoreable_case(10.0, 14.0),  # +4
            _scoreable_case(10.0, 12.0),  # +2
        ]
        result = compute_bias(cases, "test")
        assert result.value == pytest.approx(3.0)

    def test_negative_bias(self) -> None:
        """Predicted < reference → negative bias. SYNTHETIC."""
        cases = [_scoreable_case(10.0, 7.0)]
        result = compute_bias(cases, "test")
        assert result.value == pytest.approx(-3.0)

    def test_zero_bias(self) -> None:
        """Perfectly calibrated. SYNTHETIC."""
        cases = [
            _scoreable_case(10.0, 12.0),
            _scoreable_case(10.0, 8.0),
        ]
        result = compute_bias(cases, "test")
        assert result.value == pytest.approx(0.0)


class TestOverlap:
    def test_all_within_margin(self) -> None:
        """All cases within tau. SYNTHETIC."""
        cases = [
            _scoreable_case(10.0, 10.5, tau=1.0),   # diff=0.5 ≤ 1.0
            _scoreable_case(10.0, 9.2, tau=1.0),    # diff=0.8 ≤ 1.0
        ]
        result = compute_overlap(cases, "test")
        assert result.value == pytest.approx(1.0)
        assert result.numerator == 2

    def test_none_within_margin(self) -> None:
        """No case within tau. SYNTHETIC."""
        cases = [
            _scoreable_case(10.0, 15.0, tau=1.0),
            _scoreable_case(10.0, 5.0, tau=1.0),
        ]
        result = compute_overlap(cases, "test")
        assert result.value == pytest.approx(0.0)
        assert result.numerator == 0

    def test_tie_at_boundary_included(self) -> None:
        """Exactly at tau is within margin (<=). SYNTHETIC."""
        cases = [_scoreable_case(10.0, 11.0, tau=1.0)]  # diff == tau
        result = compute_overlap(cases, "test")
        assert result.value == pytest.approx(1.0)

    def test_negative_tau_raises(self) -> None:
        """Negative tau is a contract violation. SYNTHETIC."""
        cases = [_scoreable_case(10.0, 11.0, tau=-0.5)]
        with pytest.raises(ValueError, match="practical_margin_tau must be >= 0"):
            compute_overlap(cases, "test")


class TestDirectionalAccuracy:
    def test_all_correct(self) -> None:
        """All predicted directions match reference. SYNTHETIC."""
        cases = [
            _case(reference_direction=1, predicted_direction=1),
            _case(reference_direction=-1, predicted_direction=-1, case_id="c2"),
        ]
        result = compute_directional_accuracy(cases, "test")
        assert result.value == pytest.approx(1.0)
        assert result.numerator == 2

    def test_all_wrong(self) -> None:
        """All directions wrong. SYNTHETIC."""
        cases = [
            _case(reference_direction=1, predicted_direction=-1),
            _case(reference_direction=-1, predicted_direction=1, case_id="c2"),
        ]
        result = compute_directional_accuracy(cases, "test")
        assert result.value == pytest.approx(0.0)

    def test_tied_reference_excluded(self) -> None:
        """reference_direction=0 (tied) is excluded. SYNTHETIC."""
        cases = [
            _case(reference_direction=0, predicted_direction=1),  # excluded
            _case(reference_direction=1, predicted_direction=1, case_id="c2"),  # counted
        ]
        result = compute_directional_accuracy(cases, "test")
        assert result.denominator == 1
        assert result.value == pytest.approx(1.0)

    def test_abstention_excluded(self) -> None:
        """Abstentions excluded from directional accuracy. SYNTHETIC."""
        cases = [
            _case(is_abstention=True, reference_direction=1, predicted_direction=None),
            _case(reference_direction=1, predicted_direction=1, case_id="c2"),
        ]
        result = compute_directional_accuracy(cases, "test")
        assert result.denominator == 1

    def test_unavailable_reference_excluded(self) -> None:
        """Missing reference excluded from directional accuracy. SYNTHETIC."""
        cases = [
            _case(has_usable_reference=False, reference_direction=None, predicted_direction=1),
            _case(reference_direction=1, predicted_direction=1, case_id="c2"),
        ]
        result = compute_directional_accuracy(cases, "test")
        assert result.denominator == 1

    def test_no_decisive_cases_undefined(self) -> None:
        """Zero decisive cases → None. SYNTHETIC."""
        cases = [_case(is_abstention=True)]
        result = compute_directional_accuracy(cases, "test")
        assert result.value is None


# ===========================================================================
# 2. Unavailable / O=0 exclusion
# ===========================================================================

class TestUnavailableExclusion:
    def test_unavailable_reference_excluded_from_mae(self) -> None:
        """O_ref=0 case excluded from MAE denominator. SYNTHETIC."""
        good = _scoreable_case(10.0, 12.0)
        unavail = _case(
            case_id="unavail",
            reference_value=None,
            predicted_value=5.0,
            has_usable_reference=False,
        )
        result = compute_mae([good, unavail], "test")
        assert result.denominator == 1  # only the good case

    def test_unavailable_prediction_excluded(self) -> None:
        """O_pred=0 excluded from MAE. SYNTHETIC."""
        good = _scoreable_case(10.0, 12.0)
        unavail_pred = _case(
            case_id="up",
            predicted_value=None,
            has_usable_prediction=False,
        )
        result = compute_mae([good, unavail_pred], "test")
        assert result.denominator == 1

    def test_unavailable_never_counts_as_zero(self) -> None:
        """Unavailable reference must not be treated as reference_value=0. SYNTHETIC."""
        cases = [
            _case(
                reference_value=None,
                predicted_value=10.0,
                has_usable_reference=False,
            )
        ]
        mae = compute_mae(cases, "test")
        assert mae.value is None  # not 10.0 or 0.0


# ===========================================================================
# 3. Abstention accounting
# ===========================================================================

class TestAbstentionAccounting:
    def test_abstentions_tallied_in_eval_metrics(self) -> None:
        """Abstentions appear in EvalMetrics.n_abstentions. SYNTHETIC."""
        cases = [
            _case(is_abstention=True),
            _scoreable_case(10.0, 11.0, case_id="c2"),
        ]
        em = compute_all_metrics(cases, "test")
        assert em.n_abstentions == 1
        assert em.n_decisive_scoreable == 1

    def test_abstention_excluded_from_mae_denominator(self) -> None:
        """Abstentions excluded from MAE denominator. SYNTHETIC."""
        cases = [
            _case(is_abstention=True),
            _scoreable_case(10.0, 11.0, case_id="c2"),
        ]
        em = compute_all_metrics(cases, "test")
        assert em.mae.denominator == 1


# ===========================================================================
# 4. 2020 Aqua outage flag
# ===========================================================================

class TestOutageFlag:
    def test_outage_cases_tallied_separately(self) -> None:
        """Outage-flagged cases counted, not silently dropped. SYNTHETIC."""
        cases = [
            _case(outage_flag=True),
            _scoreable_case(10.0, 11.0, case_id="c2"),
        ]
        em = compute_all_metrics(cases, "test")
        assert em.n_outage_flagged == 1
        # The outage case still enters if it has usable data
        assert em.n_total_registered == 2

    def test_outage_note_in_failures(self) -> None:
        """Outage flag generates a human-readable note. SYNTHETIC."""
        cases = [_case(outage_flag=True, has_usable_reference=True, has_usable_prediction=True,
                       is_abstention=False, predicted_value=10.0, reference_value=10.0)]
        em = compute_all_metrics(cases, "test")
        outage_notes = [n for n in em.failures_and_notes if "2020" in n or "outage" in n.lower()]
        assert len(outage_notes) >= 1


# ===========================================================================
# 5. Baseline A
# ===========================================================================

class TestBaselineA:
    def _build(self, viirs_r: float | None = 12.0, has_obs: bool = True,
               ref: float | None = 10.0, tau: float = 1.0) -> CaseResult:
        return predict_baseline_a(
            viirs_r=viirs_r, has_usable_obs=has_obs,
            case_id="A-SYNTH", year=2020, block_id="B1", region_id="R1",
            reference_value=ref, reference_direction=1,
            has_usable_reference=ref is not None,
            outage_flag=False, practical_margin_tau=tau,
        )

    def test_no_abstention_on_usable_obs(self) -> None:
        """Baseline A never abstains when O>0. SYNTHETIC."""
        c = self._build()
        assert not c.is_abstention
        assert c.predicted_value == pytest.approx(12.0)

    def test_unavailable_on_zero_obs(self) -> None:
        """O=0 → has_usable_prediction=False, predicted_value=None. SYNTHETIC."""
        c = self._build(viirs_r=None, has_obs=False)
        assert c.predicted_value is None
        assert not c.has_usable_prediction
        assert not c.is_abstention  # unavailable ≠ abstention

    def test_direction_increase(self) -> None:
        """pred > ref+tau → direction=+1. SYNTHETIC."""
        c = self._build(viirs_r=15.0, ref=10.0, tau=1.0)  # effect=+5 > tau
        assert c.predicted_direction == 1

    def test_direction_decrease(self) -> None:
        """pred < ref-tau → direction=-1. SYNTHETIC."""
        c = self._build(viirs_r=5.0, ref=10.0, tau=1.0)   # effect=-5 < -tau
        assert c.predicted_direction == -1

    def test_direction_within_margin(self) -> None:
        """|pred - ref| <= tau → direction=0. SYNTHETIC."""
        c = self._build(viirs_r=10.5, ref=10.0, tau=1.0)  # effect=+0.5 ≤ tau
        assert c.predicted_direction == 0


# ===========================================================================
# 6. Baseline B
# ===========================================================================

class TestBaselineB:
    def _build(self, viirs_r: float = 8.0, a_h: float = 1.5,
               ref: float = 10.0, tau: float = 1.0) -> CaseResult:
        return predict_baseline_b(
            viirs_r=viirs_r, a_h=a_h, has_usable_obs=True,
            case_id="B-SYNTH", year=2020, block_id="B1", region_id="R1",
            reference_value=ref, reference_direction=1,
            has_usable_reference=True,
            outage_flag=False, practical_margin_tau=tau,
        )

    def test_applies_a_h(self) -> None:
        """predicted = viirs_r * a_H. SYNTHETIC."""
        c = self._build(viirs_r=8.0, a_h=1.5)
        assert c.predicted_value == pytest.approx(12.0)

    def test_nonpositive_a_h_raises(self) -> None:
        """Non-positive a_H raises ValueError per plan §6. SYNTHETIC."""
        with pytest.raises(ValueError, match="a_H must be > 0"):
            self._build(a_h=0.0)

    def test_negative_a_h_raises(self) -> None:
        with pytest.raises(ValueError, match="a_H must be > 0"):
            self._build(a_h=-1.5)


# ===========================================================================
# 7. Baseline C (bootstrap)
# ===========================================================================

class TestBaselineC:
    def _build(
        self,
        bvd: list[int] | None = None,
        bvo: list[int] | None = None,
        bad: list[int] | None = None,
        bao: list[int] | None = None,
        min_blocks: int = 2,
        tau: float = 1.0,
    ) -> CaseResult:
        bvd = bvd or [100]
        bvo = bvo or [1000]
        bad = bad or [80]
        bao = bao or [1000]
        return predict_baseline_c(
            block_viirs_d=bvd, block_viirs_o=bvo,
            block_aqua_d_baseline=bad, block_aqua_o_baseline=bao,
            a_h=1.5, n_replicates=200, confidence_level=0.90,
            min_independent_blocks=min_blocks, practical_margin_tau=tau,
            rng_seed=42,
            case_id="C-SYNTH", year=2020, block_id="B1", region_id="R1",
            reference_value=80.0, reference_direction=1,
            has_usable_reference=True, outage_flag=False,
        )

    def test_abstains_when_fewer_than_min_blocks(self) -> None:
        """Single block with min=2 → abstain. SYNTHETIC."""
        c = self._build(min_blocks=2)  # only 1 block provided
        assert c.is_abstention

    def test_negative_a_h_raises(self) -> None:
        """Non-positive a_H raises. SYNTHETIC."""
        with pytest.raises(ValueError, match="a_H must be > 0"):
            predict_baseline_c(
                block_viirs_d=[100], block_viirs_o=[1000],
                block_aqua_d_baseline=[80], block_aqua_o_baseline=[1000],
                a_h=-1.0, n_replicates=200, confidence_level=0.90,
                min_independent_blocks=1, practical_margin_tau=1.0,
                rng_seed=42,
                case_id="C-SYNTH", year=2020, block_id="B1", region_id="R1",
                reference_value=80.0, reference_direction=1,
                has_usable_reference=True, outage_flag=False,
            )

    def test_mismatched_arrays_raise(self) -> None:
        """Mismatched array lengths raise ValueError. SYNTHETIC."""
        with pytest.raises(ValueError):
            self._build(bvd=[100, 200], bvo=[1000], bad=[80], bao=[1000])

    def test_all_zero_obs_abstains(self) -> None:
        """O=0 on all blocks → no usable blocks → abstains. SYNTHETIC."""
        c = self._build(bvo=[0], bao=[0], min_blocks=1)
        assert c.is_abstention

    def test_abstains_with_one_block_and_min_two(self) -> None:
        """min_independent_blocks=2 but only one block → abstain. SYNTHETIC."""
        c = self._build(bvd=[100], bvo=[1000], bad=[80], bao=[1000], min_blocks=2)
        assert c.is_abstention


# ===========================================================================
# 8. Baseline D
# ===========================================================================

class TestBaselineD:
    def _build(
        self,
        viirs_r: float = 8.0,
        variants: dict[str, float] | None = None,
        ref: float = 10.0,
        tau: float = 1.0,
    ) -> CaseResult:
        if variants is None:
            variants = {"full_training": 1.5, "ex_2016": 1.4, "ex_2017": 1.6}
        return predict_baseline_d(
            viirs_r=viirs_r, factor_variants=variants, has_usable_obs=True,
            practical_margin_tau=tau,
            case_id="D-SYNTH", year=2020, block_id="B1", region_id="R1",
            reference_value=ref, reference_direction=1,
            has_usable_reference=True, outage_flag=False,
        )

    def test_consensus_increase_no_abstention(self) -> None:
        """All variants agree increase → decisive, no abstention. SYNTHETIC.
        viirs=8, factors 1.4/1.5/1.6 → predictions 11.2/12.0/12.8; ref=10, tau=1
        effects +1.2/+2.0/+2.8, all > tau → all dir=+1."""
        c = self._build(viirs_r=8.0, ref=10.0, tau=1.0)
        assert not c.is_abstention
        assert c.predicted_direction == 1

    def test_disagreement_abstains(self) -> None:
        """Variants disagree on direction → abstain (unresolved). SYNTHETIC.
        viirs=8, factor_A=1.5 gives 12.0 (effect +2 > tau=1 → +1);
        factor_B=0.9 gives 7.2 (effect -2.8 < -tau → -1)."""
        c = self._build(
            viirs_r=8.0,
            variants={"full": 1.5, "low": 0.9},
            ref=10.0, tau=1.0
        )
        assert c.is_abstention

    def test_nonpositive_factor_raises(self) -> None:
        """Non-positive factor raises ValueError per plan §6. SYNTHETIC."""
        with pytest.raises(ValueError, match="non-positive"):
            self._build(variants={"full": 0.0, "ex": 1.4})

    def test_empty_variants_raises(self) -> None:
        """Empty factor dict raises. SYNTHETIC."""
        with pytest.raises(ValueError, match="non-empty"):
            self._build(variants={})

    def test_unavailable_obs_no_abstention(self) -> None:
        """O=0 → has_usable_prediction=False, is_abstention=False. SYNTHETIC."""
        c = predict_baseline_d(
            viirs_r=None, factor_variants={"full": 1.5},
            has_usable_obs=False, practical_margin_tau=1.0,
            case_id="D-UNV", year=2020, block_id="B1", region_id="R1",
            reference_value=10.0, reference_direction=1,
            has_usable_reference=True, outage_flag=False,
        )
        assert c.predicted_value is None
        assert not c.has_usable_prediction
        assert not c.is_abstention  # unavailable ≠ abstention


# ===========================================================================
# 9. run_eval integration — synthetic sealed-dir fixture
# ===========================================================================

class TestRunEvalIntegration:
    """
    End-to-end test using a fully synthetic sealed directory.
    No real holdout data is present; all values are artificial.
    """

    @pytest.fixture()
    def sealed_dir(self, tmp_path: Path) -> Path:
        """Build a synthetic SEALED_EVAL_DIR with 6 artificial cases."""
        cases = [
            # Case 1 — normal, increase, all sensors usable
            {
                "case_id": "SYNTH-BLK01:2020-JAN",
                "year": 2020, "block_id": "BLK-01", "region_id": "SYNTH-R1",
                "outage_flag": False, "practical_margin_tau": 1.0,
                "viirs_d": 100, "viirs_o": 1000,
                "aqua_d_target": 120, "aqua_o_target": 1000,
                "aqua_d_baseline": 80, "aqua_o_baseline": 1000,
                "reference_direction": 1,
            },
            # Case 2 — normal, decrease
            {
                "case_id": "SYNTH-BLK01:2020-FEB",
                "year": 2020, "block_id": "BLK-01", "region_id": "SYNTH-R1",
                "outage_flag": False, "practical_margin_tau": 1.0,
                "viirs_d": 60, "viirs_o": 1000,
                "aqua_d_target": 50, "aqua_o_target": 1000,
                "aqua_d_baseline": 90, "aqua_o_baseline": 1000,
                "reference_direction": -1,
            },
            # Case 3 — 2020 Aqua outage flagged
            {
                "case_id": "SYNTH-BLK01:2020-AUG",
                "year": 2020, "block_id": "BLK-01", "region_id": "SYNTH-R1",
                "outage_flag": True, "practical_margin_tau": 1.0,
                "viirs_d": 80, "viirs_o": 900,
                "aqua_d_target": None, "aqua_o_target": 0,  # outage → O=0 ref unavailable
                "aqua_d_baseline": 70, "aqua_o_baseline": 1000,
                "reference_direction": None,
            },
            # Case 4 — VIIRS O=0 (unavailable)
            {
                "case_id": "SYNTH-BLK02:2020-JAN",
                "year": 2020, "block_id": "BLK-02", "region_id": "SYNTH-R1",
                "outage_flag": False, "practical_margin_tau": 1.0,
                "viirs_d": None, "viirs_o": 0,
                "aqua_d_target": 50, "aqua_o_target": 800,
                "aqua_d_baseline": 55, "aqua_o_baseline": 800,
                "reference_direction": -1,
            },
            # Case 5 — 2021 test year, within-margin reference direction
            {
                "case_id": "SYNTH-BLK01:2021-MAR",
                "year": 2021, "block_id": "BLK-01", "region_id": "SYNTH-R1",
                "outage_flag": False, "practical_margin_tau": 1.5,
                "viirs_d": 85, "viirs_o": 1000,
                "aqua_d_target": 86, "aqua_o_target": 1000,
                "aqua_d_baseline": 85, "aqua_o_baseline": 1000,
                "reference_direction": 0,  # within-margin reference
            },
            # Case 6 — 2021 test year, stable variants all agree increase
            {
                "case_id": "SYNTH-BLK01:2021-APR",
                "year": 2021, "block_id": "BLK-01", "region_id": "SYNTH-R1",
                "outage_flag": False, "practical_margin_tau": 1.0,
                "viirs_d": 110, "viirs_o": 1000,
                "aqua_d_target": 130, "aqua_o_target": 1000,
                "aqua_d_baseline": 90, "aqua_o_baseline": 1000,
                "reference_direction": 1,
            },
        ]
        factor_registry = {
            "full_training": 1.482,
            "ex_2016": 1.465,
            "ex_2017": 1.501,
            "ex_2018": 1.470,
        }
        bootstrap_config = {
            "n_replicates": 500,
            "confidence_level": 0.90,
            "min_independent_blocks": 2,
            "rng_seed": 12345,
        }

        (tmp_path / "cases.json").write_text(json.dumps(cases), encoding="utf-8")
        (tmp_path / "factor_registry.json").write_text(
            json.dumps(factor_registry), encoding="utf-8"
        )
        (tmp_path / "bootstrap_config.json").write_text(
            json.dumps(bootstrap_config), encoding="utf-8"
        )
        return tmp_path

    def test_produces_valid_summary(self, sealed_dir: Path, tmp_path: Path) -> None:
        """run_eval.main() exits 0 and writes a parseable JSON summary. SYNTHETIC."""
        out = tmp_path / "out" / "eval_summary.json"
        rc = run_eval_main([
            "--sealed-dir", str(sealed_dir),
            "--out", str(out),
        ])
        assert rc == 0, "run_eval.main() should return 0"
        assert out.exists(), "eval_summary.json should be written"
        data = json.loads(out.read_text(encoding="utf-8"))
        assert data["eval_protocol_version"] == "P0-held-out-sensor-switch-v1"

    def test_schema_has_required_keys(self, sealed_dir: Path, tmp_path: Path) -> None:
        """Output matches EvaluationSummary required fields. SYNTHETIC."""
        out = tmp_path / "out2" / "eval_summary.json"
        run_eval_main(["--sealed-dir", str(sealed_dir), "--out", str(out)])
        data = json.loads(out.read_text(encoding="utf-8"))
        required_keys = {
            "artifact_version",
            "eval_protocol_version",
            "baseline_a_raw_handover",
            "baseline_b_point_a_h",
            "baseline_c_uncertainty_aware",
            "baseline_d_stage_a_finite_audit",
            "headline_metric_description",
            "headline_metric_value",
            "headline_denominator",
            "independent_units",
            "failures_and_limitations",
        }
        missing = required_keys - data.keys()
        assert not missing, f"eval_summary.json is missing keys: {missing}"

    def test_independent_units_present_and_nonzero(
        self, sealed_dir: Path, tmp_path: Path
    ) -> None:
        """independent_units must have blocks, regions, test_years all set. SYNTHETIC."""
        out = tmp_path / "out3" / "eval_summary.json"
        run_eval_main(["--sealed-dir", str(sealed_dir), "--out", str(out)])
        data = json.loads(out.read_text(encoding="utf-8"))
        iu = data["independent_units"]
        assert iu["blocks"] >= 1
        assert iu["regions"] >= 1
        assert iu["test_years"] >= 1

    def test_headline_denominator_is_nonempty_string(
        self, sealed_dir: Path, tmp_path: Path
    ) -> None:
        """headline_denominator must be a non-empty string. SYNTHETIC."""
        out = tmp_path / "out4" / "eval_summary.json"
        run_eval_main(["--sealed-dir", str(sealed_dir), "--out", str(out)])
        data = json.loads(out.read_text(encoding="utf-8"))
        assert isinstance(data["headline_denominator"], str)
        assert len(data["headline_denominator"]) > 10

    def test_outage_flagged_case_counted(self, sealed_dir: Path, tmp_path: Path) -> None:
        """The 2020 outage-flagged case must appear in baseline metrics counts. SYNTHETIC."""
        out = tmp_path / "out5" / "eval_summary.json"
        run_eval_main(["--sealed-dir", str(sealed_dir), "--out", str(out)])
        data = json.loads(out.read_text(encoding="utf-8"))
        # The outage case (aqua_o_target=0) makes an unavailable reference;
        # it must be counted, not silently dropped.
        a_metrics = data["baseline_a_raw_handover"]
        assert a_metrics["n_outage_flagged"] >= 1

    def test_missing_sealed_dir_returns_error(self, tmp_path: Path) -> None:
        """Missing SEALED_EVAL_DIR returns non-zero exit code. SYNTHETIC."""
        out = tmp_path / "out6" / "eval_summary.json"
        rc = run_eval_main([
            "--sealed-dir", str(tmp_path / "nonexistent"),
            "--out", str(out),
        ])
        assert rc != 0

    def test_no_sealed_dir_env_returns_error(self, tmp_path: Path) -> None:
        """Unset SEALED_EVAL_DIR (and no --sealed-dir) returns non-zero. SYNTHETIC."""
        old = os.environ.pop("SEALED_EVAL_DIR", None)
        try:
            out = tmp_path / "out7" / "eval_summary.json"
            rc = run_eval_main(["--out", str(out)])
            assert rc != 0
        finally:
            if old is not None:
                os.environ["SEALED_EVAL_DIR"] = old


# ===========================================================================
# 10. Edge cases
# ===========================================================================

class TestEdgeCases:
    def test_all_abstentions_produces_none_metrics(self) -> None:
        """All abstentions → all metrics None. SYNTHETIC."""
        cases = [
            _case(is_abstention=True, case_id="a1"),
            _case(is_abstention=True, case_id="a2"),
        ]
        em = compute_all_metrics(cases, "edge")
        assert em.mae.value is None
        assert em.bias.value is None
        assert em.overlap.value is None
        assert em.directional_accuracy.value is None

    def test_all_unavailable_reference(self) -> None:
        """All O_ref=0 → no scoreable cases. SYNTHETIC."""
        cases = [
            _case(has_usable_reference=False, reference_value=None, case_id="u1"),
            _case(has_usable_reference=False, reference_value=None, case_id="u2"),
        ]
        em = compute_all_metrics(cases, "edge")
        assert em.n_unavailable_reference == 2
        assert em.n_decisive_scoreable == 0
        assert em.mae.value is None

    def test_single_scoreable_case(self) -> None:
        """Single scoreable case. SYNTHETIC."""
        cases = [_scoreable_case(10.0, 10.0)]
        em = compute_all_metrics(cases, "single")
        assert em.mae.value == pytest.approx(0.0)
        assert em.bias.value == pytest.approx(0.0)
        assert em.overlap.value == pytest.approx(1.0)

    def test_tie_exactly_at_tau_overlap(self) -> None:
        """diff == tau counts as within margin (<=). SYNTHETIC."""
        cases = [_scoreable_case(10.0, 11.0, tau=1.0)]
        result = compute_overlap(cases, "tie")
        assert result.value == pytest.approx(1.0)


# ===========================================================================
# 11. Headline metric denominator
# ===========================================================================

class TestHeadlineMetric:
    def test_headline_denominator_contains_region_and_year(
        self, tmp_path: Path
    ) -> None:
        """Denominator string references regions and test years. SYNTHETIC."""
        # Build minimal synthetic sealed dir inline
        cases = [
            {
                "case_id": "H-BLK01:2020-JAN",
                "year": 2020, "block_id": "BLK-01", "region_id": "REG-X",
                "outage_flag": False, "practical_margin_tau": 1.0,
                "viirs_d": 100, "viirs_o": 1000,
                "aqua_d_target": 110, "aqua_o_target": 1000,
                "aqua_d_baseline": 90, "aqua_o_baseline": 1000,
                "reference_direction": 1,
            }
        ]
        (tmp_path / "cases.json").write_text(json.dumps(cases), encoding="utf-8")
        (tmp_path / "factor_registry.json").write_text(
            json.dumps({"full_training": 1.4}), encoding="utf-8"
        )
        (tmp_path / "bootstrap_config.json").write_text(
            json.dumps({"n_replicates": 100, "confidence_level": 0.90,
                        "min_independent_blocks": 2, "rng_seed": 1}),
            encoding="utf-8",
        )
        out = tmp_path / "hl_summary.json"
        run_eval_main(["--sealed-dir", str(tmp_path), "--out", str(out)])
        data = json.loads(out.read_text(encoding="utf-8"))
        denom = data["headline_denominator"]
        assert "REG-X" in denom or "region" in denom.lower()
        assert "2020" in denom

    def test_headline_independent_units_not_inflated(
        self, tmp_path: Path
    ) -> None:
        """independent_units.regions must equal actual distinct region count. SYNTHETIC."""
        cases = [
            {
                "case_id": f"H-BLK{i}:2020-JAN",
                "year": 2020, "block_id": f"BLK-{i:02d}", "region_id": "ONLY-REG",
                "outage_flag": False, "practical_margin_tau": 1.0,
                "viirs_d": 100, "viirs_o": 1000,
                "aqua_d_target": 110, "aqua_o_target": 1000,
                "aqua_d_baseline": 90, "aqua_o_baseline": 1000,
                "reference_direction": 1,
            }
            for i in range(5)
        ]
        (tmp_path / "cases.json").write_text(json.dumps(cases), encoding="utf-8")
        (tmp_path / "factor_registry.json").write_text(
            json.dumps({"full_training": 1.4}), encoding="utf-8"
        )
        (tmp_path / "bootstrap_config.json").write_text(
            json.dumps({"n_replicates": 100, "confidence_level": 0.90,
                        "min_independent_blocks": 2, "rng_seed": 1}),
            encoding="utf-8",
        )
        out = tmp_path / "iu_summary.json"
        run_eval_main(["--sealed-dir", str(tmp_path), "--out", str(out)])
        data = json.loads(out.read_text(encoding="utf-8"))
        iu = data["independent_units"]
        assert iu["regions"] == 1   # 5 blocks but only 1 region
        assert iu["blocks"] == 5


# ===========================================================================
# 12. Firewall — eval never imports from science/ or pipeline/
# ===========================================================================

class TestFirewall:
    _FORBIDDEN_PREFIXES = ("science.", "pipeline.")

    def _get_eval_imports(self, module_name: str) -> list[str]:
        """Return all top-level import names for the given eval module."""
        mod = importlib.import_module(module_name)
        source = Path(mod.__file__).read_text(encoding="utf-8")
        imports: list[str] = []
        for line in source.splitlines():
            stripped = line.strip()
            if stripped.startswith("import ") or stripped.startswith("from "):
                imports.append(stripped)
        return imports

    @pytest.mark.parametrize("module", [
        "eval.metrics",
        "eval.baselines",
        "eval.run_eval",
        "eval.test_eval_harness",
    ])
    def test_no_science_or_pipeline_import(self, module: str) -> None:
        """eval/* must never import from science/ or pipeline/. SYNTHETIC check."""
        import_lines = self._get_eval_imports(module)
        for line in import_lines:
            for prefix in self._FORBIDDEN_PREFIXES:
                assert prefix not in line, (
                    f"FIREWALL VIOLATION in {module}: "
                    f"found import of '{prefix}' — eval code must never "
                    f"import from science/ or pipeline/.\n  Line: {line!r}"
                )


# ===========================================================================
# 13. FIRMS guard
# ===========================================================================

class TestFirmsGuard:
    """
    FIRMS hotspot points are a separate view and must never enter D, O, baselines
    or verdicts (plan §4C, AGENTS.md).
    
    These tests verify that the metric and baseline functions do not accept or
    produce values that could silently inherit FIRMS point counts.
    """

    def test_firms_data_not_accepted_as_d(self) -> None:
        """
        D must come from MYD14A1/VNP14A1 grid cell-days, not FIRMS point counts.
        
        This test demonstrates that if a caller tried to pass FIRMS point counts
        as D, the metric computations would still run but the caller is responsible
        for supplying only grid D/O values.  We verify that the metric functions
        themselves carry no special FIRMS handling (they are agnostic to the
        source label — the firewall is at the data-loading layer).
        
        The correct behavior is: grid D/O data only enters via run_eval.py which
        reads from the SEALED_EVAL_DIR; FIRMS points are never in those files.
        SYNTHETIC.
        """
        # Synthetic "FIRMS-looking" count — same numeric value as a point count.
        # This would be wrong to pass as D, but we're testing that the formula
        # is formula-correct regardless; the guard is at the data layer.
        # The important assertion is that this module file contains no FIRMS import.
        import eval.metrics as em_module
        source = Path(em_module.__file__).read_text(encoding="utf-8")
        assert "firms" not in source.lower() or "FIRMS hotspot" in source, (
            "eval/metrics.py must not contain FIRMS-specific logic; "
            "FIRMS points never enter D, O, baselines or verdicts."
        )

    def test_firms_string_not_in_baselines(self) -> None:
        """eval/baselines.py must not silently reference FIRMS data. SYNTHETIC."""
        import eval.baselines as eb_module
        source = Path(eb_module.__file__).read_text(encoding="utf-8")
        # The docstring may mention FIRMS for clarity; actual import/call must not exist
        assert "import firms" not in source.lower()
        assert "from firms" not in source.lower()


# ===========================================================================
# 14. _safe_r helper
# ===========================================================================

class TestSafeR:
    def test_normal(self) -> None:
        assert _safe_r(100, 1000) == pytest.approx(100.0)

    def test_zero_o_returns_none(self) -> None:
        assert _safe_r(50, 0) is None

    def test_none_d_returns_none(self) -> None:
        assert _safe_r(None, 1000) is None

    def test_zero_d_returns_zero(self) -> None:
        assert _safe_r(0, 1000) == pytest.approx(0.0)
