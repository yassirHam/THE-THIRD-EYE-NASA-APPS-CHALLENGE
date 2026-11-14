# Review Verdict: P4-B-001 Round 7

- From: Codex (P4 Reviewer)
- To: P4 (Contracts / Schemas)
- Task ID: P4-B-001
- Branch: task/P4-B-001
- Tested SHA: 141435189d94ba21b9d13023f276d34d4efde363
- Round: 7
- Overall Verdict: FAIL

**BLOCK_MERGE:** Missing mandatory owner Codex PASS signature. Review identified two remaining issues:

1. **F-01 — Cutoff week cannot follow the declared ISO week definition. Severity: high.**  
   `calendar.py` rejects every S-NPP week whose end date is after November 2. The UTC ISO week containing the cutoff is November 2–8, 2026, so it cannot be represented as a partial, comparison-ineligible week. The accepted fixture instead labels October 27–November 2 as an ISO week, although it runs Tuesday to Monday. The series validator does not enforce alignment with its declared week definition.
   Expected: the frozen ISO week is representable as partial and ineligible, with no normal, unusual or critical decision. P1/P2 should resolve the scientific contract; add boundary and week-alignment tests.

2. **F-02 — The requested null label representation is not implemented. Severity: medium.**  
   Partial periods require the string `not_applicable` for unusual and critical statuses; the schema rejects null. That sentinel suppresses a decision, but it does not satisfy the stated requirement for null labels. Weekly records also have no baseline median or P90 fields, so the claim that those weekly fields are null cannot be verified. Align the contract and acceptance wording with the scientific owners' intended representation.

3. **F-03 — Other requested checks passed.**  
   Compound failed or out-of-domain states preserve missing evidence in the summary and make conclusions ineligible. The branch diff from base `71a37b13e8557723f3f5a4f20b8c77d7441f5c57` contains 35 changed paths, all under `contracts/**`. All 18 current JSON fixtures carry `[SYNTHETIC DEV FIXTURE]`. Contract version is `1.1.0`.

## Test Validation
- `python -m pytest -p no:cacheprovider contracts/tests -q`: 132 passed.
- `python -m contracts.generate_ts --check`: types.ts is current.
- `tsc -p contracts/tsconfig.json --noEmit`: passed with zero diagnostics.

**BLOCK_MERGE** pending resolution of F-01 and F-02, renewed review at the resulting SHA, and the required exact-SHA verdicts.
