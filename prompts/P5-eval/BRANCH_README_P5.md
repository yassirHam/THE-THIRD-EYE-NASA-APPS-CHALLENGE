# P5 — Independent Evaluation, Replay & Submission (12:00 AM Branch & Worktree Setup)

**Role Owner:** P5 (Validation, Clean-Room Replay & Submission Lead)  
**Primary Role Branch:** `p5/eval`  
**Mandatory Authorities:** `AGENTS.md`, `THE_THIRD_EYE_FINAL_PLAN_GEOGRAPHIC_ACCESS_UPDATED.txt`, `THE_THIRD_EYE_EXECUTION_SPEC.md`, `THE_THIRD_EYE_AI_AGENTS_PLAYBOOK.md`, `team-kit/INSTABOX.md`

---

## 1. 12:00 AM Git Checkout & 3-Worktree Initialization

```powershell
New-Item -ItemType Directory -Force "$HOME\projects" | Out-Null
Set-Location "$HOME\projects"
git clone https://github.com/yassirHam/THE-THIRD-EYE-NASA-APPS-CHALLENGE.git the-third-eye-team
Set-Location the-third-eye-team
git fetch origin

git checkout p5/eval
git rev-parse HEAD
Get-FileHash THE_THIRD_EYE_FINAL_PLAN_GEOGRAPHIC_ACCESS_UPDATED.txt -Algorithm SHA256

# Spawn 3 isolated worktrees
git worktree add -b task/P5-A-001 ../the-third-eye-P5-A p5/eval
git worktree add -b task/P5-B-001 ../the-third-eye-P5-B p5/eval
git worktree add -b task/P5-C-001 ../the-third-eye-P5-C p5/eval
git worktree list
```

---

## 2. Worktree Lane Ownership

| Lane | Worktree Folder | Branch | Editable Paths | Core Responsibility |
|---|---|---|---|---|
| **P5-A** | `../the-third-eye-P5-A` | `task/P5-A-001` | `eval/**` (code only; sealed holdout data stays OUTSIDE Git!) | Preregistered switch / no-switch experiment over rule-based block-by-period case list; raw/corrected/uncertainty baselines; error, coverage, abstention & frozen headline metric with independent units |
| **P5-B** | `../the-third-eye-P5-B` | `task/P5-B-001` | `tests/e2e/**` | Independent `playwright-cli` UI/artifact/export parity checks, geometry/missingness verification, reduced-motion/keyboard tests, plus **clean-environment InstaBox bundle replay runner** |
| **P5-C** | `../the-third-eye-P5-C` | `task/P5-C-001` | `challenge/**`, `docs/submission/**` | Pre-kickoff official challenge capture & legal/cutoff verification; analyst question + real published claim; sources/licenses; 1-page judge results, demo script (first 20s rule), raw screen capture & portal checklist |

---

## 3. Holdout Firewall & Clean-Room Replay Discipline

1. **Sealed Holdout Isolation:** `2020--2021` evaluation partitions live in local P5-controlled isolated storage (`SEALED_EVAL_DIR` outside Git worktrees, NEVER shared with P1--P4 laptops or uploaded to InstaBox/Boxes.dev).
2. **Method Freeze Rule:** Do NOT open sealed holdouts until P1/P2 sign off frozen Stage A methods & protocol. Never write sealed labels into `handoff/` verdicts or dev branches. Any post-freeze method adjustment receives a new version ID (`method_v2`) and is never labeled blind retroactively.
3. **InstaBox Clean Replay (`team-kit/INSTABOX.md`):** On Sunday morning/noon, replay P4's frozen **public** evidence bundle (`artifact_version` + SHA256 manifest) inside a fresh Linux InstaBox container (`/data/the-third-eye`). Verify exact checksum equality and interrupted-job recovery. Report failure honestly if replay diverges.

---

## 4. Critical Checkpoints

- **Before Kickoff (Pre-12:00 AM):** Save official challenge text/judging criteria in `challenge/`, verify official portal timezone & `11:59 PM` cutoff, confirm under-18 media/NASA rules vs team build-window rules.
- **First 60 min:** Publish evaluation manifest (`eval/manifest.json` — metadata/case list only, zero outcomes), independent edge-case fixtures, and one documented real analyst question.
- **Saturday 23:00 (P0 Holdout Eval):** Execute frozen switch/no-switch experiment on untouched holdout partitions; output all baselines, failures, abstentions, and frozen headline denominator (`blocks`, `regions`, `test years`).
- **Sunday 12:00:** Complete clean-room InstaBox replay of frozen flagship bundle with P4.
- **Sunday 20:00:** Complete 1-page results sheet, demo script, and raw screen capture using actual shipped UI & numbers.
- **Sunday 22:00:** Complete internal submission freeze well ahead of the verified official cutoff.

