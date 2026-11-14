"""
Unit tests for science/calendar/rates.py and science/calendar/baseline.py

ALL expected values computed by hand from spec equations.
No outputs copied from the implementation under test.

Scientific authority:
  THE_THIRD_EYE_FINAL_PLAN_GEOGRAPHIC_ACCESS_UPDATED.txt  §3A, §4
  contracts/schemas/calendar.py

Invariants tested:
  1.  R = 1000 * sum(D) / sum(O), sums before division.
  2.  O = 0 → unavailable, never zero fire.
  3.  is_partial=True → unavailable / PARTIAL_MONTH status.
  4.  S-NPP November 2026 is always partial (snpp_month_is_partial).
  5.  S-NPP October 2026 is NOT partial (last complete month).
  6.  MODIS_Aqua and VIIRS_SNPP records are never mixed into one rate series.
  7.  Baseline: eligible prior years only; target year excluded.
  8.  Per-year rate from pooled D/O; O=0 years excluded from n, not counted.
  9.  Median: lower-median nearest-rank.
  10. 90th percentile: nearest-rank ceil(0.9*n).
  11. Unusual: strictly above p90; equal to p90 is NOT unusual.
  12. Median = 0: absolute difference valid; percentage change undefined.
  13. n < min_years → INSUFFICIENT_BASELINE.
  14. Normal season: contiguous run of qualifying months containing the peak.
  15. Normal season wraps correctly around year end.
  16. pooled_rate: sums D and O before dividing; skips unavailable observations.
"""
from __future__ import annotations

import pytest

from science.calendar.rates import (
    PeriodObs,
    RateStatus,
    SCALE,
    SNPP_CESSATION_UTC,
    SNPP_LAST_COMPLETE_MONTH,
    compute_rate,
    pooled_rate,
)
from science.calendar.baseline import (
    BaselineConfig,
    BaselineStatus,
    MonthBaseline,
    NormalSeason,
    compute_month_baseline,
    derive_normal_season,
    label_unusual,
    _lower_median,
    _nearest_rank_percentile,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _mo(sensor, year, month, D, O, partial=False):
    return PeriodObs(sensor=sensor, year=year, D=D, O=O,
                     month=month, is_partial=partial)


def _wk(sensor, year, week, D, O, partial=False):
    return PeriodObs(sensor=sensor, year=year, D=D, O=O,
                     week_number=week, is_partial=partial)


AQUA_CFG = BaselineConfig(
    sensor="MODIS_Aqua",
    eligible_start_year=2003,
    eligible_end_year=2024,
    min_years=3,
    normal_season_threshold_fraction=0.25,
)
VIIRS_CFG = BaselineConfig(
    sensor="VIIRS_SNPP",
    eligible_start_year=2016,
    eligible_end_year=2024,
    min_years=3,
    normal_season_threshold_fraction=0.25,
)


# ---------------------------------------------------------------------------
# 1.  PeriodObs validation
# ---------------------------------------------------------------------------
class TestPeriodObs:
    def test_valid_monthly(self):
        o = _mo("MODIS_Aqua", 2016, 7, D=10, O=100)
        assert o.is_available is True

    def test_valid_weekly(self):
        o = _wk("VIIRS_SNPP", 2017, 32, D=5, O=50)
        assert o.is_available is True

    def test_O_zero_D_zero_is_unavailable(self):
        o = _mo("MODIS_Aqua", 2016, 7, D=0, O=0)
        assert o.is_available is False

    def test_O_zero_D_nonzero_raises(self):
        with pytest.raises(ValueError, match="O = 0"):
            _mo("MODIS_Aqua", 2016, 7, D=5, O=0)

    def test_negative_D_raises(self):
        with pytest.raises(ValueError, match="D must be"):
            _mo("MODIS_Aqua", 2016, 7, D=-1, O=100)

    def test_negative_O_raises(self):
        with pytest.raises(ValueError, match="O must be"):
            _mo("MODIS_Aqua", 2016, 7, D=0, O=-1)

    def test_neither_month_nor_week_raises(self):
        with pytest.raises(ValueError, match="month or week_number"):
            PeriodObs(sensor="MODIS_Aqua", year=2016, D=5, O=100)

    def test_both_month_and_week_raises(self):
        with pytest.raises(ValueError, match="not both"):
            PeriodObs(sensor="MODIS_Aqua", year=2016, D=5, O=100,
                      month=7, week_number=28)

    def test_partial_obs_is_not_available(self):
        o = _mo("VIIRS_SNPP", 2026, 11, D=50, O=1000, partial=True)
        assert o.is_available is False

    def test_partial_obs_with_O_zero_still_unavailable(self):
        o = _mo("VIIRS_SNPP", 2026, 11, D=0, O=0, partial=True)
        assert o.is_available is False


# ---------------------------------------------------------------------------
# 2.  S-NPP cutoff: snpp_month_is_partial
# ---------------------------------------------------------------------------
class TestSnppCutoff:
    """
    October 2026 is the last complete S-NPP month.
    November 2026 is partial because data ceased 2026-11-02T15:40:00Z.
    """

    def test_october_2026_is_not_partial(self):
        assert PeriodObs.snpp_month_is_partial(2026, 10) is False

    def test_november_2026_is_partial(self):
        assert PeriodObs.snpp_month_is_partial(2026, 11) is True

    def test_december_2026_would_be_partial(self):
        assert PeriodObs.snpp_month_is_partial(2026, 12) is True

    def test_any_2027_month_is_partial(self):
        for m in range(1, 13):
            assert PeriodObs.snpp_month_is_partial(2027, m) is True

    def test_september_2026_is_not_partial(self):
        assert PeriodObs.snpp_month_is_partial(2026, 9) is False

    def test_any_pre_2026_month_is_not_partial(self):
        for year in [2015, 2020, 2025]:
            for month in [1, 6, 12]:
                assert PeriodObs.snpp_month_is_partial(year, month) is False

    def test_cessation_constant_is_correct(self):
        assert SNPP_CESSATION_UTC == "2026-11-02T15:40:00Z"

    def test_last_complete_month_constant(self):
        assert SNPP_LAST_COMPLETE_MONTH == (2026, 10)


# ---------------------------------------------------------------------------
# 3.  compute_rate
# ---------------------------------------------------------------------------
class TestComputeRate:
    def test_normal_rate(self):
        # R = 1000 * 50 / 500 = 100.0
        o = _mo("MODIS_Aqua", 2016, 7, D=50, O=500)
        r = compute_rate(o)
        assert r.status == RateStatus.AVAILABLE
        assert r.fire_activity_index == pytest.approx(100.0)

    def test_zero_D_valid_O_gives_zero_rate(self):
        # Valid zero-detection month: D=0, O>0 → R = 0.0
        o = _mo("MODIS_Aqua", 2016, 7, D=0, O=1000)
        r = compute_rate(o)
        assert r.status == RateStatus.AVAILABLE
        assert r.fire_activity_index == pytest.approx(0.0)

    def test_O_zero_gives_unavailable(self):
        o = _mo("VIIRS_SNPP", 2017, 8, D=0, O=0)
        r = compute_rate(o)
        assert r.status == RateStatus.UNAVAILABLE
        assert r.fire_activity_index is None

    def test_partial_snpp_month_gives_partial_month_status(self):
        # November 2026 S-NPP — marked partial
        o = _mo("VIIRS_SNPP", 2026, 11, D=5, O=100, partial=True)
        r = compute_rate(o)
        assert r.status == RateStatus.PARTIAL_MONTH
        assert r.fire_activity_index is None
        assert any("ceased" in reason.lower() or "partial" in reason.lower()
                   for reason in r.reasons)

    def test_partial_non_snpp_gives_unavailable(self):
        o = _mo("MODIS_Aqua", 2026, 11, D=5, O=100, partial=True)
        r = compute_rate(o)
        assert r.status == RateStatus.UNAVAILABLE
        assert r.fire_activity_index is None

    def test_partial_O_zero_still_partial_month(self):
        """Even O=0 partial S-NPP month: partial guard fires first."""
        o = _mo("VIIRS_SNPP", 2026, 11, D=0, O=0, partial=True)
        r = compute_rate(o)
        assert r.status == RateStatus.PARTIAL_MONTH
        assert r.fire_activity_index is None

    def test_weekly_rate(self):
        # R = 1000 * 20 / 200 = 100.0
        o = _wk("VIIRS_SNPP", 2018, 32, D=20, O=200)
        r = compute_rate(o)
        assert r.status == RateStatus.AVAILABLE
        assert r.fire_activity_index == pytest.approx(100.0)


# ---------------------------------------------------------------------------
# 4.  pooled_rate — sums before division
# ---------------------------------------------------------------------------
class TestPooledRate:
    def test_single_obs(self):
        # 1000 * 50 / 500 = 100.0
        assert pooled_rate([_mo("MODIS_Aqua", 2016, 7, 50, 500)]) == pytest.approx(100.0)

    def test_two_obs_sums_before_divide(self):
        # D=10, O=900 → rate  11.11…
        # D=10, O=100 → rate 100.0
        # Average-of-rates = 55.55…; pooled = 1000*20/1000 = 20.0
        obs = [
            _mo("MODIS_Aqua", 2016, 7, D=10, O=900),
            _mo("MODIS_Aqua", 2016, 8, D=10, O=100),
        ]
        assert pooled_rate(obs) == pytest.approx(20.0)

    def test_all_unavailable_returns_none(self):
        obs = [_mo("MODIS_Aqua", 2016, 7, D=0, O=0),
               _mo("MODIS_Aqua", 2017, 7, D=0, O=0)]
        assert pooled_rate(obs) is None

    def test_partial_obs_excluded(self):
        # Partial obs (D=999, O=9999) must be excluded; only the available
        # obs contributes: 1000 * 50 / 500 = 100.0
        obs = [
            _mo("VIIRS_SNPP", 2026, 10, D=50, O=500),
            _mo("VIIRS_SNPP", 2026, 11, D=999, O=9999, partial=True),
        ]
        assert pooled_rate(obs) == pytest.approx(100.0)

    def test_empty_list_returns_none(self):
        assert pooled_rate([]) is None


# ---------------------------------------------------------------------------
# 5.  Baseline helper functions
# ---------------------------------------------------------------------------
class TestBaselineHelpers:
    """
    Hand-computed expected values:

    _lower_median:
      [1]        → 1          (n=1)
      [1,2]      → 1          (n=2, even: sorted[0])
      [1,2,3]    → 2          (n=3, odd:  sorted[1])
      [1,2,3,4]  → 2          (n=4, even: sorted[1])
      [1,2,3,4,5]→ 3          (n=5, odd:  sorted[2])

    _nearest_rank_percentile at p=90:
      n=1: rank=ceil(0.9)=1   → sorted[0]
      n=2: rank=ceil(1.8)=2   → sorted[1]
      n=3: rank=ceil(2.7)=3   → sorted[2]
      n=4: rank=ceil(3.6)=4   → sorted[3]
      n=5: rank=ceil(4.5)=5   → sorted[4]
      n=10:rank=ceil(9.0)=9   → sorted[8]
    """

    def test_lower_median_n1(self):
        assert _lower_median([5.0]) == pytest.approx(5.0)

    def test_lower_median_n2(self):
        assert _lower_median([3.0, 7.0]) == pytest.approx(3.0)

    def test_lower_median_n3(self):
        assert _lower_median([1.0, 2.0, 3.0]) == pytest.approx(2.0)

    def test_lower_median_n4(self):
        assert _lower_median([1.0, 2.0, 3.0, 4.0]) == pytest.approx(2.0)

    def test_lower_median_n5(self):
        assert _lower_median([1.0, 2.0, 3.0, 4.0, 5.0]) == pytest.approx(3.0)

    def test_p90_n1(self):
        # rank = ceil(0.9) = 1; value = sorted[0]
        assert _nearest_rank_percentile([10.0], 90.0) == pytest.approx(10.0)

    def test_p90_n2(self):
        # rank = ceil(1.8) = 2; value = sorted[1] = 20.0
        assert _nearest_rank_percentile([10.0, 20.0], 90.0) == pytest.approx(20.0)

    def test_p90_n3(self):
        # rank = ceil(2.7) = 3; value = sorted[2] = 30.0
        assert _nearest_rank_percentile([10.0, 20.0, 30.0], 90.0) == pytest.approx(30.0)

    def test_p90_n5(self):
        # rank = ceil(4.5) = 5; value = sorted[4] = 50.0
        assert _nearest_rank_percentile([10.0, 20.0, 30.0, 40.0, 50.0], 90.0) == pytest.approx(50.0)

    def test_p90_n10(self):
        # rank = ceil(9.0) = 9; value = sorted[8] = 90.0
        vals = [float(x * 10) for x in range(1, 11)]  # [10,20,...,100]
        assert _nearest_rank_percentile(vals, 90.0) == pytest.approx(90.0)


# ---------------------------------------------------------------------------
# 6.  compute_month_baseline
# ---------------------------------------------------------------------------
class TestComputeMonthBaseline:
    """
    Fixture: MODIS Aqua, month=7 (July), target_year=2020.
    Eligible prior years: 2003-2019 (from config eligible_start_year=2003).

    Use years 2016, 2017, 2018 to keep it manageable:
      2016: D=100, O=1000 → R = 100.0
      2017: D=200, O=2000 → R = 100.0
      2018: D=150, O=1500 → R = 100.0
      sorted rates = [100.0, 100.0, 100.0]
      median (n=3, odd): sorted[1] = 100.0
      p90 (n=3): rank=ceil(2.7)=3, sorted[2] = 100.0

    Asymmetric fixture for distinct median/p90:
      2016: D=10,  O=1000 → R = 10.0
      2017: D=50,  O=1000 → R = 50.0
      2018: D=80,  O=1000 → R = 80.0
      2019: D=90,  O=1000 → R = 90.0
      sorted rates = [10.0, 50.0, 80.0, 90.0], n=4
      lower-median (n=4, even): sorted[1] = 50.0
      p90 (n=4): rank=ceil(3.6)=4, sorted[3] = 90.0
    """

    @pytest.fixture()
    def uniform_obs(self):
        return [
            _mo("MODIS_Aqua", 2016, 7, D=100, O=1000),
            _mo("MODIS_Aqua", 2017, 7, D=200, O=2000),
            _mo("MODIS_Aqua", 2018, 7, D=150, O=1500),
        ]

    @pytest.fixture()
    def asym_obs(self):
        return [
            _mo("MODIS_Aqua", 2016, 7, D=10,  O=1000),
            _mo("MODIS_Aqua", 2017, 7, D=50,  O=1000),
            _mo("MODIS_Aqua", 2018, 7, D=80,  O=1000),
            _mo("MODIS_Aqua", 2019, 7, D=90,  O=1000),
        ]

    def test_uniform_median_and_p90(self, uniform_obs):
        bl = compute_month_baseline(7, 2020, uniform_obs, AQUA_CFG)
        assert bl.status == BaselineStatus.AVAILABLE
        assert bl.median_rate == pytest.approx(100.0)
        assert bl.p90_rate == pytest.approx(100.0)
        assert bl.n_years == 3

    def test_asym_median_and_p90(self, asym_obs):
        # median = 50.0, p90 = 90.0
        bl = compute_month_baseline(7, 2020, asym_obs, AQUA_CFG)
        assert bl.status == BaselineStatus.AVAILABLE
        assert bl.median_rate == pytest.approx(50.0)
        assert bl.p90_rate == pytest.approx(90.0)
        assert bl.n_years == 4

    def test_target_year_excluded(self, uniform_obs):
        """Target year 2018's obs must not enter the baseline."""
        all_obs = uniform_obs + [_mo("MODIS_Aqua", 2018, 7, D=9999, O=1000)]
        # 2018 is the target year — using target_year=2018 means only 2016,2017 eligible
        bl = compute_month_baseline(7, 2018, all_obs, AQUA_CFG)
        # n=2 < min_years=3 → INSUFFICIENT
        assert bl.status == BaselineStatus.INSUFFICIENT_BASELINE

    def test_later_years_excluded(self, uniform_obs):
        """Years >= target_year must be excluded."""
        future_obs = [
            _mo("MODIS_Aqua", 2021, 7, D=9999, O=1000),
            _mo("MODIS_Aqua", 2022, 7, D=9999, O=1000),
        ]
        bl = compute_month_baseline(7, 2020, uniform_obs + future_obs, AQUA_CFG)
        # 2021 and 2022 must not enter; n still 3
        assert bl.n_years == 3
        assert bl.median_rate == pytest.approx(100.0)

    def test_O_zero_year_excluded_from_n(self):
        """A year with O=0 must not be counted in n or enter the median."""
        obs = [
            _mo("MODIS_Aqua", 2016, 7, D=100, O=1000),
            _mo("MODIS_Aqua", 2017, 7, D=0,   O=0),    # unavailable
            _mo("MODIS_Aqua", 2018, 7, D=200, O=2000),
            _mo("MODIS_Aqua", 2019, 7, D=300, O=3000),
        ]
        # Rates: 2016→100.0, 2017→excluded, 2018→100.0, 2019→100.0
        # sorted = [100.0, 100.0, 100.0], n=3
        bl = compute_month_baseline(7, 2020, obs, AQUA_CFG)
        assert bl.status == BaselineStatus.AVAILABLE
        assert bl.n_years == 3
        assert 2017 not in bl.eligible_years

    def test_insufficient_n_returns_insufficient(self):
        obs = [
            _mo("MODIS_Aqua", 2016, 7, D=100, O=1000),
            _mo("MODIS_Aqua", 2017, 7, D=100, O=1000),
            # only 2 years; min_years=3
        ]
        bl = compute_month_baseline(7, 2020, obs, AQUA_CFG)
        assert bl.status == BaselineStatus.INSUFFICIENT_BASELINE
        assert bl.median_rate is None
        assert bl.p90_rate is None

    def test_no_obs_returns_no_available_years(self):
        bl = compute_month_baseline(7, 2020, [], AQUA_CFG)
        assert bl.status == BaselineStatus.NO_AVAILABLE_YEARS

    def test_wrong_month_obs_excluded(self):
        """Observations for a different month must not enter the baseline."""
        obs = [
            _mo("MODIS_Aqua", 2016, 8, D=100, O=1000),  # month 8, not 7
            _mo("MODIS_Aqua", 2017, 8, D=100, O=1000),
            _mo("MODIS_Aqua", 2018, 8, D=100, O=1000),
        ]
        bl = compute_month_baseline(7, 2020, obs, AQUA_CFG)
        assert bl.status == BaselineStatus.NO_AVAILABLE_YEARS

    def test_cross_sensor_obs_excluded(self):
        """VIIRS observations must not enter an Aqua baseline."""
        viirs_obs = [
            _mo("VIIRS_SNPP", 2016, 7, D=100, O=1000),
            _mo("VIIRS_SNPP", 2017, 7, D=100, O=1000),
            _mo("VIIRS_SNPP", 2018, 7, D=100, O=1000),
        ]
        bl = compute_month_baseline(7, 2020, viirs_obs, AQUA_CFG)
        assert bl.status == BaselineStatus.NO_AVAILABLE_YEARS


# ---------------------------------------------------------------------------
# 7.  label_unusual
# ---------------------------------------------------------------------------
class TestLabelUnusual:
    """
    Fixture — target_year=2020, month=7, sensor=MODIS_Aqua:
      Baseline (pre-computed): median=50.0, p90=90.0
      (uses asym fixture from above)

    Unusual threshold: strictly > 90.0
      target rate  91.0 → unusual
      target rate  90.0 → NOT unusual (tie is not unusual)
      target rate  50.0 → NOT unusual
    """

    @pytest.fixture()
    def baseline_90(self):
        """MonthBaseline with p90=90.0 (from asymmetric fixture)."""
        obs = [
            _mo("MODIS_Aqua", 2016, 7, D=10,  O=1000),
            _mo("MODIS_Aqua", 2017, 7, D=50,  O=1000),
            _mo("MODIS_Aqua", 2018, 7, D=80,  O=1000),
            _mo("MODIS_Aqua", 2019, 7, D=90,  O=1000),
        ]
        return compute_month_baseline(7, 2020, obs, AQUA_CFG)

    def test_strictly_above_p90_is_unusual(self, baseline_90):
        # D=91, O=1000 → R=91.0 > 90.0 → unusual
        target = [_mo("MODIS_Aqua", 2020, 7, D=91, O=1000)]
        label = label_unusual(target, 2020, 7, baseline_90)
        assert label.is_unusual is True
        assert label.status == "labeled"
        assert label.target_rate == pytest.approx(91.0)

    def test_equal_to_p90_is_not_unusual(self, baseline_90):
        # D=90, O=1000 → R=90.0 == p90=90.0 → NOT unusual (tie rule)
        target = [_mo("MODIS_Aqua", 2020, 7, D=90, O=1000)]
        label = label_unusual(target, 2020, 7, baseline_90)
        assert label.is_unusual is False
        assert label.status == "labeled"
        assert label.target_rate == pytest.approx(90.0)

    def test_below_p90_is_not_unusual(self, baseline_90):
        target = [_mo("MODIS_Aqua", 2020, 7, D=50, O=1000)]
        label = label_unusual(target, 2020, 7, baseline_90)
        assert label.is_unusual is False

    def test_target_O_zero_gives_target_unavailable(self, baseline_90):
        target = [_mo("MODIS_Aqua", 2020, 7, D=0, O=0)]
        label = label_unusual(target, 2020, 7, baseline_90)
        assert label.is_unusual is False
        assert label.status == "target_unavailable"
        assert label.target_rate is None

    def test_unavailable_baseline_gives_baseline_unavailable(self):
        bl = MonthBaseline(
            calendar_month=7,
            sensor="MODIS_Aqua",
            median_rate=None,
            p90_rate=None,
            n_years=0,
            eligible_years=[],
            status=BaselineStatus.INSUFFICIENT_BASELINE,
            reasons=["only 2 years"],
        )
        target = [_mo("MODIS_Aqua", 2020, 7, D=100, O=1000)]
        label = label_unusual(target, 2020, 7, bl)
        assert label.is_unusual is False
        assert label.status == "baseline_unavailable"

    def test_median_zero_p90_zero_tie_not_unusual(self):
        """
        When p90 = 0.0 and target rate = 0.0, the tie rule says not unusual.
        When target rate > 0.0, it is unusual (strictly above 0.0).
        """
        obs = [
            _mo("MODIS_Aqua", 2016, 2, D=0, O=1000),
            _mo("MODIS_Aqua", 2017, 2, D=0, O=1000),
            _mo("MODIS_Aqua", 2018, 2, D=0, O=1000),
        ]
        bl = compute_month_baseline(2, 2020, obs, AQUA_CFG)
        assert bl.status == BaselineStatus.AVAILABLE
        assert bl.median_rate == pytest.approx(0.0)
        assert bl.p90_rate == pytest.approx(0.0)

        # Target rate = 0.0: tie — not unusual
        label_zero = label_unusual(
            [_mo("MODIS_Aqua", 2020, 2, D=0, O=1000)], 2020, 2, bl
        )
        assert label_zero.is_unusual is False

        # Target rate > 0.0: unusual (strictly above 0.0)
        label_pos = label_unusual(
            [_mo("MODIS_Aqua", 2020, 2, D=1, O=1000)], 2020, 2, bl
        )
        assert label_pos.is_unusual is True


# ---------------------------------------------------------------------------
# 8.  Normal season
# ---------------------------------------------------------------------------
class TestNormalSeason:
    """
    Fixture: 12 baselines for MODIS_Aqua with known median rates.

    Peak fire months: July (month 7) and August (month 8) are highest.
    With threshold_fraction=0.25 of peak, only months with median >= 25%
    of peak qualify.

    Hand-computed fixture rates (target_year=2020):
      Jan–Mar: median  5.0  (below threshold if peak>=20)
      Apr–Jun: median 20.0
      Jul:     median 80.0  ← peak
      Aug:     median 60.0
      Sep:     median 25.0  (threshold = 0.25*80 = 20.0 → qualifies)
      Oct–Dec: median  5.0

    Qualifying months (>= 20.0): Apr, May, Jun, Jul, Aug, Sep
    Contiguous run containing Jul: Apr-Sep (months 4-9)
    peak_month = 7 (July)
    """

    def _make_baselines(self, monthly_rates: dict[int, float]) -> dict[int, MonthBaseline]:
        """Build MonthBaseline stubs with pre-set median and p90."""
        result = {}
        for m, rate in monthly_rates.items():
            result[m] = MonthBaseline(
                calendar_month=m,
                sensor="MODIS_Aqua",
                median_rate=rate,
                p90_rate=rate * 1.1,  # p90 not tested here
                n_years=5,
                eligible_years=[2015, 2016, 2017, 2018, 2019],
                status=BaselineStatus.AVAILABLE,
            )
        return result

    def test_normal_season_start_end_peak(self):
        rates = {
            1: 5.0, 2: 5.0, 3: 5.0,
            4: 20.0, 5: 20.0, 6: 20.0,
            7: 80.0, 8: 60.0, 9: 25.0,
            10: 5.0, 11: 5.0, 12: 5.0,
        }
        bls = self._make_baselines(rates)
        cfg = BaselineConfig(
            sensor="MODIS_Aqua",
            eligible_start_year=2003,
            eligible_end_year=2019,
            min_years=3,
            normal_season_threshold_fraction=0.25,
        )
        season = derive_normal_season(bls, cfg)
        assert season.status == "available"
        assert season.peak_month == 7
        # threshold = 0.25 * 80.0 = 20.0
        # qualifying: Apr(20), May(20), Jun(20), Jul(80), Aug(60), Sep(25)
        assert season.start_month == 4
        assert season.end_month == 9

    def test_no_baselines_gives_insufficient(self):
        cfg = BaselineConfig(
            sensor="MODIS_Aqua",
            eligible_start_year=2003,
            eligible_end_year=2019,
            min_years=3,
            normal_season_threshold_fraction=0.25,
        )
        season = derive_normal_season({}, cfg)
        assert season.status == "insufficient_baseline"
        assert season.peak_month is None

    def test_single_peak_month(self):
        """When only one month has a positive median, season is that month."""
        rates = {m: 0.0 for m in range(1, 13)}
        rates[8] = 50.0
        bls = self._make_baselines(rates)
        # Months with rate >= 0.25*50 = 12.5: only month 8
        cfg = BaselineConfig(
            sensor="MODIS_Aqua",
            eligible_start_year=2003,
            eligible_end_year=2019,
            min_years=3,
            normal_season_threshold_fraction=0.25,
        )
        season = derive_normal_season(bls, cfg)
        assert season.status == "available"
        assert season.peak_month == 8
        assert season.start_month == 8
        assert season.end_month == 8

    def test_year_boundary_wrap(self):
        """
        Season that spans Dec→Jan (Southern Hemisphere dry-season example):
          Peak month: January (month 1), median=80
          Qualifying: Nov(20), Dec(60), Jan(80), Feb(60), Mar(20)
          threshold = 0.25*80 = 20.0
          Contiguous run from Jan: Nov-Mar wrapping through Dec.

        Expected: start=11, end=3 (wrapping season).
        """
        rates = {m: 5.0 for m in range(1, 13)}
        rates.update({11: 20.0, 12: 60.0, 1: 80.0, 2: 60.0, 3: 20.0})
        bls = self._make_baselines(rates)
        cfg = BaselineConfig(
            sensor="MODIS_Aqua",
            eligible_start_year=2003,
            eligible_end_year=2019,
            min_years=3,
            normal_season_threshold_fraction=0.25,
        )
        season = derive_normal_season(bls, cfg)
        assert season.status == "available"
        assert season.peak_month == 1
        # Wrapping season: start=11 (Nov), end=3 (Mar)
        assert season.start_month == 11
        assert season.end_month == 3

    def test_insufficient_baseline_months_excluded_from_season(self):
        """
        Months with INSUFFICIENT_BASELINE must not contribute to season
        derivation; they are treated as unavailable.
        """
        bls: dict[int, MonthBaseline] = {}
        # July has insufficient baseline; surrounding months are available.
        for m, rate in {6: 30.0, 8: 30.0}.items():
            bls[m] = MonthBaseline(
                calendar_month=m,
                sensor="MODIS_Aqua",
                median_rate=rate,
                p90_rate=rate * 1.1,
                n_years=5,
                eligible_years=[2015, 2016, 2017, 2018, 2019],
                status=BaselineStatus.AVAILABLE,
            )
        bls[7] = MonthBaseline(
            calendar_month=7,
            sensor="MODIS_Aqua",
            median_rate=None,
            p90_rate=None,
            n_years=2,
            eligible_years=[2015, 2016],
            status=BaselineStatus.INSUFFICIENT_BASELINE,
            reasons=["only 2 years"],
        )
        cfg = BaselineConfig(
            sensor="MODIS_Aqua",
            eligible_start_year=2003,
            eligible_end_year=2019,
            min_years=3,
            normal_season_threshold_fraction=0.25,
        )
        season = derive_normal_season(bls, cfg)
        # Only June and August are available; they are not contiguous
        # (July is a gap); season may resolve to one of them or be fragmented
        assert season.status == "available"
        # peak should be one of the available months (rate=30.0 for both)
        assert season.peak_month in (6, 8)


# ---------------------------------------------------------------------------
# 9.  Cross-sensor rate isolation
# ---------------------------------------------------------------------------
class TestCrossSensorIsolation:
    """
    MODIS Aqua and VIIRS S-NPP observations must never be pooled into the
    same rate.  pooled_rate and compute_month_baseline silently accept
    mixed sensor lists (the caller is responsible for filtering), so we
    test the boundary: a baseline computed with only Aqua records must
    not be affected by VIIRS records passed alongside.
    """

    def test_baseline_ignores_wrong_sensor_records(self):
        viirs_obs = [
            _mo("VIIRS_SNPP", 2016, 7, D=9999, O=1000),
            _mo("VIIRS_SNPP", 2017, 7, D=9999, O=1000),
            _mo("VIIRS_SNPP", 2018, 7, D=9999, O=1000),
        ]
        aqua_obs = [
            _mo("MODIS_Aqua", 2016, 7, D=10, O=1000),
            _mo("MODIS_Aqua", 2017, 7, D=10, O=1000),
            _mo("MODIS_Aqua", 2018, 7, D=10, O=1000),
        ]
        bl = compute_month_baseline(7, 2020, aqua_obs + viirs_obs, AQUA_CFG)
        # Rate for each Aqua year = 10.0; median = 10.0
        assert bl.status == BaselineStatus.AVAILABLE
        assert bl.median_rate == pytest.approx(10.0)
        assert bl.n_years == 3  # only 3 Aqua years


# ---------------------------------------------------------------------------
# 10. Median = 0 edge case
# ---------------------------------------------------------------------------
class TestMedianZero:
    """
    When all baseline years have D=0 with O>0, median rate = 0 and p90 = 0.
    The plan says: 'if the median is zero, report the absolute difference only;
    percentage change is undefined.'

    This module only computes the rates; the undefined-percentage rule is
    enforced by the presentation/template layer.  We verify here that:
      - median_rate = 0.0 (not None)
      - p90_rate = 0.0 (not None)
      - status = AVAILABLE (zero is a valid observed rate)
      - Labeling still works: target rate > 0.0 is unusual (strictly above 0.0)
    """

    def test_all_zero_rates_gives_zero_median_and_p90(self):
        obs = [
            _mo("MODIS_Aqua", 2016, 2, D=0, O=1000),
            _mo("MODIS_Aqua", 2017, 2, D=0, O=1000),
            _mo("MODIS_Aqua", 2018, 2, D=0, O=1000),
        ]
        bl = compute_month_baseline(2, 2020, obs, AQUA_CFG)
        assert bl.status == BaselineStatus.AVAILABLE
        assert bl.median_rate == pytest.approx(0.0)
        assert bl.p90_rate == pytest.approx(0.0)

    def test_zero_baseline_target_above_zero_is_unusual(self):
        obs = [
            _mo("MODIS_Aqua", 2016, 2, D=0, O=1000),
            _mo("MODIS_Aqua", 2017, 2, D=0, O=1000),
            _mo("MODIS_Aqua", 2018, 2, D=0, O=1000),
        ]
        bl = compute_month_baseline(2, 2020, obs, AQUA_CFG)
        target = [_mo("MODIS_Aqua", 2020, 2, D=1, O=1000)]
        label = label_unusual(target, 2020, 2, bl)
        # 1.0 > 0.0 → unusual
        assert label.is_unusual is True
