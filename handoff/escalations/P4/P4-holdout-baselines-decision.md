# Authoritative P5 Decision: 2020–2021 Holdout Rules & Baseline Eligibility

- **From:** P5 (Validation, Evaluation & Submission Lead)
- **To:** P4 (Contracts & Integration Lead), P1 (Scientific / Geospatial Lead), P2 (Data Lead)
- **Date:** 2026-11-14 19:10 UTC
- **Topic:** Eligibility of 2020–2021 observations in historical baselines for subsequent target years ($T \ge 2022$)
- **Status:** **BINDING ARCHITECTURAL & EVALUATION DECISION**
- **Governing Plan Authorities:** `THE_THIRD_EYE_FINAL_PLAN_GEOGRAPHIC_ACCESS_UPDATED.txt` (Plan SHA256: `84B012E26B808AB98BE6B66232ADBC22DC03AC3F1D4423304C38EBD21A521DDC`), specifically:
  - Lines 45–54 (Core data partitions, baseline spans, and the "never reuse holdouts" rule)
  - Lines 71, 139, 143 (Sealed holdout isolation and outcome-inspection boundaries)
  - Lines 301–310 (Same-sensor seasonal baseline calculations)
  - Lines 730–734 (Provisional data splits and holdout freeze safeguards)
  - Lines 788–791 ("Do not consume a holdout to obtain more factor variants")
  - Lines 1404–1408 (Aqua 2020 FMU/SSR disruption and post-2021 orbital drift)
  - Lines 1958, 1991 ("Training and early-transfer evaluation cannot reuse the same records as independent evidence")

---

## 1. Executive Ruling & Direct Answer to P4

1. **For Current Contract 1.1.0, Pre-Freeze Static Artifacts, and Saturday 20:00 Checkpoint:**
   - **DECISION: 2020–2021 observations are STRICTLY INELIGIBLE.**
   - P4 must **NOT** assume 2020–2021 are eligible. All static fixtures, contract assertions, and pre-freeze calendar series must exclude 2020–2021 from `eligible_prior_years`.
   - The holdout firewall remains hermetically sealed in isolated local storage (`$env:SEALED_EVAL_DIR`) under P5's sole custody. Zero sealed holdout data or outcomes may be unsealed, read, or incorporated into development or integration branches prior to the Saturday 23:00 evaluation freeze.

2. **For Post-Freeze Operations (After the Saturday 23:00 Evaluation Report is Published):**
   - **Factor Fitting & Calibration Models:** 2020–2021 observations **MAY NEVER** be included in Stage A training, factor fitting ($a_H, a_C$), or variant generation.
   - **Descriptive Same-Sensor Historical Calendars ($T \ge 2022$):** 2020–2021 observations **MAY ONLY** be included in same-sensor descriptive baselines (e.g. median and P90 rates for VIIRS or Aqua) if and only if **all four mandatory conditions in Section 3** are satisfied.
   - If any condition is unmet, 2020–2021 remain **permanently ineligible**, and baselines lacking sufficient prior years must report `"insufficient_baseline"` rather than silently ingesting holdouts.

---

## 2. Authoritative Reasoning from the Plan

### A. The Partition Split and Firewall Mandate
The authoritative plan preregisters a strict 4-way temporal partition (Plan lines 45–47, 730–731):
- `2016–2018`: Stage A training (factor fitting $a_H$, $a_C$).
- `2019`: Development validation.
- `2020–2021`: Primary sealed evaluation holdout (held under P5 in `$env:SEALED_EVAL_DIR`).
- `2022–2024`: Separate late-period temporal applicability check.

The 2020–2021 partition is the core benchmark holdout used to evaluate cross-sensor handover ($A \to V$ vs $A \to A$) at the artificial sensor switch (Section 9A). As established in Plan lines 143 and 734:
> *"Holdout and outcome-inspection rules stay regardless: they are scientific safeguards, not event rules... renaming a project does not reset holdouts."*

### B. The "Never Reuse Holdouts" Rule (Plan Lines 48–54)
While line 49–50 states that for later targets, baselines use *"all eligible prior years from 2016 through the year before the target"*, line 53 establishes the immediate overriding constraint:
> *"Earlier targets without enough prior years show unavailable. If required years/support are missing, report the affected experiment or baseline unavailable; never reuse holdouts. Disclose the actual spans and gaps; do not imply full-history coverage."*

"Never reuse holdouts" means that holdout data cannot be opportunistically repurposed to patch gaps in development baselines, expand training pools, or manufacture statistical support. During development and prior to the evaluation freeze, 2020–2021 data is physically sealed. Including it in pre-freeze baseline series would destroy the holdout firewall.

### C. Prohibition Against Holdout Consumption for Models (Plan Line 790, 1958, 1991)
The plan is unequivocal regarding model parameters:
- Line 790: *"Do not consume a holdout to obtain more factor variants."*
- Line 1958: *"Training and early-transfer evaluation cannot reuse the same records as independent evidence."*
- Line 1991: *"no used holdout reclassified as untouched after a split revision."*

Thus, under no circumstances may 2020–2021 be used to fit, tune, or re-estimate calibration parameters ($a_H$, $a_C$) or variant dictionaries.

### D. Sensor Quality Disruptions in 2020–2021 (Plan Lines 1404–1408)
The plan identifies critical sensor health anomalies during 2020–2021:
- Aqua FMU/SSR disruption began August 16, 2020 (recovered September 2, 2020).
- Evolving orbital drift and sampling geometry changes occurred around and after 2021.
Blindly including Aqua 2020–2021 into an unweighted reference baseline without explicit QA exclusion would contaminate the baseline with mission-outage artifacts, violating Section 9B.

---

## 3. Mandatory Conditions for Post-Freeze Inclusion in Later Baselines ($T \ge 2022$)

2020–2021 observations may be included in descriptive historical baselines for subsequent target years ($T \ge 2022$) **if and only if** all four conditions are met:

1. **Temporal & Procedural Gate (Post-Saturday 23:00):**
   - The primary held-out sensor-switch evaluation (Section 9A) has executed against `$env:SEALED_EVAL_DIR`, its results are frozen and committed into `eval/eval_summary.json`, and Stage A methods are locked.
   - Zero pre-freeze public artifact or test fixture may reference or ingest 2020–2021.

2. **Domain & Task Isolation:**
   - Inclusion is restricted strictly to **descriptive same-sensor historical rate distributions** (`MonthlyCalendarSeries.baseline_median` and `baseline_p90`, and `WeeklyCalendarSeries` critical/unusual labels) within the same sensor era (`MODIS_Aqua` or `VIIRS_SNPP`).
   - Strictly prohibited from cross-sensor calibration fitting, variant sensitivity audits, or claim validation.

3. **Instrument Quality & Outage Accounting (Section 9B):**
   - For **Aqua (MODIS)**: The August 16 – September 2, 2020 FMU/SSR outage must be explicitly masked out and recorded as `qa_unusable` or `source_not_available`, never treated as valid zero detection or zero-filled.
   - For **VIIRS (S-NPP)**: Observations must pass standard usable land support ($O > 0$) and footprint completeness validation.

4. **Transparent Contractual Metadata:**
   - `SeasonalBaselineInfo.eligible_prior_years` must explicitly enumerate `2020` and `2021`.
   - The UI and metadata must disclose the baseline span and note documented sensor anomalies rather than implying an uninterrupted, ideal baseline.

---

## 4. Implementation Guidance for Teams

### For P4 (Contracts & Integration):
- **Immediate action:** Keep Contract 1.1.0 and all static fixtures assuming 2020–2021 are **INELIGIBLE**.
- In `contracts/schemas/calendar.py`, ensure that for any series where 2020–2021 are absent, if the remaining eligible prior years do not meet `minimum_year_count`, `SeasonalBaselineInfo.status` evaluates strictly to `"insufficient_baseline"`.
- Do not add 2020 or 2021 to `sample_calendar.json` or any synthetic fixture without explicit P5 coordination.

### For P1 (Science):
- In `science/calendar/baseline.py`, parameterize `eligible_start_year` and `eligible_end_year` explicitly in `BaselineConfig`. For pre-freeze runs on target years $T \ge 2020$, ensure the eligible range respects the holdout firewall.
- Do not consume 2020–2021 to generate additional leave-one-out factor variants.

### For P2 (Data):
- Keep 2020–2021 evaluation partitions securely segregated in `$env:SEALED_EVAL_DIR`.
- Only supply development partitions (`2016–2019`, `2022–2024`) to P1/P3/P4 for static site generation prior to the Saturday 23:00 evaluation checkpoint.
