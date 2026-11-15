# THE THIRD EYE: one-page results

## 1. Header

- **Project Identity**: THE THIRD EYE, a historical fire calendar that shows when a satellite change, not the fire, made the difference, and when it can't tell.
- **Challenge Category**: NASA Space Apps 2026, "Harmonization of MODIS and VIIRS Hot Spots" ([capture](../../challenge/CHALLENGE_CAPTURE.md)). Category tags: [PENDING VERIFICATION]
- **Team Members**: [PENDING TEAM INPUT]
- **Artifact Hashes**: SHA256 of git blob content. Pinned commit: `71a37b13e8557723f3f5a4f20b8c77d7441f5c57`

| artifact_id | Path | SHA256 |
|---|---|---|
| plan | `THE_THIRD_EYE_FINAL_PLAN_GEOGRAPHIC_ACCESS_UPDATED.txt` | `84b012e26b808ab98be6b66232adbc22dc03ac3f1d4423304c38ebd21a521ddc` |
| execution-spec | `THE_THIRD_EYE_EXECUTION_SPEC.md` | `61127df71708c56c2a07981f6130063d384e981f9e277f8d5cb3d3d241e71331` |
| primary-region | `data/manifests/canonical_regions.geojson` | `0d6574ad87942d343d124386357337c6d2a12a30003c88efa4e24528b843f1f1` |
| eval-summary | frozen held-out report | [PENDING MEASURED RUN] |
| evidence-bundle | public replay bundle | [PENDING MEASURED RUN] |

Data: Aqua MODIS `MODIS/061/MYD14A1` and Suomi NPP VIIRS `NASA/VIIRS/002/VNP14A1`, daily 1 km grids. Unit: fire-cell-day rate, detected fire cell-days per thousand usable land cell-days. It is not a count of fires or hotspot points.

## 2. Denominator Statement

Headline metric (frozen wording; numbers appear only after the Saturday 23:00 evaluation):

> At an artificial sensor switch, raw MODIS-to-VIIRS comparisons pointed the wrong way in [PENDING MEASURED RUN] of [PENDING MEASURED RUN] cases; after correction, [PENDING MEASURED RUN]. THE THIRD EYE flagged [PENDING MEASURED RUN] of the remaining errors and abstained on [PENDING MEASURED RUN].

| Independent unit | Count |
|---|---|
| regions | [PENDING MEASURED RUN] |
| test years | [PENDING MEASURED RUN] (registered: 2020-2021, sealed) |
| blocks (block diagnostics only; dependent within a region) | [PENDING MEASURED RUN] |

Cases are not independent tests. Blocks inside one region share weather, land cover and sensor conditions.

## 3. Primary Finding Table

Same registered whole-region case list, windows and support policy for every row.

| Method | Wrong direction (cases) | Flagged | Abstained | Answer coverage |
|---|---|---|---|---|
| Reference: Aqua to Aqua, no switch | reference | n/a | [PENDING MEASURED RUN] | [PENDING MEASURED RUN] |
| Raw handover: Aqua then VIIRS | [PENDING MEASURED RUN] | n/a | n/a | [PENDING MEASURED RUN] |
| Point correction (single training factor) | [PENDING MEASURED RUN] | n/a | n/a | [PENDING MEASURED RUN] |
| Stage A finite-factor correction (full-training plus leave-one-year-out factors) | [PENDING MEASURED RUN] | [PENDING MEASURED RUN] | [PENDING MEASURED RUN] | [PENDING MEASURED RUN] |
| Uncertainty-aware baseline | [PENDING MEASURED RUN] | n/a | [PENDING MEASURED RUN] | [PENDING MEASURED RUN] |

Artificial jump at the seam, raw versus corrected versus reference: [PENDING MEASURED RUN]. Missed failures among answers marked stable: [PENDING MEASURED RUN]. Every result is published, including a null or negative one.

## 4. Limitations & Abstentions

- **2020 Aqua outage**: Aqua had a 2020 science-data interruption ([NASA notice](https://forum.earthdata.nasa.gov/viewtopic.php?t=606)). Affected days are unavailable, never zero. Reference periods they invalidate cannot score direction and are listed in a separate availability table. Affected cases: [PENDING MEASURED RUN]
- **Uncalibrated boundaries**: the primary geometry is a rectangle that extends beyond Angola's administrative border ([boundary caveat](../../challenge/CHALLENGE_CAPTURE.md#primary-region)). Predeclared sub-areas are raw only. Sub-areas, unions and other areas inherit no calibration factor and receive no evaluated verdict.
- **Reference is a satellite**: Aqua is another imperfect measurement, not true fire activity.
- **Few variants**: three training years give three leave-one-year-out factors. Agreement among them tests training-year composition only, not every plausible sensor bias.
- **Suomi NPP ended**: new data stopped on November 2, 2026. NOAA-20 is a separate satellite and inherits no factor or status.
- **Hotspot points are separate**: FIRMS points never enter rates, baselines or verdicts.
- **Abstentions**: unavailable, insufficient-support and outside-evaluated-domain cases are counted separately and never dropped: [PENDING MEASURED RUN]

Full report and failure cases: [PENDING MEASURED RUN]
