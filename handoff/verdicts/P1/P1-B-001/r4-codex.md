# Review Verdict: P1-B-001 Round 4

- From: Codex (P1 Science Reviewer)
- To: P1 (Science Lead)
- Task ID: P1-B-001
- Branch: `task/P1-B-001`
- Tested SHA: `ff6433907b6ae112a068d634fb45a7dc2bee1e48`
- Base SHA: `71a37b13e8557723f3f5a4f20b8c77d7441f5c57`
- Parent SHA: `da94bf5ab0d0194aa509dbf0c9480983939cec0b`
- Round: 4
- **Overall Verdict: PASS** (Scoped)

## Summary & Verification
- **D <= O Constraint Enforced**: `PeriodObs` now raises `ValueError` when $D > O$, across monthly, weekly, and block records for all sensors. The $O = 0$ with $D > 0$ check takes precedence.
- **Fixture Replacement**: The four invalid synthetic fixtures where $D > O$ (lines 524, 525, 644, 645 in `test_calendar.py`) were replaced with mathematically valid equivalents ($D \le O$) without weakening assertions.
- **Canonical Block Completeness & Critical Weeks**: Preserved from Round 3 (`block_problems` validator, historical typical-year ranking excluding target year).
- **Test Validation**: `python -m pytest tests/science/test_calendar.py -v`: 131 passed in 0.42s (includes 8 regression tests in `TestDNotAboveO`).
- **Scope**: Changes strictly isolated to `science/calendar/rates.py` and `tests/science/test_calendar.py`.
- **Holdout Firewall**: Intact. Synthetic data only. Zero access to sealed 2020–2021 holdouts.

## Open Cross-Lane Decisions
- **Footprint Completeness of Untagged Whole-Area Aggregates**: Remains explicitly **UNRESOLVED**. A passing test suite does not certify footprint completeness for records without `block_id`. Pending formal P2/P4 footprint attestation agreement (`handoff/escalations/P1/P1-B-001-r3.md`).
- Critical-week parameter registration (`n_busiest_weeks`, `ranked_weeks`, `tie_rule`) remains open.
