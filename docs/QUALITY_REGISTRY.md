# THE THIRD EYE - Data Quality and Outage Registry

This document records all known sensor lifecycle events, orbital dynamics, algorithmic artifacts,
and temporal/spatial boundary conditions affecting daily active fire detections ($D$), usable observation
opportunities ($O$), and fire rates ($R = 1000 \cdot \sum D / \sum O$) across NASA MODIS (Aqua) and VIIRS (Suomi NPP).

Each entry provides reference URLs, operational context, and explicit impact on D and O accounting.

---

## 1. Suomi NPP Data Cessation and Mission Decommissioning

- **Issue ID:** `QUAL-001`
- **Component / Sensor:** Suomi NPP VIIRS (`NASA/VIIRS/002/VNP14A1`)
- **Event Date:** November 2, 2026, 15:40 UTC
- **Authoritative URLs:**
  - NOAA/NESDIS Update #3: [Cessation of Suomi NPP Data Users and Decommissioning](https://www.nesdis.noaa.gov/news/update-3-cessation-of-suomi-national-polar-orbiting-partnership-s-npp-data-users-november-02-2026-1540-utc-and-decommissioning-issued-october-30-2026-1400-utc)
  - NASA Earthdata LANCE Transition Notice: [Transitioning from Suomi NPP to NOAA-20 and NOAA-21: What LANCE Users Need to Know](https://www.earthdata.nasa.gov/news/blog/transitioning-from-suomi-npp-noaa-20-noaa-21-what-lance-users-need-know)
- **Status:** Closed archive.
- **Description:**
  NOAA/NESDIS terminated operational science data transmissions from the Suomi National Polar-orbiting Partnership (S-NPP) spacecraft at 15:40 UTC on November 2, 2026, as the satellite maneuvers for controlled atmospheric reentry in December 2026. Consequently, `VNP14A1` is a completed historical archive with no acquisitions after this timestamp.
- **Impact on D and O:**
  - **Availability flag:** For all dates after 2026-11-02 15:40 UTC, `viirs_file_present = 0`.
  - **Missingness vs Zero:** Ingestion and calendar pipelines must report `null` (unavailable) for $D_{viirs}$ and $O_{viirs}$. It is strictly forbidden to treat post-cessation dates as zero detections ($D=0$) or zero fire activity.
  - **Continuity path:** Near-real-time and post-2026 monitoring transitions to NOAA-20 VIIRS (`VJ114A1.002`). As mandated by scientific governance, NOAA-20 is an independent sensor platform; it does **not** inherit Suomi NPP calibration factors ($a_H$, $a_C$) or evaluation verdicts without separate registered calibration.

---

## 2. NASA Aqua Orbital Drift (Post-2022 Free-Drift Mode)

- **Issue ID:** `QUAL-002`
- **Component / Sensor:** Aqua MODIS (`MODIS/061/MYD14A1`)
- **Event Date:** Commenced January 2022 (exact maneuver date: to verify from flight operations logs; free drift ongoing)
- **Authoritative URLs:**
  - NASA Aqua Mission Status Reports: [Aqua Project Science & Status Reports (aqua.nasa.gov)](https://aqua.nasa.gov/)
  - NASA MODAPS Known Issues: [MODIS Known Issues - Aqua](https://landweb.modaps.eosdis.nasa.gov/knownissue?as=6&sat=Aqua&sensor=MODIS)
- **Status:** Ongoing operational drift.
- **Description:**
  To conserve remaining fuel reserves for eventual safe spacecraft de-orbiting, Aqua ceased orbital inclination-maintenance maneuvers in January 2022 (to verify) and exited the international Afternoon Constellation ("A-Train"). Without active inclination control, Aqua's sun-synchronous orbit has been freely drifting: its mean local equator-crossing time (MLT) has progressively delayed from nominal 13:30 (1:30 PM local) toward later afternoon hours, accompanied by gradual orbital altitude degradation.
- **Impact on D and O:**
  - **Working Hypothesis on D ($D_{aqua}$):** Because diurnal wildfire activity typically exhibits pronounced variations during mid-to-late afternoon (driven by surface heating, relative humidity drops, and winds), a drifting overpass time is hypothesized to sample a different phase of the diurnal fire curve. This effect is **treated as a working hypothesis to measure empirically from FIRMS `acq_time` distributions**, rather than asserted as an established fact.
  - **Observation opportunity ($O_{aqua}$):** Shifting overpass times alter solar zenith angles and diurnal cloud formation patterns (e.g., afternoon convective cumulus), potentially modifying cloud masking and clear-sky land counts ($O_{aqua}$).
  - **Evaluation boundary:** Harmonization factors ($a_H$, $a_C$) learned during the stable 2016–2018 window face potential non-stationarity when applied to 2022–2025. This drift is treated as an applicability condition requiring explicit disclosure.

---

## 3. NASA Terra Orbital Drift (Context Only)

- **Issue ID:** `QUAL-003`
- **Component / Sensor:** Terra MODIS (`MODIS/061/MOD14A1`) — *Reference context only*
- **Event Date:** Maneuvers ceased February 2020 (to verify); orbital lowering executed October 2022 (to verify)
- **Authoritative URLs:**
  - NASA Terra Orbital Drift Information: [Terra Orbital Drift Information](https://terra.nasa.gov/about/terra-orbital-drift-information)
- **Status:** Context only (Terra is not used in the primary baseline).
- **Description:**
  Terra ceased inclination adjustment maneuvers in 2020, allowing its descending equator crossing time to drift earlier from 10:30 AM MLT toward 09:00 AM MLT, and lowered its altitude in October 2022.
- **Impact on D and O:**
  - **Platform segregation:** This project designates Aqua (`MYD14A1`) as the sole reference scale. Terra data are neither merged nor averaged with Aqua data.
  - **Contextual lesson:** Terra confirms the physical dynamics of EOS constellation aging and reinforces why cross-platform factors cannot be inherited between sensors.

---

## 4. Heavy Smoke and Pyrocumulonimbus Misclassification as Cloud

- **Issue ID:** `QUAL-004`
- **Component / Sensor:** Aqua MODIS (`MYD14A1`) and Suomi NPP VIIRS (`VNP14A1`)
- **Event Date:** Recurring during severe wildfire events
- **Authoritative URLs:**
  - Giglio et al. (2016), Collection 6 MODIS Active Fire Algorithm: [Remote Sensing of Environment 178: 31–41](https://doi.org/10.1016/j.rse.2016.02.054)
  - NASA VIIRS Active Fire Product User Guide: [VIIRS Active Fire User Guide](https://viirsland.gsfc.nasa.gov/PDF/VIIRS_activefire_User_Guide.pdf)
- **Status:** Algorithmic characteristic.
- **Description:**
  Extremely dense smoke plumes and pyrocumulonimbus clouds generated by megafires exhibit high reflectance in visible wavelengths, strong absorption in infrared channels, and sharp spatial temperature gradients. Standard contextual algorithms can misclassify dense smoke cores as meteorological clouds (`FireMask = 4`).
- **Impact on D and O:**
  - **Suppression of fire detections ($D$):** Active flaming pixels beneath dense smoke may fail absolute or contextual thermal contrast tests, or be skipped entirely if pre-filtered as cloud.
  - **Suppression of usable observations ($O$):** By project definition, usable observation opportunity $O$ consists of clear land (`FireMask = 5`) and detected fire (`FireMask = 7–9`). Pixels flagged as cloud (`FireMask = 4`) are excluded from $O$. When smoke is classified as cloud over non-burning or smoldering land, $O$ is suppressed.
  - **Effect on Rate ($R = 1000 \cdot \sum D / \sum O$):** If smoke obscures surrounding land (reducing $O$) while central fire pixels pierce through (retaining $D$), localized rate spikes can occur. Conversely, complete cloud-masking of fire heads suppresses both $D$ and $O$.

---

## 5. Polar Night, Low Solar Angles, and Snow Cover at High Latitudes

- **Issue ID:** `QUAL-005`
- **Component / Sensor:** Aqua MODIS (`MYD14A1`) and Suomi NPP VIIRS (`VNP14A1`)
- **Event Date:** Seasonal (boreal winter, high northern latitudes)
- **Authoritative URLs:**
  - MODIS Active Fire ATBD: [MODIS Fire Algorithm Theoretical Basis Document](https://modis.gsfc.nasa.gov/data/atbd/atbd_mod14.pdf)
  - Google Earth Engine Catalog: [MYD14A1.061 Documentation](https://developers.google.com/earth-engine/datasets/catalog/MODIS_061_MYD14A1)
- **Status:** Seasonal environmental condition (Alaska, northern Canada).
- **Description:**
  At high northern latitudes during boreal winter, low solar elevation or complete polar night eliminates visible-band solar reflectance. Sub-freezing surface temperatures ($< 265\text{ K}$), extensive snow cover, and ice fog/stratus depress thermal contrast and induce algorithm rejection or widespread cloud flagging.
- **Impact on D and O:**
  - **Depressed observations ($O$):** Clear-sky non-fire land observations (`FireMask = 5`) drop dramatically during winter months across sub-arctic and arctic GAUL level 1 blocks.
  - **Undefined and volatile rates:** When winter conditions cause $O = 0$, rate calculations must strictly yield `null` (unavailable), avoiding division by zero. When $O$ drops to very small numbers, isolated thermal anomalies (such as industrial flares or false reflections) cause mathematical rate spikes.
  - **Methodological mandate:** Minimum observation thresholds and winter filtering rules must not be arbitrarily assumed by data engineering: any such threshold is **to be registered by P1 (Rim)** before evaluation.

---

## 6. Partial Ingestion Periods and Incomplete Calendar Coverage

- **Issue ID:** `QUAL-006`
- **Component / Sensor:** Aqua MODIS (`MYD14A1`) and Suomi NPP VIIRS (`VNP14A1`)
- **Event Dates:** 
  - Aqua first archive data day: **2002-07-04** (to verify launch vs commissioning: launch was 2002-05-04)
  - VIIRS S-NPP first archive data day: **2012-01-19** (to verify launch vs commissioning: launch was 2011-10-28)
- **Authoritative URLs:**
  - LP DAAC MYD14A1 Product Page: [MODIS/Aqua Thermal Anomalies/Fire Daily L3 Global 1km SIN Grid V061](https://doi.org/10.5067/MODIS/MYD14A1.061)
  - LP DAAC VNP14A1 Product Page: [VIIRS/NPP Thermal Anomalies/Fire Daily L3 Global 1km SIN Grid V002](https://doi.org/10.5067/VIIRS/VNP14A1.002)
- **Status:** Permanent historical boundary condition.
- **Description:**
  Sensor archives do not start on January 1 of their initial archive years:
  - Aqua archive data begin on **2002-07-04** (days 2002-01-01 to 2002-07-03 do not exist in the record).
  - July 2002 begins on **July 4** (July 1–3 are missing).
  - VIIRS S-NPP archive data begin on **2012-01-19** (days 2012-01-01 to 2012-01-18 do not exist in the record).
- **Impact on D and O:**
  - **Partial Year 2002:** Unstandardized annual sums for 2002 contain only ~6 months of data. Presenting 2002 as an annual total alongside full 12-month years creates an artificial ~50% deficit.
  - **Partial Month July 2002:** Aqua has 28 observation days instead of 31.
  - **Partial Month January 2012:** Aqua has 31 observation days, whereas VIIRS has only 13 days (Jan 19–31). Direct sensor comparison of monthly totals without day-level common masking (`O_common`) creates an artificial discrepancy.
  - **Availability flags:** Incomplete days have `file_present = 0`. Aggregations must enforce common valid days or rate-standardized denominators.

---

## 7. Earth Engine Dataset Catalog Specifications and Native Grid Sampling

- **Issue ID:** `QUAL-007`
- **Component / Sensor:** GEE Collections `MODIS/061/MYD14A1` and `NASA/VIIRS/002/VNP14A1`
- **Authoritative URLs:**
  - GEE Aqua MODIS: [MODIS/061/MYD14A1 on Google Earth Engine](https://developers.google.com/earth-engine/datasets/catalog/MODIS_061_MYD14A1)
  - GEE S-NPP VIIRS: [NASA/VIIRS/002/VNP14A1 on Google Earth Engine](https://developers.google.com/earth-engine/datasets/catalog/NASA_VIIRS_002_VNP14A1)
- **Status:** Operational catalog reference.
- **Description:**
  Both products are delivered in Google Earth Engine on the 1 km Sinusoidal equal-area grid.
  - `MYD14A1.061`: Derived directly from 1 km MODIS channels.
  - `VNP14A1.002`: Gridded 1 km composite generated from 750 m VIIRS M-band thermal detections (with bow-tie deletion applied in L2).
- **Impact on D and O:**
  - **Shared classification semantics:** Both products share identical `FireMask` band integer definitions:
    - `0–2`: Not processed
    - `3`: Water
    - `4`: Cloud
    - `5`: Clear land (usable non-fire land)
    - `6`: Unknown
    - `7`: Fire, low confidence
    - `8`: Fire, nominal confidence
    - `9`: Fire, high confidence
  - **Land filtering via QA:** Land mask is enforced using QA bits 0–1 == 2 (binary `10` = land; binary `00` = water).
  - **Resolution disparity & Factor $a_H$ / $a_C$:** Because VIIRS grids higher-resolution 750 m detections into 1 km cells, it detects smaller, cooler fires than MODIS 1 km, yielding consistently higher raw fire counts ($D_{viirs} > D_{aqua}$). This structural sensitivity gap is the exact estimand calibrated by own-support factor $a_H$ and diagnostic common-support factor $a_C$.
