# To P5: replay format answer and backend exact-SHA review (2026-11-14)

- From: P4 (sent by the implementation agent on P4's instruction). To: P5. Copy: P1, P2, P3.

## Message from P4
Please answer the replay-format question in handoff/escalations/P5/P5-exact-sha-review-request-r1.md, then
independently review the final exact backend SHAs after the producer/consumer fix. Record PASS or FAIL and the
tests actually run.

## Format implemented (proposal for your decision)
P4-A now writes, beside `bundle_index.json`, one contract 1.5.0 `ProvenanceManifest` per bundle file under
`manifests/...`. Each lists that single file as its partition, with the described artifact's five-field identity,
sha256, size and cache-key digest, so your existing `replay_bundle.py` replays it unchanged (only its
CONTRACT_VERSION constant moved to 1.5.0). `bundle_index.json` lists each manifest with its sha256 for
`--expected-manifest-sha256`. Please confirm this format, or name the format you will replay instead.

## Exact SHAs to review (synthetic evidence only)
| Task | Branch | SHA |
|---|---|---|
| P4-B-001 r11 | task/P4-B-001 | edf9d65255377320b0a544e69f64db897e2960bd |
| P4-A-001 r2 | task/P4-A-001 | 0edd7d304a1ba0f40161e7f059394b42a0fb4bc5 |
| P4-C-001 r2 | task/P4-C-001 | 03c76006ab0bc785faeb97f4357230d0de15b792 |
| P5-B-001 r3 (your lane, agent-edited) | task/P5-B-001 | fdd3d69e909801d64863ccaa3f37685b913e7880 |
| P5-C-001 r3 (your lane, agent-edited) | task/P5-C-001 | 1ccb9a25c2ad6ab68782d750e8eb880b0573ea5d |
| P3-A-002 r2 (consumer) | task/P3-A-002 | 502795565dd66f25f9efa485693b4cd56f412553 |

Other r10 SHAs (P1-A dcaf63e, P1-B 1a7be92, P1-C 5be5cf7, P2-A-002 c686b20) are unchanged.
The agent's runs above are implementation testing, not independent verification.