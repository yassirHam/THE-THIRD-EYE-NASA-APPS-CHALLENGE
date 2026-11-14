"""
Unit tests for science/calendar/rates.py and science/calendar/baseline.py.

Expected values are hand-computed from the plan's equations, not copied from
the implementation.  All data below are synthetic fixtures.

Hand-checked calendar facts used here:
  2026-11-02 is a Monday; it starts ISO week 45 of 2026.
  ISO week 44 of 2026 = 2026-10-26 to 2026-11-02 00:00 UTC (ends before cutoff).
  ISO week 45 of 2026 = 2026-11-02 to 2026-11-09 (contains 15:40 UTC cutoff).
  ISO week 46 of 2026 starts 2026-11-09 (after cessation).
  2026 has 53 ISO weeks (1 January 2026 is a Thursday); 2025 has 52.
"""
from __future__ import annotations

from datetime import datetime, timezone

import pytest

from science.calendar.rates import (
    SNPP_CESSATION,
    SNPP_CESSATION_UTC,
    SNPP_LAST_COMPLETE_MONTH,
    CutoffStatus,
    PeriodObs,
    RateStatus,
    compute_rate,
    period_bounds_utc,
    pooled_rate,
)
from science.calendar.baseline import (
    BaselineConfig,
    BaselineStatus,
    MonthBaseline,
    _median,
    _nearest_rank_percentile,
    compute_month_baseline,
    compute_week_baseline,
    derive_normal_season,
    label_unusual,
    label_unusual_week,
)


def _mo(sensor, year, month, D, O, partial=False, policy="own_support"):
    return PeriodObs(sensor=sensor, year=year, D=D, O=O, month=month,
                     is_partial=partial, policy=policy)


def _wk(sensor, year, week, D, O, partial=False):
    return PeriodObs(sensor=sensor, year=year, D=D, O=O, week_number=week,
                     is_partial=partial)


def _mo_block(sensor, year, month, D, O, block_id, partial=False, policy="own_support"):
    """PeriodObs with block_id for footprint/area tests."""
    return PeriodObs(sensor=sensor, year=year, D=D, O=O, month=month,
                     is_partial=partial, policy=policy, block_id=block_id)


def _wk_block(sensor, year, week, D, O, block_id, partial=False):
    """PeriodObs with block_id for weekly footprint/area tests."""
    return PeriodObs(sensor=sensor, year=year, D=D, O=O, week_number=week,
                     is_partial=partial, block_id=block_id)


def _cfg(sensor="MODIS_Aqua", start=2016, end=2024, min_years=3,
         min_support=100, fraction=0.25, season_start=1, policy="own_support"):
    return BaselineConfig(
        sensor=sensor, eligible_start_year=start, eligible_end_year=end,
        min_years=min_years, min_support_O=min_support,
        normal_season_threshold_fraction=fraction,
        season_year_start_month=season_start, policy=policy,
    )


# ---------------------------------------------------------------------------
# PeriodObs validation
# ---------------------------------------------------------------------------
class TestPeriodObs:
    def test_valid_monthly_and_weekly(self):
        assert _mo("MODIS_Aqua", 2016, 7, 10, 100).is_available
        assert _wk("VIIRS_SNPP", 2017, 32, 5, 50).is_available

    def test_O_zero_is_unavailable(self):
        assert not _mo("MODIS_Aqua", 2016, 7, 0, 0).is_available

    def test_O_zero_D_positive_raises(self):
        with pytest.raises(ValueError, match="O = 0"):
            _mo("MODIS_Aqua", 2016, 7, 5, 0)

    def test_negative_counts_raise(self):
        with pytest.raises(ValueError, match="D must be"):
            _mo("MODIS_Aqua", 2016, 7, -1, 100)
        with pytest.raises(ValueError, match="O must be"):
            _mo("MODIS_Aqua", 2016, 7, 0, -1)

    def test_month_or_week_required_exclusively(self):
        with pytest.raises(ValueError, match="month or week_number"):
            PeriodObs(sensor="MODIS_Aqua", year=2016, D=5, O=100)
        with pytest.raises(ValueError, match="not both"):
            PeriodObs(sensor="MODIS_Aqua", year=2016, D=5, O=100,
                      month=7, week_number=28)

    def test_invalid_iso_week_raises(self):
        # 2025 has 52 ISO weeks
        with pytest.raises(ValueError, match="not a valid ISO week"):
            _wk("MODIS_Aqua", 2025, 53, 0, 100)

    def test_week_53_valid_in_2026(self):
        assert _wk("MODIS_Aqua", 2026, 53, 0, 100).is_available


# ---------------------------------------------------------------------------
# Period bounds
# ---------------------------------------------------------------------------
class TestPeriodBounds:
    def test_month_bounds(self):
        s, e = period_bounds_utc(2026, month=11)
        assert s == datetime(2026, 11, 1, tzinfo=timezone.utc)
        assert e == datetime(2026, 12, 1, tzinfo=timezone.utc)

    def test_december_rolls_year(self):
        s, e = period_bounds_utc(2026, month=12)
        assert e == datetime(2027, 1, 1, tzinfo=timezone.utc)

    def test_iso_week_45_2026(self):
        s, e = period_bounds_utc(2026, week_number=45)
        assert s == datetime(2026, 11, 2, tzinfo=timezone.utc)
        assert e == datetime(2026, 11, 9, tzinfo=timezone.utc)

    def test_iso_week_1_2026_starts_in_2025(self):
        # 1 Jan 2026 is Thursday -> ISO week 1 starts Monday 29 Dec 2025
        s, _ = period_bounds_utc(2026, week_number=1)
        assert s == datetime(2025, 12, 29, tzinfo=timezone.utc)


# ---------------------------------------------------------------------------
# S-NPP cutoff enforced from record bounds (finding 1)
# ---------------------------------------------------------------------------
class TestSnppCutoffEnforced:
    def test_constants(self):
        assert SNPP_CESSATION_UTC == "2026-11-02T15:40:00Z"
        assert SNPP_CESSATION == datetime(2026, 11, 2, 15, 40, tzinfo=timezone.utc)
        assert SNPP_LAST_COMPLETE_MONTH == (2026, 10)

    def test_unflagged_november_2026_is_partial(self):
        o = _mo("VIIRS_SNPP", 2026, 11, D=50, O=1000)  # is_partial not set
        assert o.cutoff_status == CutoffStatus.PARTIAL
        assert not o.is_available
        r = compute_rate(o)
        assert r.status == RateStatus.PARTIAL_MONTH
        assert r.fire_activity_index is None

    def test_october_2026_is_complete(self):
        o = _mo("VIIRS_SNPP", 2026, 10, D=50, O=1000)
        assert o.cutoff_status == CutoffStatus.COMPLETE
        assert compute_rate(o).fire_activity_index == pytest.approx(50.0)

    def test_december_2026_is_after_cessation(self):
        o = _mo("VIIRS_SNPP", 2026, 12, D=0, O=1000)
        assert o.cutoff_status == CutoffStatus.AFTER_CESSATION
        r = compute_rate(o)
        assert r.status == RateStatus.AFTER_CESSATION
        assert r.fire_activity_index is None

    def test_2027_is_after_cessation(self):
        for m in (1, 6, 12):
            assert _mo("VIIRS_SNPP", 2027, m, 0, 10).is_after_cessation

    def test_weekly_cutoff_boundaries(self):
        w44 = _wk("VIIRS_SNPP", 2026, 44, D=10, O=100)
        w45 = _wk("VIIRS_SNPP", 2026, 45, D=10, O=100)
        w46 = _wk("VIIRS_SNPP", 2026, 46, D=10, O=100)
        assert w44.cutoff_status == CutoffStatus.COMPLETE
        assert compute_rate(w44).fire_activity_index == pytest.approx(100.0)
        assert w45.cutoff_status == CutoffStatus.PARTIAL
        assert compute_rate(w45).status == RateStatus.PARTIAL_WEEK
        assert w46.cutoff_status == CutoffStatus.AFTER_CESSATION
        assert compute_rate(w46).status == RateStatus.AFTER_CESSATION

    def test_cutoff_not_applied_to_other_sensors(self):
        aqua = _mo("MODIS_Aqua", 2026, 11, D=50, O=1000)
        noaa = _mo("VIIRS_NOAA20", 2026, 12, D=50, O=1000)
        assert aqua.cutoff_status == CutoffStatus.NOT_APPLICABLE
        assert noaa.cutoff_status == CutoffStatus.NOT_APPLICABLE
        assert compute_rate(aqua).fire_activity_index == pytest.approx(50.0)
        assert compute_rate(noaa).fire_activity_index == pytest.approx(50.0)

    def test_caller_flag_cannot_make_snpp_partial_complete(self):
        o = _mo("VIIRS_SNPP", 2026, 11, D=50, O=1000, partial=False)
        assert o.is_period_partial

    def test_pooled_rate_excludes_unflagged_partial_snpp(self):
        # Only Oct 2026 contributes: 1000 * 50 / 500 = 100.0
        obs = [_mo("VIIRS_SNPP", 2026, 10, 50, 500),
               _mo("VIIRS_SNPP", 2026, 11, 999, 9999)]
        assert pooled_rate(obs) == pytest.approx(100.0)

    def test_caller_flagged_partial_month_other_sensor(self):
        r = compute_rate(_mo("MODIS_Aqua", 2026, 11, 5, 100, partial=True))
        assert r.status == RateStatus.PARTIAL_MONTH
        assert r.fire_activity_index is None


# ---------------------------------------------------------------------------
# compute_rate and pooled_rate
# ---------------------------------------------------------------------------
class TestRates:
    def test_rate(self):
        # 1000 * 50 / 500 = 100.0
        assert compute_rate(_mo("MODIS_Aqua", 2016, 7, 50, 500)).fire_activity_index == pytest.approx(100.0)

    def test_valid_zero_detection(self):
        r = compute_rate(_mo("MODIS_Aqua", 2016, 7, 0, 1000))
        assert r.status == RateStatus.AVAILABLE
        assert r.fire_activity_index == pytest.approx(0.0)

    def test_O_zero_unavailable(self):
        r = compute_rate(_mo("VIIRS_SNPP", 2017, 8, 0, 0))
        assert r.status == RateStatus.UNAVAILABLE
        assert r.fire_activity_index is None

    def test_sums_before_division(self):
        # (10/900, 10/100) -> pooled 1000*20/1000 = 20.0, not mean-of-rates 55.6
        obs = [_mo("MODIS_Aqua", 2016, 7, 10, 900), _mo("MODIS_Aqua", 2016, 7, 10, 100)]
        assert pooled_rate(obs) == pytest.approx(20.0)

    def test_all_unavailable_and_empty(self):
        assert pooled_rate([_mo("MODIS_Aqua", 2016, 7, 0, 0)]) is None
        assert pooled_rate([]) is None


# ---------------------------------------------------------------------------
# Same-sensor / same-policy enforcement (finding 3)
# ---------------------------------------------------------------------------
class TestPoolingHomogeneity:
    def test_mixed_sensors_raise(self):
        with pytest.raises(ValueError, match="mixed sensors"):
            pooled_rate([_mo("MODIS_Aqua", 2016, 7, 10, 100),
                         _mo("VIIRS_SNPP", 2016, 7, 10, 100)])

    def test_mixed_policies_raise(self):
        with pytest.raises(ValueError, match="mixed policies"):
            pooled_rate([_mo("MODIS_Aqua", 2016, 7, 10, 100),
                         _mo("MODIS_Aqua", 2016, 7, 10, 100, policy="common_support")])

    def test_mixed_period_types_raise(self):
        with pytest.raises(ValueError, match="monthly and weekly"):
            pooled_rate([_mo("MODIS_Aqua", 2016, 7, 10, 100),
                         _wk("MODIS_Aqua", 2016, 28, 10, 100)])

    def test_baseline_filters_other_sensor_and_policy(self):
        aqua = [_mo("MODIS_Aqua", y, 7, 10, 1000) for y in (2016, 2017, 2018)]
        noise = ([_mo("VIIRS_SNPP", y, 7, 999, 1000) for y in (2016, 2017, 2018)]
                 + [_mo("MODIS_Aqua", y, 7, 999, 1000, policy="common_support")
                    for y in (2016, 2017, 2018)])
        bl = compute_month_baseline(7, 2019, aqua + noise, _cfg())
        assert bl.status == BaselineStatus.AVAILABLE
        assert bl.median_rate == pytest.approx(10.0)
        assert bl.n_years == 3


# ---------------------------------------------------------------------------
# Median and percentile (finding 4)
# ---------------------------------------------------------------------------
class TestStatistics:
    """
    Conventional median: [5]->5; [3,7]->5; [1,2,3]->2; [1,2,3,4]->2.5;
                         [10,50,80,90]->65.
    Nearest-rank p90, rank = ceil(0.9 n): n=1->1, 2->2, 3->3, 4->4, 5->5, 10->9.
    """

    @pytest.mark.parametrize("vals,expected", [
        ([5.0], 5.0), ([3.0, 7.0], 5.0), ([1.0, 2.0, 3.0], 2.0),
        ([1.0, 2.0, 3.0, 4.0], 2.5), ([10.0, 50.0, 80.0, 90.0], 65.0),
    ])
    def test_median(self, vals, expected):
        assert _median(vals) == pytest.approx(expected)

    @pytest.mark.parametrize("vals,expected", [
        ([10.0], 10.0), ([10.0, 20.0], 20.0), ([10.0, 20.0, 30.0], 30.0),
        ([10.0, 20.0, 30.0, 40.0, 50.0], 50.0),
        ([float(10 * k) for k in range(1, 11)], 90.0),
    ])
    def test_p90_nearest_rank(self, vals, expected):
        assert _nearest_rank_percentile(vals, 90.0) == pytest.approx(expected)


# ---------------------------------------------------------------------------
# PeriodObs with block_id (finding 1)
# ---------------------------------------------------------------------------
class TestPeriodObsBlock:
    def test_block_id_optional(self):
        # Without block_id
        o1 = _mo("MODIS_Aqua", 2016, 7, 10, 100)
        assert o1.block_id is None
        # With block_id
        o2 = _mo_block("MODIS_Aqua", 2016, 7, 10, 100, "BLOCK_A")
        assert o2.block_id == "BLOCK_A"

    def test_pooled_rate_with_required_blocks(self):
        # Two blocks, each with O > 0 -> should succeed
        obs = [
            _mo_block("MODIS_Aqua", 2016, 7, 10, 60, "BLOCK_A"),
            _mo_block("MODIS_Aqua", 2016, 7, 10, 40, "BLOCK_B"),
        ]
        result = pooled_rate(obs, required_blocks=("BLOCK_A", "BLOCK_B"))
        # Total: 20 / 100 * 1000 = 200.0
        assert result == pytest.approx(200.0)

    def test_pooled_rate_missing_block_returns_none(self):
        # Missing BLOCK_B
        obs = [
            _mo_block("MODIS_Aqua", 2016, 7, 10, 100, "BLOCK_A"),
        ]
        result = pooled_rate(obs, required_blocks=("BLOCK_A", "BLOCK_B"))
        assert result is None

    def test_pooled_rate_block_with_O_zero_returns_none(self):
        # BLOCK_B has O=0
        obs = [
            _mo_block("MODIS_Aqua", 2016, 7, 10, 100, "BLOCK_A"),
            _mo_block("MODIS_Aqua", 2016, 7, 0, 0, "BLOCK_B"),
        ]
        result = pooled_rate(obs, required_blocks=("BLOCK_A", "BLOCK_B"))
        assert result is None


# ---------------------------------------------------------------------------
# Monthly baseline: required years (finding 2)
# ---------------------------------------------------------------------------
class TestMonthBaseline:
    """
    Config: eligible 2016-2024, min_years 3, min_support_O 100.
    Target 2020 -> required years 2016, 2017, 2018, 2019.
    Asymmetric fixture rates: 10, 50, 80, 90 -> median 65.0, p90 90.0.
    """

    @pytest.fixture()
    def asym(self):
        return [_mo("MODIS_Aqua", y, 7, d, 1000)
                for y, d in ((2016, 10), (2017, 50), (2018, 80), (2019, 90))]

    def test_available_baseline(self, asym):
        bl = compute_month_baseline(7, 2020, asym, _cfg())
        assert bl.status == BaselineStatus.AVAILABLE
        assert bl.required_years == [2016, 2017, 2018, 2019]
        assert bl.median_rate == pytest.approx(65.0)
        assert bl.p90_rate == pytest.approx(90.0)
        assert bl.missing_years == []

    def test_absent_required_year_makes_baseline_unavailable(self, asym):
        # Drop 2017: three years remain (>= min_years), but 2017 is required.
        obs = [o for o in asym if o.year != 2017]
        bl = compute_month_baseline(7, 2020, obs, _cfg())
        assert bl.status == BaselineStatus.MISSING_REQUIRED_YEARS
        assert bl.missing_years == [2017]
        assert bl.median_rate is None and bl.p90_rate is None

    def test_O_zero_required_year_makes_baseline_unavailable(self, asym):
        obs = [o for o in asym if o.year != 2018] + [_mo("MODIS_Aqua", 2018, 7, 0, 0)]
        bl = compute_month_baseline(7, 2020, obs, _cfg())
        assert bl.status == BaselineStatus.MISSING_REQUIRED_YEARS
        assert bl.missing_years == [2018]

    def test_under_supported_year_makes_baseline_unavailable(self, asym):
        obs = [o for o in asym if o.year != 2019] + [_mo("MODIS_Aqua", 2019, 7, 1, 50)]
        bl = compute_month_baseline(7, 2020, obs, _cfg(min_support=100))
        assert bl.status == BaselineStatus.MISSING_REQUIRED_YEARS
        assert bl.missing_years == [2019]

    def test_support_summed_across_blocks(self, asym):
        # 2019 split into two blocks of O=60: summed 120 >= 100 -> supported.
        # Rate 1000*(54+54)/120 = 900.0
        obs = [o for o in asym if o.year != 2019] + [
            _mo("MODIS_Aqua", 2019, 7, 54, 60), _mo("MODIS_Aqua", 2019, 7, 54, 60)]
        bl = compute_month_baseline(7, 2020, obs, _cfg(min_support=100))
        assert bl.status == BaselineStatus.AVAILABLE
        # rates 10, 50, 80, 900 -> median (50+80)/2 = 65.0, p90 = 900.0
        assert bl.median_rate == pytest.approx(65.0)
        assert bl.p90_rate == pytest.approx(900.0)

    def test_partial_required_year_makes_baseline_unavailable(self, asym):
        obs = [o for o in asym if o.year != 2016] + [_mo("MODIS_Aqua", 2016, 7, 10, 1000, partial=True)]
        bl = compute_month_baseline(7, 2020, obs, _cfg())
        assert bl.status == BaselineStatus.MISSING_REQUIRED_YEARS
        assert bl.missing_years == [2016]

    def test_short_span_is_insufficient(self):
        # Target 2018 -> required 2016, 2017 -> 2 < 3
        obs = [_mo("MODIS_Aqua", y, 7, 10, 1000) for y in (2016, 2017, 2018)]
        bl = compute_month_baseline(7, 2018, obs, _cfg())
        assert bl.status == BaselineStatus.INSUFFICIENT_BASELINE
        assert bl.required_years == [2016, 2017]

    def test_target_and_later_years_never_enter(self, asym):
        extra = [_mo("MODIS_Aqua", y, 7, 999, 1000) for y in (2020, 2021, 2022)]
        bl = compute_month_baseline(7, 2020, asym + extra, _cfg())
        assert bl.eligible_years == [2016, 2017, 2018, 2019]
        assert bl.median_rate == pytest.approx(65.0)

    def test_eligible_end_year_caps_span(self):
        # Target 2022, end 2019 -> required 2016-2019 only
        obs = [_mo("MODIS_Aqua", y, 7, 10, 1000) for y in range(2016, 2022)]
        bl = compute_month_baseline(7, 2022, obs, _cfg(end=2019))
        assert bl.required_years == [2016, 2017, 2018, 2019]
        assert bl.status == BaselineStatus.AVAILABLE

    def test_snpp_baseline_rejects_unflagged_partial_year(self):
        # Target 2027, VIIRS_SNPP, Nov: required 2016-2026; 2026-11 is partial.
        obs = [_mo("VIIRS_SNPP", y, 11, 10, 1000) for y in range(2016, 2027)]
        bl = compute_month_baseline(11, 2027, obs, _cfg(sensor="VIIRS_SNPP", end=2026))
        assert bl.status == BaselineStatus.MISSING_REQUIRED_YEARS
        assert bl.missing_years == [2026]

    def test_config_rejects_bad_values(self):
        with pytest.raises(ValueError):
            _cfg(min_support=0)
        with pytest.raises(ValueError):
            _cfg(fraction=0.0)
        with pytest.raises(ValueError):
            _cfg(season_start=13)

    def test_block_completeness_required_for_baseline(self):
        # Prepare observations with all required years and block support
        # Each year has both BLOCK_A and BLOCK_B
        obs = [
            _mo_block("MODIS_Aqua", 2016, 7, 10, 500, "BLOCK_A"),
            _mo_block("MODIS_Aqua", 2016, 7, 10, 500, "BLOCK_B"),
            _mo_block("MODIS_Aqua", 2017, 7, 50, 500, "BLOCK_A"),
            _mo_block("MODIS_Aqua", 2017, 7, 50, 500, "BLOCK_B"),
            _mo_block("MODIS_Aqua", 2018, 7, 80, 500, "BLOCK_A"),
            _mo_block("MODIS_Aqua", 2018, 7, 80, 500, "BLOCK_B"),
            _mo_block("MODIS_Aqua", 2019, 7, 54, 60, "BLOCK_A"),
            _mo_block("MODIS_Aqua", 2019, 7, 54, 60, "BLOCK_B"),
        ]
        # Without required_blocks, should work (summed O=5600 >= 100)
        bl = compute_month_baseline(7, 2020, obs, _cfg(min_support=100))
        assert bl.status == BaselineStatus.AVAILABLE
        
        # With required_blocks, both must be present with O > 0
        bl = compute_month_baseline(7, 2020, obs, _cfg(min_support=100),
                                     required_blocks=("BLOCK_A", "BLOCK_B"))
        assert bl.status == BaselineStatus.AVAILABLE
        
        # Missing BLOCK_B in all years -> unavailable for each year
        obs_no_b = [o for o in obs if o.block_id != "BLOCK_B"]
        bl = compute_month_baseline(7, 2020, obs_no_b, _cfg(min_support=100),
                                     required_blocks=("BLOCK_A", "BLOCK_B"))
        assert bl.status == BaselineStatus.MISSING_REQUIRED_YEARS
        assert bl.missing_years == [2016, 2017, 2018, 2019]

    def test_block_with_O_zero_makes_baseline_unavailable(self):
        # Prepare observations with all required years
        # BLOCK_B has O=0 for all years
        obs = [
            _mo_block("MODIS_Aqua", 2016, 7, 10, 500, "BLOCK_A"),
            _mo_block("MODIS_Aqua", 2016, 7, 0, 0, "BLOCK_B"),
            _mo_block("MODIS_Aqua", 2017, 7, 50, 500, "BLOCK_A"),
            _mo_block("MODIS_Aqua", 2017, 7, 0, 0, "BLOCK_B"),
            _mo_block("MODIS_Aqua", 2018, 7, 80, 500, "BLOCK_A"),
            _mo_block("MODIS_Aqua", 2018, 7, 0, 0, "BLOCK_B"),
            _mo_block("MODIS_Aqua", 2019, 7, 54, 60, "BLOCK_A"),
            _mo_block("MODIS_Aqua", 2019, 7, 0, 0, "BLOCK_B"),
        ]
        bl = compute_month_baseline(7, 2020, obs, _cfg(min_support=100),
                                     required_blocks=("BLOCK_A", "BLOCK_B"))
        assert bl.status == BaselineStatus.MISSING_REQUIRED_YEARS
        assert bl.missing_years == [2016, 2017, 2018, 2019]


# ---------------------------------------------------------------------------
# Unusual labels
# ---------------------------------------------------------------------------
class TestLabelUnusual:
    @pytest.fixture()
    def bl(self):
        obs = [_mo("MODIS_Aqua", y, 7, d, 1000)
               for y, d in ((2016, 10), (2017, 50), (2018, 80), (2019, 90))]
        return compute_month_baseline(7, 2020, obs, _cfg())  # p90 = 90.0

    def test_strictly_above(self, bl):
        lab = label_unusual([_mo("MODIS_Aqua", 2020, 7, 91, 1000)], 2020, 7, bl)
        assert lab.status == "labeled" and lab.is_unusual

    def test_tie_not_unusual(self, bl):
        lab = label_unusual([_mo("MODIS_Aqua", 2020, 7, 90, 1000)], 2020, 7, bl)
        assert lab.status == "labeled" and not lab.is_unusual

    def test_target_O_zero(self, bl):
        lab = label_unusual([_mo("MODIS_Aqua", 2020, 7, 0, 0)], 2020, 7, bl)
        assert lab.status == "target_unavailable" and lab.target_rate is None

    def test_target_under_support(self, bl):
        lab = label_unusual([_mo("MODIS_Aqua", 2020, 7, 10, 50)], 2020, 7, bl)
        assert lab.status == "target_insufficient_support" and not lab.is_unusual

    def test_target_partial(self, bl):
        lab = label_unusual([_mo("MODIS_Aqua", 2020, 7, 99, 1000, partial=True)], 2020, 7, bl)
        assert lab.status == "target_partial" and not lab.is_unusual

    def test_unflagged_snpp_november_2026_target_is_partial(self):
        obs = [_mo("VIIRS_SNPP", y, 11, 10, 1000) for y in range(2016, 2026)]
        bl = compute_month_baseline(11, 2026, obs, _cfg(sensor="VIIRS_SNPP"))
        assert bl.status == BaselineStatus.AVAILABLE
        lab = label_unusual([_mo("VIIRS_SNPP", 2026, 11, 500, 1000)], 2026, 11, bl)
        assert lab.status == "target_partial" and not lab.is_unusual

    def test_unavailable_baseline(self):
        bl = compute_month_baseline(7, 2020, [], _cfg())
        lab = label_unusual([_mo("MODIS_Aqua", 2020, 7, 99, 1000)], 2020, 7, bl)
        assert lab.status == "baseline_unavailable" and not lab.is_unusual

    def test_baseline_target_mismatch_raises(self, bl):
        with pytest.raises(ValueError, match="computed for"):
            label_unusual([_mo("MODIS_Aqua", 2021, 7, 99, 1000)], 2021, 7, bl)

    def test_block_completeness_required_for_label(self, bl):
        # Test that label_unusual respects required_blocks
        # Target rate 100 > p90=90 -> unusual if blocks are complete
        target = [
            _mo_block("MODIS_Aqua", 2020, 7, 91, 60, "BLOCK_A"),
            _mo_block("MODIS_Aqua", 2020, 7, 91, 40, "BLOCK_B"),
        ]
        lab = label_unusual(target, 2020, 7, bl, required_blocks=("BLOCK_A", "BLOCK_B"))
        # Rate = 1000 * 182 / 100 = 1820.0 > 90 -> unusual
        assert lab.status == "labeled" and lab.is_unusual and lab.target_rate == pytest.approx(1820.0)
        
        # Missing BLOCK_B -> unavailable for label
        target_no_b = [o for o in target if o.block_id != "BLOCK_B"]
        lab = label_unusual(target_no_b, 2020, 7, bl, required_blocks=("BLOCK_A", "BLOCK_B"))
        assert lab.status == "target_unavailable" and not lab.is_unusual


# ---------------------------------------------------------------------------
# Weekly baseline (finding 2)
# ---------------------------------------------------------------------------
class TestWeekBaseline:
    """
    Weekly baseline follows the same rules as monthly baseline.
    Config: eligible 2016-2024, min_years 3, min_support_O 100.
    Target 2020 week 28 -> required years 2016, 2017, 2018, 2019.
    Asymmetric fixture rates: 10, 50, 80, 90 -> median 65.0, p90 90.0.
    """
    
    @pytest.fixture()
    def asym_weekly(self):
        # Week 28 in 2026 starts 2026-07-13 (Monday)
        return [_wk("MODIS_Aqua", y, 28, d, 1000)
                for y, d in ((2016, 10), (2017, 50), (2018, 80), (2019, 90))]

    def test_available_weekly_baseline(self, asym_weekly):
        bl = compute_week_baseline(28, 2020, asym_weekly, _cfg())
        assert bl.status == BaselineStatus.AVAILABLE
        assert bl.required_years == [2016, 2017, 2018, 2019]
        assert bl.calendar_month == 28  # Week number stored in calendar_month
        assert bl.median_rate == pytest.approx(65.0)
        assert bl.p90_rate == pytest.approx(90.0)
        assert bl.missing_years == []

    def test_absent_required_year_makes_weekly_baseline_unavailable(self, asym_weekly):
        # Drop 2017
        obs = [o for o in asym_weekly if o.year != 2017]
        bl = compute_week_baseline(28, 2020, obs, _cfg())
        assert bl.status == BaselineStatus.MISSING_REQUIRED_YEARS
        assert bl.missing_years == [2017]
        assert bl.median_rate is None and bl.p90_rate is None

    def test_O_zero_required_year_makes_weekly_baseline_unavailable(self, asym_weekly):
        obs = [o for o in asym_weekly if o.year != 2018] + [_wk("MODIS_Aqua", 2018, 28, 0, 0)]
        bl = compute_week_baseline(28, 2020, obs, _cfg())
        assert bl.status == BaselineStatus.MISSING_REQUIRED_YEARS
        assert bl.missing_years == [2018]

    def test_under_supported_year_makes_weekly_baseline_unavailable(self, asym_weekly):
        obs = [o for o in asym_weekly if o.year != 2019] + [_wk("MODIS_Aqua", 2019, 28, 1, 50)]
        bl = compute_week_baseline(28, 2020, obs, _cfg(min_support=100))
        assert bl.status == BaselineStatus.MISSING_REQUIRED_YEARS
        assert bl.missing_years == [2019]

    def test_partial_required_year_makes_weekly_baseline_unavailable(self, asym_weekly):
        obs = [o for o in asym_weekly if o.year != 2016] + [_wk("MODIS_Aqua", 2016, 28, 10, 1000, partial=True)]
        bl = compute_week_baseline(28, 2020, obs, _cfg())
        assert bl.status == BaselineStatus.MISSING_REQUIRED_YEARS
        assert bl.missing_years == [2016]

    def test_short_span_is_insufficient_weekly(self):
        # Target 2018 -> required 2016, 2017 -> 2 < 3
        obs = [_wk("MODIS_Aqua", y, 28, 10, 1000) for y in (2016, 2017, 2018)]
        bl = compute_week_baseline(28, 2018, obs, _cfg())
        assert bl.status == BaselineStatus.INSUFFICIENT_BASELINE
        assert bl.required_years == [2016, 2017]

    def test_invalid_week_number_raises(self):
        with pytest.raises(ValueError, match="must be 1-53"):
            compute_week_baseline(0, 2020, [], _cfg())
        with pytest.raises(ValueError, match="not a valid ISO week"):
            compute_week_baseline(53, 2025, [], _cfg())  # 2025 has 52 weeks


class TestLabelUnusualWeek:
    """Weekly version of label_unusual tests."""

    @pytest.fixture()
    def bl_week(self):
        obs = [_wk("MODIS_Aqua", y, 28, d, 1000)
               for y, d in ((2016, 10), (2017, 50), (2018, 80), (2019, 90))]
        return compute_week_baseline(28, 2020, obs, _cfg())  # p90 = 90.0

    def test_strictly_above(self, bl_week):
        lab = label_unusual_week([_wk("MODIS_Aqua", 2020, 28, 91, 1000)], 2020, 28, bl_week)
        assert lab.status == "labeled" and lab.is_unusual

    def test_tie_not_unusual(self, bl_week):
        lab = label_unusual_week([_wk("MODIS_Aqua", 2020, 28, 90, 1000)], 2020, 28, bl_week)
        assert lab.status == "labeled" and not lab.is_unusual

    def test_target_O_zero(self, bl_week):
        lab = label_unusual_week([_wk("MODIS_Aqua", 2020, 28, 0, 0)], 2020, 28, bl_week)
        assert lab.status == "target_unavailable" and lab.target_rate is None

    def test_target_under_support(self, bl_week):
        lab = label_unusual_week([_wk("MODIS_Aqua", 2020, 28, 10, 50)], 2020, 28, bl_week)
        assert lab.status == "target_insufficient_support" and not lab.is_unusual

    def test_target_partial(self, bl_week):
        lab = label_unusual_week([_wk("MODIS_Aqua", 2020, 28, 99, 1000, partial=True)], 2020, 28, bl_week)
        assert lab.status == "target_partial" and not lab.is_unusual

    def test_unavailable_baseline(self):
        bl = compute_week_baseline(28, 2020, [], _cfg())
        lab = label_unusual_week([_wk("MODIS_Aqua", 2020, 28, 99, 1000)], 2020, 28, bl)
        assert lab.status == "baseline_unavailable" and not lab.is_unusual

    def test_baseline_target_mismatch_raises(self, bl_week):
        with pytest.raises(ValueError, match="computed for"):
            label_unusual_week([_wk("MODIS_Aqua", 2020, 29, 99, 1000)], 2020, 29, bl_week)

    def test_block_completeness_for_weekly(self, bl_week):
        # With block_id
        target = [
            _wk_block("MODIS_Aqua", 2020, 28, 91, 60, "BLOCK_A"),
            _wk_block("MODIS_Aqua", 2020, 28, 91, 40, "BLOCK_B"),
        ]
        lab = label_unusual_week(target, 2020, 28, bl_week, required_blocks=("BLOCK_A", "BLOCK_B"))
        assert lab.status == "labeled" and lab.is_unusual
        
        # Missing BLOCK_B
        target_no_b = [o for o in target if o.block_id != "BLOCK_B"]
        lab = label_unusual_week(target_no_b, 2020, 28, bl_week, required_blocks=("BLOCK_A", "BLOCK_B"))
        assert lab.status == "target_unavailable" and not lab.is_unusual

    def test_weekly_baseline_with_blocks(self):
        # Prepare observations with all required years and block support
        # Each year has both BLOCK_A and BLOCK_B with O=500 each (total O=1000)
        obs = [
            _wk_block("MODIS_Aqua", 2016, 28, 10, 500, "BLOCK_A"),
            _wk_block("MODIS_Aqua", 2016, 28, 10, 500, "BLOCK_B"),
            _wk_block("MODIS_Aqua", 2017, 28, 50, 500, "BLOCK_A"),
            _wk_block("MODIS_Aqua", 2017, 28, 50, 500, "BLOCK_B"),
            _wk_block("MODIS_Aqua", 2018, 28, 80, 500, "BLOCK_A"),
            _wk_block("MODIS_Aqua", 2018, 28, 80, 500, "BLOCK_B"),
            _wk_block("MODIS_Aqua", 2019, 28, 54, 60, "BLOCK_A"),
            _wk_block("MODIS_Aqua", 2019, 28, 54, 60, "BLOCK_B"),
        ]
        bl = compute_week_baseline(28, 2020, obs, _cfg(min_support=100),
                                     required_blocks=("BLOCK_A", "BLOCK_B"))
        assert bl.status == BaselineStatus.AVAILABLE
        # Rates: 2016=20.0, 2017=100.0, 2018=160.0, 2019=900.0 -> median (100+160)/2=130.0
        assert bl.median_rate == pytest.approx(130.0)
        
        # Missing BLOCK_B -> unavailable
        obs_no_b = [o for o in obs if o.block_id != "BLOCK_B"]
        bl = compute_week_baseline(28, 2020, obs_no_b, _cfg(min_support=100),
                                     required_blocks=("BLOCK_A", "BLOCK_B"))
        assert bl.status == BaselineStatus.MISSING_REQUIRED_YEARS
        assert bl.missing_years == [2016, 2017, 2018, 2019]

    def test_zero_baseline(self):
        obs = [_mo("MODIS_Aqua", y, 2, 0, 1000) for y in (2016, 2017, 2018)]
        bl = compute_month_baseline(2, 2019, obs, _cfg())
        assert bl.median_rate == pytest.approx(0.0) and bl.p90_rate == pytest.approx(0.0)
        assert not label_unusual([_mo("MODIS_Aqua", 2019, 2, 0, 1000)], 2019, 2, bl).is_unusual
        assert label_unusual([_mo("MODIS_Aqua", 2019, 2, 1, 1000)], 2019, 2, bl).is_unusual


# ---------------------------------------------------------------------------
# Normal season (finding 5)
# ---------------------------------------------------------------------------
def _stub(month, median, status=BaselineStatus.AVAILABLE, sensor="MODIS_Aqua",
          target_year=2020, policy="own_support"):
    ok = status == BaselineStatus.AVAILABLE
    return MonthBaseline(
        calendar_month=month, target_year=target_year, sensor=sensor, policy=policy,
        min_support_O=100, median_rate=median if ok else None,
        p90_rate=median if ok else None, n_years=4 if ok else 0,
        eligible_years=[2016, 2017, 2018, 2019] if ok else [],
        required_years=[2016, 2017, 2018, 2019],
        missing_years=[] if ok else [2017], status=status,
    )


def _season(medians: dict[int, float], **cfg_kw):
    bls = {m: _stub(m, r) for m, r in medians.items()}
    return derive_normal_season(bls, _cfg(**cfg_kw))


class TestNormalSeason:
    BASE = {1: 5.0, 2: 5.0, 3: 5.0, 4: 20.0, 5: 20.0, 6: 20.0,
            7: 80.0, 8: 60.0, 9: 25.0, 10: 5.0, 11: 5.0, 12: 5.0}

    def test_first_and_last_qualifying(self):
        # threshold 0.25*80 = 20 -> qualifying 4..9
        s = _season(self.BASE)
        assert (s.status, s.start_month, s.end_month, s.peak_month) == ("available", 4, 9, 7)
        assert s.threshold_rate == pytest.approx(20.0)
        assert s.interior_nonqualifying_months == []

    def test_noncontiguous_uses_first_and_last_and_reports_gaps(self):
        med = {m: 1.0 for m in range(1, 13)}
        med.update({4: 30.0, 7: 100.0, 9: 40.0})  # threshold 25
        s = _season(med)
        assert (s.start_month, s.end_month, s.peak_month) == (4, 9, 7)
        assert s.interior_nonqualifying_months == [5, 6, 8]

    def test_missing_month_gives_insufficient_baseline(self):
        bls = {m: _stub(m, r) for m, r in self.BASE.items()}
        bls[2] = _stub(2, 0.0, status=BaselineStatus.MISSING_REQUIRED_YEARS)
        del bls[11]
        s = derive_normal_season(bls, _cfg())
        assert s.status == "insufficient_baseline"
        assert s.missing_months == [2, 11]
        assert s.start_month is None and s.peak_month is None

    def test_calendar_year_boundary_rule(self):
        # Qualifying {11,12,1,2,3}; season-year starts January -> span 1..12
        med = {m: 5.0 for m in range(1, 13)}
        med.update({11: 20.0, 12: 60.0, 1: 80.0, 2: 60.0, 3: 20.0})
        s = _season(med, season_start=1)
        assert (s.start_month, s.end_month, s.peak_month) == (1, 12, 1)
        assert s.interior_nonqualifying_months == [4, 5, 6, 7, 8, 9, 10]

    def test_registered_july_boundary_rule(self):
        med = {m: 5.0 for m in range(1, 13)}
        med.update({11: 20.0, 12: 60.0, 1: 80.0, 2: 60.0, 3: 20.0})
        s = _season(med, season_start=7)
        assert (s.start_month, s.end_month, s.peak_month) == (11, 3, 1)
        assert s.interior_nonqualifying_months == []

    def test_peak_tie_takes_earliest_in_order(self):
        med = {m: 1.0 for m in range(1, 13)}
        med.update({6: 50.0, 8: 50.0})
        s = _season(med)
        assert s.peak_month == 6 and s.tied_peak_months == [6, 8]
        s7 = _season(med, season_start=7)
        assert s7.peak_month == 8 and s7.tied_peak_months == [8, 6]

    def test_all_zero_medians_give_no_season(self):
        s = _season({m: 0.0 for m in range(1, 13)})
        assert s.status == "no_detected_activity" and s.start_month is None

    def test_sensor_mismatch_raises(self):
        bls = {m: _stub(m, 5.0) for m in range(1, 13)}
        bls[3] = _stub(3, 5.0, sensor="VIIRS_SNPP")
        with pytest.raises(ValueError, match="config is"):
            derive_normal_season(bls, _cfg())

    def test_mixed_target_years_raise(self):
        bls = {m: _stub(m, 5.0) for m in range(1, 13)}
        bls[3] = _stub(3, 5.0, target_year=2021)
        with pytest.raises(ValueError, match="mix target years"):
            derive_normal_season(bls, _cfg())
