# P1 — Science & Comparison Engine (12:00 AM Branch & Worktree Setup)

**Role Owner:** P1 (Science Lead)  
**Primary Role Branch:** `p1/science`  
**Mandatory Science Authorities:** `AGENTS.md`, `THE_THIRD_EYE_FINAL_PLAN_GEOGRAPHIC_ACCESS_UPDATED.txt`, `THE_THIRD_EYE_AI_AGENTS_PLAYBOOK.md`, `THE_THIRD_EYE_FIVE_PERSON_ASSIGNMENTS.txt`

---

## 1. 12:00 AM Git Checkout & 3-Worktree Initialization

Run once after P4 announces `BASE_SHA` and the GitHub repository URL:

```powershell
# Clone outside OneDrive (works for any Windows username)
New-Item -ItemType Directory -Force "$HOME\projects" | Out-Null
Set-Location "$HOME\projects"
git clone https://github.com/yassirHam/THE-THIRD-EYE-NASA-APPS-CHALLENGE.git the-third-eye-team
Set-Location the-third-eye-team
git fetch origin

# Verify plan integrity
git checkout p1/science
git rev-parse HEAD
Get-FileHash THE_THIRD_EYE_FINAL_PLAN_GEOGRAPHIC_ACCESS_UPDATED.txt -Algorithm SHA256

# Spawn 3 isolated worktrees (one Kiro writer per worktree)
git worktree add -b task/P1-A-001 ../the-third-eye-P1-A p1/science
git worktree add -b task/P1-B-001 ../the-third-eye-P1-B p1/science
git worktree add -b task/P1-C-001 ../the-third-eye-P1-C p1/science
git worktree list
```

---

## 2. Worktree Lane Ownership

| Lane | Worktree Folder | Branch | Editable Paths | Core Responsibility |
|---|---|---|---|---|
| **P1-A** | `../the-third-eye-P1-A` | `task/P1-A-001` | `science/methods/` | Own-support ($a_H$) vs common-support ($a_C$) pooled-rate ratios, Stage A calibration, leave-one-training-year-out variants, policy eligibility & invariance |
| **P1-B** | `../the-third-eye-P1-B` | `task/P1-B-001` | `science/calendar/` | Monthly & weekly rates, seasonal baseline, normal season, critical & unusual week rules, period effects, equality boundaries, missingness accounting |
| **P1-C** | `../the-third-eye-P1-C` | `task/P1-C-001` | `tests/science/` | Independent hand-calculated fixtures (missing vs zero, factor invariance, policy compatibility, **8.2/2.8 vs 5.5/5.5 composition fixture**) |

---

## 3. Timeboxed Checkpoints (Local Event Time)

- **First 60--90 min (12:00 AM -- 01:30 AM):** Review schema & cache keys with P2 & P4; freeze candidate region rules (with P2) without inspecting outcomes; register target, Stage A splits (`2016-2018` train, `2019` dev, `2020-2021` sealed, `2022-2024` applicability), and headline denominator with P5 before any holdout opens. Build initial synthetic fixture modules in `P1-A`, `P1-B`, `P1-C`.
- **Saturday 13:00:** Inspect P2's real `D/O` sample; verify feasibility fallback if full history is delayed (2016--2024 core required).
- **Saturday 20:00 (P0 Gate):** Real-data monthly/weekly calendar, normal season, frozen week labels, Stage A factors, and honest applicability/unavailable states handed off to P4 & P3.
- **Saturday 23:00 (P0 Holdout Eval):** Review P5's held-out outputs with P2 without retuning frozen Stage A parameters.
- **Sunday 18:00 (P1 Cutoff):** Complete/verify optional P1 (`8.2/2.8` vs `5.5/5.5` geographic composition fixture if extra areas ship) or cut cleanly.

---

## 4. Optional Cloud Tooling: InstaBox for P1

Use **InstaBox** (`team-kit/INSTABOX.md`) to run clean-room Linux reproducibility tests of `science/methods/`, `science/calendar/`, and `tests/science/` (confirming zero Windows-path assumptions or floating-point drift). Keep **P5's 2020--2021 holdout data strictly out** of your InstaBox workspace and git branches.

