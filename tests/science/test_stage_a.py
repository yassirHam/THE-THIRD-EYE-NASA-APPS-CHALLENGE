"""
Unit tests for science/methods/stage_a.py

ALL expected values are computed by hand from the spec equations.
No outputs are ever copied from the implementation under test.

Scientific authority:
  THE_THIRD_EYE_FINAL_PLAN_GEOGRAPHIC_ACCESS_UPDATED.txt  §4, §6, §7, §8
  contracts/schemas/comparison.py

Key invariants being tested:
  1. O = 0 is MISSING → never yields D = 0 fire, never enters any denominator.
  2. Pooled rate = SCALE * sum(D) / sum(O)  (sums BEFORE division).
  3. a_H = aqua_own_rate / viirs_own_rate   (own-support policy only).
  4. a_C = aqua_common_rate / viirs_common_rate  (common-support policy only).
  5. a_H and a_C are independent; a_C never substitutes for a_H.
  6. Leave-one-year-out re-runs the full calculation on the remaining years.
  7. Zero VIIRS rate → factor UNAVAILABLE (never 0.0 or inf).
  8. Non-positive factor → UNAVAILABLE.
  9. All four status dimensions are independent.
  10. Equality boundary: a_break = B / V  for V > 0.
  11. Policy guard: mixing 'own_support' and 'common_support' records raises.
"""
from __future__ import annotations

import math
import pytest

from science.methods.stage_a import (
    SCALE,
    TRAINING_YEARS_DEFAULT,
    ApplicabilityStatus,
    AppliedComparison,
    Availability,
    FactorStatus,
    HeadlineDirection,
    InferenceStatus,
    ObsRecord,
    PracticalChange,
    SensitivityStatus,
    apply_factor,
    assess_sensitivity,
    fit_common_support_variants,
    fit_own_support_variants,
    _pooled_rate,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _own(sensor: str, year: int, D: int, O: int) -> ObsRecord:
    return ObsRecord(sensor=sensor, year=year, stratum="annual",
                     policy="own_support", D=D, O=O)


def _common(sensor: str, year: int, D: int, O: int) -> ObsRecord:
    return ObsRecord(sensor=sensor, year=year, stratum="annual",
                     policy="common_support", D=D, O=O)


# ---------------------------------------------------------------------------
# 1.  ObsRecord invariants
# ---------------------------------------------------------------------------
class TestObsRecord:
    def test_available_when_O_positive(self):
        r = _own("aqua", 2016, D=10, O=100)
        assert r.is_available is True
        assert r.availability == Availability.AVAILABLE

    def test_unavailable_when_O_is_zero(self):
        r = _own("aqua", 2016, D=0, O=0)
        assert r.is_available is False
        assert r.availability == Availability.UNAVAILABLE

    def test_O_zero_D_zero_is_valid_missing(self):
        """O=0, D=0 is the correct representation of a missing period."""
        r = _own("viirs", 2017, D=0, O=0)
        assert r.O == 0
        assert r.D == 0

    def test_O_zero_D_nonzero_raises(self):
        """An unobserved period cannot have detected fires."""
        with pytest.raises(ValueError, match="O = 0"):
            ObsRecord(sensor="aqua", year=2016, stratum="annual",
                      policy="own_support", D=5, O=0)

    def test_negative_D_raises(self):
        with pytest.raises(ValueError, match="D must be >= 0"):
            _own("aqua", 2016, D=-1, O=100)

    def test_negative_O_raises(self):
        with pytest.raises(ValueError, match="O must be >= 0"):
            _own("aqua", 2016, D=0, O=-1)


# ---------------------------------------------------------------------------
# 2.  _pooled_rate — sums before division
# ---------------------------------------------------------------------------
class TestPooledRate:
    def test_single_record(self):
        # R = 1000 * 50 / 500 = 100.0
        r = _own("aqua", 2016, D=50, O=500)
        assert _pooled_rate([r]) == pytest.approx(100.0)

    def test_two_records_sum_before_divide(self):
        # Aqua 2016: D=10, O=100  (rate 100)
        # Aqua 2017: D=30, O=100  (rate 300)
        # Pooled: 1000 * 40 / 200 = 200.0  (NOT average of 100 and 300 = 200 coincidence)
        # Test a non-uniform case to prove sums-before-division:
        # D=10, O=900 → rate  11.11…
        # D=10, O=100 → rate 100.0
        # Average-of-rates would be (11.11 + 100.0) / 2 = 55.555…
        # Pooled:  1000 * 20 / 1000 = 20.0  ← correct
        r1 = _own("aqua", 2016, D=10, O=900)
        r2 = _own("aqua", 2017, D=10, O=100)
        result = _pooled_rate([r1, r2])
        assert result == pytest.approx(20.0), (
            "Must sum D and O before dividing, not average individual rates"
        )

    def test_all_unavailable_returns_none(self):
        """O=0 records must never enter the denominator."""
        r1 = _own("aqua", 2016, D=0, O=0)
        r2 = _own("aqua", 2017, D=0, O=0)
        assert _pooled_rate([r1, r2]) is None

    def test_mixed_available_and_unavailable(self):
        # Only the available record (D=20, O=200) enters the sum.
        # Rate = 1000 * 20 / 200 = 100.0
        avail = _own("aqua", 2016, D=20, O=200)
        missing = _own("aqua", 2017, D=0, O=0)
        assert _pooled_rate([avail, missing]) == pytest.approx(100.0)

    def test_empty_iterable_returns_none(self):
        assert _pooled_rate([]) is None

    def test_zero_D_non_zero_O_gives_zero_rate(self):
        """Valid zero-detection period: D=0, O>0 → rate = 0.0, not None."""
        r = _own("aqua", 2016, D=0, O=500)
        assert _pooled_rate([r]) == pytest.approx(0.0)


# ---------------------------------------------------------------------------
# 3.  fit_own_support_variants — a_H calculation
# ---------------------------------------------------------------------------
class TestFitOwnSupportVariants:
    """
    Hand-computed fixture (Section 6 equations):
      a_H = (SCALE * ΣD_aqua / ΣO_aqua) / (SCALE * ΣD_viirs / ΣO_viirs)
           = (ΣD_aqua / ΣO_aqua) / (ΣD_viirs / ΣO_viirs)   [SCALE cancels]

    Training data:
      Aqua  2016: D=100, O=1000  → partial rate 100.0
      Aqua  2017: D=200, O=2000  → partial rate 100.0
      Aqua  2018: D=150, O=1500  → partial rate 100.0
      Pooled Aqua (all): D=450, O=4500 → 1000 * 450 / 4500 = 100.0

      VIIRS 2016: D= 80, O=1000  → partial rate  80.0
      VIIRS 2017: D=160, O=2000  → partial rate  80.0
      VIIRS 2018: D=120, O=1500  → partial rate  80.0
      Pooled VIIRS (all): D=360, O=4500 → 1000 * 360 / 4500 = 80.0

      a_H (full training) = 100.0 / 80.0 = 1.25

    Leave-one-out:
      ex_2016: Aqua  D=350, O=3500 → 100.0;  VIIRS D=280, O=3500 → 80.0 → a_H = 1.25
      ex_2017: Aqua  D=250, O=2500 → 100.0;  VIIRS D=200, O=2500 → 80.0 → a_H = 1.25
      ex_2018: Aqua  D=300, O=3000 → 100.0;  VIIRS D=240, O=3000 → 80.0 → a_H = 1.25
    (All equal because rates are uniform across years; this is intentional for
     a clean unit test.  Sensitivity test below uses non-uniform rates.)
    """

    @pytest.fixture()
    def records(self):
        aqua = [
            _own("aqua", 2016, D=100, O=1000),
            _own("aqua", 2017, D=200, O=2000),
            _own("aqua", 2018, D=150, O=1500),
        ]
        viirs = [
            _own("viirs", 2016, D=80,  O=1000),
            _own("viirs", 2017, D=160, O=2000),
            _own("viirs", 2018, D=120, O=1500),
        ]
        return aqua, viirs

    def test_full_training_factor_value(self, records):
        aqua, viirs = records
        variants = fit_own_support_variants(aqua, viirs)
        full = variants["full_training_2016_2017_2018"]
        assert full.status == FactorStatus.AVAILABLE
        assert full.factor_value == pytest.approx(1.25)
        assert full.factor_type == "own_support_a_H"

    def test_all_four_variant_keys_present(self, records):
        aqua, viirs = records
        variants = fit_own_support_variants(aqua, viirs)
        assert "full_training_2016_2017_2018" in variants
        assert "ex_2016" in variants
        assert "ex_2017" in variants
        assert "ex_2018" in variants

    def test_leave_one_out_ex_2016(self, records):
        aqua, viirs = records
        variants = fit_own_support_variants(aqua, viirs)
        # ex_2016: Aqua D=350, O=3500 → 100.0; VIIRS D=280, O=3500 → 80.0 → 1.25
        assert variants["ex_2016"].factor_value == pytest.approx(1.25)

    def test_leave_one_out_uses_only_remaining_years(self, records):
        aqua, viirs = records
        variants = fit_own_support_variants(aqua, viirs)
        # ex_2017 must use only 2016 and 2018
        assert set(variants["ex_2017"].training_years) == {2016, 2018}

    def test_aqua_and_viirs_pooled_rates_stored(self, records):
        aqua, viirs = records
        variants = fit_own_support_variants(aqua, viirs)
        full = variants["full_training_2016_2017_2018"]
        assert full.aqua_pooled_rate == pytest.approx(100.0)
        assert full.viirs_pooled_rate == pytest.approx(80.0)

    def test_records_outside_training_years_ignored(self, records):
        """Development-year records must NOT enter factor computation."""
        aqua, viirs = records
        # Add 2019 (dev) records — must be ignored
        aqua_with_dev = aqua + [_own("aqua", 2019, D=999, O=1000)]
        viirs_with_dev = viirs + [_own("viirs", 2019, D=1,   O=1000)]
        variants = fit_own_support_variants(aqua_with_dev, viirs_with_dev)
        # Factor must equal the same 1.25 as without dev records
        assert variants["full_training_2016_2017_2018"].factor_value == pytest.approx(1.25)

    def test_zero_viirs_rate_yields_unavailable(self):
        """VIIRS D=0, O>0 → pooled rate = 0 → factor UNAVAILABLE (no division)."""
        aqua = [_own("aqua", 2016, D=100, O=1000)]
        viirs = [_own("viirs", 2016, D=0,   O=1000)]
        variants = fit_own_support_variants(aqua, viirs,
                                            training_years=(2016,))
        full_key = "full_training_2016"
        assert variants[full_key].status == FactorStatus.UNAVAILABLE
        assert variants[full_key].factor_value is None
        assert any("zero" in r.lower() for r in variants[full_key].reasons)

    def test_all_aqua_unavailable_yields_unavailable_factor(self):
        aqua = [_own("aqua", 2016, D=0, O=0)]
        viirs = [_own("viirs", 2016, D=50, O=1000)]
        variants = fit_own_support_variants(aqua, viirs,
                                            training_years=(2016,))
        assert variants["full_training_2016"].status == FactorStatus.UNAVAILABLE

    def test_policy_guard_raises_on_common_support_record(self):
        aqua = [_common("aqua", 2016, D=10, O=100)]  # wrong policy
        viirs = [_own("viirs", 2016, D=10, O=100)]
        with pytest.raises(ValueError, match="own_support"):
            fit_own_support_variants(aqua, viirs, training_years=(2016,))


# ---------------------------------------------------------------------------
# 4.  fit_common_support_variants — a_C is strictly separate from a_H
# ---------------------------------------------------------------------------
class TestFitCommonSupportVariants:
    """
    Hand-computed fixture:
      Aqua common  2016: D=60,  O=800   → rate = 1000*60/800  = 75.0
      Aqua common  2017: D=120, O=1600  → rate = 1000*120/1600 = 75.0
      Pooled Aqua: D=180, O=2400 → 75.0

      VIIRS common 2016: D=48,  O=800   → rate = 1000*48/800  = 60.0
      VIIRS common 2017: D=96,  O=1600  → rate = 1000*96/1600 = 60.0
      Pooled VIIRS: D=144, O=2400 → 60.0

      a_C = 75.0 / 60.0 = 1.25
    """

    @pytest.fixture()
    def records(self):
        aqua = [
            _common("aqua",  2016, D=60,  O=800),
            _common("aqua",  2017, D=120, O=1600),
        ]
        viirs = [
            _common("viirs", 2016, D=48,  O=800),
            _common("viirs", 2017, D=96,  O=1600),
        ]
        return aqua, viirs

    def test_full_training_factor_value(self, records):
        aqua, viirs = records
        variants = fit_common_support_variants(aqua, viirs,
                                               training_years=(2016, 2017))
        full = variants["full_training_2016_2017"]
        assert full.status == FactorStatus.AVAILABLE
        assert full.factor_value == pytest.approx(1.25)
        assert full.factor_type == "common_support_a_C"

    def test_factor_type_is_a_C_not_a_H(self, records):
        aqua, viirs = records
        variants = fit_common_support_variants(aqua, viirs,
                                               training_years=(2016, 2017))
        for v in variants.values():
            assert v.factor_type == "common_support_a_C", (
                "a_C variants must never carry the own_support_a_H type"
            )

    def test_policy_guard_raises_on_own_support_record(self):
        aqua = [_own("aqua", 2016, D=10, O=100)]  # wrong policy
        viirs = [_common("viirs", 2016, D=10, O=100)]
        with pytest.raises(ValueError, match="common_support"):
            fit_common_support_variants(aqua, viirs, training_years=(2016,))


# ---------------------------------------------------------------------------
# 5.  Missing-data guardrail — O=0 NEVER coerces to zero fire
# ---------------------------------------------------------------------------
class TestMissingDataGuardrail:
    def test_fully_missing_training_produces_unavailable_not_zero_rate(self):
        """
        If every training record has O=0, the pooled rate is None (unavailable),
        not 0.0.  A factor of 0 / 0 must never be returned as 0.0.
        """
        aqua  = [_own("aqua",  2016, D=0, O=0),
                 _own("aqua",  2017, D=0, O=0)]
        viirs = [_own("viirs", 2016, D=0, O=0),
                 _own("viirs", 2017, D=0, O=0)]
        variants = fit_own_support_variants(aqua, viirs,
                                            training_years=(2016, 2017))
        full = variants["full_training_2016_2017"]
        assert full.status == FactorStatus.UNAVAILABLE
        assert full.factor_value is None
        assert full.aqua_pooled_rate is None
        assert full.viirs_pooled_rate is None

    def test_unavailable_record_does_not_contribute_to_denominator(self):
        """
        Mix of one available and one unavailable record.
        Only the available record should enter the pooled rate.
        Rate = 1000 * 50 / 500 = 100.0  (the O=0 record is ignored)
        """
        records = [
            _own("aqua", 2016, D=50, O=500),
            _own("aqua", 2017, D=0,  O=0),   # unavailable
        ]
        rate = _pooled_rate(records)
        assert rate == pytest.approx(100.0)

    def test_unavailable_viirs_target_in_apply_produces_unresolved(self):
        """
        When the target VIIRS rate is None (O=0 in target period),
        apply_factor must return delta=None and headline_direction=UNRESOLVED.
        """
        aqua  = [_own("aqua",  2016, D=100, O=1000)]
        viirs = [_own("viirs", 2016, D=80,  O=1000)]
        variants = fit_own_support_variants(aqua, viirs, training_years=(2016,))
        full = variants["full_training_2016"]

        result = apply_factor(
            factor_result=full,
            baseline_B=100.0,
            viirs_V=None,          # ← target period is unavailable (O=0)
            sensitivity_status=SensitivityStatus.STABLE,
            applicability_status=ApplicabilityStatus.EVALUATED,
        )
        assert result.delta is None
        assert result.mapped_Z is None
        assert result.headline_direction == HeadlineDirection.UNRESOLVED


# ---------------------------------------------------------------------------
# 6.  Sums-before-division composition fixture (§4B)
# ---------------------------------------------------------------------------
class TestSumsBeforeDivision:
    """
    Block weighting fixture from the plan §4B:
      Block A rate: 10 (D=10, O=1 each unit of O)
      Block B rate:  1 (D= 1, O=1 each unit of O)
      Period 1: block A gets 0.8 of total O, block B gets 0.2
      Period 2: block A gets 0.2 of total O, block B gets 0.8

    With total O = 1000 in each period:
      Period 1: O_A=800, D_A=8;   O_B=200, D_B=0.2  → D_B=200*0.001≈ ... 

    Use integer-friendly values:
      Period 1: O_A=800, D_A=8000*? ... let's use rate exactly:
        Block A: D=8,  O=800   → rate  10.0
        Block B: D=2,  O=2000  → rate   1.0
        Pooled: 1000 * (8+2) / (800+2000) = 1000 * 10 / 2800 ≈ 3.571...

    The plan's specific example uses decimal shares on abstract units.
    We test the PRINCIPLE: pooled ≠ average of block rates.

    Exact plan fixture:
      block rates 10 and 1, shares 0.8/0.2 → pooled = 0.8*10 + 0.2*1 = 8.2
      shares 0.2/0.8 → pooled = 0.2*10 + 0.8*1 = 2.8
      (These are the WEIGHTED AVERAGES of rates, equivalent to sums-before-division
       when weights = O_b / sum(O_b).  We verify this identity.)

    To match exactly: total O = 10, period 1: O_A=8, D_A=80/1000*8=0.064? No.
    Use O units where D = rate * O / 1000:
      If rate_A=10, O_A=8: D_A = 10*8/1000 = 0.08  (not integer).

    Use O=100 as the unit to get integer D:
      rate_A=10 → D_A=1 per O=100
      rate_B=1  → D_B=0 per O=100 (not integer either)

    Use O=1000:
      rate_A=10 → D_A=10 per O=1000
      rate_B=1  → D_B=1  per O=1000

    Period 1 (0.8/0.2 of total O=10000):
      Block A: D=80, O=8000
      Block B: D=1,  O=1000
      Pooled = 1000 * 81 / 9000 = 9.0  (≠ 0.8*10 + 0.2*1 = 8.2 because shares differ)

    For exact 0.8/0.2 weighted-rate equality, total O must split 8000:2000.
      Block A: D=80, O=8000  → rate 10.0
      Block B: D=2,  O=2000  → rate  1.0
      Pooled = 1000 * 82 / 10000 = 8.2  ✓

    Period 2 (0.2/0.8):
      Block A: D=20, O=2000  → rate 10.0
      Block B: D=8,  O=8000  → rate  1.0
      Pooled = 1000 * 28 / 10000 = 2.8  ✓

    Change = (2.8 - 8.2) / 8.2 = -5.4 / 8.2 ≈ -0.6585  → -65.85%  ✓
    """

    def test_period1_pooled_rate_8_2(self):
        recs = [
            _own("aqua", 2016, D=80, O=8000),   # block A: rate 10.0
            _own("aqua", 2016, D=2,  O=2000),   # block B: rate  1.0  ← note same year
        ]
        # Sum D=82, O=10000; rate = 1000*82/10000 = 8.2
        assert _pooled_rate(recs) == pytest.approx(8.2)

    def test_period2_pooled_rate_2_8(self):
        recs = [
            _own("aqua", 2017, D=20, O=2000),   # block A: rate 10.0
            _own("aqua", 2017, D=8,  O=8000),   # block B: rate  1.0
        ]
        # Sum D=28, O=10000; rate = 1000*28/10000 = 2.8
        assert _pooled_rate(recs) == pytest.approx(2.8)

    def test_pooled_rate_change_is_not_equal_as_unweighted_average_would_give(self):
        """
        Unweighted average of block rates: (10+1)/2 = 5.5 in BOTH periods.
        That would falsely show no change.  Pooled sums-before-division gives
        8.2 and 2.8 — a large real shift.  Confirm the two calculations differ.
        """
        p1 = _pooled_rate([
            _own("aqua", 2016, D=80, O=8000),
            _own("aqua", 2016, D=2,  O=2000),
        ])
        p2 = _pooled_rate([
            _own("aqua", 2017, D=20, O=2000),
            _own("aqua", 2017, D=8,  O=8000),
        ])
        naive_avg = (10.0 + 1.0) / 2  # 5.5

        assert p1 != pytest.approx(naive_avg), (
            "Period 1 pooled rate should not equal the naive unweighted average"
        )
        assert p2 != pytest.approx(naive_avg), (
            "Period 2 pooled rate should not equal the naive unweighted average"
        )
        # Direction and magnitude of change
        pct_change = (p2 - p1) / p1
        assert pct_change == pytest.approx(-0.6585, abs=1e-4)


# ---------------------------------------------------------------------------
# 7.  assess_sensitivity
# ---------------------------------------------------------------------------
class TestAssessSensitivity:
    def test_stable_when_all_variants_available(self):
        aqua  = [_own("aqua",  y, D=100, O=1000) for y in [2016, 2017, 2018]]
        viirs = [_own("viirs", y, D=80,  O=1000) for y in [2016, 2017, 2018]]
        variants = fit_own_support_variants(aqua, viirs)
        status, reasons = assess_sensitivity(variants)
        assert status == SensitivityStatus.STABLE

    def test_unresolved_when_required_variant_unavailable(self):
        """
        ex_2017 uses only 2016 and 2018.
        Make VIIRS D=0 in both 2016 and 2018 so the ex_2017 pooled VIIRS rate
        is exactly 0 → ex_2017 factor is UNAVAILABLE.
        When that variant is listed as required, assess_sensitivity → UNRESOLVED.

        Fixture:
          Aqua  2016: D=100, O=1000;  Aqua  2017: D=100, O=1000;  Aqua  2018: D=100, O=1000
          VIIRS 2016: D=0,   O=1000;  VIIRS 2017: D=80,  O=1000;  VIIRS 2018: D=0,   O=1000

          full_training: VIIRS pooled = 1000*80/3000 = 26.67 → available
          ex_2016 (2017+2018): VIIRS D=80, O=2000 → 40.0 → available
          ex_2017 (2016+2018): VIIRS D=0,  O=2000 →  0.0 → UNAVAILABLE (zero VIIRS rate)
          ex_2018 (2016+2017): VIIRS D=80, O=2000 → 40.0 → available
        """
        aqua  = [_own("aqua",  2016, D=100, O=1000),
                 _own("aqua",  2017, D=100, O=1000),
                 _own("aqua",  2018, D=100, O=1000)]
        viirs = [_own("viirs", 2016, D=0,   O=1000),  # D=0 valid zero-detection
                 _own("viirs", 2017, D=80,  O=1000),
                 _own("viirs", 2018, D=0,   O=1000)]  # D=0 valid zero-detection
        variants = fit_own_support_variants(aqua, viirs)
        assert variants["ex_2017"].status == FactorStatus.UNAVAILABLE, (
            "ex_2017 must be UNAVAILABLE: VIIRS pooled rate = 0 (D=0 in both 2016 and 2018)"
        )
        required = [
            "full_training_2016_2017_2018",
            "ex_2016", "ex_2017", "ex_2018",
        ]
        status, reasons = assess_sensitivity(variants, required_variant_ids=required)
        assert status == SensitivityStatus.UNRESOLVED
        assert any("unavailable" in r.lower() for r in reasons)

    def test_unresolved_with_fewer_than_two_available_variants(self):
        from science.methods.stage_a import FactorResult
        single_variant = {
            "full_training_2016": FactorResult(
                variant_id="full_training_2016",
                factor_type="own_support_a_H",
                training_years=(2016,),
                status=FactorStatus.AVAILABLE,
                factor_value=1.25,
                aqua_pooled_rate=100.0,
                viirs_pooled_rate=80.0,
                n_aqua_obs=1,
                n_viirs_obs=1,
            )
        }
        status, reasons = assess_sensitivity(single_variant)
        assert status == SensitivityStatus.UNRESOLVED


# ---------------------------------------------------------------------------
# 8.  apply_factor — independent status dimensions and equality boundary
# ---------------------------------------------------------------------------
class TestApplyFactor:
    """
    Hand-computed targets:
      a_H = 1.25  (from previous fixture)
      B   = 100.0  (Aqua baseline rate)
      V   = 80.0   (VIIRS target rate)
      Z   = 1.25 * 80.0 = 100.0
      Delta = 100.0 - 100.0 = 0.0  → NO_CHANGE
      a_break = B / V = 100.0 / 80.0 = 1.25

    Scenario 2: B = 90.0, V = 80.0
      Z = 1.25 * 80.0 = 100.0
      Delta = 100.0 - 90.0 = 10.0 → INCREASE
      a_break = 90.0 / 80.0 = 1.125
    """

    @pytest.fixture()
    def full_factor(self):
        aqua  = [_own("aqua",  y, D=100, O=1000) for y in TRAINING_YEARS_DEFAULT]
        viirs = [_own("viirs", y, D=80,  O=1000) for y in TRAINING_YEARS_DEFAULT]
        return fit_own_support_variants(aqua, viirs)["full_training_2016_2017_2018"]

    def test_delta_and_direction_no_change(self, full_factor):
        result = apply_factor(
            factor_result=full_factor,
            baseline_B=100.0,
            viirs_V=80.0,
            sensitivity_status=SensitivityStatus.STABLE,
            applicability_status=ApplicabilityStatus.EVALUATED,
        )
        assert result.mapped_Z == pytest.approx(100.0)
        assert result.delta    == pytest.approx(0.0)
        assert result.headline_direction == HeadlineDirection.NO_CHANGE

    def test_delta_and_direction_increase(self, full_factor):
        # B=90, V=80: Z=100, Delta=+10
        result = apply_factor(
            factor_result=full_factor,
            baseline_B=90.0,
            viirs_V=80.0,
            sensitivity_status=SensitivityStatus.STABLE,
            applicability_status=ApplicabilityStatus.EVALUATED,
        )
        assert result.delta == pytest.approx(10.0)
        assert result.headline_direction == HeadlineDirection.INCREASE

    def test_delta_and_direction_decrease(self, full_factor):
        # B=110, V=80: Z=100, Delta=-10
        result = apply_factor(
            factor_result=full_factor,
            baseline_B=110.0,
            viirs_V=80.0,
            sensitivity_status=SensitivityStatus.STABLE,
            applicability_status=ApplicabilityStatus.EVALUATED,
        )
        assert result.delta == pytest.approx(-10.0)
        assert result.headline_direction == HeadlineDirection.DECREASE

    def test_equality_boundary_a_break(self, full_factor):
        # B=90, V=80: a_break = 90/80 = 1.125
        result = apply_factor(
            factor_result=full_factor,
            baseline_B=90.0,
            viirs_V=80.0,
            sensitivity_status=SensitivityStatus.STABLE,
            applicability_status=ApplicabilityStatus.EVALUATED,
        )
        assert result.equality_break_a == pytest.approx(1.125)

    def test_equality_boundary_v_zero_b_nonzero(self, full_factor):
        """V=0, B≠0: Delta = -B for every a; no equality break."""
        result = apply_factor(
            factor_result=full_factor,
            baseline_B=50.0,
            viirs_V=0.0,
            sensitivity_status=SensitivityStatus.STABLE,
            applicability_status=ApplicabilityStatus.EVALUATED,
        )
        assert result.equality_break_a is None
        assert result.delta == pytest.approx(-50.0)
        assert result.headline_direction == HeadlineDirection.DECREASE
        assert any("V = 0" in r for r in result.reasons)

    def test_equality_boundary_v_zero_b_zero(self, full_factor):
        """V=0, B=0: Delta=0 for every a."""
        result = apply_factor(
            factor_result=full_factor,
            baseline_B=0.0,
            viirs_V=0.0,
            sensitivity_status=SensitivityStatus.STABLE,
            applicability_status=ApplicabilityStatus.EVALUATED,
        )
        assert result.equality_break_a is None
        assert result.delta == pytest.approx(0.0)
        assert result.headline_direction == HeadlineDirection.NO_CHANGE

    def test_inference_status_always_not_established(self, full_factor):
        """inference_status must NEVER be overridden at Stage A."""
        result = apply_factor(
            factor_result=full_factor,
            baseline_B=100.0,
            viirs_V=80.0,
            sensitivity_status=SensitivityStatus.STABLE,
            applicability_status=ApplicabilityStatus.EVALUATED,
        )
        assert result.inference_status == InferenceStatus.NOT_ESTABLISHED

    def test_practical_change_meaningful_increase(self, full_factor):
        # Delta = 10.0, tau = 5.0 → meaningful increase
        result = apply_factor(
            factor_result=full_factor,
            baseline_B=90.0,
            viirs_V=80.0,
            sensitivity_status=SensitivityStatus.STABLE,
            applicability_status=ApplicabilityStatus.EVALUATED,
            practical_margin_tau=5.0,
        )
        assert result.practical_change == PracticalChange.MEANINGFUL_INCREASE

    def test_practical_change_within_margin(self, full_factor):
        # Delta = 10.0, tau = 15.0 → within margin
        result = apply_factor(
            factor_result=full_factor,
            baseline_B=90.0,
            viirs_V=80.0,
            sensitivity_status=SensitivityStatus.STABLE,
            applicability_status=ApplicabilityStatus.EVALUATED,
            practical_margin_tau=15.0,
        )
        assert result.practical_change == PracticalChange.WITHIN_MARGIN

    def test_practical_change_unspecified_when_no_tau(self, full_factor):
        result = apply_factor(
            factor_result=full_factor,
            baseline_B=90.0,
            viirs_V=80.0,
            sensitivity_status=SensitivityStatus.STABLE,
            applicability_status=ApplicabilityStatus.EVALUATED,
            practical_margin_tau=None,
        )
        assert result.practical_change == PracticalChange.UNSPECIFIED

    def test_negative_tau_raises(self, full_factor):
        with pytest.raises(ValueError, match="non-negative"):
            apply_factor(
                factor_result=full_factor,
                baseline_B=100.0,
                viirs_V=80.0,
                sensitivity_status=SensitivityStatus.STABLE,
                applicability_status=ApplicabilityStatus.EVALUATED,
                practical_margin_tau=-1.0,
            )

    def test_unavailable_factor_yields_unresolved_direction(self):
        """An UNAVAILABLE factor must produce delta=None and UNRESOLVED direction."""
        aqua  = [_own("aqua",  2016, D=0, O=0)]
        viirs = [_own("viirs", 2016, D=0, O=0)]
        variants = fit_own_support_variants(aqua, viirs, training_years=(2016,))
        unavail_factor = variants["full_training_2016"]
        assert unavail_factor.status == FactorStatus.UNAVAILABLE

        result = apply_factor(
            factor_result=unavail_factor,
            baseline_B=100.0,
            viirs_V=80.0,
            sensitivity_status=SensitivityStatus.UNRESOLVED,
            applicability_status=ApplicabilityStatus.INSUFFICIENT_EVIDENCE,
        )
        assert result.delta is None
        assert result.headline_direction == HeadlineDirection.UNRESOLVED
        assert result.mapped_Z is None

    def test_a_H_and_a_C_produce_independent_results(self):
        """
        a_H and a_C applied to the same target must remain distinct objects.
        Changing a_C must not alter the a_H result.
        """
        # a_H fixture: Aqua own D=100, O=1000; VIIRS own D=80, O=1000 → a_H=1.25
        a_own  = [_own("aqua",  2016, D=100, O=1000)]
        v_own  = [_own("viirs", 2016, D=80,  O=1000)]
        h_vars = fit_own_support_variants(a_own, v_own, training_years=(2016,))
        full_H = h_vars["full_training_2016"]

        # a_C fixture: Aqua common D=60, O=800; VIIRS common D=48, O=800 → a_C=1.25
        a_comm = [_common("aqua",  2016, D=60, O=800)]
        v_comm = [_common("viirs", 2016, D=48, O=800)]
        c_vars = fit_common_support_variants(a_comm, v_comm, training_years=(2016,))
        full_C = c_vars["full_training_2016"]

        res_H = apply_factor(
            factor_result=full_H,
            baseline_B=100.0,
            viirs_V=80.0,
            sensitivity_status=SensitivityStatus.STABLE,
            applicability_status=ApplicabilityStatus.EVALUATED,
        )
        res_C = apply_factor(
            factor_result=full_C,
            baseline_B=100.0,
            viirs_V=80.0,
            sensitivity_status=SensitivityStatus.STABLE,
            applicability_status=ApplicabilityStatus.EVALUATED,
        )
        # Both happen to give the same value here (1.25), but types differ
        assert res_H.factor_type == "own_support_a_H"
        assert res_C.factor_type == "common_support_a_C"
        # They are separate objects; modifying one's reasons list doesn't affect the other
        res_H.reasons.append("test")
        assert "test" not in res_C.reasons


# ---------------------------------------------------------------------------
# 9.  Sensitivity — non-uniform factor fixture shows genuine divergence
# ---------------------------------------------------------------------------
class TestSensitivityNonUniform:
    """
    Use non-uniform rates across years so leave-one-out factors differ,
    confirming that the full recalculation happens correctly.

    Aqua  2016: D=100, O=1000 (rate 100)
    Aqua  2017: D=200, O=1000 (rate 200)
    VIIRS 2016: D= 50, O=1000 (rate  50)
    VIIRS 2017: D=100, O=1000 (rate 100)

    Full training:
      Aqua pooled  = 1000 * 300 / 2000 = 150.0
      VIIRS pooled = 1000 * 150 / 2000 =  75.0
      a_H = 150 / 75 = 2.0

    ex_2016 (only 2017):
      Aqua  = 1000 * 200 / 1000 = 200.0
      VIIRS = 1000 * 100 / 1000 = 100.0
      a_H = 200 / 100 = 2.0

    ex_2017 (only 2016):
      Aqua  = 1000 * 100 / 1000 = 100.0
      VIIRS = 1000 *  50 / 1000 =  50.0
      a_H = 100 / 50 = 2.0

    (All equal here too — the ratio is constant. Use asymmetric D to show difference.)

    Asymmetric fixture:
    Aqua  2016: D=200, O=1000 (rate 200)
    Aqua  2017: D=100, O=1000 (rate 100)
    VIIRS 2016: D= 50, O=1000 (rate  50)
    VIIRS 2017: D=100, O=1000 (rate 100)

    Full training:
      Aqua  pooled = 1000 * 300 / 2000 = 150.0
      VIIRS pooled = 1000 * 150 / 2000 =  75.0
      a_H = 2.0

    ex_2016 (only 2017):
      Aqua  = 100.0,  VIIRS = 100.0  → a_H = 1.0
    ex_2017 (only 2016):
      Aqua  = 200.0,  VIIRS =  50.0  → a_H = 4.0

    Factors: 2.0, 1.0, 4.0 — genuinely different.
    """

    @pytest.fixture()
    def asymmetric_variants(self):
        aqua  = [_own("aqua",  2016, D=200, O=1000),
                 _own("aqua",  2017, D=100, O=1000)]
        viirs = [_own("viirs", 2016, D=50,  O=1000),
                 _own("viirs", 2017, D=100, O=1000)]
        return fit_own_support_variants(aqua, viirs, training_years=(2016, 2017))

    def test_full_training_factor(self, asymmetric_variants):
        v = asymmetric_variants["full_training_2016_2017"]
        assert v.factor_value == pytest.approx(2.0)

    def test_ex_2016_factor(self, asymmetric_variants):
        v = asymmetric_variants["ex_2016"]
        # Only year 2017: Aqua=100, VIIRS=100 → a_H=1.0
        assert v.factor_value == pytest.approx(1.0)

    def test_ex_2017_factor(self, asymmetric_variants):
        v = asymmetric_variants["ex_2017"]
        # Only year 2016: Aqua=200, VIIRS=50 → a_H=4.0
        assert v.factor_value == pytest.approx(4.0)

    def test_factors_span_range_confirming_sensitivity(self, asymmetric_variants):
        values = [
            v.factor_value
            for v in asymmetric_variants.values()
            if v.status == FactorStatus.AVAILABLE
        ]
        assert min(values) == pytest.approx(1.0)
        assert max(values) == pytest.approx(4.0)
