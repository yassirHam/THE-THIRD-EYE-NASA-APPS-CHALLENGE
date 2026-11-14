# DATA CARD: THE THIRD EYE (AFTERIMAGE) - Raw Daily D/O Fire & Observation Aggregates

## 1. Dataset Summary & Governance
- **Dataset Title:** Raw Daily D/O Active Fire & Observation Opportunity Aggregates
- **Domain:** United States (including Alaska and Hawaii) and Canada
- **Zonal Units:** Administrative Level 1 subdivisions (States and Provinces) from FAO GAUL 2015 (`ADM1_CODE`, `ADM1_NAME`, `ADM0_NAME`)
- **Temporal Range:** 2002-07-04 through 2025-12-31 (first data days: 2002-07-04 for Aqua, 2012-01-19 for VIIRS S-NPP)
- **Lead / Owner:** P2 (NASA Data & Geography Lead), reviewed with P1 (Science Lead, Rim) and P4 (Integration Lead)
- **Scientific Nature:** These are **raw daily D/O aggregates**, not harmonized data. Harmonization factors ($a_H$ own-support, $a_C$ common-support) and rates are computed downstream by P1/P4.
- **Reference Platform:** Aqua MODIS (`MYD14A1.061`) represents the canonical baseline scale (2002–2019 native Aqua scale; never claim pre-2012 is harmonized).

---

## 2. Upstream Data Sources
| Dataset | Source Collection | Platform / Sensor | Native Spatial Resolution | Temporal Coverage | Provider |
|---|---|---|---|---|---|
| **Aqua Fire Daily** | `MODIS/061/MYD14A1` | Aqua MODIS | 1 km Sinusoidal Grid | 2002-07-04 (first data day) to present | NASA LP DAAC / Google Earth Engine |
| **VIIRS Fire Daily** | `NASA/VIIRS/002/VNP14A1` | Suomi NPP VIIRS | 1 km Sinusoidal Grid (from 750m) | 2012-01-19 (first data day) to 2026-11-02 (closed) | NASA LP DAAC / Google Earth Engine |
| **Administrative Units** | `FAO/GAUL/2015/level1` | Global Administrative Unit Layers | Polygons | 2015 | FAO / Google Earth Engine |
| **Auxiliary Hotspots** | FIRMS Country Summaries (CSV) | MODIS & VIIRS 375m | Point vector | 2002–2025 | NASA FIRMS (Separate view only; never enters D/O) |

---

## 3. Data Processing & Aggregation Logic
1. **Grid & Boundary Assignment:** Computations are performed on the native Sinusoidal projection grid. Grid cell center points are assigned to FAO GAUL level 1 polygons via unweighted zonal summation.
2. **Land Surface Verification:** Enforced by evaluating QA bits 0–1 == 2 (binary `10` = land; binary `00` = water). Water and non-land pixels are excluded.
3. **Active Fire Identification ($D$):**
   - Standard: `FireMask` values 7 (low confidence), 8 (nominal confidence), 9 (high confidence) on land.
   - Nominal/High subset ($D_{nh}$): `FireMask` values 8 and 9 on land.
4. **Usable Observation Opportunity ($O$):**
   - Defined as clear non-fire land (`FireMask = 5`) OR confirmed fire (`FireMask \in \{7, 8, 9\}`), on land.
   - Cloudy pixels (`FireMask = 4`), non-processed (`0–2`), and unknown (`6`) pixels are strictly excluded from $O$.
5. **Common Support Mask ($O_{common}$):**
   - Pixel cell is usable in both Aqua and VIIRS on the identical UTC date and location.
6. **Downstream Rate Calculation ($R$):**
   - Rates ($R = 1000 \cdot \sum D / \sum O$) are **not** stored in this daily table.
   - Sums of $D$ and $O$ across spatial units or temporal intervals must always be performed **before** division to avoid Simpson's paradox and undefined ratios.

---

## 4. Dataset Partitions, Phased Access, and Quarantined Splits
| Split Name | Temporal Span | Status | Access Rights & Purpose |
|---|---|---|---|
| **Pre-VIIRS Historical** | 2002-07-04 to 2011-12-31 | Available | Native Aqua reference scale. Not harmonized (no VIIRS exists). |
| **Historical Overlap** | 2012-01-19 to 2015-12-31 | Controlled | Use must be formally registered by P1 before inspection. |
| **Training Split** | 2016-01-01 to 2018-12-31 | Active | Transferred to P1 to compute own-support $a_H$ and diagnostic $a_C$. |
| **Development Split** | 2019-01-01 to 2019-12-31 | Active | Transferred to P1 for method tuning and boundary verification. |
| **SEALED Evaluation** | 2020-01-01 to 2021-12-31 | **SEALED** | **Quarantined exclusively for P5.** Quarantined from P1, P2, P3, P4. |
| **Applicability Window** | 2022-01-01 to 2025-12-31 | Held | Out-of-sample evaluation under Aqua orbit drift dynamics. |

*Phased Access Rule:* P1 receives only 2016–2019 until scientific methods freeze. 2020–2021 exports route strictly to P5 storage.

---

## 5. Proposed Geographic Evaluation Status
- **Primary Candidate (Proposed):** `California` (`ADM0_NAME = "United States of America"`, `ADM1_NAME = "California"`)
- **Backup Candidate (Proposed):** `British Columbia` (`ADM0_NAME = "Canada"`, exact GAUL name `ADM1_NAME = "British Columbia / Colombie-Britannique"`)
- **Status:** **Proposed candidates, not registered.** Formal registration requires P1 (Rim) sign-off and a frozen numeric feasibility rule, recorded before any outcome is inspected.
- **All Remaining Blocks:** Designated as `raw_only` (total 64 blocks across US and Canada). Factors calibrated on California or BC must never be inherited by `raw_only` blocks without explicit separate calibration.

---

## 6. Table Schema & Column Specifications
Raw daily export files are stored as `afterimage_daily_YYYY.csv` (raw export) and converted to validated `afterimage_daily_YYYY.parquet` (checked).

The table schema matches the exact export columns:

| Column Name | Type | Nullable | Description |
|---|---|---|---|
| `ADM0_NAME` | `STRING` | No | Country name ("United States of America" or "Canada"). |
| `ADM1_CODE` | `INT32` | No | FAO GAUL 2015 level 1 unique numeric code (read from GAUL asset). |
| `ADM1_NAME` | `STRING` | No | Administrative division name (e.g., "California", "British Columbia / Colombie-Britannique"). |
| `date` | `DATE` | No | Calendar date in UTC (`YYYY-MM-DD`). |
| `aqua_file_present` | `INT8` | No | 1 if Aqua data file was present; 0 if missing/unavailable. |
| `viirs_file_present`| `INT8` | No | 1 if VIIRS data file was present; 0 if missing/unavailable. |
| `D_aqua` | `INT32` | Yes | Daily active fire pixel count on land for Aqua (`FireMask` 7–9). Null if file missing. |
| `O_aqua` | `INT32` | Yes | Daily usable observation pixel count on land for Aqua (`FireMask` 5 or 7–9). Null if file missing. |
| `D_viirs` | `INT32` | Yes | Daily active fire pixel count on land for VIIRS (`FireMask` 7–9). Null if file missing. |
| `O_viirs` | `INT32` | Yes | Daily usable observation pixel count on land for VIIRS (`FireMask` 5 or 7–9). Null if file missing. |
| `O_common` | `INT32` | Yes | Count of pixels mutually usable in both Aqua and VIIRS on this day. |
| `D_aqua_common` | `INT32` | Yes | Aqua active fire pixels within the mutually usable mask. |
| `D_viirs_common` | `INT32` | Yes | VIIRS active fire pixels within the mutually usable mask. |
| `D_aqua_nh` | `INT32` | Yes | Aqua nominal and high confidence fire pixels (`FireMask` 8–9). |
| `D_viirs_nh` | `INT32` | Yes | VIIRS nominal and high confidence fire pixels (`FireMask` 8–9). |

*(Note: Rates $r\_aqua$ and $r\_viirs$ are deliberately excluded from this daily table; rates must be computed after aggregation by summing $D$ and $O$ first).*

---

## 7. Nullity, Zero, and Edge Case Rules
1. **Missing Data vs Zero Detections:**
   - If an orbital tile or day is not collected: `file_present = 0`, and detection columns ($D, O$) are `NULL`.
   - A value of `0` in $D$ strictly represents a valid observation day where clear land was observed ($O > 0$) with zero active fires detected.
2. **Zero Opportunity ($O = 0$):**
   - If extensive cloud cover or winter polar darkness results in $O = 0$, fire rate $R$ is `NULL` (unavailable). Division by zero is prohibited.
3. **Strict Separation of FIRMS Point Hotspots:**
   - FIRMS point CSVs are maintained in standalone typed Parquet tables (`data/firms/`) flagged with `is_vegetation_fire` and `is_reference_platform`.
   - FIRMS point counts are strictly intended for P3's "Reported Hotspots" visual layer. They never enter $D$, $O$, rate calculations, baseline distributions, or harmonization factors.
