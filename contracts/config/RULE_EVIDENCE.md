# P4-B contract 1.6.0: rule evidence and registration status

First prepared 2026-11-14T19:32:28Z; updated 2026-11-14T19:56:09Z and 2026-11-14T21:38:42Z (UTC,
contract 1.4.0, Round 10) on `task/P4-B-001`. Plan file
`THE_THIRD_EYE_FINAL_PLAN_GEOGRAPHIC_ACCESS_UPDATED.txt`, SHA-256
`84B012E26B808AB98BE6B66232ADBC22DC03AC3F1D4423304C38EBD21A521DDC` (matches the hash cited in
P5 records). Handoff references are commits on `origin/handoff`.

Registration state lives in `pending_registrations.json`. Registered there, from the
P1 decision record `handoff/escalations/P1/P1-decision-week-definition-and-week53.md` (`origin/handoff` `bb1bf4c`, 2026-11-14 23:19:58 UTC): the UTC ISO week definition, the sealed window 2020-01-01..2021-12-31, the sealed
partial reason and the week-53 minimum (3). Everything else stays `registered: false`. No date is
backdated; the decision date is the one in P1's record. Sections 1-3 below keep their original
evidence; their status lines were corrected 2026-11-15 to match the config. All tests use fabricated data marked
`[SYNTHETIC DEV FIXTURE]`; no sealed observation is read or derived from.

## External-registry check

- When: 2026-11-14T19:32:28Z. Scope: every ref on `origin` after `git fetch`, including
  `handoff` at `6201f21`.
- Searched for: preregistration URLs (osf.io, aspredicted), "external registry", registry
  entries, and a `challenge/` directory.
- Result: none found. The only matches are plan text about preregistration and P2's data
  quality registry. Registries outside the repository were not checked; P4-B cannot see them.
- Rechecked 2026-11-14T21:38:42Z after `git fetch` (`handoff` at `b18ed3e`): no osf.io, aspredicted or
  external-registry record in any ref. `challenge/CHALLENGE_CAPTURE.md` on `task/P5-C-001` holds event
  rules only, no scientific registration.

## 1. Week definition: UTC ISO weeks

- Status: registered (P1 decision A in the P1 decision record `handoff/escalations/P1/P1-decision-week-definition-and-week53.md` (`origin/handoff` `bb1bf4c`, 2026-11-14 23:19:58 UTC)). Earlier rounds held it unregistered
  because no written P1 approval existed then.
- Evidence: plan L322-323 requires freezing "UTC ISO weeks or fixed 7-day bins". P1's
  escalation `handoff/escalations/P1/P1-B-001-r3.md` (`f9ab606`, 2026-11-14T18:10:57Z) says
  registration of ISO 8601 UTC weeks "is still needed". No conflicting registration exists.
- Contract: `WeeklyCalendarSeries.week_definition` is required, with no default; ISO identity,
  Monday-Sunday bounds and overlaps are validated.
- Tests: `test_week_boundaries.py` ISO identity cases; `test_week_definition_is_declared_per_series_not_inferred`.

## 2. Week-53 rule

- Agreed rule (P1, relayed by P4): three complete, supported, eligible prior ISO week-53
  observations from the same sensor and policy; otherwise `insufficient_baseline` and no
  unusual label.
- Status: minimum 3 registered (P1 decision B in the P1 decision record `handoff/escalations/P1/P1-decision-week-definition-and-week53.md` (`origin/handoff` `bb1bf4c`, 2026-11-14 23:19:58 UTC)). Since contract 1.6.0 an
  insufficient week-53 baseline carries a null unusual label (P1 decision B3), and week 53 is
  unranked for critical weeks (`critical_status` null; P1 open item 1). The text below is the
  original round-9 evidence.
- Evidence: plan L325-328 ("With few same-sensor years, show 'insufficient baseline'
  instead of a flag"); P1 escalation `f9ab606` item 3 (week 53 rejected for 52-week years).
- Contract: `Week53Baseline` lives inside one weekly series (same sensor and policy). Prior
  years must be earlier ISO years that have a week 53, unique, and outside the sealed window.
  `available` only with a registered rule and eligible count >= its minimum; otherwise a
  week-53 record carries `insufficient_baseline` and no unusual or critical decision.
  `Week53Rule` cannot carry a minimum while unregistered.
- Tests: `test_three_complete_supported_priors_allow_a_decision`,
  `test_two_eligible_priors_force_insufficient_baseline`,
  `test_insufficient_week_53_cannot_carry_an_unusual_label`,
  `test_sealed_week_53_year_cannot_be_a_prior_observation`,
  `test_week_53_baseline_is_per_series_so_sensor_and_policy_cannot_mix`,
  `test_current_phase_week_53_stays_insufficient_even_with_a_registered_rule`. Tests register a
  rule labelled `synthetic-test-only`; that is not a decision reference.
- In the current phase (data to 2025-12-31) no week 53 can reach three priors: the fixture's
  2015-W53 has two (2004, 2009), 2020 is sealed, 2026 is out of scope. The three-prior mechanism
  is tested only on a test-only artifact with hypothetical Aqua coverage to 2027-01-03.

## 3. Sealed-boundary periods

- Rule: a period straddling the sealed window is partial and comparison-ineligible, with null
  unusual/critical labels, and uses only its permitted (outside-window) days.
- Status: window `2020-01-01..2021-12-31` and reason `crosses_sealed_evaluation_boundary` are
  registered (P1 decision C in the P1 decision record `handoff/escalations/P1/P1-decision-week-definition-and-week53.md` (`origin/handoff` `bb1bf4c`, 2026-11-14 23:19:58 UTC)). The window is artifact data, not a schema constant.
- A period wholly inside the window is rejected: it is excluded from artifacts, never represented
  (section 8).
- Evidence: plan L46 (2020-2021 sealed evaluation), L53 ("never reuse holdouts"), L71
  (holdouts sealed until methods freeze); P5 decision
  `handoff/escalations/P4/P4-holdout-baselines-decision.md` (`d0b8c90`); P5 governance
  record `P5-DESCRIPTIVE-HOLDOUT-USE-SPECIFICATION.md` (`a111487`).
- Contract: status from period dates only (`sealed_window_period_status`);
  `included_day_count` must equal the outside-window day count (`days_outside_window`);
  sealed years barred from `eligible_prior_years` and week-53 priors; production artifacts
  must declare a registered window.
- Tests: `test_crossing_week_must_be_partial_ineligible_with_null_labels`,
  `test_crossing_week_must_declare_exactly_its_permitted_days`,
  `test_sealed_years_cannot_be_baseline_prior_years`,
  `test_production_artifact_must_declare_a_registered_sealed_window`.
- S-NPP cutoff week 2026-W45 stays partial (P2 r8 verdict `6201f21` item 4: PASS).

## 4. Footprint coverage

- Rule: `complete`, `partial` or `unverified`. Complete and partial need P2's documented
  reference and UTC timestamp; partial needs a coverage fraction in (0, 1). Only `complete`
  supports comparison-eligible whole-area periods. Production eligible periods require it.
  Completeness is never inferred from available data.
- Status: proposed shape. P2's Q3 certification rule is not in any ref P4-B can read.
- Evidence: plan L615 ("A partially extracted footprint is unavailable for a whole-area
  conclusion"); P1 escalation `f9ab606` item 2 (option B, P2 attestation); P1-A/P1-B r4 and
  P5 r4 records list footprint attestation as unresolved pending P2/P4 agreement.
- Tests: footprint section of `test_week_boundaries.py`;
  `test_available_aggregate_never_implies_whole_footprint_completeness`.

## 5. Holdout exclusion and fixture dates

- No exception is proposed. Real 2020-2021 outcomes stay out of every baseline and
  calibration (P5 `d0b8c90`, `a111487`; P1 agreement relayed by P4).
- Fabricated 2020-2021 dates appear only in the sealed-boundary fixture and boundary tests
  (P1 permission relayed by P4). Other fixtures moved to 2023.
- Tests: `test_non_boundary_fixtures_use_no_2020_2021_dates`,
  `test_no_fixture_lists_sealed_years_as_baseline_prior_years`.

## 6. Record-boundary partial periods (P2 r8 item 2)

- Rule as written by P2 (`6201f21`, `handoff/verdicts/P4/P4-B-001/r8-P2.md`): represent the 2002
  partial year (Aqua from 2002-07-04), July 2002, January 2012 (VIIRS from 2012-01-19), ISO weeks
  2002-W27 and 2012-W03, and the last ISO week 2026-W01 (2025-12-29..2025-12-31 only), with
  per-sensor `days_with_file` and `days_in_period`; a period is eligible for MODIS/VIIRS
  comparison only when both sensors are complete.
- Contract: every month and week record carries required `days_in_period` (checked against the
  calendar) and `days_with_file`. A period straddling its sensor's declared record start or end
  must be partial with reason `outside_sensor_record`, comparison-ineligible, null labels, and
  `days_with_file` no larger than its days inside the record. Periods wholly outside the record
  are rejected. `comparison_eligible` requires a file for every day. Annual coverage entries
  (`annual_coverage`) represent partial years; baseline years must be declared, non-partial years.
- Pairing: new `paired_comparison_eligible` flag. True only if the period is comparison-eligible
  and the other sensor (MODIS_Aqua <-> VIIRS_SNPP) has a record for the same period that is also
  paired. Checked in both directions.
- Status: record dates are P2's stated scope, held in `pending_registrations.json`
  (`current_phase_coverage`, unregistered) and read by the fixture builder; none is in the schema.
- Tests: `test_p2_boundary_periods_are_represented_as_partial`,
  `test_p2_boundary_periods_reject_completion`,
  `test_p2_partial_years_are_declared_and_cannot_be_baseline_years`,
  `test_periods_wholly_outside_the_declared_record_are_rejected`,
  `test_paired_comparison_requires_both_sensors_complete`, `test_paired_comparison_needs_a_twin_record`.

## 7. Reserved scope (P2 r8 item 3)

- Rule as written by P2: NOAA-20/21 and 2026 cutoff fields are reserved/inactive for the current
  phase (Aqua MYD14A1.061 and S-NPP VNP14A1.002, 2002-07-04 to 2025-12-31) and must not imply that
  those data exist.
- Contract: `sensor_coverage` must declare all four sensors; NOAA-20/21 are `reserved_inactive`
  and cannot carry dates or records. `snpp_cutoff_status` (calendar and manifest) must be
  `reserved_inactive` unless declared S-NPP coverage reaches 2026-11-02; S-NPP coverage cannot pass
  it. Consumer fixtures hold no data after 2025-12-31 except the partial 2026-W01.
- The S-NPP cutoff logic itself (P2 r8 item 4: PASS) is unchanged and is exercised only on a
  test-only artifact (`build_fixtures.reserved_cutoff_calendar`) that declares hypothetical S-NPP
  coverage to 2026-11-02. It is never written to `contracts/fixtures/`.
- Tests: `test_current_phase_coverage_comes_from_p2_scope_in_config`,
  `test_consumer_fixtures_hold_no_data_after_the_phase_end`,
  `test_reserved_sensors_cannot_carry_records_or_dates`, `test_every_sensor_coverage_must_be_declared`,
  `test_snpp_cutoff_is_inactive_unless_snpp_coverage_reaches_it`,
  `test_manifest_cutoff_status_reflects_listed_sources`, `test_p2_scope_dates_are_not_hard_coded_in_the_schema`.

## 8. Sealed window: periods wholly inside

- Rule (contract 1.6.0): a month or week lying wholly inside the declared sealed window is
  rejected. Such periods are excluded from artifacts: no record at all, so they are never shown as
  missing data, as unavailable / `no_file`, or with `partition_boundary`. An unavailable,
  undecided placeholder is rejected too (`contracts/schemas/calendar.py`, `validate_calendar`).
- Earlier text here described an unavailable placeholder; that path was removed in 1.6.0 and is
  not allowed.
- Evidence: P2 r11 section 3 (`origin/handoff` `8f67011`); P2 r12 condition 1 (`93820f0`); P5
  `d0b8c90` and `a111487`; P5 reconciliation `0a49cbb` (strict default: 2020-2021 excluded from all
  baselines; PA-001 not approved).
- Test: `test_period_wholly_inside_window_is_excluded_even_as_a_placeholder`.

## 9. Coverage states and reasons (P2 r9 required changes 1 and 3; contract 1.4.0)

- Source: P2 r9 verdict on `da25ad7` (`origin/handoff` `b18ed3e`,
  `handoff/verdicts/P4/P4-B-001/r9-P2.md`, sections 1, 3 and 5).
- Contract: every month and week record carries required `coverage_state`
  (`complete` / `partial` / `unavailable`) and `coverage_reasons` in P2's vocabulary
  (`period_clipped`, `sensor_not_operating`, `partition_boundary`, `missing_days_or_tiles`,
  `low_processed_coverage`, `no_file`), plus optional `processed_coverage`.
- The reasons are checked against the period's own dates, the declared sensor record and the
  sealed window: a reason is listed exactly when the data call for it.
- Mapping from contract partial reasons (explicit, `PARTIAL_REASON_TO_P2`):
  `outside_sensor_record` and `snpp_record_ended_2026_11_02` -> `period_clipped`;
  `crosses_sealed_evaluation_boundary` -> `partition_boundary`; the new partial reasons
  `missing_days_or_tiles` and `low_processed_coverage` map to themselves. Unavailable reason
  `source_not_available` with no file day -> `no_file`; new unavailable reason
  `sensor_not_operating` -> `sensor_not_operating`. `partition_boundary` applies only to periods
  that cross a sealed-window edge. A period wholly inside the window is not represented at all
  (section 8), so it lists no reason.
- Mid-record missing files: partial (`missing_days_or_tiles`) when at least one permitted day has a
  file, otherwise unavailable (`no_file`). Partial periods are comparison-ineligible with null
  labels and null thresholds. D and O cover only days with a file; missing days are never zero.
  Label suppression is P2's proposal; P2 says the final display rule is P4/P1, so P1 must confirm.
- Periods wholly outside an active sensor record are unavailable (`sensor_not_operating`, no file
  days, null labels) instead of rejected. Reserved NOAA-20/21 still cannot carry records.
- Coverage minimum C_MIN is unregistered (P2 proposes 0.99, alternative 1.0). Until registered,
  any `processed_coverage` < 1.0 must list `low_processed_coverage` and is partial (fail closed).
- Tests: `test_coverage_reasons.py` (raw validation, no recomputation shim).

## 10. Required-year baselines (P2 r9 required change 2)

- `SeasonalBaselineInfo` gains required `excluded_years` (year + reason) and `unavailable_reason`,
  and status `unavailable`. Every year of the registered span is either eligible or excluded with a
  reason (`sealed_evaluation_window`, `partial_record_year`, `required_year_invalid`), so a baseline
  is never shortened silently. `required_year_invalid` makes the baseline `unavailable`; widening the
  span to add another year is visible and does not make it available.
- Year validity: P2 proposes >= 9 of 12 months kept and an O floor; this is P1's decision and is
  unregistered. Until it is registered, an eligible prior year must have a file for every day.
- Exclusions must be backed by the artifact (a declared sealed window overlapping the year, or a
  declared partial year).

## 11. Footprint certification (P2 r9 Q3)

- `FootprintCertification.footprint_evidence` is required: `cell_level`, `day_level` or `none`.
  `complete` and `partial` require `cell_level`; day-level file presence never certifies a footprint.
- Comparison-eligible periods now require a `complete` certification for every artifact class
  (1.3.0 only required it for production). Production artifacts cannot use a certification whose
  reference contains "synthetic".
- P2 r9: no region-period is certified complete today. `sample_calendar_unverified_footprint.json`
  shows that state (no eligible period). `sample_calendar.json` keeps a certification labelled
  `SYNTHETIC-TEST-ONLY: not a P2 certification` to exercise the certified path.

## 12. Manifest binding (P3 calendar vs manifest method_id)

- 1.3.0 manifests carried their own method `artifact_manifest` while listing a calendar file whose
  method is `same_sensor_calendar`, so the five-field key of the manifest never matched the
  calendar it described.
- 1.4.0: `ProvenanceManifest.described_artifact_type` is required, and the manifest carries the
  described artifact's five-field identity. `assert_manifest_describes(manifest, artifact, type)`
  rejects a different family or any differing identity field.

## 13. P1-A status vocabulary (PROPOSED mapping, unregistered)

- `contracts/config/p1a_status_mapping.json` and `contracts/schemas/status_mapping.py`.
  `registered: false`; production use raises `UnregisteredMappingError`.
- `insufficient_evidence` has no target and always raises until P1 decides (escalations
  `P1-A-001-r3` item 2, `P1-C-001-r5` item 1). `evaluated_for_conditions` maps only with an explicit
  `applicability_passed`; both failed spellings map to `failed_applicability`. Unknown names raise.

## 14. Versioning and identity reuse (Round 10b)

- `contract_version` is now required with no default, so an artifact that omits it is not read as
  1.4.0; 1.1.0 and 1.3.0 artifacts are rejected (tests on every committed fixture).
- Manifest partitions must carry the manifest's five-field identity and its digest; a manifest is
  bound to one artifact with `assert_manifest_describes` (tests for cross-region, cross-period,
  cross-policy and cross-version reuse).

## 15. Replayable manifests (contract 1.5.0, backend replay gap)

- Purpose: P4-A emits one `ProvenanceManifest` per described artifact so P5-B's replay verifier can check
  the bundle file by file (path, size, sha256, five-field cache key, totals). Proposed to P5 in
  `handoff/escalations/P5/P5-exact-sha-review-request-r1.md`; P5 has not answered yet.
- `PartitionFileRecord.sensor` is nullable with a required key: null for files that hold several
  same-sensor series or non-sensor data. It never denotes a merged cross-sensor series.
- `coverage_status` gains `unverified`. `assert_manifest_describes` refuses a manifest whose
  partitions claim more coverage than the calendar's footprint certification (complete -> complete,
  partial -> partial, otherwise unverified) and a manifest whose data classification differs.
- Breaking: 1.4.0 artifacts are rejected (version is a literal).

## 16. Recorded owner decisions (contract 1.6.0, Round 12)

Sources: P1 binding decision `handoff/escalations/P1/P1-decision-week-definition-and-week53.md`
(`origin/handoff` `bb1bf4c`, decision time 2026-11-14T23:19:58Z) and P2 Round 11 verdict
`handoff/verdicts/P4/P4-B-001/r11-P2.md` (`8f67011`, CONDITIONAL APPROVE).

| Rule | Owner record | Contract 1.6.0 |
|---|---|---|
| UTC ISO weeks | P1 decision A | `week_definition` registered in config; schema still requires it per series |
| Week-53 unusual baseline: >= 3 complete, supported eligible priors per sensor/policy; never weeks 52/1 | P1 decision B | `week_53_minimum` = 3 registered; fixtures carry the registered rule; per-series baselines |
| Insufficient week-53 baseline: unusual label withheld (null) | P1 decision B3 | null required (1.5.0 required `insufficient_baseline`) |
| Week-53 critical ranking OPEN (unranked) | P1 open item 1 | every week-53 record has `critical_status` null |
| Sealed 2020-2021 boundary: permitted days only, partial, ineligible, null labels, never read sealed days | P1 decision C | window 2020-01-01..2021-12-31 and reason registered; rules unchanged |
| Period wholly inside the sealed window: excluded, never missing / no_file / partition_boundary | P2 r11 s.3 | such records are rejected; the placeholder path and its `partition_boundary` derivation are removed |
| C_MIN fail-closed; footprint unverified without cell-level evidence | P2 r11 s.3, condition 2 | unchanged |
| `pipeline/grid/coverage.py` not cited as existing contract dependency | P2 r11 condition 4 | contract does not reference it |

Breaking for 1.5.0 artifacts with week-53 labels or wholly sealed placeholders: version 1.6.0.

Not decided by these records (still unregistered): label suppression for mid-record missing files,
baseline year-validity threshold (P1 open item 6 confirms only "missing or incomplete required years
-> unavailable", already implemented), paired-only scope, C_MIN, critical-week parameters, Stage A
settings, P1-A mapping, footprint certification. Note: P1's record cites batch "items 1, 2, 3" but its
item C answers sealed boundaries, not batch item 3 (label suppression for missing files).

## Test shim

Older tests mutate a period and check one rule. `contracts/tests/_coverage.py` recomputes the 1.4.0
coverage fields with the fixture builder before validating, so those tests keep checking their own
rule. All coverage rules, and all committed calendar fixtures, are validated raw in
`test_coverage_reasons.py`.

## Open decisions and findings (not resolved by this revision)

- P1: confirm label suppression for mid-record missing-file periods (P2 proposal; implemented).
- P1: year-validity rule for baseline years (P2 proposal >= 9 of 12 months and O floor;
  unregistered; contract currently requires every day to have a file).
- P1/P2: register C_MIN (0.99 or 1.0). Contract treats any shortfall as low until then.
- Resolved (P2 r11 section 3, `8f67011`): wholly sealed periods are excluded, not placeholders,
  so `partition_boundary` never applies to them.
- P1: paired-only scope of the both-sensors-complete rule (P2 r9 section 2 answered paired-only;
  implemented as `paired_comparison_eligible`).
- Week 53: P1 proposal r1 (`3727f8f`, Section 5) says week 53 is never ranked for critical weeks. The
  contract allows a critical label only once a registered rule and three eligible priors exist, which
  cannot happen in the current phase. P1 to confirm whether week 53 may ever carry a critical label.
- P1 proposal r1 items still unfrozen: strata and incomplete-month rule, support fraction f and
  D_min, ranked weeks, `n_busiest_weeks`, tie rule, excluded years.
- UTC ISO week, sealed window, sealed reason and week-53 minimum: registered from the P1 decision record `handoff/escalations/P1/P1-decision-week-definition-and-week53.md` (`origin/handoff` `bb1bf4c`, 2026-11-14 23:19:58 UTC).
  The in-repo registry searches (19:32Z, 21:38Z) found no external registry record; none outside the
  repository was checked.
- P1-A vocabulary mapping: proposed only (section 13).
- P5 gates held open (`0a49cbb`): footprint attestation (P2 r9 now says unverified), unregistered
  settings, P1-A mapping.
- D <= O: P2 r9 section 6 is now a written P2 record (masks, nh policy, 123 unit tests, 0 violating
  rows in 16,512 monthly rows, 2020-2021 excluded). The contract rejects D > O.
- Holdout reuse (P5 PA-001) remains NOT approved; 2020-2021 stay excluded everywhere.
- FIRMS `FirmsPlatform` still lists NOAA-20/21 (FIRMS points are a separate product; not changed).