# Decisions needed from P1 and P2 (one batch, 2026-11-14T22:25:50Z)

- From: implementation agent (Kiro) for P4. To: P1 (science), P2 (data). Copy: P4, P5.
- Every item is implemented fail-closed and `registered: false` until the owner records the decision with a UTC
  date/time and a reference. Options come from owners' own records; the agent has chosen none of them.
- Code: P4-B `8edec46`, P1-A `dcaf63e`, P1-B `1a7be92`, P1-C `5be5cf7`, P2-A-002 `c686b20`.
- No data looked at; no 2020-2021 outcome used.

| # | Owner | Decision | Evidence | Options | Current fail-closed behaviour |
|---|---|---|---|---|---|
| 1 | P1 | Register the week definition | plan L322-323; P1-B-001-r3 says ISO weeks still need registration; no external registry record in any ref | A: UTC ISO 8601 weeks (P1-B implements). B: fixed 7-day bins (contract caps at 52; Dec 30/31 fall outside) | `week_definition` required per series; config `registered: false` |
| 2 | P1 | Week 53 | proposal r1 s.5 (never ranked); relayed minimum 3 priors; none of 2016-2019 has W53 | A: never ranked, always insufficient baseline. B: minimum 3 complete priors (cannot occur in current phase) | no W53 decision without a registered rule |
| 3 | P1 | Labels on periods with missing files inside the record | P2 r9 s.3 proposes suppression; "final display rule P4/P1" | A: suppress (null). B: allow labels on partial periods | suppressed (null), ineligible |
| 4 | P1 | Baseline year validity | P2 r9 s.4 proposal: >= 9 of 12 months kept AND O floor | A: P2 proposal. B: every day must have a file | any missing file day -> `required_year_invalid` -> baseline unavailable |
| 5 | P1+P2 | Coverage minimum C_MIN | P2 r9 s.1 | A: 0.99. B: 1.0 | any processed coverage < 1.0 is `low_processed_coverage` (partial) |
| 6 | P1 | Scope of "both sensors complete" | P2 r9 s.2 answered paired-only | A: paired comparisons only (implemented). B: all comparisons (bars pre-2012 cross-era) | paired-only via `paired_comparison_eligible` |
| 7 | P1+P4 | P1-A vocabulary at the export boundary | `contracts/config/p1a_status_mapping.json`; P1-A-001-r3 item 2 | approve table as is, or adopt contract names inside P1-A | production export refuses the unregistered mapping |
| 8 | P1 | Missing calibration evidence state | P1-C-001-r5 item 1 | A: keep `missing_required_support` + reason. B: new state. C: B + unknown status raises (P1-C recommends C) | `insufficient_evidence` unmapped (raises) |
| 9 | P1 | Incomplete months in Stage A | proposal r1 s.1 | strict (implemented in P1-A `dcaf63e`), or a frozen availability-only cell list recorded before any D/O sum | partial/no-file cells make variants unavailable |
| 10 | P1 | Stage A strata, support fraction f, `min_support_O`, D_min | proposal r1 s.1-3; no candidate value appears in any artifact | values to be recorded before fitting | no defaults; fitting needs explicit values |
| 11 | P1 | Critical weeks: `ranked_weeks`, `n_busiest_weeks`, tie rule | proposal r1 s.5; P1-B-001-r3 item 3 | ranked 1-52; n = owner value; `include_all_tied` or `lower_week_number_first` | no defaults |
| 12 | P2 | `partition_boundary` for periods wholly inside the sealed window | contract 1.4.0 RULE_EVIDENCE s.9 | confirm, or name another reason | placeholder lists `partition_boundary` |
| 13 | P2 | Coverage reference code (`pipeline/grid/coverage.py`) | P2-A-002 `c686b20` | confirm it matches the r9 rule, or request changes | not used by any export yet |
| 14 | P2 | Cell-level footprint evidence | `ee_check_report.json` is empty; no per-cell counts committed | produce processed vs expected cell-days per sensor/block/period | every footprint `unverified`; no comparison-eligible period |

Not open for this batch: holdout reuse PA-001 stays NOT approved; 2020-2021 remain excluded everywhere.
