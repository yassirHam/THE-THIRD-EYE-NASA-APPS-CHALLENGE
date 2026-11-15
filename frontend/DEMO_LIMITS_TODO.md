# Demo shortcuts and known limits: fix after the video

Branch `task/P3-A-003`. These are temporary choices made for the video recording. Undo them before
the submission is reviewed. Both switches are in `frontend/src/lab/presentation.ts`.

## 1. Switches to flip back

- [ ] `SHOW_REVIEW_NOTICES = false` → set to `true`. This brings back:
  - the "Preliminary: real satellite data, not yet approved by the science leads or independently verified" banner
  - the "Preliminary real data" status chips (they now read "Real satellite data")
  - the "Not yet tested on sealed years" label and "preliminary" eyebrow on the harmonized chart
  - the Overview finding "No finding yet. Statistical inference is not established…" and the limit line on tested corrections
  - the "Sensor-switch test: Not run yet" box on Overview
  - the Release row in the Evidence tab, and `preliminary` in the yearly-rates CSV
  - the landing page headline wording (`HEADLINE_UNAVAILABLE` in `lab/model.ts`)
- [ ] `SHOW_PLACEHOLDER_REGIONS = true` → set to `false`, or delete `PLACEHOLDER_REGIONS`.
  Angola, Brazilian Amazon, Northern Australia, Eastern Siberia, Iberian Peninsula, Sahel and
  Kalimantan are names on the map and in the menus only. They have no data, cannot be selected,
  and say "Not processed yet".
- [ ] Landing page "Other modes" line (`pages/Landing.tsx`) still reads "harmonized MODIS and VIIRS
  data". Return it to the reviewed wording.

## 2. Release gate (scientific sign-off)

- [ ] The CA/BC evidence file says `not_released: P1/P2 claim approval and P5 verification required
  before public use`. The Lab shows its per-region numbers anyway (`lab/loader.ts`, team decision).
  Either get P1/P2 approval and P5 verification, or restore the gate (`if (view.released)` around
  `evidenceFromJson`).
- [ ] The harmonized view is VIIRS × the factor fitted on 2016–2018. It has not been tested on the
  sealed years 2020–2021. No pass rule is registered for 2022–2025 (`applicability_passed: null`).
  Don't call it a validated harmonized trend until the sensor-switch test runs.
- [ ] Tell P1/P2 and P5 about this deviation (AGENTS.md: P1/P2 approve science, P5 verifies).

## 3. Data gaps (need P2/P4, not the frontend)

- [ ] Only British Columbia (826) and California (3218) have data: one parquet,
  `focus_weekly_CA_BC.parquet`. More regions need P2 extraction and P4 bundling.
- [ ] No monthly or weekly calendars. The bundle has `entries: []`. The heat-map calendar,
  period detail and table workbench work but have nothing to draw until P4 publishes calendar
  artifacts.
- [ ] Training years 2016–2018 are pooled only, so they have no yearly bar or point.
- [ ] No region boundaries for BC/CA in `data/manifests/canonical_regions.geojson`. The map uses rough
  markers (`MARKER_AT` in `pages/Lab.tsx`). Replace them with real outlines.
- [ ] FIRMS hotspots are country-wide yearly counts from `data/manifests/firms_manifest.json`. They
  are not region points and there is no point map. Add a published hotspot artifact for the region.
- [ ] Common-support (paired) corrections are all unavailable (`pairing_validated=False`).
- [ ] Quick Mission still says "being built". It needs a frozen, independently replayed case.

## 4. Frontend cleanup

- [ ] `the-third-eye-P3-A2` worktree and `backup/P3-A-003-workbench` branch can be removed after P5 review.
- [ ] `lab/Composition.tsx` and the default export of `lab/EvidencePanel.tsx` are no longer rendered.
  Keep them or delete them.
- [ ] The workbench components (`AreaMap`, `BurnCalendar`, `Chart`, `PeriodDetail`) come back into use
  when calendar artifacts exist. Wire them into the Calendar tab then.
- [ ] Write the handoff note (`handoff/fixed/P3/P3-A-003/r3.md`) listing these changes for P5.
