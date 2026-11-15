# THE THIRD EYE - Architecture & Data Decisions Log (P2 Data Lead)

This document records formal architectural, spatial, temporal, and methodological data decisions
adopted by the P2 Data lane in coordination with Science (P1, Rim), Frontend (P3), Integration (P4),
and Independent Verification (P5).

---

## Decision Record 2026-11-14-01: Spatial Domain and Block Keying
- **Date:** 2026-11-14
- **Decision:** The spatial domain encompasses the United States (including Alaska and Hawaii) and Canada (64 blocks from FAO GAUL 2015 Level 1).
- **Boundary Source:** FAO GAUL 2015 Level 1 (`FAO/GAUL/2015/level1` in Google Earth Engine).
- **Keying:** Each block is uniquely identified and keyed by `ADM1_CODE` (with accompanying `ADM1_NAME` and `ADM0_NAME` for display).
- **Exact GAUL Naming:** British Columbia's exact GAUL name (`ADM1_NAME`) is `"British Columbia / Colombie-Britannique"`.
- **Rationale:** Standardized administrative boundaries ensure reproducible zonal aggregation without boundary drift or arbitrary polygon creation. GAUL 2015 Level 1 aligns with official country/state/province designations.

---

## Decision Record 2026-11-14-02: Sensor Archive Bounds and Reference Scale
- **Date:** 2026-11-14
- **Sensors:**
  - MODIS Aqua: `MODIS/061/MYD14A1` (archive begins 2002-07-04)
  - VIIRS S-NPP: `NASA/VIIRS/002/VNP14A1` (archive begins 2012-01-19)
- **Period Bounds:** 2002-07-04 through 2025-12-31.
- **Reference Scale:** Aqua MODIS is established as the canonical reference scale.
  - The historical era (2002–2019) remains on native Aqua scale.
  - VIIRS data from 2020 onward are harmonized onto the Aqua scale using calibration factor $a_H$ learned during the overlap period.
  - **Hard Rule:** Never claim that the pre-2012 era is harmonized (VIIRS did not exist prior to January 2012).
- **Partial Periods:** 2002 (first archive day July 4), July 2002 (missing July 1–3), and January 2012 (first VIIRS archive day Jan 19) are formally recorded as partial periods. Direct unstandardized comparisons across these partial spans are prohibited.

---

## Decision Record 2026-11-14-03: Temporal Partitioning, Phased Access, and Sealed Evaluation Split
- **Date:** 2026-11-14
- **Splits:**
  - **Training:** 2016–2018 (3 full overlap years for Rim / P1 to compute own-support factor $a_H$ and diagnostic factor $a_C$).
  - **Development / Tuning:** 2019 (1 full year for P1 method validation and parameter checks).
  - **SEALED Evaluation (P5 only):** 2020–2021 (strictly held out; direct export to P5-only storage).
  - **Applicability Assessment:** 2022–2025 (testing behavior under Aqua orbital drift and late-mission dynamics).
  - **Historical Overlap:** 2012–2015.
- **Phased Access Policy:**
  - P1 receives **only 2016–2019** until scientific methods are frozen.
  - 2012–2015 data use must be formally registered by P1 before any inspection.
  - 2020–2021 is strictly SEALED for P5: P2, P1, P3, P4, and automated agents must never open, read, parse, summarize, or tune methods on the 2020–2021 partition.

---

## Decision Record 2026-11-14-04: Proposed Evaluated vs Raw-Only Regions
- **Date:** 2026-11-14
- **Proposed Evaluated Regions:**
  - **Primary (Proposed):** California (`ADM1_NAME = "California"`, United States)
  - **Backup (Proposed):** British Columbia (`ADM1_NAME = "British Columbia / Colombie-Britannique"`, Canada)
- **Status of Other Blocks:** All other US states and Canadian provinces are classified as `raw_only` (total 64 blocks).
- **Pre-Registration Requirement:** California and British Columbia are **proposed candidates**, not registered. Official registration requires:
  1. P1 (Rim) scientific sign-off, and
  2. A frozen numeric feasibility rule (minimum fire observations / events),
  recorded in this log **before any outcome or result is inspected**. Factors learned on California/British Columbia must never be automatically inherited by un-evaluated `raw_only` blocks.

---

## Decision Record 2026-11-14-05: Grid Aggregation, Masking, and D/O Accounting
- **Date:** 2026-11-14
- **Grid:** Native 1 km Sinusoidal grid. Pixels are assigned to administrative blocks based on pixel center coordinates (unweighted sum; no artificial resampling or reprojection).
- **Land Mask:** QA bits 0–1 == 2 (binary `10` = land; binary `00` = water).
- **Active Fire ($D$):** `FireMask` values 7, 8, 9 (low, nominal, high confidence) on land.
  - Nominal/High subset ($D_{nh}$): `FireMask` values 8, 9 on land.
- **Usable Observation Opportunity ($O$):** `FireMask = 5` (clear non-fire land) OR `FireMask \in \{7, 8, 9\}` (fire), on land.
- **Common Support ($O_{common}$):** Pixels that are simultaneously usable ($O$) in both Aqua and VIIRS on the same cell and UTC day.
- **Missingness vs Zero:**
  - If a file or tile is missing or not acquired: `file_present = 0`. Data values are recorded as `null` (unavailable), never zero.
  - If $O = 0$ (all cloudy, polar night, or missing): fire rate $R$ is unavailable/`null`. Never divide by zero.
- **Rate Formulation:** $R = 1000 \cdot \frac{\sum D}{\sum O}$. Rates are not stored in raw daily tables; sums across pixels and days must always be computed prior to performing division.

---

## Decision Record 2026-11-14-06: Strict FIRMS Hotspot Point Segregation
- **Date:** 2026-11-14
- **Decision:** NASA FIRMS Country Yearly Summary CSV/Parquet point detections are strictly segregated from grid calculations.
- **Enforcement:** FIRMS points NEVER enter $D$, $O$, rate calculations, baseline distributions, harmonization factors, or scientific verdicts.
- **Role:** FIRMS data serve solely as an auxiliary visual/explainer feed for P3's "Reported Hotspots" view (scheduled for P0-late).

---

## Decision Record 2026-11-14-07: Monthly Export Execution (V2 Method) and Phased Data Delivery
- **Date:** 2026-11-14
- **Execution & Scope:** Monthly export of all 64 blocks, 2002-07 to 2025-12, V2 method (blocks rasterized once on the native 1 km grid, grouped monthly reduction).
- **Row Count & Validation:** 16,512 rows, checks OK.
- **Phased Delivery to P1:**
  - P1 received 2016–2019 only:
    - California + British Columbia: 96 rows.
    - All 64 blocks: 3,072 rows.
  - A sharing error was fixed and P1 did not open 2020–2025.
