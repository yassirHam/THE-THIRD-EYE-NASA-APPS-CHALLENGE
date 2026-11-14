# Specification & Governance Record: Exclusion of Real 2020–2021 Holdout Outcomes and Framework for Prospective Descriptive Use

- **Document ID:** P5-GOV-2026-11-14-01
- **From:** P5 (Independent Evaluation, E2E Parity & Submission Lead)
- **To:** P4 (Contracts & Integration Lead), P1 (Scientific / Geospatial Lead), P2 (Data Lead), Codex (Independent Reviewer & Judge)
- **Date:** 2026-11-14 19:22 UTC
- **Status:** **RATIFIED GOVERNANCE PROTOCOL & ARCHITECTURAL SPECIFICATION**
- **Authority:** User Directive (2026-11-14T19:17:54Z) & `THE_THIRD_EYE_FINAL_PLAN_GEOGRAPHIC_ACCESS_UPDATED.txt` (Plan SHA256: `84B012E26B808AB98BE6B66232ADBC22DC03AC3F1D4423304C38EBD21A521DDC`)

---

## 1. Formal Confirmation of Policy: Strict Holdout Exclusion

Effective immediately and binding across all lanes (P1, P2, P3, P4, P5):

1. **Absolute Exclusion:** Until the authoritative plan and a formal unanimous joint decision explicitly permit otherwise, **real 2020–2021 holdout observations are STRICTLY EXCLUDED** from:
   - All calibration models, factor fitting ($a_H, a_C$), variant generation, and sensitivity analysis.
   - All historical baseline spans (`SeasonalBaselineInfo.eligible_prior_years`, `MonthlyCalendarSeries`, `WeeklyCalendarSeries`) across all sensors and policies.
   - All claim audit evidence packages and cross-era comparisons.
2. **Firewall Isolation:** Real 2020–2021 data remains exclusively within isolated local storage (`$env:SEALED_EVAL_DIR`) under P5 custody for the singular purpose of the Saturday 23:00 P0 Holdout Evaluation (Plan Section 9A). Zero real holdout data may be checked into Git, transferred across network worktrees, or included in public static bundles.
3. **P4 Operational Posture:** P4 must continue to strictly assume that 2020 and 2021 are **INELIGIBLE** for all contract schemas, validation fixtures, and static site builds.

---

## 2. Documentation of Prospective Descriptive Use

This section documents the prospective descriptive use analyzed by P5, its motivation, its footprint, and its evaluation impacts:

### A. What the Proposed Descriptive Use Is
The prospective descriptive use would incorporate real 2020–2021 observations strictly as historical reference observations when computing non-parametric historical distributions:
- **Metrics:** Calendar-month median rate ($R_{\text{median}}$) and 90th percentile rate ($R_{\text{p90}}$, nearest-rank) in `MonthlyCalendarSeries`.
- **Labels:** Descriptive `"unusual"` month/week labels and `"critical"` week rankings in `WeeklyCalendarSeries`.
- **Sensors:** Separately within `VIIRS_SNPP` and `MODIS_Aqua` (never crossing sensors).
- **Target Periods:** Only for late target years ($T \in \{2022, 2023, 2024, 2025, 2026\}$).

### B. Why It Was Conceived / Why It Might Be Needed
1. **Statistical Sample Depth for VIIRS S-NPP:**
   - VIIRS S-NPP historical records in the core extract begin in 2016.
   - If 2020–2021 are excluded, a 2022 target year has only 4 prior years (2016, 2017, 2018, 2019), which creates marginal sample depth for 90th percentile estimations ($\lceil 0.90 \times 4 \rceil = 4$, making the single maximum historical year the sole p90 threshold).
   - For 2024 targets, excluding 2020–2021 leaves a non-contiguous span (2016–2019 and 2022–2023) with an artificial 2-year hole.
2. **Context for Extreme Fire Seasons:**
   - Assessing whether 2023 or 2024 regional fires were historically unusual benefits from knowing their relationship to the high-activity 2020 fire season.

### C. Which Artifacts and Claims Would Be Affected
- **Affected Artifacts:**
  - `contracts/schemas/calendar.py`: `SeasonalBaselineInfo.eligible_prior_years` would contain `2020` and `2021`.
  - Exported production calendar JSON files for target years $T \ge 2022$.
  - Public static site displays on `/lab` and `Calendar.tsx`.
- **Unaffected Artifacts (Firewalled):**
  - `StageAArtifact` / `FactorResult`: Calibration factors ($a_H, a_C$) are mathematically and procedurally isolated; they are fitted strictly on `2016–2018` training data and remain immutable.
  - `ClaimAuditArtifact`: Flagship claims evaluate specific period pairs and do not rely on 2020–2021 holdouts as training data.
  - `EvaluationArtifact`: Headless evaluation runner output (`eval/eval_summary.json`) remains independent.
- **Affected Claims:**
  - Only descriptive calendar labels: whether a specific week or month in 2022–2026 is designated `"unusual"` or `"critical"`.
  - Zero impact on cross-sensor correction validity or factor sensitivity conclusions.

---

## 3. Compromise Analysis: Impact on Independent Evaluation & Replay

| Evaluation Vector | Potential Compromise / Risk | P5 Assessment & Safeguard |
| :--- | :--- | :--- |
| **Saturday 23:00 P0 Evaluation** *(Plan Section 9A)* | **FATAL if accessed pre-freeze.** Opening holdout data before methods and configurations freeze destroys the double-blind integrity of the primary benchmark. | **Absolute Firewall:** Pre-freeze access is forbidden under all circumstances. Sealed evaluation runner operates strictly on local isolated storage outside Git. |
| **Late-Period Applicability Check** *(2022–2024)* | **HIGH RISK of Circularity.** The 2022–2024 period acts as a temporal transfer check. If its descriptive baseline incorporates holdouts used to validate the model, temporal independence is degraded. | **Exclusion Preserves Independence:** Excluding 2020–2021 guarantees complete temporal separation between the primary holdout test and the late-period applicability check. |
| **Clean-Room InstaBox Replay** *(Plan §3 & INSTABOX.md)* | **SEVERE REPLAY HAZARD.** The Sunday 12:00 InstaBox replay operates on a clean Linux container against the **public evidence bundle**. Public bundles cannot require private credentials or isolated holdout directories. | **Public Reproducibility:** If public calendar artifacts require real holdouts, holdout data would leak into the public bundle. Excluding holdouts ensures public bundles replay cleanly without holdout access. |

**Conclusion:** Using real 2020–2021 holdout outcomes in public baselines introduces significant evaluation and replay risks that outweigh descriptive sample-depth gains. **Strict exclusion is the scientifically sound choice.**

---

## 4. Exception Protocol & Required Approvals

If any team member proposes an exception to permit real 2020–2021 outcomes in post-freeze baselines, all of the following steps **must be completed prior to any data access, code modification, or computation**:

1. **Authoritative Plan Revision:**
   - Formal amendment of `THE_THIRD_EYE_FINAL_PLAN_GEOGRAPHIC_ACCESS_UPDATED.txt`:
     - Line 53 ("never reuse holdouts") must be amended with an explicit, narrowly scoped exception clause.
     - Section 3A (Seasonal Baseline) must define the exact date range and unsealing timestamp.
     - Section 5A must record the lifecycle change for the evaluation partition.
2. **Satellite-Quality Registry Amendment (Plan Section 9B):**
   - The NASA Aqua FMU/SSR outage (August 16 – September 2, 2020) and post-2021 orbital drift must be formally registered with explicit `qa_unusable` masking rules to prevent outage contamination.
3. **Unanimous Formal Concurrence:**
   - Formal sign-off in `handoff/` from:
     - **P1 (Science Lead):** Concurrence on scientific validity of the resulting baseline.
     - **P2 (Data Lead):** Attestation of export completeness and mask integrity.
     - **P4 (Contracts Lead):** Validation of schema and cache-key compatibility.
     - **P5 (Evaluation Lead):** Certification that Saturday 23:00 evaluation and clean-room replay are uncompromised.
     - **Codex (Independent Judge):** Formal review verdict confirming firewall compliance.
4. **Sequencing:** Any approved unsealing can occur **only after** the Saturday 23:00 P0 Evaluation is finalized, frozen, and published in `eval/eval_summary.json`.

---

## 5. Synthetic Fixtures Protocol for Boundary Tests

To prevent confusion between test infrastructure and real holdout data:

1. **Fabricated Values Only:** Synthetic test fixtures containing 2020–2021 dates (e.g. testing S-NPP cessation on 2026-11-02, week 45 straddling, or leap-year boundaries) must use purely artificial, mathematically fabricated numbers.
2. **Zero Derivation from Real Holdouts:** Synthetic fixtures must never be derived from, sampled from, or calibrated against real sealed observations in `$env:SEALED_EVAL_DIR`.
3. **Mandatory Explicit Labeling:** All synthetic fixtures must carry explicit top-level metadata or file header comments:
   ```json
   "fixture_classification": "[SYNTHETIC DEV FIXTURE - NOT REAL OBSERVATION DATA]"
   ```
4. **No Authorization Conferred:** The presence of synthetic 2020–2021 dates in test suites confers **zero authorization** to access, commit, or compute with real holdout outcomes.
