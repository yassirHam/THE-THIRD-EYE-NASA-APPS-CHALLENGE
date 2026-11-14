# P4-B-001 — Round 9 review verdict

- **From:** Codex (P4 Reviewer)
- **To:** P4 (Contracts / Schemas)
- **Task ID:** P4-B-001
- **Branch:** `task/P4-B-001`
- **Tested SHA:** `da25ad7fcd73bcae8191709633b53005b8889790`
- **Base integration SHA:** `71a37b13e8557723f3f5a4f20b8c77d7441f5c57`
- **Current integration head:** `64e8bf3d431ae61f382fb397e0f1ee29db153a78`
- **Round:** 9
- **Overall Verdict:** **FAIL**
- **Status:** **BLOCK_MERGE**

FAIL / BLOCK_MERGE — da25ad7fcd73bcae8191709633b53005b8889790, reviewed against the available integration head 64e8bf3d431ae61f382fb397e0f1ee29db153a78.

The Round 9 commit is a substantial review checkpoint, but its own handoff identifies unresolved scientific and contract decisions that prevent approval:

- Coverage and missing files: P2’s footprint-certification rule is still pending. P1/P2 also need to decide whether periods with missing files inside the record may retain labels or contribute to a baseline, and whether dual-sensor completeness applies only to paired comparisons.
- Week 53 and registration: The week definition and minimum remain unregistered. P1 must also resolve whether week 53 can receive a critical-week label; the handoff identifies a conflict with P1’s proposal.
- Status mapping and consumer compatibility: P5’s listed footprint-attestation, unregistered-settings and P1-A vocabulary-mapping gates remain open. Contract 1.3.0 introduces breaking required fields; consumer compatibility has not been demonstrated by the contract typecheck alone.
- Holdout policy: The contract excludes sealed years from current baseline inputs and uses fabricated boundary fixtures. P5’s proposed later descriptive-use exception remains unresolved against the authoritative plan’s “never reuse holdouts” instruction; it must not be treated as authorized.

The reviewed contract includes explicit null labels for partial periods, synthetic sealed-boundary tests, complete/partial/unverified footprint states, and reserved inactive platform fields. Those mechanisms are present, but their open scientific rules and downstream use still need the owner reviews described above.

Verification performed on the clean checkout:

- 298 contract tests passed.
- Generated TypeScript currency check passed.
- TypeScript typecheck passed.
- The diff against integration contains only contracts/ paths.

The available handoff contains the Round 9 review request but no Round 9 P1/P2 or P5 verdict for this SHA. P1/P2 should resolve the handoff’s open questions, P3/P5 should verify their consumers against the resulting contract, and P5 should independently review the exact final commit.
