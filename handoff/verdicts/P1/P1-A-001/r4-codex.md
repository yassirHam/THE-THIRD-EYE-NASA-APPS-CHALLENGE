# Review Verdict: P1-A-001 Round 4

- From: Codex (P1 Science Reviewer)
- To: P1 (Science Lead)
- Task ID: P1-A-001
- Branch: `task/P1-A-001`
- Tested SHA: `ab8068821550638daab1e1e8670be432c84c4b55`
- Base SHA: `71a37b13e8557723f3f5a4f20b8c77d7441f5c57`
- Parent SHA: `b80b67867557b77dbd5d40d8a49ad372906936a9`
- Round: 4
- **Overall Verdict: PASS** (Scoped)

## Summary & Verification
- **D <= O Constraint Enforced**: `ObsRecord` now rejects $D > O$ with `ValueError` for available observations, aligning with P2 decision record 2026-11-14-05 and Contract 1.1.0 (fire pixels are a subset of usable land). The $O = 0$ with $D > 0$ check takes precedence.
- **Within-Margin Semantics**: `HeadlineDirection.WITHIN_PRACTICAL_MARGIN` and `AppliedComparison.observed_sign` preserved from Round 3.
- **Sensitivity & Applicability Gates**: Unchanged and intact.
- **Test Validation**: `python -m pytest tests/science/test_stage_a.py -v`: 149 passed in 0.50s (includes 7 regression tests in `TestDNotAboveO`).
- **Scope**: Changes strictly isolated to `science/methods/stage_a.py` and `tests/science/test_stage_a.py`.
- **Holdout Firewall**: Intact. Synthetic data only. Zero access to sealed 2020–2021 holdouts.

## Open Cross-Lane Decisions
- Status vocabulary mapping vs Contract 1.1.0 remains open (`handoff/escalations/P1/P1-A-001-r3.md`).
- Registration of numeric `min_support_O` and strata for Stage A remains pending before factor fitting on production extracts.
