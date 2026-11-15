# THE THIRD EYE

THE THIRD EYE explores how changes between satellite sensors can affect the interpretation of historical fire observations. It brings a fire calendar, sensor comparison and evidence together in a browser interface for the NASA Space Apps challenge “Harmonization of MODIS and VIIRS Hot Spots”.

## Current status

This repository contains a prototype and its scientific and data-processing work. The held-out evaluation and independent replay are recorded as pending in the [results summary](docs/submission/ONE_PAGE_RESULTS.md); the project should not be treated as a validated fire assessment. Missing observations are not zero, and a satellite observation is not a count of fires. FIRMS hotspot points are a separate view and do not enter the grid-based rates or verdicts.

## Explore the project

- [Frontend](frontend/): browser interface and local setup.
- [Scientific methods](science/) and [data pipeline](pipeline/): methods and preparation of satellite observations.
- [Contracts](contracts/) and [artifact pipeline](artifact_pipeline/): versioned interfaces and publication artifacts.
- [Evaluation](eval/) and [results summary](docs/submission/ONE_PAGE_RESULTS.md): evaluation work, pending results and limitations.
- [Scientific plan](THE_THIRD_EYE_FINAL_PLAN_GEOGRAPHIC_ACCESS_UPDATED.txt): registered scope, interpretation and safeguards.

## Run the frontend

With Node.js installed, run from the `frontend` directory:

```sh
npm ci
npm run dev
```

The interface may show unavailable or fixture-backed content when published data and evaluation artifacts are absent; see the results summary before interpreting a display as a measured result.

## Data and limitations

The planned comparison uses Aqua MODIS MYD14A1 and Suomi NPP VIIRS VNP14A1 daily grids. Rates describe detected fire cell-days per usable land cell-day, not individual fires. Factors and evaluated status do not automatically transfer to other areas or satellites. Suomi NPP is a closed archive; NOAA-20 is a separate platform. See the [results summary](docs/submission/ONE_PAGE_RESULTS.md) for further limitations and outstanding evidence.
