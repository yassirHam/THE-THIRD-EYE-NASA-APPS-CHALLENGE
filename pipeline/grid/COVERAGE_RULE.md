# Period coverage and footprint certification (P2 r9 rule, reference implementation)

Source of the rule: P2's Round 9 review of the P4 contract, `origin/handoff` `b18ed3e`,
`handoff/verdicts/P4/P4-B-001/r9-P2.md` (sections 1, 3, 5, 6). This file documents how
`pipeline/grid/coverage.py` implements that rule. It does not change it.

## Per sensor and period (`period_coverage`)

| Input | Meaning |
|---|---|
| period and record dates | UTC days; days outside the record do not count as expected |
| `sealed_window` | days inside it are counted from dates only; reporting one present raises |
| `day_present` | one boolean per expected day, already reduced over every expected tile; a missing key raises (unknown is not absent) |
| `processed_cell_days`, `footprint_cells` | P (FireMask >= 3 footprint cell-days) and N_fp; both or neither |
| `c_min` | coverage minimum. NOT registered (P2 proposes 0.99, alternative 1.0). Required argument; `None` applies 1.0 |

| State | Condition | Reasons |
|---|---|---|
| complete | every expected day present, period not clipped, coverage >= C_MIN when measured | none |
| partial | at least one day present and any reason | `period_clipped`, `partition_boundary`, `missing_days_or_tiles`, `low_processed_coverage` |
| unavailable | no expected day present | `no_file` inside the record, `sensor_not_operating` outside it |

`certifiable_complete` is true only for `complete` with cell-level evidence. A file-complete
period with day-level evidence stays complete for file accounting but is not certifiable.

## Footprint (`footprint_evidence_summary`)

Summarises period results for one geometry. `supports_status` is `complete` only if every
period is certifiable at cell level, `partial` (with a coverage fraction) if all periods have
cell-level evidence but some fall short, otherwise `unverified`. It never adds a reference or
timestamp: certification remains P2's human decision (contract 1.4.0 requires both).

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
