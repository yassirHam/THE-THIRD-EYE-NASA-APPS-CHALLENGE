# Request for P5 independent exact-SHA review (2026-11-14T22:25:50Z)

- From: implementation agent (Kiro) for P4. To: P5. Copy: P1, P2, P3, P4.
- Integration head checked: `64e8bf3d431ae61f382fb397e0f1ee29db153a78`. All branches below merge without conflict
  into it, alone and combined (local throwaway candidate, not pushed).
- The agent's own test runs are listed in each `handoff/fixed/...` note. They are not independent verification.
- Please test each exact SHA from a clean checkout and post `handoff/verdicts/<owner>/<task>/r<n>-P5.md`.

| Order | Task | Branch | Exact SHA | Depends on | Note |
|---|---|---|---|---|---|
| 1 | P4-B-001 r10 | task/P4-B-001 | 8edec4676b26237c81b11140587ad0989d28ba22 | - | contract 1.4.0, breaking |
| 2 | P4-A-001 r1 | task/P4-A-001 | 9294fbfd28b4756da065e0fe06b3be36086a733a | P4-B 8edec46 (stacked) | |
| 3 | P4-C-001 r1 | task/P4-C-001 | 12e1b5eb6c37a98dd2ccf050c830c829fa1f113e | P4-A 9294fbf (stacked) | |
| 4 | P1-A-001 r5 | task/P1-A-001 | dcaf63ebc88bea30ac91f9c892ebd9883d7c4868 | - | P1 approval needed (strict rule) |
| 5 | P1-B-001 r5 | task/P1-B-001 | 1a7be925a0f05bc45273de6b66e54ef8e94d13ee | - | |
| 6 | P1-C-001 r6 | task/P1-C-001 | 5be5cf7960a4048c27460f42129c857b99ab8bbb | - | follow-up to merged 96fe592 |
| 7 | P2-A-002 r1 | task/P2-A-002 | c686b20198eaba68cb8239798c07465f90435630 | - (base p2/data) | P2 owner review needed |
| 8 | P3-A-002 r1 | task/P3-A-002 | 14b7e434b7cdc8784dd6ab2becc6679bcb281d65 | P4-B 8edec46 types | live browser: networkidle timeouts on `/` |
| 9 | P5-B-001 r2 | task/P5-B-001 | 01c309d1ea9b89f5c1aea6b53b90f451e3a1e096 | P4-B 8edec46 | your lane: mechanical edits by the agent |
| 10 | P5-C-001 r2 | task/P5-C-001 | 6369890c7cd355d60d78e39de8e80522354dfbe9 | P4-B 8edec46 fixtures | your lane: checker now fails on 8 integer hits |

Specific requests:
- P5-B/P5-C were edited by the implementation agent. Review them as untrusted changes to your lane.
- Holdout firewall: confirm no 2020-2021 observation is used anywhere (only fabricated dates in boundary fixtures).
- Replay gap: P4-A writes `bundle_index.json`; no producer yet writes a ProvenanceManifest whose partitions point at bundle
  files, so P5-B's manifest replay cannot replay a P4-A bundle. Say which format P5 will replay.
