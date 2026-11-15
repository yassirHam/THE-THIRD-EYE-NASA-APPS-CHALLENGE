# Period coverage and footprint certification (P2 r9 rule, contract 1.6.0)

Source of the rule: P2's Round 9 review of the P4 contract, `origin/handoff` `b18ed3e`,
`handoff/verdicts/P4/P4-B-001/r9-P2.md` (sections 1, 3, 5, 6). This file documents how
`pipeline/grid/coverage.py` implements that rule in the contract 1.6.0 vocabulary
(`contracts/schemas/common.py` `CONTRACT_VERSION = "1.6.0"`, `contracts/schemas/calendar.py`).
It does not change the rule or the contract.

## Per sensor and period (`period_coverage`)

| Input | Meaning |
|---|---|
| period and record dates | UTC days; days outside the record do not count as expected. `record_end` later than 2025-12-31 raises. A period may end after `record_end` if it starts on or before it (it is then clipped) |
| sealed set | union of the fixed holdout years 2020-01-01..2021-12-31 and the optional caller `sealed_window`. Each window is excluded on its own, never merged into one min(start)..max(end) span. A caller window with start > end raises |
| `day_present` | one `bool` per expected day, already reduced over every expected tile. A missing key raises (unknown is not absent); a non-`bool` value (including `0`, `1`, `None`, `numpy.bool_`) raises; any truthy key inside the sealed set raises, whether or not it lies in the period |
| `processed_cell_days`, `footprint_cells` | P (FireMask >= 3 footprint cell-days) and N_fp; both or neither |
| `c_min` | fixed at 1.0. Required argument; only `None` (read as 1.0) or `1.0` is accepted. Any other value raises, so coverage below 1.0 is never complete |

Expected days = period days inside the record and outside the sealed set.

| State | Condition | Reasons |
|---|---|---|
| complete | every expected day present, period not clipped, no sealed day excluded, coverage == 1.0 when measured | none |
| partial | at least one expected day present and any reason | `period_clipped`, `partition_boundary`, `missing_days_or_tiles`, `low_processed_coverage` |
| unavailable | no expected day present | `sensor_not_operating` if no period day is inside the record; `partition_boundary` alone if every in-record day is sealed; otherwise `no_file`, plus `partition_boundary` when some in-record days are sealed |

Reason rules:

- `period_clipped`: some, not all, period days are inside the record (for example 2026-W01,
  2025-12-29..2026-01-04, keeps 3 days and is partial).
- `partition_boundary`: one or more in-record days were excluded as sealed. It is never emitted
  for a non-sealed year or split crossing such as 2024-12-30..2025-01-05.
- `missing_days_or_tiles`: an expected day has no file for every tile.
- `low_processed_coverage`: measured coverage P / (N_fp x days_with_file) < 1.0, matching
  `_check_coverage` in the contract ("listed exactly when processed coverage < 1.0").

These match `CalendarArtifact._validate_coverage_reasons`: `sensor_not_operating` when no day
is inside the record, `no_file` only when permitted days exist and none has a file, and
`partition_boundary` through the mapping of `crosses_sealed_evaluation_boundary`.

`certifiable_complete` is true only for `complete` with cell-level evidence. A file-complete
period with day-level evidence stays complete for file accounting but is not certifiable.

## Paired comparison

This module classifies one sensor at a time and does not set `paired_comparison_eligible`.
Under the contract (`_check_file_days`, `_check_coverage`, `_validate_pairing`), a record may be
`paired_comparison_eligible` only if it is `comparison_eligible`, which requires
`coverage_state == "complete"` and a file for every day, and only if the paired sensor's record
(MODIS_Aqua with VIIRS_SNPP) for the same period is also `paired_comparison_eligible`. Any
`partial` or `unavailable` result from `period_coverage`, including every period that touches
the sealed set, therefore makes both sensors' records ineligible for paired comparison.

## Footprint (`footprint_evidence_summary`)

Summarises period results for one geometry in the `FootprintCertification` status vocabulary:

- `complete`: every period is certifiable at cell level (`coverage_fraction` 1.0 in the
  summary; the contract model carries no fraction for `complete`).
- `partial`: every period has cell-level evidence, some are not complete, and
  0.0 < `coverage_fraction` < 1.0, matching `coverage_fraction: Field(gt=0.0, lt=1.0)`.
- `unverified`, with `coverage_fraction` None: any period has day-level evidence, there are no
  periods, or the cell-level fraction is None (no expected days, for example wholly sealed),
  0.0, or not below 1.0 while some period is not complete.

It never adds a reference or timestamp: certification remains P2's human decision (the contract
requires both for `complete` and `partial`).

## Evidence status in this repository (checked 2026-11-14)

- `data/manifests/ee_check_report.json` is an empty list.
- No per-cell processed versus expected counts are committed for any region or period.
- Therefore every footprint is `unverified`, matching P2 r9 ("no region-period is certified
  complete today").

## D <= O

`tests/unit/test_coverage.py::test_d_le_o_for_every_class_and_qa_state_and_policy` checks every
FireMask class 0-9 against every QA land/water state for MYD14A1.061 and VNP14A1.002 under the
all, nominal+high (O_nh = O - (D - D_nh)) and, through `check_row` on random synthetic grids,
common-support policies. These are rule tests on synthetic arrays, not checks of real data.
