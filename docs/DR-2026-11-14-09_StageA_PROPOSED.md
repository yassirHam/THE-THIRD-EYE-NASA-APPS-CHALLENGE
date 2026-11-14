# DR-2026-11-14-09 (PROPOSED): Stage A training settings

- **Status:** PROPOSED by P2 (Data) for P1 (Science) approval. Not frozen until P1 records approval
  of this exact commit SHA.
- **Applies to:** registered candidate regions California and British Columbia /
  Colombie-Britannique (FAO GAUL 2015 level 1); sensors Aqua MODIS MYD14A1.061 and S-NPP VIIRS
  VNP14A1.002; confidence policies `all` (FireMask 7-9) and `nh` (8-9, class 7 removed from O);
  supports `own` (factor a_H, historical target) and `common` (factor a_C, diagnostic only).
- **Current evidence level:** `day_level` (file presence per day, Earth Engine monthly extracts).
  Footprint completeness is UNVERIFIED until cell-level evidence exists.

## 1. Provenance of the thresholds

The thresholds below were proposed in `docs/HANDOFF_P2_to_P1.md` (Q6, then Q8 revision 2) from the
plan's requirements and general reasoning, before P2 computed or inspected any 2016-2018 Stage A
outcome they govern: no pooled rate, factor, O share or D sum was computed or examined by P2.
The only 2016-2018 information used to build this record is the source-presence list (section 4),
generated from presence columns only. Sealed 2020-2021 data were never opened; 2022-2024
applicability outcomes were not used. No threshold will be adjusted to make data pass.

## 2. Training span and stratum

- Span: the 36 calendar months 2016-01 to 2018-12.
- One stratum per region and policy, pooling the included months. No seasonal or monthly
  sub-strata in P0.

## 3. Paired-month selection rule (predeclared, presence only)

A month is **included for both sensors** if and only if
`aqua_days = days_in_month` AND `viirs_days = days_in_month`
(a product file every day of the month for both sensors). Otherwise it is excluded for both
sensors (`aqua_incomplete`, `viirs_incomplete` or `both_sensors_incomplete`). Both pooled rates
therefore always cover the same calendar months.

## 4. Source-presence list (frozen input)

- File: `stageA_source_presence_2016_2018.csv` (also committed as
  `data/manifests/stageA_source_presence_2016_2018.csv`).
- Generated from columns ADM1_CODE, ADM1_NAME, month, days_in_month, aqua_days, viirs_days of
  `all_blocks_monthly.parquet` only; D and O were not loaded. N_fp computed from geometry only.
- **SHA-256 (UTF-8, LF line endings):** `e23b26cf1ffe98b961a14cc0c65978d1bee99b40742470e1f174e7db31287893`
- Summary (included months out of 12, both sensors):

  | Region | 2016 | 2017 | 2018 | Years valid (>= 9 months) |
  |---|---|---|---|---|
  | California | 12 | 12 | 12 | all |
  | British Columbia / Colombie-Britannique | 12 | 12 | 12 | all |

- N_fp (footprint cells, geometry only): California 478,430; British Columbia /
  Colombie-Britannique 1,107,341. Plausibility: at about 0.859 km2 per cell these correspond to
  about 410,800 km2 and 950,800 km2, consistent with the official areas of both regions.
- Excluded months: none (all 36 months included for both sensors in both regions).

## 5. Required training years

Each of 2016, 2017 and 2018 is required for both sensors. A training year is **valid** only if it
keeps at least **9 of its 12 months** after rule 3 AND passes the O floor (rule 6) for both sensors.
No other year may replace an invalid required year.

## 6. O floor (per sensor, support, policy and training year)

```
included_days(y)  = sum of days_in_month over the included months of year y
O(s,k,y)          = sum of O over the included months of year y      (sensor s, support k)
pass_O(s,k,y)     = O(s,k,y) >= 0.20 x N_fp x included_days(y)
```
`N_fp` = footprint cells of the region (1 km sinusoidal cell centres inside the GAUL polygon;
value in the presence list). For `nh`, O(s,k,y) is O_nh = O - (D - D_nh).
Purpose: representativeness (at least one fifth of footprint cell-days usable), independent of
fire activity. N_fp includes inland water, so the floor is conservative for lake-rich regions.

## 7. D floor (per fit, sensor, support and policy)

```
sum_D(f,s,k) = sum of D over the included months of every year in fit f
pass_D(f,s,k) = sum_D(f,s,k) >= 100
```
Purpose: minimum-information safeguard so that a pooled rate does not rest on a handful of
detections. It is not an uncertainty statement.

## 8. Fits, factor and availability

- Required fits: `full_2016_2018`, `loyo_without_2016`, `loyo_without_2017`, `loyo_without_2018`.
- Pooled rate: `R(f,s,k) = 1000 x sum_D(f,s,k) / sum_O(f,s,k)` over the fit's included months
  (sums before division).
- Factor: `a(f,k) = R(f,Aqua,k) / R(f,VIIRS,k)`; applied to VIIRS rates.
- A fit is **available** only if, for both sensors: every year in the fit is valid (rule 5),
  `pass_D` holds, both pooled rates are > 0, and the factor is positive and finite. Otherwise it
  is **unavailable**, with reasons (`required_year_invalid`, `o_floor_failed:<year>`,
  `d_floor_failed`, `zero_rate`, `undefined_factor`).
- P1-A record: one row per fit x sensor x support x policy x region, with per-year checks
  (included months, included days, O, O share, pass_O), sum_D, pass_D and fit status.

## 9. Interpretation rules

- **A failed or missing required fit prevents a stable conclusion.** No fit is dropped or replaced
  to obtain a stable label.
- **Any directional conflict already observed among the available fits remains visible**
  (reported and displayed), even when the conclusion is unavailable.
- The spread across the full and leave-one-year-out fits is **training-year sensitivity**, not
  the real uncertainty of the factor, and is never shown as an error bar or interval.

## 10. Later baselines and sealed years

- Baselines for targets 2022-2025 require all eligible prior years from 2016 (plan), including
  2020-2021. While their use is not authorized, those baselines are **unavailable**
  (`required_sealed_year_unusable`) and are never shortened.
- 2020-2021 are not reused unless P1 and P5 reconcile that use with the authoritative plan and
  record any required plan change before 2022-2025 outcomes are inspected.

## 11. Values that remain PROPOSED (not part of this decision)

- Processed footprint coverage: 0.99 (tolerance disclosed as coverage and unprocessed cell-days)
  versus 1.0 (any unprocessed footprint cell-day gives `partial`). Not approved; P4 has not
  confirmed whether `complete` admits a tolerance. Field `footprint_evidence`
  (cell_level / day_level / none) proposed to P4.
- Critical weeks: ISO 8601 UTC weeks, four busiest weeks, include all ties at the cut-off rank,
  week-53 minimum count. Not frozen until registration and the sealed-year question are resolved.

## 12. Approval

- P1 decision: `PENDING` (approve / reject / request changes), date, reviewer.
- Approved commit SHA: `<P1 fills in>`
