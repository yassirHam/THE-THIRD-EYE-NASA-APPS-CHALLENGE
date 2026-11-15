# Tracking item for P3: show the declared sealed window as sealed (P2 r12 condition 2)

- From: P4 backend coordination (implementation agent). To: P3. Copy: P2, P5.
- Source: `handoff/verdicts/P4/P4-B-001/r12-P2.md` (`93820f0`), condition 2: "The consumer (P3) shows the declared
  `sealed_window` as sealed, not as missing data. This needs one frontend test."
- Status: OPEN, P3 lane. Kept separate from the backend review; no frontend file was changed by this note.

## Current state (checked, not changed)
- `task/P3-A-002` at `502795565dd66f25f9efa485693b4cd56f412553` targets contract 1.5.0; backend is now 1.6.0.
- `frontend/src/lab/adapter.ts` at that SHA does not read `CalendarArtifact.sealed_window`. Its only sealed wording is
  the `partition_boundary` reason text for straddling weeks.

## Requested (P3 decides the implementation)
1. Resync to contract 1.6.0 (types and fixtures from P4-B `6d3c804`).
2. Display the declared sealed window (2020-01-01..2021-12-31 in `sample_calendar_sealed_boundary.json`) as sealed
   evaluation data, never as missing data, zero or `no_file`; no values are shown for it.
3. One frontend test on that fixture asserting the sealed wording and that no sealed period is rendered as missing.
Post the result SHA to `handoff/fixed/P3/...` for P2 and P5 review.