# P5 Policy Reconciliation & Plan Change Notice: "Never Reuse Holdouts"

- **Task ID:** P5-GOV-001
- **From:** P5 (Validation, Evaluation & Submission Lead)
- **To:** P1 (Science Lead), P2 (Data Lead), P4 (Contracts & Integration Lead), P3 (Frontend Lead)
- **Date:** 2026-11-14 19:30 UTC
- **Topic:** Reconciling Post-Freeze Holdout Usage with the Plan's "Never Reuse Holdouts" Mandate and Integration Gate Status
- **Status:** **BINDING SCIENTIFIC SAFEGUARD & OPEN INTEGRATION GATE**
- **Governing Plan Authorities:** `THE_THIRD_EYE_FINAL_PLAN_GEOGRAPHIC_ACCESS_UPDATED.txt` (Plan SHA256: `84B012E26B808AB98BE6B66232ADBC22DC03AC3F1D4423304C38EBD21A521DDC`):
  - Lines 48–54: *"Earlier targets without enough prior years show unavailable. If required years/support are missing, report the affected experiment or baseline unavailable; never reuse holdouts. Disclose the actual spans and gaps; do not imply full-history coverage."*
  - Line 143: *"Holdout and outcome-inspection rules stay regardless: they are scientific safeguards, not event rules... renaming a project does not reset holdouts."*
  - Line 790: *"Do not consume a holdout to obtain more factor variants."*
  - Line 1958: *"Training and early-transfer evaluation cannot reuse the same records as independent evidence."*
  - Line 1991: *"no used holdout reclassified as untouched after a split revision."*

---

## 1. Executive Reconciliation: The "Never Reuse Holdouts" Rule

In review of P5's earlier guidance on post-freeze operations (`handoff/escalations/P4/P4-holdout-baselines-decision.md`), this document provides the authoritative reconciliation with the written plan's explicit mandate: **"never reuse holdouts"** (Plan Line 53).

### A. The Conflict
- **Plan Line 49–50** provides that for later targets, descriptive baselines use *"all eligible prior years from 2016 through the year before the target..."*
- **Plan Line 53** immediately commands: *"If required years/support are missing, report the affected experiment or baseline unavailable; never reuse holdouts."*
- Permitting 2020–2021 observations to enter descriptive baselines for subsequent target years ($T \ge 2022$) creates tension with Line 53's absolute prohibition against reusing holdouts.

### B. The Authoritative Resolution (Default Rule)
1. **Perpetual Holdout Integrity:** The 2020–2021 partition is the designated primary sealed evaluation benchmark. Under the plan's literal text, holdout data may **NEVER** be reused to backfill baseline pools, patch sample gaps, or compute statistics for other target years.
2. **Missing Prior Years = `insufficient_baseline`:** For target years $T \ge 2022$, if prior eligible years excluding 2020–2021 do not meet the registered `minimum_year_count`, the baseline must honestly evaluate to `"insufficient_baseline"` / `"unavailable"`. It must **never** borrow 2020–2021 holdout observations.
3. **Factor Fitting Absolute Ban:** 2020–2021 data may NEVER enter Stage A calibration or variant generation under any circumstance.

---

## 2. Proposed Plan Amendment PA-001 (Requires 4-Owner Unanimous Approval)

If the project team determines that post-freeze descriptive historical calendars for $T \ge 2022$ should include 2020–2021 under the four strict conditions outlined in `P4-holdout-baselines-decision.md`, this constitutes a formal **Plan Amendment (PA-001)** modifying Plan Line 53.

### Required Human Owner Approvals for PA-001:
- [ ] **P1 (Scientific / Geospatial Lead - Human Owner):** Approves scientific validity of descriptive inclusion and confirms zero contamination of calibration models.
- [ ] **P2 (Data / NASA Earth Observation Lead - Human Owner):** Certifies QA exclusion of Aqua FMU/SSR outage (Aug 16–Sep 2, 2020) and data lineage.
- [ ] **P4 (Contracts / Integration Lead - Human Owner):** Approves Contract 1.1.0 schema representation, explicit metadata disclosures, and serial merge impact.
- [ ] **P5 (Independent Evaluation Lead - Human Owner):** Certifies that the Saturday 23:00 evaluation benchmark on `$env:SEALED_EVAL_DIR` is fully frozen, committed, and uncompromised.

> **Current Status: PENDING / NOT APPROVED.**  
> Until all four human owners execute written sign-offs on PA-001, the **strict default rule governs**: 2020–2021 remains 100% sealed, excluded from all baselines, and never reused.

---

## 3. Mandatory Pre-Integration Gate Status (Held Open)

Prior to serial integration into `integration` and production packaging, the following three gates remain explicitly **UNRESOLVED / HELD OPEN**:

1. **Untagged Footprint Completeness (UNRESOLVED):**
   - Whole-area observation records without `block_id` (`required_blocks=None`) are accepted as aggregates, but are **NOT certified footprint-complete**.
   - Neither observation records nor fitted Stage A factors may be presented as verified whole-area coverage pending P2/P4 footprint attestation agreement (`handoff/escalations/P1/P1-B-001-r3.md` Item 2).
2. **Scientific Settings & Registry Decisions (UNRESOLVED / PENDING):**
   - Numeric `min_support_O` thresholds and strata lists for Stage A factor fitting remain unregistered.
   - Critical-week ranking parameters (`n_busiest_weeks`, `ranked_weeks`, `tie_rule`) remain unregistered.
   - These parameters must be registered before outcomes are inspected or factors fitted on production data.
3. **Status Vocabulary Mapping (UNRESOLVED / PENDING):**
   - P1-A internal scientific vocabulary (`sensitive`, `unresolved`, `evaluated_for_conditions`, `insufficient_evidence`) must be formally mapped to Contract 1.1.0 enums at the P4 export adapter boundary.

> **Operational Mandate:** The science codebase must **NOT** be represented as production-ready, and sealed holdout outcomes must **NOT** be unsealed or evaluated, while these three gates remain unresolved.
