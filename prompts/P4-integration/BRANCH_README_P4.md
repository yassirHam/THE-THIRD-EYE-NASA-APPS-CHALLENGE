# P4 — Contracts, Integration, Static Artifacts & Release (12:00 AM Branch & Worktree Setup)

**Role Owner:** P4 (Backend, Contracts, CI & Integration Lead)  
**Primary Role Branch:** `p4/integration` (plus exclusive merge ownership of `integration` and human promotion to `main`)  
**Mandatory Authorities:** `AGENTS.md`, `THE_THIRD_EYE_AI_AGENTS_PLAYBOOK.md`, `team-kit/INSTABOX.md`, `team-kit/BOXES.md`

---

## 1. 12:00 AM Repository Kickoff & 3-Worktree Initialization

P4 executes the initial GitHub push from `prompts/README_BRANCH_WORKFLOW.md`, broadcasts `BASE_SHA` + `Plan SHA256`, and creates 3 local worktrees:

```powershell
New-Item -ItemType Directory -Force "$HOME\projects" | Out-Null
Set-Location "$HOME\projects"
git clone https://github.com/yassirHam/THE-THIRD-EYE-NASA-APPS-CHALLENGE.git the-third-eye-team
Set-Location the-third-eye-team
git fetch origin

git checkout p4/integration
git worktree add -b task/P4-A-001 ../the-third-eye-P4-A p4/integration
git worktree add -b task/P4-B-001 ../the-third-eye-P4-B p4/integration
git worktree add -b task/P4-C-001 ../the-third-eye-P4-C p4/integration
git worktree list
```

---

## 2. Worktree Lane Ownership

| Lane | Worktree Folder | Branch | Editable Paths | Core Responsibility |
|---|---|---|---|---|
| **P4-A** | `../the-third-eye-P4-A` | `task/P4-A-001` | `artifact_pipeline/**` | Versioned static JSON generator (gzip optional, $\le 10\text{ MB}$ compressed target, measured load size/latency), honest unavailable/null states; optional dev FastAPI server |
| **P4-B** | `../the-third-eye-P4-B` | `task/P4-B-001` | `contracts/**` | Frozen Pydantic v2 schemas, generated TypeScript interfaces, deterministic synthetic fixtures, immutable `artifact_id` + `geometry_id` + `policy_id` cache keys, contract verification tests |
| **P4-C** | `../the-third-eye-P4-C` | `task/P4-C-001` | `deploy/**`, `CI/**`, `scripts/watcher*` | 60--90 min labelled static public skeleton, pinned runtime locks, CI smoke checks, tested offline static fallback, plus the zero-token 2-min `handoff` watcher script |

---

## 3. Immediate First-Hour Targets (12:00 AM -- 01:30 AM)

1. **First 30--45 min:** Freeze minimal Pydantic schemas, TypeScript types, and clearly labelled synthetic fixtures in `P4-B` with P1/P2 sign-off; distribute contract version to P3 & P5 immediately.
2. **First 60--90 min:** Deploy the labelled static public skeleton in `P4-C` (explicitly marked `[DEVELOPMENT SKELETON — NOT SCIENTIFICALLY VALIDATED]`) and verify the automated 2-minute `git fetch` watcher script for all five laptops.
3. **Optional InstaBox / Boxes.dev Linux Verification (`team-kit/INSTABOX.md`, `team-kit/BOXES.md`):**
   - P4 owns any Linux integration smoke-check host (`instabox create --name the-third-eye-check`). Use private port previews (`--private`) only, never public unauthenticated repo dumps, and keep the separately deployed static flagship fallback active for judges.
   - Boxes.dev remains trial-first (30--45 min test on the throwaway demo only if P4 approves).
4. **Serial Integration Rule:** Only P4's `agy` merges task branches into `integration` — one branch at a time, only when the exact commit SHA holds **both** P5 PASS and Owner Codex PASS and combined CI checks pass.

