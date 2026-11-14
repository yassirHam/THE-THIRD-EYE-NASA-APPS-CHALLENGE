# P5 Decision: Replay Format Confirmation for Clean-Room InstaBox Execution

- **Task ID:** P5-EVAL-REPLAY-FORMAT
- **From:** P5 (Independent Evaluation, E2E Parity & Submission Lead)
- **To:** P4 (Contracts & Integration Lead), Implementation Agent (Kiro)
- **Copy:** P1, P2, P3
- **Date:** 2026-11-14 23:15 UTC
- **Topic:** Response to replay-format question in `handoff/escalations/P5/P5-exact-sha-review-request-r1.md` and `P5-replay-format-and-backend-review-r2.md`
- **Status:** **APPROVED & CONFIRMED**

---

## 1. Decision & Formal Confirmation

P5 formally **CONFIRMS and APPROVES** the replay format implemented in P4-A Round 2 (`0edd7d304a1ba0f40161e7f059394b42a0fb4bc5`):

1. **Per-File Replay Manifests:** P4-A emits one Contract 1.5.0 `ProvenanceManifest` per bundle file under:
   `manifests/<artifact_version>/<geometry>/<method>/<policy>/<period>/<family>.manifest.json`
   Each manifest enumerates that exact file as its single partition, containing:
   - Described artifact five-field compound identity `[artifact_version, geometry_id, period_spec, method_id, policy_id]`
   - Relative file path within the bundle
   - `byte_size`
   - Git-blob `sha256`
   - Independent compound cache-key digest
   - Classification: `[SYNTHETIC DEV FIXTURE - NOT REAL OBSERVATION DATA]` (or production equivalent)
2. **Bundle Index Integration:** `bundle_index.json` indexes each manifest alongside its computed sha256 for validation against `--expected-manifest-sha256`.
3. **Replay Engine Compatibility:** This enables P5's clean-room runner `tests/e2e/replay_bundle.py` to replay and verify every bundle artifact individually and deterministically with:
   ```bash
   python tests/e2e/replay_bundle.py --manifest <manifest_path> --bundle-root <bundle_root> --out-dir <target_dir> --expected-manifest-sha256 <sha256>
   ```
4. **Holdout Firewall Preservation:** `replay_bundle.py` continues to enforce strict sealed-boundary protection, immediately refusing (exit code 2) any manifest partition referencing `sealed/*`, `holdout/*`, or paths residing inside `$env:SEALED_EVAL_DIR`.
