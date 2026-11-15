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
         min_support=100, fraction=0.25, season_start=1, policy="own_support",
         excluded=(), sealed=()):
    # Synthetic tests only: the default has no sealed years.  Production configs
    # must pass the registered sealed window (see TestExcludedAndSealedYears).
    return BaselineConfig(
        sensor=sensor, eligible_start_year=start, eligible_end_year=end,
        min_years=min_years, min_support_O=min_support,
        normal_season_threshold_fraction=fraction,
        season_year_start_month=season_start, policy=policy,
        excluded_years=excluded, sealed_years=sealed,
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
        # Block-level records without a registered block list are rejected:
        # the analysed footprint must be registered, not inferred.
        with pytest.raises(ValueError, match="no registered"):
            compute_month_baseline(7, 2020, obs, _cfg(min_support=100))
        
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
            _mo_block("MODIS_Aqua", 2020, 7, 60, 600, "BLOCK_A"),
            _mo_block("MODIS_Aqua", 2020, 7, 40, 400, "BLOCK_B"),
        ]
        lab = label_unusual(target, 2020, 7, bl, required_blocks=("BLOCK_A", "BLOCK_B"))
        # Rate = 1000 * (60 + 40) / (600 + 400) = 100.0 > 90 -> unusual
        assert lab.status == "labeled" and lab.is_unusual and lab.target_rate == pytest.approx(100.0)
        
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
        # With block_id: rate = 1000 * (60 + 40) / (600 + 400) = 100.0 > p90 = 90
        target = [
            _wk_block("MODIS_Aqua", 2020, 28, 60, 600, "BLOCK_A"),
            _wk_block("MODIS_Aqua", 2020, 28, 40, 400, "BLOCK_B"),
        ]
        lab = label_unusual_week(target, 2020, 28, bl_week, required_blocks=("BLOCK_A", "BLOCK_B"))
        assert lab.status == "labeled" and lab.is_unusual
        assert lab.target_rate == pytest.approx(100.0)
        
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


# ===========================================================================
# Regression: block completeness (review of eb28eb2)
# Each case passed silently or gave a number under eb28eb2.
# ===========================================================================
from science.calendar.rates import block_problems  # noqa: E402
from science.calendar.baseline import (  # noqa: E402
    CriticalWeekConfig, compute_critical_weeks, label_critical_week,
)

AB = ("BLOCK_A", "BLOCK_B")


class TestBlockCompletenessRegression:
    def test_unregistered_extra_block_is_rejected(self):
        # eb28eb2 pooled C too: 1000 * 120 / 300 = 400.0, a different footprint.
        obs = [_mo_block("MODIS_Aqua", 2016, 7, 10, 100, "BLOCK_A"),
               _mo_block("MODIS_Aqua", 2016, 7, 10, 100, "BLOCK_B"),
               _mo_block("MODIS_Aqua", 2016, 7, 100, 100, "BLOCK_C")]
        with pytest.raises(ValueError, match="unregistered"):
            pooled_rate(obs, required_blocks=AB)

    def test_record_without_block_id_is_rejected(self):
        obs = [_mo_block("MODIS_Aqua", 2016, 7, 10, 100, "BLOCK_A"),
               _mo_block("MODIS_Aqua", 2016, 7, 10, 100, "BLOCK_B"),
               _mo("MODIS_Aqua", 2016, 7, 10, 100)]
        with pytest.raises(ValueError, match="unregistered or missing block_id"):
            pooled_rate(obs, required_blocks=AB)

    def test_duplicate_block_record_is_rejected(self):
        # eb28eb2 double-counted A: 1000 * 30 / 300 = 100.0
        obs = [_mo_block("MODIS_Aqua", 2016, 7, 10, 100, "BLOCK_A"),
               _mo_block("MODIS_Aqua", 2016, 7, 10, 100, "BLOCK_A"),
               _mo_block("MODIS_Aqua", 2016, 7, 10, 100, "BLOCK_B")]
        with pytest.raises(ValueError, match="more than one record"):
            pooled_rate(obs, required_blocks=AB)

    @pytest.mark.parametrize("bad", [(), ["BLOCK_A", "BLOCK_B"], ("BLOCK_A", "BLOCK_A"), ("BLOCK_A", "")])
    def test_invalid_required_blocks(self, bad):
        with pytest.raises(ValueError, match="required_blocks"):
            pooled_rate([_mo_block("MODIS_Aqua", 2016, 7, 1, 10, "BLOCK_A")], required_blocks=bad)

    def test_block_completeness_checked_per_period(self):
        # July has A and B; August lacks B.  eb28eb2 checked the union of
        # periods, saw both blocks, and returned 1000 * 40 / 400 = 100.0.
        obs = [_mo_block("MODIS_Aqua", 2016, 7, 10, 100, "BLOCK_A"),
               _mo_block("MODIS_Aqua", 2016, 7, 10, 100, "BLOCK_B"),
               _mo_block("MODIS_Aqua", 2016, 8, 20, 200, "BLOCK_A")]
        assert pooled_rate(obs, required_blocks=AB) is None
        assert block_problems(obs, AB) == ["2016-08: required block BLOCK_B missing."]

    def test_partial_block_makes_period_unavailable(self):
        obs = [_mo_block("MODIS_Aqua", 2016, 7, 10, 100, "BLOCK_A"),
               _mo_block("MODIS_Aqua", 2016, 7, 10, 100, "BLOCK_B", partial=True)]
        assert pooled_rate(obs, required_blocks=AB) is None
        assert block_problems(obs, AB) == ["2016-07: required block BLOCK_B has no usable observations."]

    def test_complete_blocks_pool_sums_before_division(self):
        # 1000 * (10 + 30) / (100 + 300) = 100.0
        obs = [_mo_block("MODIS_Aqua", 2016, 7, 10, 100, "BLOCK_A"),
               _mo_block("MODIS_Aqua", 2016, 7, 30, 300, "BLOCK_B")]
        assert block_problems(obs, AB) == []
        assert pooled_rate(obs, required_blocks=AB) == pytest.approx(100.0)

    def test_unblocked_aggregates_still_allowed(self):
        obs = [_mo("MODIS_Aqua", 2016, 7, 10, 100)]
        assert block_problems(obs, None) == []
        assert pooled_rate(obs) == pytest.approx(100.0)

    def test_baseline_and_label_reject_unregistered_block(self):
        obs = [_mo_block("MODIS_Aqua", y, 7, 10, 500, b)
               for y in (2016, 2017, 2018) for b in ("BLOCK_A", "BLOCK_B", "BLOCK_C")]
        with pytest.raises(ValueError, match="unregistered"):
            compute_month_baseline(7, 2019, obs, _cfg(), required_blocks=AB)
        good = [o for o in obs if o.block_id != "BLOCK_C"]
        bl = compute_month_baseline(7, 2019, good, _cfg(), required_blocks=AB)
        assert bl.status == BaselineStatus.AVAILABLE
        target = [_mo_block("MODIS_Aqua", 2019, 7, 10, 500, b) for b in ("BLOCK_A", "BLOCK_C")]
        with pytest.raises(ValueError, match="unregistered"):
            label_unusual(target, 2019, 7, bl, required_blocks=AB)

    def test_weekly_baseline_reason_names_period_and_block(self):
        obs = [_wk_block("MODIS_Aqua", y, 28, 10, 500, b)
               for y in (2016, 2017, 2018) for b in AB]
        obs = [o for o in obs if not (o.year == 2017 and o.block_id == "BLOCK_B")]
        bl = compute_week_baseline(28, 2019, obs, _cfg(), required_blocks=AB)
        assert bl.status == BaselineStatus.MISSING_REQUIRED_YEARS
        assert bl.missing_years == [2017]
        assert "2017: 2017-W28: required block BLOCK_B missing." in bl.reasons


# ===========================================================================
# Regression: critical weeks of the typical year (review of eb28eb2)
# ===========================================================================
class TestCriticalWeeksRegression:
    """
    Synthetic fixture, target 2019, required prior years 2016-2018, O = 1000.
    Weekly rates (1000 * D / O) per year -> conventional median:
      week 10: 10, 10, 10 -> 10
      week 11: 40, 50, 60 -> 50
      week 12: 80, 80, 80 -> 80
      week 13: 50, 50, 50 -> 50   (ties with week 11)
    Order by (-median, week): 12 (rank 1), 11 (rank 2), 13 (rank 2), 10 (rank 4).
    """
    WEEKS = (10, 11, 12, 13)
    D = {10: (10, 10, 10), 11: (40, 50, 60), 12: (80, 80, 80), 13: (50, 50, 50)}

    def _obs(self, drop=None):
        out = []
        for w, ds in self.D.items():
            for y, d in zip((2016, 2017, 2018), ds):
                if drop != (y, w):
                    out.append(_wk("MODIS_Aqua", y, w, d, 1000))
        return out

    def _cw(self, n, tie):
        return CriticalWeekConfig(n_busiest_weeks=n, ranked_weeks=self.WEEKS, tie_rule=tie)

    def test_ranking_and_include_all_tied(self):
        r = compute_critical_weeks(2019, self._obs(), _cfg(), self._cw(2, "include_all_tied"))
        assert r.status == "available"
        assert r.ranking == [(12, 80.0, 1), (11, 50.0, 2), (13, 50.0, 2), (10, 10.0, 4)]
        assert r.critical_weeks == [12, 11, 13]
        assert r.cutoff_rate == pytest.approx(50.0)
        assert r.tied_at_cutoff == [11, 13]

    def test_lower_week_number_first(self):
        r = compute_critical_weeks(2019, self._obs(), _cfg(), self._cw(2, "lower_week_number_first"))
        assert r.critical_weeks == [12, 11]
        assert r.tied_at_cutoff == [11, 13]

    def test_single_busiest_week(self):
        r = compute_critical_weeks(2019, self._obs(), _cfg(), self._cw(1, "include_all_tied"))
        assert r.critical_weeks == [12] and r.tied_at_cutoff == [12]

    def test_target_year_outcomes_never_enter(self):
        # eb28eb2 ranked the target year's own weeks.  Extreme and partial 2019
        # records must not change the typical-year result.
        noise = [_wk("MODIS_Aqua", 2019, 10, 999, 1000),
                 _wk("MODIS_Aqua", 2019, 11, 5, 100, partial=True)]
        base = compute_critical_weeks(2019, self._obs(), _cfg(), self._cw(2, "include_all_tied"))
        with_noise = compute_critical_weeks(2019, self._obs() + noise, _cfg(),
                                            self._cw(2, "include_all_tied"))
        assert with_noise.critical_weeks == base.critical_weeks == [12, 11, 13]
        assert with_noise.ranking == base.ranking

    def test_missing_week_blocks_result(self):
        # Week 13 missing for 2017: no critical set over a reduced list.
        r = compute_critical_weeks(2019, self._obs(drop=(2017, 13)), _cfg(),
                                   self._cw(2, "include_all_tied"))
        assert r.status == "insufficient_baseline"
        assert r.missing_weeks == [13] and r.critical_weeks == []

    def test_missing_block_blocks_result(self):
        obs = [_wk_block("MODIS_Aqua", y, w, d // 2, 500, b)
               for w, ds in self.D.items() for y, d in zip((2016, 2017, 2018), ds) for b in AB]
        obs = [o for o in obs if not (o.year == 2016 and o.week_number == 12 and o.block_id == "BLOCK_B")]
        r = compute_critical_weeks(2019, obs, _cfg(), self._cw(2, "include_all_tied"), required_blocks=AB)
        assert r.status == "insufficient_baseline" and r.missing_weeks == [12]

    def test_all_zero_gives_no_activity(self):
        obs = [_wk("MODIS_Aqua", y, w, 0, 1000) for w in self.WEEKS for y in (2016, 2017, 2018)]
        r = compute_critical_weeks(2019, obs, _cfg(), self._cw(2, "include_all_tied"))
        assert r.status == "no_detected_activity" and r.critical_weeks == []

    def test_labels(self):
        r = compute_critical_weeks(2019, self._obs(), _cfg(), self._cw(2, "include_all_tied"))
        lab13 = label_critical_week(13, r)
        assert (lab13.is_critical, lab13.rank, lab13.typical_rate, lab13.status) == (True, 2, 50.0, "labeled")
        lab10 = label_critical_week(10, r)
        assert (lab10.is_critical, lab10.rank) == (False, 4)
        assert label_critical_week(30, r).status == "not_ranked"
        bad = compute_critical_weeks(2019, self._obs(drop=(2017, 13)), _cfg(), self._cw(2, "include_all_tied"))
        lab = label_critical_week(12, bad)
        assert lab.status == "unavailable" and not lab.is_critical

    def test_week_53_not_valid_for_52_week_target(self):
        # 2019 has 52 ISO weeks; registering week 53 is rejected, not skipped.
        cw = CriticalWeekConfig(n_busiest_weeks=1, ranked_weeks=(52, 53), tie_rule="include_all_tied")
        with pytest.raises(ValueError, match="not a valid ISO week"):
            compute_critical_weeks(2019, self._obs(), _cfg(), cw)

    def test_config_has_no_defaults(self):
        with pytest.raises(TypeError):
            CriticalWeekConfig(ranked_weeks=(1, 2))  # type: ignore[call-arg]

    @pytest.mark.parametrize("kw", [
        dict(n_busiest_weeks=0, ranked_weeks=(1, 2), tie_rule="include_all_tied"),
        dict(n_busiest_weeks=3, ranked_weeks=(1, 2), tie_rule="include_all_tied"),
        dict(n_busiest_weeks=True, ranked_weeks=(1, 2), tie_rule="include_all_tied"),
        dict(n_busiest_weeks=1, ranked_weeks=(), tie_rule="include_all_tied"),
        dict(n_busiest_weeks=1, ranked_weeks=(1, 1), tie_rule="include_all_tied"),
        dict(n_busiest_weeks=1, ranked_weeks=(54,), tie_rule="include_all_tied"),
        dict(n_busiest_weeks=1, ranked_weeks=[1, 2], tie_rule="include_all_tied"),
        dict(n_busiest_weeks=1, ranked_weeks=(1, 2), tie_rule="random"),
    ])
    def test_config_rejects_bad_values(self, kw):
        with pytest.raises(ValueError):
            CriticalWeekConfig(**kw)


# ===========================================================================
# Regression: D <= O by construction (P2 decision record 2026-11-14-05)
# ===========================================================================
class TestDNotAboveO:
    """D counts FireMask 7-9 on land; O counts FireMask 5 or 7-9 on land."""

    @pytest.mark.parametrize("sensor", ["MODIS_Aqua", "VIIRS_SNPP", "VIIRS_NOAA20"])
    def test_monthly_D_above_O_rejected(self, sensor):
        with pytest.raises(ValueError, match="cannot exceed O"):
            _mo(sensor, 2016, 7, 101, 100)

    def test_weekly_and_block_D_above_O_rejected(self):
        with pytest.raises(ValueError, match="cannot exceed O"):
            _wk("MODIS_Aqua", 2016, 28, 101, 100)
        with pytest.raises(ValueError, match="cannot exceed O"):
            _mo_block("MODIS_Aqua", 2016, 7, 101, 100, "BLOCK_A")

    @pytest.mark.parametrize("D,O", [(91, 60), (91, 40)])
    def test_former_fixture_values_now_rejected(self, D, O):
        # Values used by the four replaced fixtures before this change.
        with pytest.raises(ValueError, match="cannot exceed O"):
            _mo_block("MODIS_Aqua", 2020, 7, D, O, "BLOCK_A")
        with pytest.raises(ValueError, match="cannot exceed O"):
            _wk_block("MODIS_Aqua", 2020, 28, D, O, "BLOCK_A")

    def test_D_equal_O_accepted_rate_1000(self):
        r = compute_rate(_mo("MODIS_Aqua", 2016, 7, 100, 100))
        assert r.status == RateStatus.AVAILABLE
        assert r.fire_activity_index == pytest.approx(1000.0)

    def test_O_zero_message_takes_precedence(self):
        with pytest.raises(ValueError, match="O = 0"):
            _mo("MODIS_Aqua", 2016, 7, 5, 0)


# ---------------------------------------------------------------------------
# Excluded and sealed years (P5 binding decision d0b8c90 / 0a49cbb)
# Synthetic values only.  Fabricated 2020-2021 records appear only to prove they
# are refused; no sealed observation is read.
# ---------------------------------------------------------------------------
SEALED = (2020, 2021)


def _years(sensor, years, month=7, D=10, O=1000):
    return [_mo(sensor, y, month, D, O) for y in years]


class TestExcludedAndSealedYears:
    def test_sealed_years_inside_the_span_must_be_excluded(self):
        with pytest.raises(ValueError, match="never reused"):
            _cfg(start=2016, end=2023, sealed=SEALED)
        _cfg(start=2016, end=2023, sealed=SEALED, excluded=SEALED)
        _cfg(start=2016, end=2019, sealed=SEALED)  # span does not reach the window

    def test_excluded_years_must_lie_in_the_span_and_be_unique(self):
        with pytest.raises(ValueError, match="outside"):
            _cfg(start=2016, end=2019, excluded=(2015,))
        with pytest.raises(ValueError, match="unique"):
            _cfg(start=2016, end=2019, excluded=(2017, 2017))
        with pytest.raises(ValueError, match="tuple"):
            _cfg(start=2016, end=2019, excluded=[2017])

    def test_later_target_skips_sealed_years_and_reports_them(self):
        cfg = _cfg(start=2016, end=2023, min_years=3, sealed=SEALED, excluded=SEALED)
        obs = _years("MODIS_Aqua", [2016, 2017, 2018, 2019, 2022])
        bl = compute_month_baseline(7, 2023, obs, cfg)
        assert bl.status == BaselineStatus.AVAILABLE
        assert bl.required_years == [2016, 2017, 2018, 2019, 2022]
        assert bl.eligible_years == [2016, 2017, 2018, 2019, 2022]
        assert bl.excluded_years == [2020, 2021]

    def test_records_from_sealed_years_are_refused_not_ignored(self):
        cfg = _cfg(start=2016, end=2023, sealed=SEALED, excluded=SEALED)
        obs = _years("MODIS_Aqua", [2016, 2017, 2018, 2019, 2020, 2022])
        with pytest.raises(ValueError, match="sealed years \\[2020\\]"):
            compute_month_baseline(7, 2023, obs, cfg)
        wk = [_wk("MODIS_Aqua", y, 27, 5, 500) for y in (2016, 2017, 2018, 2021)]
        with pytest.raises(ValueError, match="sealed years \\[2021\\]"):
            compute_week_baseline(27, 2023, wk, cfg)

    def test_too_few_years_after_exclusion_is_insufficient_not_backfilled(self):
        cfg = _cfg(start=2018, end=2023, min_years=3, sealed=SEALED, excluded=SEALED)
        bl = compute_month_baseline(7, 2022, _years("MODIS_Aqua", [2018, 2019]), cfg)
        assert bl.status == BaselineStatus.INSUFFICIENT_BASELINE
        assert bl.required_years == [2018, 2019] and bl.excluded_years == [2020, 2021]

    def test_missing_required_year_stays_unavailable_after_exclusion(self):
        cfg = _cfg(start=2016, end=2023, min_years=3, sealed=SEALED, excluded=SEALED)
        obs = _years("MODIS_Aqua", [2016, 2018, 2019, 2022])  # 2017 missing
        bl = compute_month_baseline(7, 2023, obs, cfg)
        assert bl.status == BaselineStatus.MISSING_REQUIRED_YEARS
        assert bl.missing_years == [2017] and bl.median_rate is None and bl.p90_rate is None

    def test_partial_required_year_is_never_dropped(self):
        cfg = _cfg(start=2016, end=2019, min_years=3)
        obs = _years("MODIS_Aqua", [2016, 2018, 2019]) + [_mo("MODIS_Aqua", 2017, 7, 10, 1000, partial=True)]
        bl = compute_month_baseline(7, 2020, obs, cfg)
        assert bl.status == BaselineStatus.MISSING_REQUIRED_YEARS and bl.missing_years == [2017]

    def test_weekly_baseline_uses_the_same_exclusions(self):
        cfg = _cfg(start=2016, end=2023, min_years=3, sealed=SEALED, excluded=SEALED)
        wk = [_wk("MODIS_Aqua", y, 27, 5, 500) for y in (2016, 2017, 2018, 2019, 2022)]
        bl = compute_week_baseline(27, 2023, wk, cfg)
        assert bl.status == BaselineStatus.AVAILABLE
        assert bl.excluded_years == [2020, 2021] and 2020 not in bl.required_years


# ---------------------------------------------------------------------------
# P2 r9 coverage state (handoff b18ed3e).  Synthetic values only.
# ---------------------------------------------------------------------------
class TestCoverageState:
    def test_partial_coverage_never_yields_a_rate(self):
        r = PeriodObs(sensor="MODIS_Aqua", year=2023, D=5, O=500, month=7, coverage_state="partial")
        assert r.is_period_partial and not r.is_available

    def test_default_not_reported_keeps_existing_behaviour(self):
        r = PeriodObs(sensor="MODIS_Aqua", year=2023, D=5, O=500, month=7)
        assert r.coverage_state == "not_reported" and r.is_available

    def test_partial_required_year_from_p2_is_missing_not_pooled(self):
        cfg = _cfg(start=2016, end=2019, min_years=3)
        obs = _years("MODIS_Aqua", [2016, 2018, 2019]) + [
            PeriodObs(sensor="MODIS_Aqua", year=2017, D=10, O=1000, month=7, coverage_state="partial")]
        bl = compute_month_baseline(7, 2020, obs, cfg)
        assert bl.status == BaselineStatus.MISSING_REQUIRED_YEARS and bl.missing_years == [2017]
        assert bl.median_rate is None and bl.p90_rate is None

    def test_partial_target_week_gets_no_label(self):
        cfg = _cfg(start=2016, end=2019, min_years=3)
        hist = [_wk("MODIS_Aqua", y, 27, 5, 500) for y in (2016, 2017, 2018, 2019)]
        target = [PeriodObs(sensor="MODIS_Aqua", year=2023, D=50, O=500, week_number=27, coverage_state="partial")]
        bl = compute_week_baseline(27, 2023, hist, cfg)
        assert bl.status == BaselineStatus.AVAILABLE
        lab = label_unusual_week(target, 2023, 27, bl)
        assert lab.is_unusual is False and lab.status != "labeled"

    def test_unavailable_coverage_cannot_carry_counts(self):
        with pytest.raises(ValueError, match="no file"):
            PeriodObs(sensor="MODIS_Aqua", year=2023, D=0, O=10, month=7, coverage_state="unavailable")

    def test_unknown_coverage_state_rejected(self):
        with pytest.raises(ValueError, match="coverage_state"):
            PeriodObs(sensor="MODIS_Aqua", year=2023, D=0, O=10, month=7, coverage_state="mostly")
