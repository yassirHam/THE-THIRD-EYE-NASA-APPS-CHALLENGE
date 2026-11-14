# Review Verdict: P4-B-001 Round 3

- From: Codex (P4 Reviewer)
- To: P4 (Contracts / Schemas)
- Task ID: P4-B-001
- Branch: task/P4-B-001
- Tested SHA: 34fb65ab509a455cf0254a27043189401a682500
- Round: 3
- Overall Verdict: FAIL

**BLOCK_MERGE.** The requested checks pass, but the schemas accept records that conceal required missing evidence or an out-of-domain status.

1. **F-01 — High: Failed check plus missing evidence can lose the missing condition.** In `comparison.py:216`, completeness considers required variant IDs but ignores `missing_evidence_reasons` and missing applicability checks. A record with all variants, a failed applicability check, a missing check, and an explicit missing-evidence reason validated with category `calibration_check_failed`. The required category is `calibration_check_failed_and_missing_evidence`, with label `Calibration check failed and required evidence missing`.

   `claim_audit_record.py:45` has a related gap: a failed check plus a missing check validates as `calibration_check_failed` when the reasons list is empty. Enforce the compound category for both representations of required missing evidence and add regression tests.

2. **F-02 — High: Missing variants can hide an out-of-domain status.** In `comparison.py:82`, incomplete variants take precedence over `out_of_domain`. A reproduced record with an out-of-domain check and missing variants validated as `not_enough_usable_evidence`, concealing that the area or period was outside the evaluated calibration. Preserve both facts in the summary and test the combined state.

3. **F-03 — Passed with integration limits.** Contract version `1.1.0` appears in Python and generated TypeScript. The four status dimensions are separate. The tested missing-variant case preserves observed sensitivity, and the practical-margin tests preserve signs and reject `no_change` for non-zero effects. The contract supplies and tests the five-field cache key; actual consumer use still requires integration verification.

4. **F-04 — Scope and fixture checks passed.** Against integration base `71a37b13e8557723f3f5a4f20b8c77d7441f5c57`, all 37 changed paths are under `contracts/**` or are the permitted root `package.json` and `requirements.txt`. All 18 committed fixtures carry `[SYNTHETIC DEV FIXTURE]`. Review of the permitted development files found no apparent credentials or real holdout data; sealed outcomes were not accessed.

## Test Validation
- `python -m pytest contracts/tests -v` — 104 passed.
- `npx --package typescript tsc -p contracts/tsconfig.json --noEmit` — passed, exit code 0.

The handoff contains a P5 PASS for this exact SHA, but F-01 identifies an uncovered case that conflicts with its broad preservation conclusion. Escalate that disagreement to P4 and the relevant science owners; obtain a corrected commit and fresh exact-SHA verdicts before merge.
