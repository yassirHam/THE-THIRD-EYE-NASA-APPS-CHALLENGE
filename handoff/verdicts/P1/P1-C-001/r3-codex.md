# Review Verdict: P1-C-001 Round 3

- From: Codex (P1 Science Reviewer)  
- To: P1 (Science Lead)  
- Task ID: P1-C-001  
- Branch: `task/P1-C-001`  
- Tested SHA: `202517cab62dd2ca6dd0937730ca427ab4f0e51b`  
- Base SHA: `71a37b13e8557723f3f5a4f20b8c77d7441f5c57`  
- Round: 3  
- **Overall Verdict: FAIL**

## Findings

### P1-C-001-R3-01 — High: contradictory standardization helper
In `tests/science/test_composition_fixture.py`, `_fixed_weight_pool` calculates `sum(q*D)/sum(q*O)` while `fixed_weight_standardize` calculates `sum(q*r)`. Retaining both contradicts the true standardization formulation.

### P1-C-001-R3-02 — High: missing calibration evidence can become applicable
In `tests/science/test_stage_a_invariance.py`, `check_applicability` defaults to `"passed"` and treats any non-failed status as `"applicable"`. Explicit passed evidence must be required so missing/unrecognized statuses do not silently become applicable.

### P1-C-001-R3-03 — Medium: weight constraints not enforced
`fixed_weight_standardize` should validate that weights are non-negative and sum to 1.0 (within float tolerance) and reject invalid weights.

## Test Validation
- `python -m pytest -s -p no:cacheprovider tests/science -q`: 124 passed in 0.13s.
- Commit scope: Only `tests/science/` modified.
