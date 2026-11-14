# HANDOFF P2 (Data) -> P1 (Science): D/O inclusion and footprint completeness

Date: 2026-11-14. Answers the two science-contract questions raised by P1 before integration.
No sealed holdout outcome (2020-2021) was opened or used to reach these answers: both are
answered from the masking rules, the code, synthetic unit tests and checks on non-sealed years.

## Q1. Is every detected fire-cell-day D included in usable support O, so that D <= O always holds?

**Answer: yes, by construction, for every sensor, support and confidence policy delivered.**

Per 1 km cell and UTC day, for each sensor (same rule for MYD14A1.061 and VNP14A1.002):

- land = QA bits 0-1 == 2 (binary `10`)
- fire (D, policy "all") = FireMask in {7, 8, 9} AND land
- usable (O) = (FireMask == 5 OR fire) AND land

Since `fire` is one of the two terms of `usable`, every fire cell-day is also a usable cell-day:
D is a subset of O cell by cell, so every sum over cells, days, months or blocks keeps D <= O.

| Delivered pair | Why D <= O |
|---|---|
| D_aqua / O_aqua, D_viirs / O_viirs | fire is a subset of usable (above) |
| D_aqua_common / O_common, D_viirs_common / O_common | common = usable_aqua AND usable_viirs on the same cell and day; D_common = fire_sensor AND common, a subset of common |
| D_nh / O_nh (nominal+high, 8-9), own support only | O_nh = O - (D - D_nh): class-7 cell-days are removed from O, not counted as "no fire". O_nh - D_nh = O - D >= 0. Nominal/high common support is not exported and is unavailable (DR-2026-11-14-09 section 2). |

Not counted in D or O: cloud (4), unknown (6), water (3), not processed (0-2), and any fire
class on water or coast (land mask). A low-confidence fire excluded by the nh policy is removed
from O as well, so it is never treated as an observed absence of fire.

**Evidence**
- Rule: `docs/DECISIONS.md` (2026-11-14-05) and `docs/DATA_CARD.md` section 3.
- Code: `pipeline/masks/firemask.py`, `pipeline/grid/accounting.py`; Earth Engine notebook
  `notebooks/AFTERIMAGE_EE_V2.ipynb` (function `masks`).
- Tests: `tests/unit/` (123 passed), covering every FireMask class, water and coast cells,
  empty days and sum-before-divide; independent review by Codex found no rule mismatch.
- Data checks: monthly export, 64 blocks, 2002-07 to 2025-12 excluding 2020-2021 (16,512 rows):
  0 rows with D > O, D_common > O_common, D_nh > D, or O_common > min(O_aqua, O_viirs)
  (`AFTERIMAGE/ee/checked_v2/check_report_monthly.json`).

## Q2. How does P2 certify that an untagged whole-area aggregate covers the complete registered footprint?

**Answer: P2 does not deliver untagged aggregates. Every aggregate carries its footprint and
coverage tags, and completeness is certified at two levels.**

**Registered footprint.** A block is the FAO GAUL 2015 level 1 polygon, keyed by ADM1_CODE. Its
footprint is the set of native 1 km sinusoidal cells whose centre lies inside the polygon (each
cell belongs to exactly one block, so unions of blocks are exact sums, never averages).
N_fp = number of footprint cells (fixed per block).

**Level 1, day-level (all 64 blocks, already delivered).** For each sensor, the number of days
in the period with a product file (`aqua_days`, `viirs_days`) and `*_complete` (file present every
day of the month). A sensor with no file in a period is null, never zero.

**Level 2, cell-level (registered evaluated regions: California, British Columbia /
Colombie-Britannique).** Computed directly from NASA LP DAAC granules
(`notebooks/AFTERIMAGE_weekly_NASA_direct.ipynb`):
- P_sensor = footprint cell-days the algorithm processed (FireMask >= 3, any surface),
- coverage_sensor = P_sensor / (N_fp x days in the period).
A period is certified complete only if coverage meets the minimum registered by P1.
Checks enforced: P <= N_fp per day, O <= P, D <= O.

**Cross-pipeline check.** The NASA-direct daily counts, summed by month, are compared with the
Earth Engine monthly export for the same blocks and months (median and max relative
difference reported). Agreement shows both pipelines cover the same footprint; any residual
comes from boundary cells (the NASA-direct run uses GAUL boundaries simplified to 1 km).

**Known limit (stated, not hidden).** For the 62 raw_only blocks, only Level 1 is available:
a product file present on a day but with missing tiles or unprocessed cells inside the footprint
would lower O without being flagged. These blocks therefore stay `raw_only` with
"footprint coverage not certified at cell level". The Earth Engine quota (Community tier) is
exhausted; Level 2 for other blocks is possible later with the same NASA-direct notebook.

**Rule for consumers.** An aggregate without ADM1_CODE (or registered union), geometry version,
N_fp, period, days with file and, for evaluated regions, coverage, must be rejected.

## Decisions requested from P1 (to register before inspecting outcomes)
1. Minimum coverage for a period to count as complete (for example coverage >= 0.95).
2. Minimum support (minimum O and/or minimum fire cell-days per sensor and year).
3. Confirmation of the evaluated regions and their feasibility rule.

## Q3. Evidence required to certify a whole-area period as complete / partial / unavailable

Proposed by P2 for P4's coverage states. Thresholds marked PROPOSED must be registered by P1
before any outcome is inspected.

**Registered footprint.** Block = FAO GAUL 2015 level 1 polygon (ADM1_CODE). Footprint = native
1 km sinusoidal cells whose centre lies inside the polygon. For each block P2 records
`N_fp` (footprint cells) and `tiles_expected` (MODIS/VIIRS grid tiles holding at least one
footprint cell), both fixed and recomputable from the geometry alone.

**Per sensor and UTC day (evidence kept in focus_daily_CA_BC.parquet):**
- `tiles` present = tiles of the footprint with a product file that day. The sensor is present
  that day only if `tiles == tiles_expected`; a missing tile makes the day unavailable for that
  sensor (its D, O, P are null, never zero, and common support is null).
- `P` = footprint cells processed by the algorithm (FireMask >= 3, any surface, cloud included).
- `coverage = P / N_fp`.

**Per sensor and period (week or month), state rule:**

| State | Rule |
|---|---|
| complete | every expected day present (all tiles), period not clipped, and P / (N_fp x days present) >= C_MIN (PROPOSED 0.99) |
| partial | at least one day present but any of: `period_clipped` (sensor start, registered period end, partition boundary), `missing_days_or_tiles`, `low_processed_coverage` |
| unavailable | no day present: `sensor_not_operating` (e.g. VIIRS before 2012-01-19) or `no_file` |

Every record carries: ADM1_CODE, geometry version, N_fp, tiles_expected, period, expected
days, days present, P, coverage, D, O, state and reason codes.
`comparison_eligible` (MODIS vs VIIRS) is true only when BOTH sensors are complete.

**Evidence level.** California and British Columbia / Colombie-Britannique: cell-level evidence
above (NASA-direct pipeline). The 62 raw_only blocks (Earth Engine monthly export) have day-level
evidence only (`aqua_days`, `viirs_days`): they may be labeled complete at day level but are
marked "cell-level coverage not certified" and are never used for evaluated comparisons.

## Q4. Does the ISO-week choice conflict with an existing registration?

The plan allows "UTC ISO weeks or fixed 7-day bins" and requires the choice to be frozen before
computing; no weekly value has been computed yet, so registering ISO weeks now is valid.
Four boundary interactions must be registered with it (none blocks the choice):

1. **Partitions are defined by UTC calendar date, not ISO year.** 2019-12-30 and 2019-12-31
   (dev) fall in ISO 2020-W01; 2022-01-01 and 2022-01-02 (applicability) fall in ISO 2021-W52.
   A week crossing a partition boundary is split into separate partial records; sealed
   2020-2021 days are never read, so no week mixes sealed and open days.
2. **Registered period ends 2025-12-31**, which is in ISO 2026-W01. That week holds only
   2025-12-29 to 2025-12-31 and is labeled partial (`period_clipped`). It contains no 2026 data,
   so the "no 2026 data" rule is not broken.
3. **Start weeks:** Aqua starts 2002-07-04 (ISO 2002-W27, partial); VIIRS starts 2012-01-19
   (ISO 2012-W03, partial for VIIRS).
4. **53-week ISO years in range: 2004, 2009, 2015, 2020 (sealed).** Same-week-of-year baselines
   (critical and unusual weeks) need a registered rule for week 53 (for example: compared only
   with other week-53 years, or shown as "insufficient baseline").

Weekly values stay same-sensor tracks; evaluated cross-era comparisons remain monthly, as the
plan requires.

## Q5. Week-53 rule and minimum eligible-year count (P1 proposal, P2 data check)

**Existing registration.** Neither the plan nor docs/DECISIONS.md registers a week-53 rule or a
numeric minimum year count. The plan only requires that a minimum count, the first and last
baseline years, the percentile, support and tie rules be frozen before outcomes are inspected
(plan: seasonal baseline and "Unusual weeks"; core baseline years start in 2016). P2 has no
objection to P1's proposed week-53 rule.

**Data facts that the rule must account for** (ISO 8601, UTC):
- ISO years with 53 weeks in the source record: 2004, 2009, 2015, 2020. None in 2016-2019 or
  2022-2025.
- 2020-W53 = 2020-12-28 to 2021-01-03: entirely sealed (P5).
- Consequence with baselines starting in 2016: no target week 53 in development or
  applicability years, and the only in-range week 53 (2020-W53) has zero eligible prior
  week-53 years, so it returns `insufficient_baseline` under P1's rule. If P1 ever registers
  pre-2016 baseline years, Aqua would have 2004, 2009, 2015 and S-NPP only 2015 (S-NPP starts
  2012-01-19).

**Proposed minimum eligible-year count: 3 (PROPOSED, not frozen; P1 decides).**
Rationale: the plan's 90th percentile by nearest rank uses rank ceil(0.9 n). For n = 1 to 9 this
rank equals n, so the threshold is the maximum of the eligible prior years; for n = 10 it is the
ninth sorted value. With n = 3 the threshold is therefore the maximum of three years: it is
computable, but it is a highly limited comparison, not a precise percentile estimate, and the
UI must say so. A year counts only if that week is complete for the sensor and policy (state
`complete`, see Q3) and meets the registered minimum support; otherwise it is not eligible,
never zero.

**Eligible-year scope (plan, core baseline).** For a target year Y: prior years from 2016 to
Y-1, same sensor and policy, each complete with minimum support; the target year and later
years are excluded. During development 2020-2021 are sealed and are not eligible. Whether
2020-2021 become eligible baseline years for 2022-2025 targets after P5's evaluation is not
registered and must be decided by P1 before any 2022-2025 outcome is inspected.

**Week-53 consequence for the 2016-start core.** Week-53 years from 2016 onward are 2020 (sealed)
and 2026 (outside the registered period). No development or applicability year (2016-2019,
2022-2025) has a week 53, and the only in-range week-53 target, 2020-W53, has zero eligible
prior week-53 years. No relevant case reaches three prior week-53 observations: every week-53
target returns `insufficient_baseline`.

**Sealed-date boundary weeks.** P2 data already follow P1's request: weeks are split by UTC date
at partition boundaries; the open portion is stored as `partial` with reason
`partition_boundary`, is not comparison-eligible and receives no unusual or critical label;
sealed 2020-2021 days are never read to complete it (2019-12-30/31 in ISO 2020-W01;
2022-01-01/02 in ISO 2021-W52). P4 should add `partition_boundary` as a partial reason in the
next contract revision.

## Q6. Registrations and proposals for P1 freeze: Stage A support/strata, footprint coverage, critical weeks

**Registry status.** Registered (docs/DECISIONS.md): masks, D/O definitions, common support,
domain, period, splits, sealed years. NOT registered with values: Stage A strata and minimum
support, footprint-coverage threshold, critical-week settings. The plan requires these to be
frozen at kickoff before outcomes ("Freeze strata, masks and minimum support at kickoff; record
them"; critical weeks: "freeze the week definition, eligible prior years, minimum support, number
of busiest weeks, aggregation and tie rules before computing"). Everything below is a P2 PROPOSAL.

### Stage A strata, minimum support, footprint coverage
Superseded by Q8 (clarified proposals). Earlier wording that linked D = 100 to a 10 % uncertainty
is withdrawn.

### Critical weeks (PROPOSED)
- Week: ISO 8601 week, UTC, Monday to Sunday; partitions by UTC date (Q4).
- Eligible prior years: same sensor and policy, 2016 to Y-1, sealed years excluded during
  development; each week counted only if `complete` and meeting the period support rule.
- Minimum eligible years: 3 (Q5); week 53 is excluded from the critical-week ranking
  (`insufficient_baseline`, Q5).
- Aggregation: for each ISO week number, R per eligible year from summed D and O; the week's
  typical value is the median across eligible years.
- Number of busiest weeks: 4 (about one month, matching the monthly evaluated resolution).
- Ties at rank 4: include all tied weeks and show the count (no arbitrary drop).
- Same-sensor only; never joined across MODIS and VIIRS without an evaluated weekly mapping.

## Q7. Development extracts and completeness evidence

- **Ready now, separate from sealed data:** `RIM_dev_long_2016_2019.csv` (64 blocks x 48 months x
  2 sensors x 3 support/confidence variants = 18,432 rows; split = train 2016-2018 / dev 2019).
  The exported columns allow only own/all, own/nh and common/all, so these should be the three
  variants and there is no common/nh variant; P2 to confirm against the file.
  2020-2021 exist only in the P5-only folder `AFTERIMAGE_P5_SEALED` and were never opened by P2.
  (At P2's decision, P1 also received `RIM_full_long_2016_2024.csv`, which contains no 2020-2021
  rows; using 2022-2024 only after the methods freeze is P1's responsibility.)
- **Completeness evidence delivered with the monthly extracts (all 64 blocks):** per sensor and
  month `days_with_file`, `days_in_month`, `complete`; nulls (never zeros) when a sensor has no
  file; `check_report_monthly.json` with SHA-256 of every source export, row and block counts,
  period range and 0 violations of D <= O, D_common <= O_common, O_common <= min(O_aqua, O_viirs).
  Evidence level: day-level.
- **Cell-level evidence (California, British Columbia / Colombie-Britannique):** N_fp,
  tiles_expected, P, coverage and complete/partial/unavailable states with reason codes come
  from the NASA-direct pipeline; weekly 2016-2019 is produced first. Status: pipeline tested on
  synthetic data; the real run is in progress and its report (`report_weekly.json`) will be
  attached when complete.

## Q8. Proposals for P1 decision, revision 2 (supersedes Q6 and earlier Q8 where they differ)

Status: all values are PROPOSALS, none frozen. None was chosen or tuned using sealed 2020-2021
outcomes or 2022-2024 applicability outcomes, and none will be adjusted to make data pass.
Eligibility rules use only availability metadata (file and tile presence, processed coverage)
fixed before any factor is computed; never D, O, rates or factors.

### 8.1 Leave-one-year-out spread
The spread of the full-training factor and the three leave-one-year-out factors is
**training-year sensitivity**: how much the factor moves when one training year is removed. It is
not the real uncertainty of the factor and must never be presented as an error bar, confidence
interval or bound.

### 8.2 Predeclared missing-month rule and required years
- Training stratum: the 36 calendar months 2016-01 to 2018-12, one stratum per region and policy.
- Month rule: a month is included for BOTH sensors only if both sensors have a product file every
  day of that month; otherwise it is excluded for both. Decided from presence columns only.
- Required years: the plan requires each training year 2016, 2017 and 2018 for both sensors.
  A training year is valid only if, after the month rule, it keeps at least 9 of its 12 months
  AND passes the year-level O floor (8.3). No other year may replace it.
- If any required training year is invalid, the full-training factor is `unavailable`
  (reason `required_year_invalid`), and so is every variant that needs that year; the variant set
  is then incomplete and no "stable" label can be issued.
- Before any factor is computed, P2 publishes the per-region list of included and excluded months
  with reasons (generated from presence columns only) and records its SHA-256 in DECISIONS.md.

### 8.3 How the two floors appear in P1-A (full and leave-one-year-out fits)
Definitions, per region, policy, support (own or common) and sensor:
- included_days(year) = number of days in that year's included months (8.2);
- N_fp = footprint cells (Q3);
- O floor, per training year: O_year >= 0.20 x N_fp x included_days(year)
  (screening floor on the usable share of footprint cell-days; not evidence of
  representativeness; the denominator N_fp x included_days is the same for every sensor, support
  and confidence policy, and for nh the numerator is O_nh);
- D floor, per fit: sum of D over the fit's years >= 100 fire cell-days
  (minimum-information safeguard; not an uncertainty or precision statement: fire cell-days are
  clustered, so no relative error can be read from 100).

Revision note (P1 review draft, branch `proposal/DR-2026-11-14-09-p1-rev1`): the supported
combinations, the interaction of the month rule, required years and each fit, and the P1-A
changes needed are set out in DR-2026-11-14-09 sections 2, 8 and 9. All values remain unfrozen.

Proposed P1-A record, one row per fit x sensor x support x policy x region:

| field | content |
|---|---|
| fit_id | full_2016_2018, loyo_without_2016, loyo_without_2017, loyo_without_2018 |
| years_in_fit | e.g. [2017, 2018] |
| per_year_checks | for each year: included_months, included_days, O_year, O_share = O_year / (N_fp x included_days), o_floor_pass |
| sum_D, d_floor_pass | fit-level D sum and its check |
| fit_status | available, or unavailable with reasons (required_year_invalid, o_floor_failed:<year>, d_floor_failed, zero_rate) |

A factor exists only if BOTH sensors' rows for that fit are available. Every year of a fit is
checked against the O floor (a year that fails makes every fit containing it unavailable); the
D floor is checked on each fit's own sum, so the full fit and each leave-one-year-out fit are
checked independently.

### 8.4 Processed coverage and pixel-level evidence
- Whether P4's `complete` permits 99 % processed coverage is NOT confirmed: the reviewed P4
  contract does not define a tolerance. P4 must answer. P1 has not approved 0.99 or 1.0.
- Options for P1:
  (a) tolerance 0.99 with disclosure: `complete` carries `coverage` and
      `unprocessed_cell_days = N_fp x days - P`, displayed as "complete (99.6 % processed)";
  (b) zero tolerance (1.0): any unprocessed footprint cell-day gives `partial`
      (`low_processed_coverage`).
- Representation of unverified evidence, in every record: `footprint_evidence` =
  `cell_level` (N_fp, tiles and P verified), `day_level` (only file presence per day: the current
  monthly extracts), or `none`. A `day_level` record must never be described as
  footprint-complete. Whether day-level records may enter Stage A provisionally, or must wait for
  cell-level evidence, is a P1 decision to record before computing.

### 8.5 Later baselines and sealed years
- Per the plan, the baseline for target year Y uses all eligible prior years from 2016 to Y-1.
  For targets 2022 to 2025 that set includes 2020 and 2021.
- While no P5 decision authorizes reuse of 2020-2021, those years cannot be used. The baseline is
  then `unavailable` (reason `required_sealed_year_unusable`), NOT shortened to the remaining
  years. It becomes computable only if P5 records a reuse decision (or P1 registers a different
  eligible-year rule) before 2022-2025 outcomes are inspected.
- Targets 2020-2021 (P5 evaluation) use 2016-2019, which contain no sealed years.

### 8.6 Critical weeks
Week definition (ISO 8601, UTC), the four-week count and the tie rule (include all ties at the
cut-off rank, show the count) remain PROPOSALS until P1 registers them and the sealed-year reuse
question (8.5) is resolved. Week 53 follows its separate rule (Q5); its minimum count is not frozen.
