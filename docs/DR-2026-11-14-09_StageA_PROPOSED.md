# DR-2026-11-14-09 (PROPOSED): Stage A training settings

- **Status:** PROPOSED by P2 (Data) for P1 (Science) approval. Not frozen until P1 records approval
  of an exact commit SHA. **All numeric values (9 months, 0.20, 100, 0.99) are unfrozen.**
- **Revision 1 (P1 review draft):** prepared by Kiro for P1 review on branch
  `proposal/DR-2026-11-14-09-p1-rev1`, parent `116c883266732bcc645121f87087e1c567f6cf06`. It changes
  wording and structure only:
  - it lists the supported sensor/support/confidence combinations (section 2);
  - it marks nominal/high common support unavailable;
  - it defines the nh denominator;
  - it removes representativeness and uncertainty readings of the floors;
  - it documents how the month rule, required years and fits interact (section 8);
  - it lists the P1-A changes needed (section 9).
  No threshold value was changed. Data facts are cited to P2 commits; P2 must confirm them before
  approval.
- **Applies to:** registered candidate regions California and British Columbia /
  Colombie-Britannique (FAO GAUL 2015 level 1); sensors Aqua MODIS MYD14A1.061 and S-NPP VIIRS
  VNP14A1.002; the combinations listed in section 2 only.
- **Current evidence level:** `day_level` (file presence per day, Earth Engine monthly extracts).
  **Footprint completeness is UNVERIFIED** for every region and period until cell-level evidence
  (processed versus expected footprint cell-days) has been produced and checked. Month inclusion in
  section 4 is file-presence evidence only and does not certify the footprint (see also P2
  `pipeline/grid/COVERAGE_RULE.md` at `c686b20`: "every footprint is `unverified`").

## 1. Provenance of the thresholds

The thresholds below were proposed in `docs/HANDOFF_P2_to_P1.md` (Q6, then Q8 revision 2) from the
plan's requirements and general reasoning, before P2 computed or inspected any 2016-2018 Stage A
outcome they govern: no pooled rate, factor, O share or D sum was computed or examined by P2.
The only 2016-2018 information used to build this record is the source-presence list (section 4),
generated from presence columns only. Sealed 2020-2021 data were never opened; 2022-2024
applicability outcomes were not used. No threshold will be adjusted to make data pass.

## 2. Supported sensor / support / confidence combinations

Exported columns are those of P2 `pipeline/grid/accounting.py` (`AQUA_COLUMNS`, `VIIRS_COLUMNS`,
`COMMON_COLUMNS`) at `p2/data` `2e60c9d` and `task/P2-A-002` `c686b20`. Monthly sums per block
and month; sums are taken over months and blocks before any division.

| # | Support | Confidence | Sensor | D (numerator) | O (denominator) | Factor | Status |
|---|---|---|---|---|---|---|---|
| 1 | own | all (FireMask 7-9) | Aqua | `D_aqua` | `O_aqua` | a_H (all) | supported: exported |
| 2 | own | all (7-9) | VIIRS | `D_viirs` | `O_viirs` | a_H (all) | supported: exported |
| 3 | own | nh (8-9) | Aqua | `D_aqua_nh` | `O_aqua_nh = O_aqua - (D_aqua - D_aqua_nh)` | a_H (nh) | supported: derived from exported columns |
| 4 | own | nh (8-9) | VIIRS | `D_viirs_nh` | `O_viirs_nh = O_viirs - (D_viirs - D_viirs_nh)` | a_H (nh) | supported: derived from exported columns |
| 5 | common | all (7-9) | Aqua | `D_aqua_common` | `O_common` | a_C (all), diagnostic | supported: exported |
| 6 | common | all (7-9) | VIIRS | `D_viirs_common` | `O_common` (same value as row 5) | a_C (all), diagnostic | supported: exported |
| 7 | common | nh (8-9) | Aqua | not exported | not exported | a_C (nh) | **UNAVAILABLE** (`paired_nh_counts_not_exported`) |
| 8 | common | nh (8-9) | VIIRS | not exported | not exported | a_C (nh) | **UNAVAILABLE** (`paired_nh_counts_not_exported`) |

- Why rows 7-8 cannot be derived:
  - Nominal/high common support needs, per cell and UTC day, the cells usable in both sensors with neither sensor's cell in class 7, and each sensor's class 8-9 cells inside that set.
  - `D_*_common` has no confidence split, and `D_*_nh` is not restricted to common support.
  - The overlap of the two sensors' class-7 cells is not recoverable from monthly totals.
- Rows 7-8 stay unavailable until P2 exports paired counts (for example `O_common_nh`, `D_aqua_common_nh`, `D_viirs_common_nh`), defined at cell-day level and with their D <= O evidence. P2 must define those counts; this record does not.
- Row 6 uses the same `O_common` as row 5 by construction. A record pair with different common-support O for the two sensors is invalid.
- The dev file described in `HANDOFF_P2_to_P1.md` Q7 ("3 support/confidence variants") can, from
  the exported columns, only hold rows 1-2, 3-4 and 5-6 (no nh common-support variant). P2 to
  confirm against the file; Kiro has not opened it.

## 3. Training span and stratum

- Span: the 36 calendar months 2016-01 to 2018-12.
- One stratum per region, support and confidence policy, pooling the included months. No seasonal
  or monthly sub-strata in P0. Because months are pooled, a year with fewer included months
  contributes a different month mix; the paired-month rule (section 4) keeps that mix identical
  for the two sensors, but not across years.

## 4. Paired-month selection rule (predeclared, presence only)

A month is **included for both sensors** if and only if
`aqua_days = days_in_month` AND `viirs_days = days_in_month`
(a product file every day of the month for both sensors). Otherwise it is excluded for both
sensors (`aqua_incomplete`, `viirs_incomplete` or `both_sensors_incomplete`).
- The rule uses presence columns only, never D, O, rates or factors.
- The same included months apply to every combination in section 2 and to every fit.
- An excluded month contributes neither D nor O, for either sensor.
- File presence on every day is day-level evidence; it does not show that the footprint was processed (section 10).

### Source-presence list (frozen input)

- File: `data/manifests/stageA_source_presence_2016_2018.csv` (single committed path).
- Generated from columns ADM1_CODE, ADM1_NAME, month, days_in_month, aqua_days, viirs_days of
  `all_blocks_monthly.parquet` only; D and O were not loaded. N_fp computed from geometry only.
- **SHA-256 (bytes as committed, LF line endings):** `e23b26cf1ffe98b961a14cc0c65978d1bee99b40742470e1f174e7db31287893`
- Summary (included months out of 12, both sensors):

  | Region | 2016 | 2017 | 2018 | Years with >= 9 included months |
  |---|---|---|---|---|
  | California | 12 | 12 | 12 | all |
  | British Columbia / Colombie-Britannique | 12 | 12 | 12 | all |

- N_fp (footprint cells, geometry only): California 478,430; British Columbia /
  Colombie-Britannique 1,107,341. Plausibility: at about 0.859 km2 per cell these correspond to
  about 410,800 km2 and 950,800 km2, consistent with the official areas of both regions.
- Excluded months: none at day level (all 36 months have a file every day for both sensors in both
  regions). Footprint processing within those days is unverified.

## 5. Required training years

Each of 2016, 2017 and 2018 is required for both sensors. For a given region, support and
confidence policy, a training year is **valid** only if:
1. it keeps at least **9 of its 12 months** after rule 4 (the same count for both sensors, because
   inclusion is paired); and
2. it passes the O floor (rule 6) for **both** sensors.

No other year may replace an invalid required year. A year can be valid for one combination and
invalid for another, because the O floor depends on the combination's O.

## 6. O floor (per region, sensor, support, confidence policy and training year)

```
included_days(y)  = sum of days_in_month over the included months of year y
N_fp              = footprint cells of the region (section 4)
O(s,k,c,y)        = sum over the included months of year y of the O column in section 2
                    for sensor s, support k, confidence c
share(s,k,c,y)    = O(s,k,c,y) / (N_fp x included_days(y))
pass_O(s,k,c,y)   = share(s,k,c,y) >= 0.20          (0.20 unfrozen)
```

- Denominator in cell-days: N_fp x included_days(y). It is the same for both sensors, all
  supports and both confidence policies. It counts every footprint cell, including inland water
  that can never enter O, so the share cannot reach 1.0 in regions with water cells.
- nh denominator: for confidence `nh` the numerator is `O_nh = O - (D - D_nh)`, which removes
  class-7 cell-days from usable support (they are not treated as observed absence of fire). The
  denominator is unchanged. Hence `share_nh <= share_all`, and the nh floor can fail where the
  all-confidence floor passes. For common support only `all` is available (section 2).
- What the floor is and is not:
  - It is a screening floor on the share of footprint cell-days that are usable.
  - Passing it does **not** show that the usable cell-days represent the footprint. Cloud, darkness and fire are clustered in space and time, and the usable share can be spatially or seasonally uneven.
  - It is also not fully independent of fire activity: O includes fire cell-days by definition (classes 7-9 for `all`; classes 8-9 for `nh`). It is never computed from rates or factors.

## 7. D floor (per fit, region, sensor, support and confidence policy)

```
sum_D(f,s,k,c)  = sum of D (column in section 2) over the included months of every year in fit f
pass_D(f,s,k,c) = sum_D(f,s,k,c) >= 100            (100 unfrozen)
```

- It is a minimum-information safeguard, so that a pooled rate does not rest on a handful of
  detections.
- It is **not** an uncertainty or precision statement. Fire cell-days are clustered (one fire
  spans many cells and days), so detections are not independent counts, and no relative error can
  be read from 100.
- The full and leave-one-year-out fits are the registered training-year sensitivity check.

## 8. How the month rule, required years and fits interact

Required fits and their years (each fit is the complete calculation repeated on its years):

| Fit | Years used |
|---|---|
| `full_2016_2018` | 2016, 2017, 2018 |
| `loyo_without_2016` | 2017, 2018 |
| `loyo_without_2017` | 2016, 2018 |
| `loyo_without_2018` | 2016, 2017 |

Order of evaluation, for each region, support and confidence policy:

1. **Month rule (section 4).** It fixes the included months per year once, from presence only, for
   both sensors, every combination and every fit.
2. **Year validity (section 5).** For each of 2016-2018: at least 9 included months, and the O floor
   on that year's included months for both sensors. This yields one valid/invalid flag per year,
   computed once and used by every fit.
3. **Fit availability.** A fit is **available** only if, for both sensors:
   - every year in the fit is valid;
   - `pass_D` holds on that fit's own pooled D;
   - both pooled rates `R = 1000 x sum_D / sum_O` (sums over the fit's included months) are > 0;
   - the factor `a = R_Aqua / R_VIIRS` is positive and finite.
   Otherwise the fit is **unavailable** with reasons: `required_year_invalid:<year>`,
   `o_floor_failed:<sensor>:<year>`, `too_few_months:<year>`, `d_floor_failed:<sensor>`,
   `zero_rate`, `undefined_factor`, or `combination_unavailable` (rows 7-8).
4. **Conclusion.** All four fits are required.
   - If any is unavailable, the variant set is incomplete and no stable label is issued.
   - No fit is dropped or replaced to obtain one.
   - Any directional conflict already observed among the available fits remains visible.

Consequences:
- **One invalid year:**
  - If 2017 is invalid, `full_2016_2018`, `loyo_without_2016` and `loyo_without_2018` are unavailable.
  - `loyo_without_2017` may still be available, but the set is incomplete.
  - The same pattern holds for 2016 or 2018.
- **Two or three invalid years:** all four fits are unavailable.
- **D floor:** it is checked separately on each fit's pooled sum. The full fit can pass while a
  leave-one-year-out fit (two years) fails. The threshold is the same for every fit and is not
  lowered for leave-one-year-out fits.
- **Excluded months:** they lower `included_days(y)`, so the O-floor denominator shrinks with them.
  They also remove D and O from every fit that uses that year. A year with 9-11 included months
  stays valid if it passes the O floor.
- **nh versus all:** the nh fits use the nh O and D columns throughout. A year valid for `all` can
  be invalid for `nh` (section 6), and the nh D floor uses `D_nh`.

## 9. P1-A code changes needed to enforce these rules

Reference: `task/P1-A-001` at `ab8068821550638daab1e1e8670be432c84c4b55`. None is implemented; all
wait for P1 approval of the final rules. Required values must be configuration with no defaults.

1. **Record shape.**
   - Current state: `ObsRecord(sensor, year, stratum, policy, D, O)` has no month, day count,
     region or confidence field.
   - Needed: month (`YYYY-MM`), `days_in_month`, region `ADM1_CODE` (or geometry ID) and confidence
     policy (`all`/`nh`).
   - Map P2 nulls to unavailable (not zero), and require whole-number counts.
2. **Combination guard.**
   - Accept only rows 1-6 of section 2.
   - Derive `O_nh = O - (D - D_nh)` for own support; reject `common`+`nh` as
     `combination_unavailable`.
   - Require identical `O_common` for the two sensors in each common-support month.
3. **Month rule.**
   - Load the source-presence list, verify its SHA-256 against this record, and use only its
     `included` months for both sensors.
   - Reject records for months not in the list, and never re-select months.
4. **Year validity.** Implement the 9-of-12 check and the per-year O floor as in sections 5-6.
   - `min_included_months` and `o_floor_share` become required config.
   - The current absolute `min_support_O` per (sensor, year, stratum) is replaced. Also required:
     `N_fp` per region and `included_days(y)`.
   - Fix the required years to 2016-2018 and reject 2020-2021 in any training input. At
     `ab80688` `training_years=(2020, 2021)` still returns available factors.
5. **D floor.** Add `d_floor` (required config) and check it per fit and per sensor on the fit's
   pooled D. Not present at `ab80688`.
6. **Fit status record.** Emit one row per fit x sensor x support x policy x region, with:
   - per-year checks: included months, included days, O, share, pass;
   - `sum_D` and its pass flag;
   - status, and the reason codes of section 8.
   Align fit IDs: P1-A uses `full_training_2016_2017_2018` / `ex_2016`; this record uses
   `full_2016_2018` / `loyo_without_2016`.
7. **Stratum.** Replace the registered strata tuple with the single pooled stratum per region,
   support and policy. Month pairing is then enforced by the month rule (item 3), not by the
   current (year, stratum) key match.
8. **Evidence level.**
   - Carry `footprint_evidence` (`cell_level` / `day_level` / `none`) on every fit record.
   - A `day_level` fit must never be described as footprint-complete.
   - Whether `day_level` inputs may enter Stage A provisionally is a P1 decision to record before
     computing.
9. **Common-support pairing.** Keep `pairing_validated` as an explicit input. This record's
   section 2 and DECISIONS 2026-11-14-05 are the documented basis; the equal-`O_common` check
   (item 2) supplements it.

## 10. Coverage and footprint completeness (unchanged proposals)

- Processed footprint coverage: 0.99 (tolerance disclosed as coverage and unprocessed cell-days)
  versus 1.0 (any unprocessed footprint cell-day gives `partial`). Not approved. P4 has not
  confirmed whether `complete` admits a tolerance, and P4's contract is not approved. A field
  `footprint_evidence` (cell_level / day_level / none) has been proposed to P4.
- Until cell-level processed versus expected counts exist and have been checked, every region and
  period is `unverified`. No Stage A output may be labelled footprint-complete.

## 11. Interpretation rules

- **A failed or missing required fit prevents a stable conclusion.** No fit is dropped or replaced
  to obtain a stable label.
- **Any directional conflict already observed among the available fits remains visible**
  (reported and displayed), even when the conclusion is unavailable.
- The spread across the full and leave-one-year-out fits is **training-year sensitivity**, not
  the real uncertainty of the factor, and is never shown as an error bar or interval.

## 12. Later baselines and sealed years

- Baselines for targets 2022-2025 require all eligible prior years from 2016 (plan), including
  2020-2021. While their use is not authorized, those baselines are **unavailable**
  (`required_sealed_year_unusable`) and are never shortened.
- P5's binding decision (`handoff/escalations/P4/P4-holdout-baselines-decision.md`, handoff
  `d0b8c90`) governs that use:
  - 2020-2021 never enter Stage A factors or variants;
  - pre-freeze they are ineligible everywhere;
  - post-freeze they may enter descriptive same-sensor baselines only under its four conditions.
  P1 and P5 must reconcile any use with the plan before 2022-2025 outcomes are inspected.

## 13. Values that remain PROPOSED (not part of this decision)

- Critical weeks: ISO 8601 UTC weeks, four busiest weeks, include all ties at the cut-off rank,
  week-53 minimum count. Not frozen until registration and the sealed-year question are resolved.

## 14. Approval

- P1 decision: `PENDING` (approve / reject / request changes), date, reviewer.
- Approved commit SHA: `<P1 fills in>`
