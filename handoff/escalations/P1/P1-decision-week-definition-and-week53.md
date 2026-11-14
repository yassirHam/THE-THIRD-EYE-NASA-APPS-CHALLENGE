# Authoritative P1 Decision Record: Week Definition, Week 53 Baselines & Sealed-Window Boundaries

- **Decision Owner:** P1 (Scientific / Geospatial Lead)
- **To:** P2 (Data Lead), P4 (Contracts & Integration Lead), P5 (Independent Verification & Submission Lead), Kiro (P1 Science Writer)
- **Date:** 2026-11-14
- **Time:** 23:19:58 UTC
- **Time Zone:** UTC
- **Message Reference:** P1 decision message timestamp `2026-11-14T23:19:58Z` responding to `handoff/escalations/P1/P1-P2-decisions-batch-r1.md` (Items 1, 2, 3)
- **Status:** **BINDING SCIENTIFIC DECISION**

---

## 1. Binding P1 Decisions

### A. Week Definition (Batch Item 1)
- **Decision:** **Use UTC ISO weeks** (`utc_iso_week`, ISO 8601 Monday–Sunday UTC).
- **Rule:** All weekly calendar series and baseline aggregations use standard ISO 8601 week boundaries (Monday 00:00:00Z to Sunday 23:59:59Z). Fixed 7-day bins are not adopted for P1 calendar series.

### B. Week-53 Unusual Baseline Rule (Batch Item 2)
- **Decision:** **Require at least three complete, supported eligible prior ISO week-53 observations**, evaluated separately by sensor and confidence policy.
- **Rules:**
  1. Complete prior week-53 observations are required; weeks 52 or 1 **must never** be substituted, merged, or imputed into week 53.
  2. If fewer than 3 complete, supported eligible prior week-53 observations exist, the baseline status returns strictly `insufficient_baseline`.
  3. When baseline status is `insufficient_baseline`, no unusual-week label is issued (label is withheld / `null`).

### C. Sealed Holdout Boundary Handling (2020–2021) (Batch Item 3)
- **Decision:** **Strict partial-period boundary enforcement without reading sealed days.**
- **Rules:**
  1. For calendar weeks crossing into or out of the sealed 2020–2021 evaluation window, compute observations using **only permitted days** outside the sealed window.
  2. Mark the week as a partial period (`is_partial_period = True`) and comparison-ineligible (`comparison_eligible = False`).
  3. Both `unusual_status` and `critical_status` labels must be strictly `null`.
  4. Under no circumstances may sealed 2020–2021 days be read, unsealed, or ingested to complete a straddling period.

---

## 2. Settings Kept Formally OPEN / PENDING / UNAVAILABLE

Per P1 directive, all other candidate settings remain explicitly **unfrozen and open**:

1. **Week-53 Critical Ranking:** Remains OPEN (unranked; not included in critical baseline candidate pool).
2. **P1-A Status Vocabulary Mapping:** Remains OPEN pending export adapter agreement with Contract enums.
3. **Stage A Thresholds & Strata:** Proposed settings in `docs/DR-2026-11-14-09_StageA_PROPOSED.md` (`proposal/DR-2026-11-14-09-p1-rev1` SHA `94c3cb4`) remain PROPOSED / UNFROZEN pending P2 data facts confirmation.
4. **Footprint Coverage Tolerance:** 0.99 vs. 1.0 strict and cell-level vs. day-level completeness attestation remain OPEN.
5. **Critical-Week Ranking Parameters:** $n_{\text{busiest}}$ count, `ranked_weeks`, and tie-breaking rules remain OPEN.
6. **Required-Year Gaps:** If required prior years are missing or incomplete, the baseline remains strictly `unavailable` (never shortened or patched).
