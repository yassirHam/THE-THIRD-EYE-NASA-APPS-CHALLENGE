# THE THIRD EYE — 12:00 AM GitHub Repository, Branch & Multi-CLI Prompt Guide

**Project:** THE THIRD EYE (NASA Space Apps Challenge 2026: *Harmonization of MODIS and VIIRS Hot Spots*)  
**Kickoff Window:** 12:00 AM (All project code, fixtures, and extracts are built during November 14--15)  
**Scientific Authority:** `../THE_THIRD_EYE_FINAL_PLAN_GEOGRAPHIC_ACCESS_UPDATED.txt`  
**Orchestration Playbook:** `../THE_THIRD_EYE_AI_AGENTS_PLAYBOOK.md`  
**Repository:** `https://github.com/yassirHam/THE-THIRD-EYE-NASA-APPS-CHALLENGE.git` (private)  
**Expected Plan SHA256:** `EF288068396CB77F2F9C1B2A5D2C9E0297FE7CA65755587638057D263E4DCB13`  
**BASE_SHA:** the `main` commit announced by P4 (`git rev-parse origin/main`). Every role branch starts at that exact commit.  
**Paths:** All commands use `$HOME\projects\...` and work for any Windows username. Never clone inside OneDrive.

---

## 1. 12:00 AM Repository & Branch Topology

Initialize **one** shared GitHub repository from this planning folder at `12:00 AM` and freeze `BASE_SHA` on `main`. Never send ZIP files between laptops.

### Shared Trunk & Coordination Branches
- `main` — Verified public/judge baseline (only **P4 human owner** promotes `integration` $\to$ `main`).
- `integration` — Serial merge branch managed exclusively by **P4's Antigravity (`agy`)** after both **P5 PASS** and **Owner Codex PASS** on the exact SHA.
- `handoff` — Append-only asynchronous relay branch written exclusively by **`agy`** (`handoff/verdicts/...`, `handoff/fixed/...`, `handoff/escalations/...`). Always sync with `git pull --rebase` then `git push` (never `--force`).

### Role Integration & Task Branches (1 Role Branch + 3 Disjoint Worktrees per Person)
Every person (`P1`--`P5`) anchors their work on a role branch created from `BASE_SHA` and spawns **3 isolated local Git worktrees** (one per owned directory lane `A`, `B`, `C`):

| Person | Role Branch | Worktree A Path (`task/P<N>-A-001`) | Worktree B Path (`task/P<N>-B-001`) | Worktree C Path (`task/P<N>-C-001`) | Key Optional Cloud Tooling |
|---|---|---|---|---|---|
| **P1** | `p1/science` | `science/methods/` | `science/calendar/` | `tests/science/` | **InstaBox** (isolated Linux math verification) + Kiro `the-third-eye-coder` delegation |
| **P2** | `p2/data` | `pipeline/masks/`, `pipeline/grid/` | `pipeline/acquisition/`, `pipeline/exports/` | `data/manifests/` | **GEE / Earthdata** (block batch exports) + **InstaBox** (bounded checksum check only) |
| **P3** | `p3/frontend` | `frontend/calendar/` | `frontend/comparison/` | `frontend/evidence/` | **60 Installed Skills** (`frontend-design`, `impeccable`, `playwright-cli` for P0; 3D/GSAP for P2) + optional **Boxes.dev** |
| **P4** | `p4/integration` | `artifact_pipeline/` | `contracts/` | `deploy/`, `CI` | **InstaBox** (Linux smoke/replay, private port 3000) + **Boxes.dev** trial pilot |
| **P5** | `p5/eval` | `eval/` | `tests/e2e/` | `docs/submission/` | **InstaBox** (clean-room `/data/the-third-eye` bundle replay) + `playwright-cli` + isolated holdout storage |

---

## 2. 12:00 AM Git Initialization Commands (Run Once by P4)

```powershell
# ALREADY EXECUTED by P4 on 2026-11-14 (reference only). Inside the repository root:
git init -b main
git add .
git commit -m "chore: initialize THE THIRD EYE planning packet and per-role prompt suite"
git remote add origin https://github.com/yassirHam/THE-THIRD-EYE-NASA-APPS-CHALLENGE.git
git push -u origin main

# Create trunk coordination branches from BASE_SHA
$BASE_SHA = git rev-parse HEAD
git branch integration $BASE_SHA
git branch p1/science $BASE_SHA
git branch p2/data $BASE_SHA
git branch p3/frontend $BASE_SHA
git branch p4/integration $BASE_SHA
git branch p5/eval $BASE_SHA
git push -u origin integration p1/science p2/data p3/frontend p4/integration p5/eval

# Create clean append-only handoff branch (or initialize from main/orphan)
git checkout --orphan handoff
git rm -rf . 2>$null
New-Item -ItemType Directory -Force handoff/verdicts, handoff/fixed, handoff/escalations | Out-Null
"" | Set-Content handoff/.gitkeep
git add handoff/.gitkeep
git commit -m "chore: initialize append-only handoff relay branch"
git push -u origin handoff
git switch main

# Print agreed BASE_SHA and Plan SHA256 for the whole team
Write-Host "BASE_SHA=$BASE_SHA"
Get-FileHash THE_THIRD_EYE_FINAL_PLAN_GEOGRAPHIC_ACCESS_UPDATED.txt -Algorithm SHA256
```

Each teammate then clones **once** outside OneDrive:
```powershell
git clone https://github.com/yassirHam/THE-THIRD-EYE-NASA-APPS-CHALLENGE.git the-third-eye-team
Set-Location the-third-eye-team
git checkout <YOUR_ROLE_BRANCH>
# Then follow prompts/P<N>-<role>/BRANCH_README_P<N>.md to create your 3 worktrees
```

---

## 3. Fixed Tool Roles on Every Teammate Laptop (Playbook Section 3)

| CLI Tool | Fixed Responsibility | Read/Write Permission | Model Pinning Guidance (`plan_f.txt`) |
|---|---|---|---|
| **Kiro CLI (`kiro-cli`)** | **Sole Coder** — only tool allowed to write project files inside assigned task worktrees. Commits to task branch; **never pushes/merges**. | Read/Write inside assigned worktree `Allowed editable paths` only. Uses `.kiro/agents/the-third-eye-coder.md`. | Cannot switch models mid-turn by phase. Plan complex logic in an Opus session (`--model claude-opus-4.8`), delegate bounded file coding to sub-agent `the-third-eye-coder` (`claude-sonnet-4.6`). |
| **Codex CLI (`codex`)** | **Read-Only Analyst & Judge** — evaluates code diffs, test outputs, and external `handoff/verdicts/`. Writes review verdicts and fix orders (`$fixOrder`). | Strictly `--sandbox read-only`. **Never edits project code or pushes.** | Pin model explicitly via `codex exec -m <MODEL_ID> --sandbox read-only ...`. |
| **Antigravity CLI (`agy`)** | **Git Operator & Relay** — manages task branches, fetches/pushes `handoff/` files via `git pull --rebase`, launches headless `codex` & `kiro-cli`, enforces the **6 Stop Rules**. | Git/CLI orchestration only. **Never edits project source or overrides verdicts.** | Pin via `agy --model <MODEL_ID> -p "<step>" --output-format json --print-timeout 15m`. |

---

## 4. Per-Person Prompt Index

- **P1 (Science & Comparison Engine):** `prompts/P1-science/`
  - Setup & worktrees: [`BRANCH_README_P1.md`](P1-science/BRANCH_README_P1.md)
  - Prompts: [`PROMPT_KIRO_P1.md`](P1-science/PROMPT_KIRO_P1.md) | [`PROMPT_CODEX_P1.md`](P1-science/PROMPT_CODEX_P1.md) | [`PROMPT_AGY_P1.md`](P1-science/PROMPT_AGY_P1.md)
- **P2 (NASA Data, Geography & Source Quality):** `prompts/P2-data/`
  - Setup & worktrees: [`BRANCH_README_P2.md`](P2-data/BRANCH_README_P2.md)
  - Prompts: [`PROMPT_KIRO_P2.md`](P2-data/PROMPT_KIRO_P2.md) | [`PROMPT_CODEX_P2.md`](P2-data/PROMPT_CODEX_P2.md) | [`PROMPT_AGY_P2.md`](P2-data/PROMPT_AGY_P2.md)
- **P3 (Frontend, Presentation & Skills):** `prompts/P3-frontend/`
  - Setup & worktrees: [`BRANCH_README_P3.md`](P3-frontend/BRANCH_README_P3.md)
  - Prompts: [`PROMPT_KIRO_P3.md`](P3-frontend/PROMPT_KIRO_P3.md) | [`PROMPT_CODEX_P3.md`](P3-frontend/PROMPT_CODEX_P3.md) | [`PROMPT_AGY_P3.md`](P3-frontend/PROMPT_AGY_P3.md)
- **P4 (Contracts, Artifacts, Integration & Release):** `prompts/P4-integration/`
  - Setup & worktrees: [`BRANCH_README_P4.md`](P4-integration/BRANCH_README_P4.md)
  - Prompts: [`PROMPT_KIRO_P4.md`](P4-integration/PROMPT_KIRO_P4.md) | [`PROMPT_CODEX_P4.md`](P4-integration/PROMPT_CODEX_P4.md) | [`PROMPT_AGY_P4.md`](P4-integration/PROMPT_AGY_P4.md)
- **P5 (Independent Evaluation, Replay & Submission):** `prompts/P5-eval/`
  - Setup & worktrees: [`BRANCH_README_P5.md`](P5-eval/BRANCH_README_P5.md)
  - Prompts: [`PROMPT_KIRO_P5.md`](P5-eval/PROMPT_KIRO_P5.md) | [`PROMPT_CODEX_P5.md`](P5-eval/PROMPT_CODEX_P5.md) | [`PROMPT_AGY_P5.md`](P5-eval/PROMPT_AGY_P5.md)

---

## 5. Non-Negotiable Event Rules (Summary)
1. **Tier Priority & Cut Order:** Ship **P0** first (exports launched in Hour 1, monthly/weekly same-sensor calendar, normal season, frozen week labels, primary + predeclared raw sub-areas, FIRMS link + explainer, Stage A, frozen held-out report + headline denominator, static no-backend judge site $\le 10\text{ MB}$ compressed target, P0-late in-app hotspots by Sun 12:00, independent replay, 1-page results + demo + submission). Do not start P1 until your own P0 is verified; do not start Story/3D/Stage B/Evidence Repair (P2) until P0 and chosen P1 pass.
2. **Holdout Firewall:** 2020--2021 evaluation data lives in P5-controlled isolated storage. Never let P1/P2/P3/P4 agents read or tune on sealed holdouts.
3. **Zero Silent Failures:** Missing data is never zero (`missing != 0`). Failed applicability is separate from missing evidence and out-of-domain checks.
4. **Stop Rules:** Escalate immediately to human owners if 3 fix rounds fail, Codex rejects a tester finding, a fix crosses editable paths or alters scientific thresholds/contracts, a verdict touches sealed holdout results, or a credential/out-of-domain leak appears.

