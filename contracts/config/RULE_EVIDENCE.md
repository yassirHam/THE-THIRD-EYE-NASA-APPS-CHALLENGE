# P4-B contract 1.2.0: rule evidence and registration status

Prepared 2026-11-14T19:32:28Z (UTC) on `task/P4-B-001`. Plan file
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
  `test_week_53_baseline_is_per_series_so_sensor_and_policy_cannot_mix`. Tests register a
  rule labelled `synthetic-test-only`; that is not a decision reference.

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

## Open items not addressed in this revision

- P2 r8 CHANGES REQUESTED (`6201f21`) items 2 and 3: record-start partial periods (Aqua from
  2002-07-04, VIIRS from 2012-01-19, last week 2026-W01), per-sensor `days_with_file` and
  `days_in_period`, dual-sensor completeness for comparison eligibility, and marking
  NOAA-20/21 and 2026-cutoff fields reserved/inactive for the current phase. These change
  scientific scope and need a fix order.
- D <= O: P2's confirmation was relayed by P4; no written P2 record found. The contract already
  rejects D > O.
