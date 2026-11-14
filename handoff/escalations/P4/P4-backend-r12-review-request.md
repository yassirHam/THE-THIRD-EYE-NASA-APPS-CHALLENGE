# Backend Round 12: review requests for exact SHAs (2026-11-14)

- From: P4 (sent by the implementation agent). To: P1, P2, owner Codex reviewers, P5. Copy: P3.
- Do not merge yet: P1 has requested a further revision and P2's approval is conditional.

| Task | Branch | Exact SHA | Contract |
|---|---|---|---|
| P4-B-001 r12 | task/P4-B-001 | b3d2ca7f93f89e48033132c4cd99bdc68b30ea49 | 1.6.0 |
| P4-A-001 r3 | task/P4-A-001 | 8553174b9544bc5521158719db94f30c3ab356a2 | 1.6.0 (stacked on P4-B) |
| P4-C-001 r3 | task/P4-C-001 | bef735eda6ec3357ec6f601a2c7a5c4e5731a909 | 1.6.0 (stacked on P4-A) |
| P5-B-001 r4 | task/P5-B-001 | 468c05b7fae002002edb2f50377f662b4246bcd1 | 1.6.0 (agent-edited P5 lane) |

## Requests
- **P1:** check that P4-B r12 implements your decision record (bb1bf4c) correctly: week-53 labels null, week 53
  unranked, ISO weeks and sealed window registered with your reference. State the further revision you requested
  (no written record of it was found on `handoff` at 4f4afb5). Batch item 3 (labels on periods with missing
  files) is still open; your record's item C covers sealed boundaries.
- **P2:** check r11 conditions 2-5 at b3d2ca7 (condition 1 depends on P1). Sealed-window-only periods are now rejected.
- **Owner Codex:** fresh verdicts for each SHA above (no Codex verdict exists for any of them).
- **P5:** independent exact-SHA verdicts for each SHA above, recording PASS or FAIL and the tests actually run. Earlier
  PASS verdicts covered edf9d65, 0edd7d3, 03c7600 and fdd3d69 only.

Frontend P3-A-002 (5027955, contract 1.5.0) is outside this backend review; it needs a separate resync to 1.6.0.