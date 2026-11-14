# P4-B contract 1.3.0: rule evidence and registration status

First prepared 2026-11-14T19:32:28Z; updated 2026-11-14T19:56:09Z (UTC) on `task/P4-B-001`. Plan file
`THE_THIRD_EYE_FINAL_PLAN_GEOGRAPHIC_ACCESS_UPDATED.txt`, SHA-256
`84B012E26B808AB98BE6B66232ADBC22DC03AC3F1D4423304C38EBD21A521DDC` (matches the hash cited in
P5 records). Handoff references are commits on `origin/handoff`.

Nothing in this file is registered or frozen. Values live in `pending_registrations.json`
with `registered: false`. No date is backdated. All tests use fabricated data marked
`[SYNTHETIC DEV FIXTURE]`; no sealed observation is read or derived from.

## External-registry check

- When: 2026-11-14T19:32:28Z. Scope: every ref on `origin` after `git fetch`, including
  `handoff` at `6201f21`.
- Searched for: preregistration URLs (osf.io, aspredicted), "external registry", registry
  entries, and a `challenge/` directory.
- Result: none found. The only matches are plan text about preregistration and P2's data
  quality registry. Registries outside the repository were not checked; P4-B cannot see them.

## 1. Week definition: UTC ISO weeks

- Status: P4's stated choice. Unfrozen: no P1 written approval with date/time and reference
  exists in any ref.
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
- Status: config value `3`, unregistered. Open: external-registry check; P1 written
  approval with actual date/time and reference. Cleared: P5 holdout-policy decision
  (`d0b8c90`).
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
  proposed and unregistered. The window is artifact data, not a schema constant.
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

- A month or week wholly inside the declared sealed window may exist only as an unavailable,
  undecided placeholder with no file days, so no sealed observation enters an artifact.
- Evidence: P5 `d0b8c90` and `a111487`; P5 reconciliation `0a49cbb` (strict default: 2020-2021
  excluded from all baselines; PA-001 not approved).
- Test: `test_available_period_wholly_inside_window_is_rejected_but_placeholder_is_allowed`.

## Open decisions and findings (not resolved by this revision)

- P2 r8 scope question: P2's rule ("eligible for MODIS/VIIRS comparison only when both sensors are
  complete") is implemented as the separate `paired_comparison_eligible` flag. Applying it to
  `comparison_eligible` itself would make every pre-2012 Aqua period ineligible for cross-era
  comparison. P1/P2 must say which they intend.
- Periods with missing files inside the record (not at a boundary): comparison-ineligible, but not
  marked partial and labels are not suppressed. P1/P2 decision needed.
- Baseline years: only partial years at the record boundary are barred. Whether a year with missing
  files inside the record (for example the Aqua 2020 outage, already sealed) can be a baseline year is
  a P1 decision.
- Week 53: P1 proposal r1 (`3727f8f`, Section 5) says week 53 is never ranked for critical weeks. The
  contract allows a critical label only once a registered rule and three eligible priors exist, which
  cannot happen in the current phase. P1 to confirm whether week 53 may ever carry a critical label.
- P1 proposal r1 items still unfrozen: strata and incomplete-month rule, support fraction f and
  D_min, coverage definition and any tolerance below 100% (it would need a contract field), ranked
  weeks, `n_busiest_weeks`, tie rule, excluded years.
- P5 gates held open (`0a49cbb`): footprint attestation; unregistered scientific settings; mapping of
  P1-A status vocabulary (`sensitive`, `unresolved`, `evaluated_for_conditions`,
  `insufficient_evidence`) to contract enums at the export adapter.
- D <= O: P2's confirmation was relayed by P4; no written P2 record found. The contract rejects D > O.
- FIRMS `FirmsPlatform` still lists NOAA-20/21 (FIRMS points are a separate product; not changed).
