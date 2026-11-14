# Proposals for P1 decision: Stage A strata, support, coverage and critical weeks

- From: Kiro (P1 science writer). To: P1 (decision). Copy: P2, P4, P5.
- Status: **PROPOSAL ONLY. Nothing here is frozen, registered or coded.**
- Code referenced: P1-A `ab8068821550638daab1e1e8670be432c84c4b55`; P1-B `ff6433907b6ae112a068d634fb45a7dc2bee1e48`.
- Other sources: P2 `p2/data` at `bdf095570d3cbca72168e35832d149f0775d6c39`; P4 contract on `task/P4-B-001` at `8902fd7`; P5 decision `handoff/escalations/P4/P4-holdout-baselines-decision.md` (handoff `d0b8c90`); plan SHA256 `84B012E2...521DDC`.
- Data looked at: **none.** These proposals were written without opening any D, O or rate values, and they use no sealed (2020-2021) or applicability (2022-2024) outcomes. The only P2 material read was documentation and code.

## 0. Provenance of the numbers being decided
The values D >= 100, 10% period support, 0.99 coverage and four critical weeks appear in **no** recorded artifact. I searched handoff, `p2/data`, `task/P4-B-001`, P5 branches, `integration` and the plan. Neither the P1-A nor the P1-B code contains them. They are evaluated below as P1's candidates, not as existing proposals from Kiro or anyone else.

## 1. Stage A strata and incomplete months
**Facts**
- Plan lines 904-913: "matched calendar strata"; "Freeze strata, masks and minimum support at kickoff; record them."
- P2 monthly file `all_blocks_monthly.parquet` carries `month`, `days_in_month`, `aqua_days`, `viirs_days`, `aqua_complete`, `viirs_complete` (DATA_CARD 6.1). Here "complete" means a file was present for every UTC day of the month. It says nothing about pixel processing.
- P1-A `ObsRecord` has `stratum` (free text), but no day-count or completeness field. **At `ab80688` an incomplete month would be pooled without any check.**

**Proposal**
1. Registered strata: the 12 UTC calendar months, `month_01` ... `month_12`. Training years: 2016, 2017 and 2018, with no exceptions. Both sensors use the same 36 (year, month) cells.
2. Incomplete-month rule (strict, recommended): a (sensor, year, month) cell is usable only if that sensor's `*_days == days_in_month` and footprint completeness is verified (Section 4). If any of the 36 registered cells fails for either sensor, every variant containing that year is **unavailable**. Cells are never dropped to obtain a factor.
3. Leave-one-year-out variants use the same registered cell list minus the excluded year. No variant re-selects cells.
4. Fallback, only by recorded P1 decision: if the strict rule leaves too few variants, P1 may freeze an explicit cell list. That list must be computed **only from the file-presence columns** (`aqua_days`, `viirs_days`, `days_in_month`), recorded with its SHA **before** any D or O sum is computed, and then treated as the registered strata. "Months where both sensors are complete" must not be decided after D, O or rates are seen.

**Code impact (after the decision):** `ObsRecord` needs `days_present` and `days_in_period` (or a P2-supplied `complete` flag), and incomplete cells must fail registered support.

## 2. Factor support: two separate checks
These two checks answer different questions; neither replaces the other.

**2a. Observation support: minimum O per (sensor, year, stratum). Already in P1-A as `StageAConfig.min_support_O`.**
- Question it answers: was this registered cell actually observed, so that the strata are genuinely matched and no year is represented by a sliver of its month?
- Proposal: express it as a fraction of expected land cell-days (Section 3 denominator), with the same fraction as period support (candidate 10%). The rule is O(s,y,m) >= f x N_exp(s,y,m) for every sensor s and every (y, m) in the variant.
- An absolute integer is not comparable across regions or month lengths, which is why a fraction is proposed.
- Implementation status: P1-A currently takes an absolute integer. Moving to a fraction needs N_exp from P2 (Section 3).
- Checked: separately for each variant, over that variant's training years (already how P1-A works).

**2b. Detection support: minimum pooled D per sensor per factor calculation. Not in P1-A yet.**
- Question it answers: are there enough detections in both sensors for a ratio of pooled rates to be meaningful? Plan lines 691-692 call for "adequate nonzero training detections in both sensors" and "handling of zero/sparse rates".
- Candidate: D_min = 100, applied to each sensor's pooled D in each factor calculation.
  - own-support D for a_H;
  - common-support D (`D_*_common`, FireMask 7-9) for a_C, checked separately.
- Checked: **for every variant on its own pooled sums.**
  - The full 2016-2018 variant is checked on 3 years.
  - Each leave-one-year-out variant is checked on its 2 years.
  - A variant below D_min in either sensor is unavailable. Missing required variants then make sensitivity `unresolved` (existing rule).
  - The threshold is not lowered for leave-one-year-out variants, and strata are not dropped to pass it.
- What D = 100 does and does not mean:
  - It is a screening floor.
  - Under an idealised independent-count model, a count of 100 has relative SD 1/sqrt(100) = 10%, and a ratio of two such counts about sqrt(1/100 + 1/100) ~ 14%.
  - Fire cell-days are clustered in space and time (one fire spans many cells and days), so the effective sample is smaller and the real uncertainty is larger.
  - **D = 100 is not evidence of 10% (or any stated) uncertainty.** The registered leave-one-year-out variants are the sensitivity check; D_min only prevents near-empty ratios.
- Order: freeze D_min **before** any training D sum is computed. Then report which variants pass, without changing D_min.

## 3. Period support (calendar months and weeks): the 10% denominator
- Definition, per sensor s and period p (month or ISO week) over the registered footprint F:
  - N_exp(s, p) = (number of 1 km land cells of F under sensor s's frozen land mask and grid inclusion rule) x (number of UTC calendar days in p).
  - support fraction(s, p) = O(s, p) / N_exp(s, p).
  - O(s, p) is the usable land cell-days (FireMask 5 or 7-9 on land) summed over every block of F and every day of p.
- Units are cell-days. The day count is calendar days, **not** days with a file, so missing files lower the fraction instead of shrinking the denominator.
- Candidate rule: fraction >= 0.10. Otherwise the period is `insufficient_support` (never zero), for the target period and for every baseline year.
- Sensor specifics: each sensor uses its own land-cell count (each product's QA land bits). For VIIRS S-NPP, periods straddling or after the 2026-11-02 15:40 UTC cutoff are partial or after-record regardless of the fraction.
- Interaction with footprint completeness: these are two separate gates, applied in this order.
  1. Footprint completeness (Section 4). If it is not verified or fails, the period is unavailable (`incomplete_footprint`), and the support fraction is not used.
  2. Only then the support fraction, which is meant to screen out low usable observation (cloud, darkness), not missing extraction.
- Missing input: P2 does not yet export land-cell counts per block (searched `p2/data` at `bdf0955`), so N_exp cannot be computed. The P1-B code also still uses an absolute `min_support_O`. Both need changing after the decision.

## 4. Coverage tolerance (candidate 0.99) and the P4 "complete" state
**Facts**
- P4 contract at `8902fd7`:
  - `UnavailableReason` includes `incomplete_footprint`.
  - The manifest `PartitionFileRecord.coverage_status` is `complete` / `partial` / `unavailable`.
  - There is **no coverage-fraction field and no tolerance**, so "complete" is undefined below 100%.
- Plan line 615: "A partially extracted footprint is unavailable for a whole-area conclusion."
- No pixel-level processed-versus-expected evidence exists in P2's export.

**Proposal**
1. Until P2 exports processed and expected land pixel-days per sensor, block and day (or month), **footprint completeness is unverified** for every period. No P1 output may label a period or a factor footprint-complete.
2. Coverage(s, p) = processed land pixel-days / expected land pixel-days.
   - "Processed" means the FireMask is not 0-2 (not processed) and a file is present.
   - "Expected" is N_exp from Section 3.
3. A 0.99 tolerance relaxes plan line 615. It needs P1 to record it as a deviation and P4 to define it in the contract (field plus rule). Without that, P4's `complete` should be read as 100%.
4. If 0.99 is adopted, every period carries its `coverage` value. The shortfall (1 - coverage, as a percentage of expected pixel-days, per sensor) is shown in the evidence drawer and exports. D and O are never scaled up or imputed for the unprocessed share.
5. Basis for the value: P2 may report the distribution of unprocessed fractions for **2016-2019 only**. That is availability metadata, not fire outcomes. Do not use 2020-2021, and do not use 2022-2024 outcomes to choose it.

## 5. Critical weeks
**Prior-year eligibility (binding P5 decision, handoff `d0b8c90`)**
- Pre-freeze (before the Saturday 23:00 evaluation): 2020-2021 are ineligible everywhere. For the VIIRS era the eligible prior years are 2016 through min(T-1, 2019). For the Aqua era, earlier years are eligible only if their spans are exported, checked and registered.
- Post-freeze, T >= 2022: 2020-2021 may enter descriptive same-sensor weekly labels (critical and unusual) only if all four P5 conditions hold:
  1. the evaluation is frozen in `eval/eval_summary.json`;
  2. use is descriptive, same-sensor only;
  3. the Aqua 2020-08-16 to 2020-09-02 FMU/SSR outage is masked as unavailable, never zero;
  4. `eligible_prior_years` enumerates 2020 and 2021.
  They never enter factors or variants.
- P1-B gap: `BaselineConfig` takes a contiguous year range only. Excluding 2020-2021 while including 2022+ needs an explicit excluded-years field (code change after decision). For now, pre-freeze configs must set `eligible_end_year = 2019`.
- Data gap: weekly records need daily data. P2's daily export covers only California and British Columbia and is marked **pending** (DATA_CARD 6.2).

**Week-53 rule (separate from ranking)**
- Recommended week definition: ISO 8601 UTC weeks. This is what P1-B implements, and the contract supports it as `utc_iso_week`.
- ISO years with a week 53, 2003-2026: 2004, 2009, 2015, 2020, 2026. **None of 2016-2019 has one**, so week 53 never has a prior-year baseline in the current window.
- Rule:
  - `ranked_weeks` = ISO weeks 1-52.
  - Week 53 of a target year is reported as not ranked for critical weeks and as `insufficient_baseline` for unusual weeks.
  - Its days are not merged into week 52 or week 1, and it is never imputed.
- If `fixed_7_day_bins` were chosen instead, the contract caps at 52 bins. Dec 31 (and Dec 30 in leap years) would fall outside every bin, and that must be disclosed.

**Count and tie rule: unfrozen**
- `n_busiest_weeks` (candidate 4) and `tie_rule` stay unfrozen until P1 records them.
- Considerations, not a decision:
  - `include_all_tied` never drops a tied week, so the set can exceed n; its size is reported.
  - `lower_week_number_first` gives a fixed size, but the cut-off is arbitrary.
- Period support (Section 3) and footprint completeness apply to every week in every prior year.

## 6. What P1 needs to record (then Kiro codes, on the task branches, with tests)
1. Strata list and incomplete-month rule (strict, or a frozen availability-only list).
2. f for observation and period support; D_min for each factor and sensor.
3. Coverage definition, and whether a tolerance below 100% is a recorded deviation (with P4).
4. Week definition, `ranked_weeks`, the week-53 rule, `n_busiest_weeks` and `tie_rule`.
5. Excluded years per the P5 decision (pre-freeze `eligible_end_year = 2019`).

P2 inputs needed: land-cell counts per block and sensor; processed and expected pixel-days; the daily export for weekly views.
