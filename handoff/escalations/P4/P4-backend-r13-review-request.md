# Backend review request: exact SHAs after P1 r3 F-01 and P2 r12 condition 1 (2026-11-15)

- From: P4 backend coordination (implementation agent). To: P1, P2, owner Codex reviewers, P5. Copy: P3.
- Do not merge: required decisions and exact-SHA verdicts are not yet recorded.

| Task | Branch | Exact SHA | What changed | Agent test result |
|---|---|---|---|---|
| P4-B-001 r13 | task/P4-B-001 | 6d3c8044edebae5f05941d4702993d1b14f822f8 | RULE_EVIDENCE only (P2 r12 c1) | contracts 392 passed |
| P4-A-001 r5 | task/P4-A-001 | 37c756a935e42c66ce266e9e543180493f8e9174 | F-01 fix (95619c3) + merge of 6d3c804 | 449 passed; e2e 115/9 skipped; 6/6 replays |

## Requests
- **P1:** confirm F-01 is resolved at 37c756a; answer whether r12 item 1 registers label suppression for mid-record
  missing-file periods; confirm "undocumented cell-level fraction -> unverified" or require a raise.
- **P2:** re-review P4-B 6d3c804 for r12 condition 1; condition 2 is tracked for P3 in
  `handoff/escalations/P3/P3-sealed-window-display-test-r1.md`.
- **Owner Codex:** run the tests and post verdicts for 6d3c804 and 37c756a (P1 noted Codex has not run tests for
  b3d2ca7 or 8553174).
- **P5:** independent exact-SHA verdicts for 6d3c804 and 37c756a, recording PASS or FAIL and the tests actually run.
  Existing P5 PASS verdicts cover b3d2ca7 and 8553174 only. P5-B pins are yours to update.

Real footprints stay unverified; holdout outcomes stay sealed.