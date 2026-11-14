"""
Unit tests for science/methods/stage_a.py  (v2)

ALL expected values are computed by hand from the spec equations.
No outputs are ever copied from the implementation under test.

Scientific authority:
  THE_THIRD_EYE_FINAL_PLAN_GEOGRAPHIC_ACCESS_UPDATED.txt  §4, §6, §7, §8
  contracts/schemas/comparison.py

Invariants tested:
  1.  O = 0 is MISSING → never yields D = 0 fire, never enters any denominator.
  2.  Pooled rate = SCALE * sum(D) / sum(O)  (sums BEFORE division).
  3.  a_H = aqua_own_rate / viirs_own_rate   (own-support policy only).
  4.  a_C = aqua_common_rate / viirs_common_rate  (common-support policy only).
  5.  a_H and a_C are independent; a_C never substitutes for a_H.
  6.  Leave-one-year-out re-runs the full calculation on the remaining years.
  7.  Zero VIIRS rate → factor UNAVAILABLE (never 0.0 or inf).
  8.  Non-positive factor → UNAVAILABLE.
  9.  All four status dimensions are independent.
  10. Equality boundary: a_break = B / V  for V > 0.
  11. Policy guard: mixing 'own_support' and 'common_support' records raises.
  12. (v2) Every registered training year must have O > 0 for each sensor;
      a year with only O = 0 records → factor UNAVAILABLE with explicit reason.
  13. (v2) assess_sensitivity requires (B, V) and checks directional sign
      agreement across variant Deltas; sign reversal → SENSITIVE.
  14. (v2) ApplicabilityStatus has five named categories: evaluated,
      failed_applicability, outside_evaluated, missing_required_support,
      insufficient_evidence.
  15. (v2) Composition fixture: fixed-weight 5.5/5.5 identity verified;
      weighted-sum identity R_t = sum_b(w_b * r_b) confirmed.
"""
from __future__ import annotations

import pytest

from science.methods.stage_a import (
    SCALE,
    TRAINING_YEARS_DEFAULT,
    ApplicabilityStatus,
    AppliedComparison,
    Availability,
    FactorResult,
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
    _check_year_support,
    _check_stratum_match,
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
        # D=10, O=900 → rate  11.11…
        # D=10, O=100 → rate 100.0
        # Average-of-rates: (11.11 + 100.0) / 2 = 55.555…
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
      Aqua  2016: D=100, O=1000  Aqua  2017: D=200, O=2000  Aqua  2018: D=150, O=1500
      Pooled Aqua: D=450, O=4500 → 1000 * 450 / 4500 = 100.0

      VIIRS 2016: D= 80, O=1000  VIIRS 2017: D=160, O=2000  VIIRS 2018: D=120, O=1500
      Pooled VIIRS: D=360, O=4500 → 1000 * 360 / 4500 = 80.0

      a_H (full training) = 100.0 / 80.0 = 1.25

    Leave-one-out:
      ex_2016: Aqua D=350, O=3500 → 100.0;  VIIRS D=280, O=3500 → 80.0 → a_H = 1.25
      ex_2017: Aqua D=250, O=2500 → 100.0;  VIIRS D=200, O=2500 → 80.0 → a_H = 1.25
      ex_2018: Aqua D=300, O=3000 → 100.0;  VIIRS D=240, O=3000 → 80.0 → a_H = 1.25
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
        aqua_with_dev = aqua + [_own("aqua", 2019, D=999, O=1000)]
        viirs_with_dev = viirs + [_own("viirs", 2019, D=1,   O=1000)]
        variants = fit_own_support_variants(aqua_with_dev, viirs_with_dev)
        assert variants["full_training_2016_2017_2018"].factor_value == pytest.approx(1.25)

    def test_zero_viirs_rate_yields_unavailable(self):
        """VIIRS D=0, O>0 → pooled rate = 0 → factor UNAVAILABLE."""
        aqua = [_own("aqua", 2016, D=100, O=1000)]
        viirs = [_own("viirs", 2016, D=0,   O=1000)]
        variants = fit_own_support_variants(aqua, viirs, training_years=(2016,))
        full_key = "full_training_2016"
        assert variants[full_key].status == FactorStatus.UNAVAILABLE
        assert variants[full_key].factor_value is None
        assert any("zero" in r.lower() for r in variants[full_key].reasons)

    def test_all_aqua_unavailable_yields_unavailable_factor(self):
        """Aqua O=0 in only training year → UNAVAILABLE."""
        aqua = [_own("aqua", 2016, D=0, O=0)]
        viirs = [_own("viirs", 2016, D=50, O=1000)]
        variants = fit_own_support_variants(aqua, viirs, training_years=(2016,))
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
      Aqua common  2016: D=60,  O=800   → 1000*60/800  = 75.0
      Aqua common  2017: D=120, O=1600  → 1000*120/1600 = 75.0
      Pooled Aqua: D=180, O=2400 → 75.0

      VIIRS common 2016: D=48,  O=800   → 1000*48/800  = 60.0
      VIIRS common 2017: D=96,  O=1600  → 1000*96/1600 = 60.0
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
        If every training record has O=0, the factor must be UNAVAILABLE,
        not 0.0.
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
        Rate = 1000 * 50 / 500 = 100.0  (the O=0 record is ignored)
        """
        records = [
            _own("aqua", 2016, D=50, O=500),
            _own("aqua", 2017, D=0,  O=0),
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
            viirs_V=None,
            sensitivity_status=SensitivityStatus.STABLE,
            applicability_status=ApplicabilityStatus.EVALUATED,
        )
        assert result.delta is None
        assert result.mapped_Z is None
        assert result.headline_direction == HeadlineDirection.UNRESOLVED


# ---------------------------------------------------------------------------
# 6.  (v2) Year-support check — finding #2
# ---------------------------------------------------------------------------
class TestYearSupportCheck:
    """
    Every registered training year must have at least one available (O > 0)
    record for each sensor.  Silently pooling over fewer years than registered
    is prohibited (§6: "registered training years").
    """

    def test_missing_aqua_year_makes_factor_unavailable(self):
        """
        Training years = (2016, 2017).  Aqua has no record for 2017.
        Factor must be UNAVAILABLE with the missing year named.
        """
        aqua  = [_own("aqua",  2016, D=100, O=1000)]  # 2017 absent entirely
        viirs = [_own("viirs", 2016, D=80,  O=1000),
                 _own("viirs", 2017, D=80,  O=1000)]
        variants = fit_own_support_variants(aqua, viirs,
                                            training_years=(2016, 2017))
        full = variants["full_training_2016_2017"]
        assert full.status == FactorStatus.UNAVAILABLE
        assert 2017 in full.missing_aqua_years
        assert any("2017" in r for r in full.reasons)

    def test_missing_viirs_year_makes_factor_unavailable(self):
        """
        Training years = (2016, 2017).  VIIRS has no record for 2017.
        """
        aqua  = [_own("aqua",  2016, D=100, O=1000),
                 _own("aqua",  2017, D=100, O=1000)]
        viirs = [_own("viirs", 2016, D=80,  O=1000)]  # 2017 absent entirely
        variants = fit_own_support_variants(aqua, viirs,
                                            training_years=(2016, 2017))
        full = variants["full_training_2016_2017"]
        assert full.status == FactorStatus.UNAVAILABLE
        assert 2017 in full.missing_viirs_years

    def test_aqua_year_with_only_O_zero_records_is_missing(self):
        """
        A year whose only record has O=0 is treated as missing,
        not silently pooled as if it had zero observations.
        """
        aqua  = [_own("aqua",  2016, D=100, O=1000),
                 _own("aqua",  2017, D=0,   O=0)]    # only O=0 record
        viirs = [_own("viirs", 2016, D=80,  O=1000),
                 _own("viirs", 2017, D=80,  O=1000)]
        variants = fit_own_support_variants(aqua, viirs,
                                            training_years=(2016, 2017))
        full = variants["full_training_2016_2017"]
        assert full.status == FactorStatus.UNAVAILABLE
        assert 2017 in full.missing_aqua_years

    def test_check_year_support_helper_returns_missing_years(self):
        """Unit test for the _check_year_support helper directly."""
        records = [
            _own("aqua", 2016, D=50, O=500),
            _own("aqua", 2017, D=0,  O=0),   # unavailable
            # 2018 entirely absent
        ]
        missing = _check_year_support(records, (2016, 2017, 2018), "Aqua")
        assert missing == [2017, 2018]  # sorted

    def test_check_year_support_all_present_returns_empty(self):
        records = [
            _own("aqua", 2016, D=100, O=1000),
            _own("aqua", 2017, D=100, O=1000),
        ]
        missing = _check_year_support(records, (2016, 2017), "Aqua")
        assert missing == []

    def test_valid_factor_has_empty_missing_year_lists(self):
        """When all years have support, missing_*_years must be empty."""
        aqua  = [_own("aqua",  2016, D=100, O=1000),
                 _own("aqua",  2017, D=100, O=1000)]
        viirs = [_own("viirs", 2016, D=80,  O=1000),
                 _own("viirs", 2017, D=80,  O=1000)]
        variants = fit_own_support_variants(aqua, viirs,
                                            training_years=(2016, 2017))
        full = variants["full_training_2016_2017"]
        assert full.status == FactorStatus.AVAILABLE
        assert full.missing_aqua_years == []
        assert full.missing_viirs_years == []


# ---------------------------------------------------------------------------
# 7.  Sums-before-division composition fixture (§4B)  — finding #4 extended
# ---------------------------------------------------------------------------
class TestSumsBeforeDivision:
    """
    Exact plan fixture (§4B):
      Block A rate = 10, Block B rate = 1.
      Period 1 (0.8/0.2 O shares): pooled = 0.8*10 + 0.2*1 = 8.2
      Period 2 (0.2/0.8 O shares): pooled = 0.2*10 + 0.8*1 = 2.8
      Change = (2.8 - 8.2) / 8.2 ≈ -65.85%

    Fixed 0.5/0.5 weights: pooled = 0.5*10 + 0.5*1 = 5.5 in BOTH periods.

    Integer-exact implementation:
      Rate 10 ↔ D = r * O / 1000.  Choose O multiples of 1000 so D is integer.

      Period 1: O_total = 10000, shares 0.8/0.2
        Block A: O=8000, D= 80  → rate = 1000*80/8000 = 10.0  ✓
        Block B: O=2000, D=  2  → rate = 1000*2/2000  =  1.0  ✓
        Pooled:  1000 * 82 / 10000 = 8.2  ✓

      Period 2: O_total = 10000, shares 0.2/0.8
        Block A: O=2000, D= 20  → rate = 1000*20/2000 = 10.0  ✓
        Block B: O=8000, D=  8  → rate = 1000*8/8000  =  1.0  ✓
        Pooled:  1000 * 28 / 10000 = 2.8  ✓

      Fixed-weight (0.5/0.5), period 1:
        Block A: O=5000, D= 50  → rate 10.0
        Block B: O=5000, D=  5  → rate  1.0
        Pooled:  1000 * 55 / 10000 = 5.5  ✓

      Fixed-weight (0.5/0.5), period 2:
        Block A: O=5000, D= 50  → rate 10.0
        Block B: O=5000, D=  5  → rate  1.0
        Pooled:  1000 * 55 / 10000 = 5.5  ✓

    Weighted-sum identity:
      R_t = sum_b(w_b_t * r_b_t)  where  w_b_t = O_b_t / O_total_t
      Period 1: w_A = 8000/10000 = 0.8, w_B = 2000/10000 = 0.2
                R_1 = 0.8*10 + 0.2*1 = 8.2  ✓
      Period 2: w_A = 2000/10000 = 0.2, w_B = 8000/10000 = 0.8
                R_2 = 0.2*10 + 0.8*1 = 2.8  ✓
    """

    def test_period1_pooled_rate_8_2(self):
        recs = [
            _own("aqua", 2016, D=80, O=8000),   # block A: rate 10.0
            _own("aqua", 2016, D=2,  O=2000),   # block B: rate  1.0
        ]
        # sum D=82, O=10000; rate = 1000*82/10000 = 8.2
        assert _pooled_rate(recs) == pytest.approx(8.2)

    def test_period2_pooled_rate_2_8(self):
        recs = [
            _own("aqua", 2017, D=20, O=2000),   # block A: rate 10.0
            _own("aqua", 2017, D=8,  O=8000),   # block B: rate  1.0
        ]
        # sum D=28, O=10000; rate = 1000*28/10000 = 2.8
        assert _pooled_rate(recs) == pytest.approx(2.8)

    def test_pooled_rate_change_is_not_equal_as_unweighted_average_would_give(self):
        """
        Unweighted average of block rates: (10+1)/2 = 5.5 in BOTH periods.
        That would falsely show no change.  Pooled sums-before-division gives
        8.2 and 2.8 — a large real shift.
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
            "Period 1 pooled rate must not equal the naive unweighted average"
        )
        assert p2 != pytest.approx(naive_avg), (
            "Period 2 pooled rate must not equal the naive unweighted average"
        )
        pct_change = (p2 - p1) / p1
        assert pct_change == pytest.approx(-0.6585, abs=1e-4)

    def test_fixed_weight_equal_shares_give_5_5_both_periods(self):
        """
        (v2, finding #4) The plan's §4B 'fixed 0.5/0.5 weights give 5.5 in
        both periods' identity: when both blocks get equal O shares,
        the pooled rate equals the unweighted average regardless of period.

        Fixed-weight period 1:
          Block A: O=5000, D=50  → rate 10.0
          Block B: O=5000, D= 5  → rate  1.0
          Pooled: 1000 * 55 / 10000 = 5.5  ✓
        Fixed-weight period 2: same records → same pooled rate 5.5.
        """
        p1_fixed = _pooled_rate([
            _own("aqua", 2016, D=50, O=5000),   # block A rate 10
            _own("aqua", 2016, D=5,  O=5000),   # block B rate  1
        ])
        p2_fixed = _pooled_rate([
            _own("aqua", 2017, D=50, O=5000),
            _own("aqua", 2017, D=5,  O=5000),
        ])
        assert p1_fixed == pytest.approx(5.5), "Fixed 0.5/0.5 period 1 must equal 5.5"
        assert p2_fixed == pytest.approx(5.5), "Fixed 0.5/0.5 period 2 must equal 5.5"
        # No change under fixed weights:
        assert p1_fixed == pytest.approx(p2_fixed)

    def test_weighted_sum_identity(self):
        """
        (v2, finding #4) Verify: R_t = sum_b(w_b * r_b)
        where w_b = O_b / O_total.

        Period 1: w_A=0.8, r_A=10; w_B=0.2, r_B=1
          Weighted sum = 0.8*10 + 0.2*1 = 8.2  == pooled rate  ✓

        Period 2: w_A=0.2, r_A=10; w_B=0.8, r_B=1
          Weighted sum = 0.2*10 + 0.8*1 = 2.8  == pooled rate  ✓
        """
        # Period 1
        p1 = _pooled_rate([
            _own("aqua", 2016, D=80, O=8000),
            _own("aqua", 2016, D=2,  O=2000),
        ])
        # Weighted sum: (8000/10000)*10 + (2000/10000)*1
        ws1 = (8000 / 10000) * 10.0 + (2000 / 10000) * 1.0
        assert p1 == pytest.approx(ws1)

        # Period 2
        p2 = _pooled_rate([
            _own("aqua", 2017, D=20, O=2000),
            _own("aqua", 2017, D=8,  O=8000),
        ])
        ws2 = (2000 / 10000) * 10.0 + (8000 / 10000) * 1.0
        assert p2 == pytest.approx(ws2)


# ---------------------------------------------------------------------------
# 8.  assess_sensitivity  (v2: target-aware, sign-based)  — finding #1
# ---------------------------------------------------------------------------
class TestAssessSensitivity:
    """
    assess_sensitivity requires (baseline_B, viirs_V) and checks directional
    agreement of Delta = a*V - B across all variants.

    Finding #1: stability must be assessed on the target, not on factor values
    alone.  Factors on opposite sides of the equality boundary (a_break = B/V)
    produce opposing Deltas → SENSITIVE.
    """

    def test_stable_when_all_deltas_same_sign_positive(self):
        """
        All variants give Delta > 0.
        Fixture: a_H=1.25 (all variants), V=80, B=90.
          Delta = 1.25*80 - 90 = 100 - 90 = 10 > 0 → STABLE (all increase).
        """
        aqua  = [_own("aqua",  y, D=100, O=1000) for y in [2016, 2017, 2018]]
        viirs = [_own("viirs", y, D=80,  O=1000) for y in [2016, 2017, 2018]]
        variants = fit_own_support_variants(aqua, viirs)
        # B=90, V=80: Delta = 1.25*80 - 90 = +10 for all variants
        status, reasons = assess_sensitivity(variants, baseline_B=90.0, viirs_V=80.0)
        assert status == SensitivityStatus.STABLE

    def test_stable_when_all_deltas_same_sign_negative(self):
        """
        All variants give Delta < 0.
        Fixture: a_H=1.25, V=80, B=110.
          Delta = 1.25*80 - 110 = 100 - 110 = -10 < 0 → STABLE (all decrease).
        """
        aqua  = [_own("aqua",  y, D=100, O=1000) for y in [2016, 2017, 2018]]
        viirs = [_own("viirs", y, D=80,  O=1000) for y in [2016, 2017, 2018]]
        variants = fit_own_support_variants(aqua, viirs)
        status, reasons = assess_sensitivity(variants, baseline_B=110.0, viirs_V=80.0)
        assert status == SensitivityStatus.STABLE

    def test_sensitive_when_variants_produce_opposing_deltas(self):
        """
        (v2 — core finding #1 test)
        Asymmetric fixture: factors span a range that straddles the equality
        boundary a_break = B/V.

        Factors:
          full_training (2016+2017): a = 2.0
          ex_2016 (only 2017):       a = 1.0
          ex_2017 (only 2016):       a = 4.0

        Target: B=150, V=80
          a_break = 150/80 = 1.875

          Delta(a=4.0) = 4.0*80 - 150 = 320 - 150 = +170  (increase)
          Delta(a=2.0) = 2.0*80 - 150 = 160 - 150 =  +10  (increase)
          Delta(a=1.0) = 1.0*80 - 150 =  80 - 150 =  -70  (decrease)

        ex_2016 (a=1.0) gives decrease; others give increase → SENSITIVE.
        """
        aqua  = [_own("aqua",  2016, D=200, O=1000),
                 _own("aqua",  2017, D=100, O=1000)]
        viirs = [_own("viirs", 2016, D=50,  O=1000),
                 _own("viirs", 2017, D=100, O=1000)]
        variants = fit_own_support_variants(aqua, viirs,
                                            training_years=(2016, 2017))
        # Verify the factors (hand-computed):
        # full: Aqua D=300, O=2000 → 150.0;  VIIRS D=150, O=2000 → 75.0 → a=2.0
        # ex_2016 (2017 only): Aqua 100.0, VIIRS 100.0 → a=1.0
        # ex_2017 (2016 only): Aqua 200.0, VIIRS  50.0 → a=4.0
        assert variants["full_training_2016_2017"].factor_value == pytest.approx(2.0)
        assert variants["ex_2016"].factor_value == pytest.approx(1.0)
        assert variants["ex_2017"].factor_value == pytest.approx(4.0)

        status, reasons = assess_sensitivity(
            variants, baseline_B=150.0, viirs_V=80.0
        )
        assert status == SensitivityStatus.SENSITIVE
        assert any("disagree" in r.lower() or "delta" in r.lower() or
                   "decrease" in r.lower() or "increase" in r.lower()
                   for r in reasons)

    def test_stable_does_not_require_all_same_factor_value(self):
        """
        Factors may differ in magnitude, but if all Deltas share the same sign
        the result is STABLE (no reversal).

        Factors: a=2.0, a=1.0, a=4.0 (same asymmetric fixture).
        Target: B=50, V=80  → a_break = 50/80 = 0.625.
          All a > a_break:
          Delta(1.0) = 1.0*80 - 50 = 30  > 0
          Delta(2.0) = 2.0*80 - 50 = 110 > 0
          Delta(4.0) = 4.0*80 - 50 = 270 > 0
          → STABLE.
        """
        aqua  = [_own("aqua",  2016, D=200, O=1000),
                 _own("aqua",  2017, D=100, O=1000)]
        viirs = [_own("viirs", 2016, D=50,  O=1000),
                 _own("viirs", 2017, D=100, O=1000)]
        variants = fit_own_support_variants(aqua, viirs,
                                            training_years=(2016, 2017))
        status, reasons = assess_sensitivity(
            variants, baseline_B=50.0, viirs_V=80.0
        )
        assert status == SensitivityStatus.STABLE

    def test_unresolved_when_target_B_is_none(self):
        aqua  = [_own("aqua",  y, D=100, O=1000) for y in [2016, 2017, 2018]]
        viirs = [_own("viirs", y, D=80,  O=1000) for y in [2016, 2017, 2018]]
        variants = fit_own_support_variants(aqua, viirs)
        status, reasons = assess_sensitivity(
            variants, baseline_B=None, viirs_V=80.0
        )
        assert status == SensitivityStatus.UNRESOLVED
        assert any("B" in r or "baseline" in r.lower() for r in reasons)

    def test_unresolved_when_target_V_is_none(self):
        aqua  = [_own("aqua",  y, D=100, O=1000) for y in [2016, 2017, 2018]]
        viirs = [_own("viirs", y, D=80,  O=1000) for y in [2016, 2017, 2018]]
        variants = fit_own_support_variants(aqua, viirs)
        status, reasons = assess_sensitivity(
            variants, baseline_B=90.0, viirs_V=None
        )
        assert status == SensitivityStatus.UNRESOLVED

    def test_unresolved_when_required_variant_unavailable(self):
        """
        ex_2017 uses only 2016 and 2018.  VIIRS D=0 in both → pooled rate=0
        → ex_2017 UNAVAILABLE.  When listed as required → UNRESOLVED.

        Fixture:
          VIIRS 2016: D=0, O=1000  (zero-detection, valid)
          VIIRS 2017: D=80, O=1000
          VIIRS 2018: D=0, O=1000  (zero-detection, valid)

          ex_2017 (2016+2018): VIIRS pooled D=0, O=2000 → rate 0.0 → UNAVAILABLE
        """
        aqua  = [_own("aqua",  2016, D=100, O=1000),
                 _own("aqua",  2017, D=100, O=1000),
                 _own("aqua",  2018, D=100, O=1000)]
        viirs = [_own("viirs", 2016, D=0,   O=1000),
                 _own("viirs", 2017, D=80,  O=1000),
                 _own("viirs", 2018, D=0,   O=1000)]
        variants = fit_own_support_variants(aqua, viirs)
        assert variants["ex_2017"].status == FactorStatus.UNAVAILABLE

        required = [
            "full_training_2016_2017_2018",
            "ex_2016", "ex_2017", "ex_2018",
        ]
        status, reasons = assess_sensitivity(
            variants, baseline_B=90.0, viirs_V=80.0,
            required_variant_ids=required,
        )
        assert status == SensitivityStatus.UNRESOLVED
        assert any("unavailable" in r.lower() for r in reasons)

    def test_unresolved_with_fewer_than_two_available_variants(self):
        single = {
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
        status, reasons = assess_sensitivity(single, baseline_B=90.0, viirs_V=80.0)
        assert status == SensitivityStatus.UNRESOLVED


# ---------------------------------------------------------------------------
# 9.  ApplicabilityStatus — five named categories (finding #3)
# ---------------------------------------------------------------------------
class TestApplicabilityStatus:
    """
    The spec §8B names five distinct output categories.
    All five must exist and must be semantically distinct in the enum.
    """

    def test_all_five_categories_exist(self):
        statuses = {s.value for s in ApplicabilityStatus}
        assert "evaluated_for_conditions"   in statuses
        assert "failed_applicability"       in statuses
        assert "outside_evaluated_conditions" in statuses
        assert "missing_required_support"   in statuses
        assert "insufficient_evidence"      in statuses

    def test_failed_applicability_distinct_from_outside_evaluated(self):
        assert ApplicabilityStatus.FAILED_APPLICABILITY != \
               ApplicabilityStatus.OUTSIDE_EVALUATED

    def test_missing_required_support_distinct_from_insufficient_evidence(self):
        assert ApplicabilityStatus.MISSING_REQUIRED_SUPPORT != \
               ApplicabilityStatus.INSUFFICIENT_EVIDENCE

    def test_apply_factor_accepts_all_five_applicability_statuses(self):
        """apply_factor must accept any of the five statuses without error."""
        aqua  = [_own("aqua",  2016, D=100, O=1000)]
        viirs = [_own("viirs", 2016, D=80,  O=1000)]
        variants = fit_own_support_variants(aqua, viirs, training_years=(2016,))
        full = variants["full_training_2016"]

        for status in ApplicabilityStatus:
            result = apply_factor(
                factor_result=full,
                baseline_B=100.0,
                viirs_V=80.0,
                sensitivity_status=SensitivityStatus.STABLE,
                applicability_status=status,
            )
            assert result.applicability_status == status

    def test_failed_applicability_does_not_imply_no_delta(self):
        """
        FAILED_APPLICABILITY means a check was done and failed — but the
        numerical result (delta) may still be computable.  The status is
        separate from the numerical outcome; it must not coerce delta to None.
        """
        aqua  = [_own("aqua",  2016, D=100, O=1000)]
        viirs = [_own("viirs", 2016, D=80,  O=1000)]
        variants = fit_own_support_variants(aqua, viirs, training_years=(2016,))
        full = variants["full_training_2016"]

        result = apply_factor(
            factor_result=full,
            baseline_B=100.0,
            viirs_V=80.0,
            sensitivity_status=SensitivityStatus.STABLE,
            applicability_status=ApplicabilityStatus.FAILED_APPLICABILITY,
        )
        # Delta is still computed — the failed applicability is a separate dimension
        assert result.delta == pytest.approx(0.0)
        assert result.applicability_status == ApplicabilityStatus.FAILED_APPLICABILITY


# ---------------------------------------------------------------------------
# 10. apply_factor — independent status dimensions and equality boundary
# ---------------------------------------------------------------------------
class TestApplyFactor:
    """
    Hand-computed targets:
      a_H = 1.25, B = 100.0, V = 80.0
        Z = 1.25 * 80.0 = 100.0
        Delta = 100.0 - 100.0 = 0.0  → NO_CHANGE
        a_break = 100.0 / 80.0 = 1.25

      B = 90.0, V = 80.0
        Z = 100.0, Delta = +10.0 → INCREASE
        a_break = 90.0 / 80.0 = 1.125

      B = 110.0, V = 80.0
        Z = 100.0, Delta = -10.0 → DECREASE
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
        result = apply_factor(
            factor_result=full_factor,
            baseline_B=100.0,
            viirs_V=80.0,
            sensitivity_status=SensitivityStatus.STABLE,
            applicability_status=ApplicabilityStatus.EVALUATED,
        )
        assert result.inference_status == InferenceStatus.NOT_ESTABLISHED

    def test_practical_change_meaningful_increase(self, full_factor):
        # Delta=10.0, tau=5.0 → meaningful increase
        result = apply_factor(
            factor_result=full_factor,
            baseline_B=90.0, viirs_V=80.0,
            sensitivity_status=SensitivityStatus.STABLE,
            applicability_status=ApplicabilityStatus.EVALUATED,
            practical_margin_tau=5.0,
        )
        assert result.practical_change == PracticalChange.MEANINGFUL_INCREASE

    def test_practical_change_within_margin(self, full_factor):
        # Delta=10.0, tau=15.0 → within margin
        result = apply_factor(
            factor_result=full_factor,
            baseline_B=90.0, viirs_V=80.0,
            sensitivity_status=SensitivityStatus.STABLE,
            applicability_status=ApplicabilityStatus.EVALUATED,
            practical_margin_tau=15.0,
        )
        assert result.practical_change == PracticalChange.WITHIN_MARGIN

    def test_practical_change_unspecified_when_no_tau(self, full_factor):
        result = apply_factor(
            factor_result=full_factor,
            baseline_B=90.0, viirs_V=80.0,
            sensitivity_status=SensitivityStatus.STABLE,
            applicability_status=ApplicabilityStatus.EVALUATED,
            practical_margin_tau=None,
        )
        assert result.practical_change == PracticalChange.UNSPECIFIED

    def test_negative_tau_raises(self, full_factor):
        with pytest.raises(ValueError, match="non-negative"):
            apply_factor(
                factor_result=full_factor,
                baseline_B=100.0, viirs_V=80.0,
                sensitivity_status=SensitivityStatus.STABLE,
                applicability_status=ApplicabilityStatus.EVALUATED,
                practical_margin_tau=-1.0,
            )

    def test_unavailable_factor_yields_unresolved_direction(self):
        aqua  = [_own("aqua",  2016, D=0, O=0)]
        viirs = [_own("viirs", 2016, D=0, O=0)]
        variants = fit_own_support_variants(aqua, viirs, training_years=(2016,))
        unavail = variants["full_training_2016"]
        assert unavail.status == FactorStatus.UNAVAILABLE

        result = apply_factor(
            factor_result=unavail,
            baseline_B=100.0, viirs_V=80.0,
            sensitivity_status=SensitivityStatus.UNRESOLVED,
            applicability_status=ApplicabilityStatus.INSUFFICIENT_EVIDENCE,
        )
        assert result.delta is None
        assert result.headline_direction == HeadlineDirection.UNRESOLVED
        assert result.mapped_Z is None

    def test_a_H_and_a_C_produce_independent_results(self):
        """a_H and a_C applied to the same target are distinct objects."""
        a_own  = [_own("aqua",  2016, D=100, O=1000)]
        v_own  = [_own("viirs", 2016, D=80,  O=1000)]
        h_vars = fit_own_support_variants(a_own, v_own, training_years=(2016,))
        full_H = h_vars["full_training_2016"]

        a_comm = [_common("aqua",  2016, D=60, O=800)]
        v_comm = [_common("viirs", 2016, D=48, O=800)]
        c_vars = fit_common_support_variants(a_comm, v_comm, training_years=(2016,))
        full_C = c_vars["full_training_2016"]

        res_H = apply_factor(
            factor_result=full_H,
            baseline_B=100.0, viirs_V=80.0,
            sensitivity_status=SensitivityStatus.STABLE,
            applicability_status=ApplicabilityStatus.EVALUATED,
        )
        res_C = apply_factor(
            factor_result=full_C,
            baseline_B=100.0, viirs_V=80.0,
            sensitivity_status=SensitivityStatus.STABLE,
            applicability_status=ApplicabilityStatus.EVALUATED,
        )
        assert res_H.factor_type == "own_support_a_H"
        assert res_C.factor_type == "common_support_a_C"
        # Modifying one's list must not affect the other
        res_H.reasons.append("test")
        assert "test" not in res_C.reasons


# ---------------------------------------------------------------------------
# 11. Sensitivity — non-uniform factor fixture shows genuine divergence
# ---------------------------------------------------------------------------
class TestSensitivityNonUniform:
    """
    Asymmetric fixture (same as TestAssessSensitivity.test_sensitive_*):
      Aqua  2016: D=200, O=1000;  Aqua  2017: D=100, O=1000
      VIIRS 2016: D= 50, O=1000;  VIIRS 2017: D=100, O=1000

      full_training (2016+2017):
        Aqua pooled  = 1000*300/2000 = 150.0
        VIIRS pooled = 1000*150/2000 =  75.0
        a_H = 2.0

      ex_2016 (2017 only):
        Aqua = 100.0, VIIRS = 100.0 → a_H = 1.0

      ex_2017 (2016 only):
        Aqua = 200.0, VIIRS =  50.0 → a_H = 4.0
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
        # Only year 2017: Aqua=100, VIIRS=100 → a_H=1.0
        v = asymmetric_variants["ex_2016"]
        assert v.factor_value == pytest.approx(1.0)

    def test_ex_2017_factor(self, asymmetric_variants):
        # Only year 2016: Aqua=200, VIIRS=50 → a_H=4.0
        v = asymmetric_variants["ex_2017"]
        assert v.factor_value == pytest.approx(4.0)

    def test_factors_span_range(self, asymmetric_variants):
        values = [
            v.factor_value
            for v in asymmetric_variants.values()
            if v.status == FactorStatus.AVAILABLE
        ]
        assert min(values) == pytest.approx(1.0)
        assert max(values) == pytest.approx(4.0)


# ---------------------------------------------------------------------------
# 12. (v3) Headline direction withheld when applicability fails or is absent
#     Issue 1 from third review
# ---------------------------------------------------------------------------
class TestApplicabilityGatesDirection:
    """
    Spec §7: "do not collapse these dimensions into a reassuring single badge
    or report a directional conclusion when its mandatory applicability evidence
    fails or is absent."

    Only ApplicabilityStatus.EVALUATED permits INCREASE/DECREASE/NO_CHANGE.
    All four non-evaluated statuses must yield UNRESOLVED headline_direction
    and UNSPECIFIED practical_change, even when delta is numerically non-None.

    Fixture:
      a_H = 1.25, B = 90.0, V = 80.0
        Z = 1.25 * 80.0 = 100.0
        delta = 100.0 - 90.0 = 10.0  (positive — would be INCREASE if applicable)
    """

    @pytest.fixture()
    def factor_and_inputs(self):
        aqua  = [_own("aqua",  y, D=100, O=1000) for y in TRAINING_YEARS_DEFAULT]
        viirs = [_own("viirs", y, D=80,  O=1000) for y in TRAINING_YEARS_DEFAULT]
        full = fit_own_support_variants(aqua, viirs)["full_training_2016_2017_2018"]
        return full, 90.0, 80.0  # factor, B, V

    _NON_EVALUATED = [
        ApplicabilityStatus.FAILED_APPLICABILITY,
        ApplicabilityStatus.OUTSIDE_EVALUATED,
        ApplicabilityStatus.MISSING_REQUIRED_SUPPORT,
        ApplicabilityStatus.INSUFFICIENT_EVIDENCE,
    ]

    @pytest.mark.parametrize("bad_status", _NON_EVALUATED)
    def test_headline_direction_unresolved_for_non_evaluated_status(
        self, factor_and_inputs, bad_status
    ):
        """
        delta = +10.0 but applicability is not EVALUATED → direction must be
        UNRESOLVED, not INCREASE.
        """
        full, B, V = factor_and_inputs
        result = apply_factor(
            factor_result=full,
            baseline_B=B,
            viirs_V=V,
            sensitivity_status=SensitivityStatus.STABLE,
            applicability_status=bad_status,
        )
        # delta is still computed (numeric dimensions are independent)
        assert result.delta == pytest.approx(10.0), (
            "delta must still be computed even when direction is withheld"
        )
        assert result.headline_direction == HeadlineDirection.UNRESOLVED, (
            f"headline_direction must be UNRESOLVED for status {bad_status.value}, "
            f"got {result.headline_direction}"
        )
        assert any("applicability" in r.lower() for r in result.reasons), (
            "reasons must explain that direction was withheld due to applicability"
        )

    @pytest.mark.parametrize("bad_status", _NON_EVALUATED)
    def test_practical_change_unspecified_for_non_evaluated_status(
        self, factor_and_inputs, bad_status
    ):
        """
        practical_change must be UNSPECIFIED when applicability is not EVALUATED,
        even when tau is supplied and delta is non-None.
        """
        full, B, V = factor_and_inputs
        result = apply_factor(
            factor_result=full,
            baseline_B=B,
            viirs_V=V,
            sensitivity_status=SensitivityStatus.STABLE,
            applicability_status=bad_status,
            practical_margin_tau=5.0,  # delta=10 would normally be MEANINGFUL_INCREASE
        )
        assert result.practical_change == PracticalChange.UNSPECIFIED, (
            f"practical_change must be UNSPECIFIED for {bad_status.value}, "
            f"got {result.practical_change}"
        )

    def test_direction_emitted_only_for_evaluated_status(
        self, factor_and_inputs
    ):
        """
        EVALUATED is the only status that permits a directional answer.
        delta = +10 → INCREASE.
        """
        full, B, V = factor_and_inputs
        result = apply_factor(
            factor_result=full,
            baseline_B=B,
            viirs_V=V,
            sensitivity_status=SensitivityStatus.STABLE,
            applicability_status=ApplicabilityStatus.EVALUATED,
        )
        assert result.headline_direction == HeadlineDirection.INCREASE
        assert result.delta == pytest.approx(10.0)

    def test_direction_unresolved_when_delta_zero_but_applicability_failed(
        self, factor_and_inputs
    ):
        """
        Even Delta = 0.0 (equality) must become UNRESOLVED when applicability
        has failed — the caller must not receive a NO_CHANGE verdict.

        Fixture: B = 100.0, V = 80.0 → Z = 1.25*80 = 100.0, Delta = 0.
        """
        full, _, _ = factor_and_inputs
        result = apply_factor(
            factor_result=full,
            baseline_B=100.0,
            viirs_V=80.0,
            sensitivity_status=SensitivityStatus.STABLE,
            applicability_status=ApplicabilityStatus.FAILED_APPLICABILITY,
        )
        assert result.delta == pytest.approx(0.0)
        assert result.headline_direction == HeadlineDirection.UNRESOLVED

    def test_stable_sensitivity_does_not_override_applicability_gate(
        self, factor_and_inputs
    ):
        """
        STABLE sensitivity must not grant a directional conclusion when
        applicability is OUTSIDE_EVALUATED.  The two dimensions are independent.
        """
        full, B, V = factor_and_inputs
        result = apply_factor(
            factor_result=full,
            baseline_B=B,
            viirs_V=V,
            sensitivity_status=SensitivityStatus.STABLE,
            applicability_status=ApplicabilityStatus.OUTSIDE_EVALUATED,
        )
        assert result.sensitivity_status == SensitivityStatus.STABLE
        assert result.headline_direction == HeadlineDirection.UNRESOLVED


# ---------------------------------------------------------------------------
# 13. (v3) Matched calendar strata required before making a factor available
#     Issue 2 from third review
# ---------------------------------------------------------------------------
class TestStratumMatch:
    """
    Spec §6: "matched calendar strata" for a_H; "identical paired
    common-support cell-days" for a_C.

    _check_stratum_match returns the symmetric difference of available
    (year, stratum) keys across the two sensor lists.  _fit_factor treats
    any mismatch as UNAVAILABLE.

    The stratum field on ObsRecord defaults to "annual" in the _own/_common
    helpers used throughout the other tests — those are matched by design.
    Here we construct records with deliberately mismatched strata.
    """

    def test_check_stratum_match_no_mismatch(self):
        """Identical (year, stratum) keys → empty list."""
        aqua  = [_own("aqua",  2016, D=100, O=1000),
                 _own("aqua",  2017, D=100, O=1000)]
        viirs = [_own("viirs", 2016, D=80,  O=1000),
                 _own("viirs", 2017, D=80,  O=1000)]
        assert _check_stratum_match(aqua, viirs) == []

    def test_check_stratum_match_extra_aqua_stratum(self):
        """Aqua has a stratum that VIIRS lacks."""
        aqua = [
            ObsRecord("aqua", 2016, "month_07", "own_support", 100, 1000),
            ObsRecord("aqua", 2016, "month_08", "own_support",  50,  500),
        ]
        viirs = [
            ObsRecord("viirs", 2016, "month_07", "own_support", 80, 1000),
            # month_08 is absent for VIIRS
        ]
        result = _check_stratum_match(aqua, viirs)
        assert (2016, "month_08") in result

    def test_check_stratum_match_extra_viirs_stratum(self):
        """VIIRS has a stratum that Aqua lacks."""
        aqua = [
            ObsRecord("aqua", 2017, "month_06", "own_support", 100, 1000),
        ]
        viirs = [
            ObsRecord("viirs", 2017, "month_06", "own_support", 80, 1000),
            ObsRecord("viirs", 2017, "month_07", "own_support", 60, 1000),
        ]
        result = _check_stratum_match(aqua, viirs)
        assert (2017, "month_07") in result

    def test_check_stratum_match_ignores_unavailable_records(self):
        """
        O=0 records are excluded from the key set; a year/stratum present
        only as O=0 for one sensor does not create a mismatch — it was never
        available to pool anyway.
        """
        aqua = [
            ObsRecord("aqua", 2016, "month_07", "own_support", 100, 1000),
            ObsRecord("aqua", 2016, "month_08", "own_support",   0,    0),  # unavailable
        ]
        viirs = [
            ObsRecord("viirs", 2016, "month_07", "own_support", 80, 1000),
            # month_08 also absent for VIIRS, but it's O=0 for Aqua too — no mismatch
        ]
        # Aqua month_08 is O=0 (unavailable), so it is excluded from key set.
        # Both sensors have only (2016, month_07) available → no mismatch.
        assert _check_stratum_match(aqua, viirs) == []

    def test_mismatched_stratum_makes_own_support_factor_unavailable(self):
        """
        a_H: Aqua has month_07 and month_08; VIIRS has only month_07.
        Factor must be UNAVAILABLE with the mismatch recorded.
        """
        aqua = [
            ObsRecord("aqua", 2016, "month_07", "own_support", 100, 1000),
            ObsRecord("aqua", 2016, "month_08", "own_support",  50,  500),
        ]
        viirs = [
            ObsRecord("viirs", 2016, "month_07", "own_support", 80, 1000),
        ]
        variants = fit_own_support_variants(aqua, viirs, training_years=(2016,))
        full = variants["full_training_2016"]
        assert full.status == FactorStatus.UNAVAILABLE
        assert (2016, "month_08") in full.mismatched_strata
        assert any("strata" in r.lower() or "stratum" in r.lower()
                   for r in full.reasons)

    def test_mismatched_stratum_makes_common_support_factor_unavailable(self):
        """
        a_C: Aqua common has month_07 and month_09; VIIRS common has only month_07.
        Factor must be UNAVAILABLE — the pairing is not identical.
        """
        aqua = [
            ObsRecord("aqua",  2016, "month_07", "common_support", 60, 800),
            ObsRecord("aqua",  2016, "month_09", "common_support", 30, 400),
        ]
        viirs = [
            ObsRecord("viirs", 2016, "month_07", "common_support", 48, 800),
        ]
        variants = fit_common_support_variants(aqua, viirs, training_years=(2016,))
        full = variants["full_training_2016"]
        assert full.status == FactorStatus.UNAVAILABLE
        assert (2016, "month_09") in full.mismatched_strata

    def test_matched_strata_across_multiple_years_produces_available_factor(self):
        """
        When every (year, stratum) key is matched, the stratum check passes
        and the factor proceeds to the pooled-rate computation.

        Fixture (two strata, two years):
          Aqua  2016 month_07: D=80, O=1000  → rate  80.0
          Aqua  2016 month_08: D=20, O=1000  → rate  20.0
          Aqua  2017 month_07: D=80, O=1000
          Aqua  2017 month_08: D=20, O=1000
          Pooled Aqua D=200, O=4000 → 1000*200/4000 = 50.0

          VIIRS 2016 month_07: D=40, O=1000  → rate  40.0
          VIIRS 2016 month_08: D=10, O=1000  → rate  10.0
          VIIRS 2017 month_07: D=40, O=1000
          VIIRS 2017 month_08: D=10, O=1000
          Pooled VIIRS D=100, O=4000 → 1000*100/4000 = 25.0

          a_H = 50.0 / 25.0 = 2.0
        """
        aqua = [
            ObsRecord("aqua", 2016, "month_07", "own_support",  80, 1000),
            ObsRecord("aqua", 2016, "month_08", "own_support",  20, 1000),
            ObsRecord("aqua", 2017, "month_07", "own_support",  80, 1000),
            ObsRecord("aqua", 2017, "month_08", "own_support",  20, 1000),
        ]
        viirs = [
            ObsRecord("viirs", 2016, "month_07", "own_support", 40, 1000),
            ObsRecord("viirs", 2016, "month_08", "own_support", 10, 1000),
            ObsRecord("viirs", 2017, "month_07", "own_support", 40, 1000),
            ObsRecord("viirs", 2017, "month_08", "own_support", 10, 1000),
        ]
        variants = fit_own_support_variants(aqua, viirs, training_years=(2016, 2017))
        full = variants["full_training_2016_2017"]
        assert full.status == FactorStatus.AVAILABLE
        assert full.factor_value == pytest.approx(2.0)
        assert full.mismatched_strata == []

    def test_valid_factor_has_empty_mismatched_strata_field(self):
        """
        Standard single-stratum fixture must carry an empty mismatched_strata
        list (the field exists and is empty when all strata match).
        """
        aqua  = [_own("aqua",  2016, D=100, O=1000)]
        viirs = [_own("viirs", 2016, D=80,  O=1000)]
        variants = fit_own_support_variants(aqua, viirs, training_years=(2016,))
        full = variants["full_training_2016"]
        assert full.status == FactorStatus.AVAILABLE
        assert full.mismatched_strata == []
