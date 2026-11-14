# P3 — Frontend, Presentation & Skills (12:00 AM Branch & Worktree Setup)

**Role Owner:** P3 (Frontend Lead)  
**Primary Role Branch:** `p3/frontend`  
**Mandatory Authorities:** `AGENTS.md`, `THE_THIRD_EYE_FRONTEND_CONTRACT.md`, `THE_THIRD_EYE_FINAL_PLAN_GEOGRAPHIC_ACCESS_UPDATED.txt`, `team-kit/FRONTEND_SKILLS.md`

---

## 1. 12:00 AM Git Checkout & 3-Worktree Initialization

```powershell
New-Item -ItemType Directory -Force "$HOME\projects" | Out-Null
Set-Location "$HOME\projects"
git clone https://github.com/yassirHam/THE-THIRD-EYE-NASA-APPS-CHALLENGE.git the-third-eye-team
Set-Location the-third-eye-team
git fetch origin

git checkout p3/frontend
git rev-parse HEAD
Get-FileHash THE_THIRD_EYE_FINAL_PLAN_GEOGRAPHIC_ACCESS_UPDATED.txt -Algorithm SHA256

# Spawn 3 isolated worktrees (each needs its own node_modules from P4's lockfile; assign distinct dev server ports per lane!)
git worktree add -b task/P3-A-001 ../the-third-eye-P3-A p3/frontend
git worktree add -b task/P3-B-001 ../the-third-eye-P3-B p3/frontend
git worktree add -b task/P3-C-001 ../the-third-eye-P3-C p3/frontend
git worktree list
```

---

## 2. Worktree Lane Ownership

| Lane | Worktree Folder | Branch | Dev Port | Editable Paths | Core Responsibility |
|---|---|---|---|---|---|
| **P3-A** | `../the-third-eye-P3-A` | `task/P3-A-001` | `5173` | `frontend/calendar/` + shared shell/`package.json` | Lab shell, area/sub-area selector, monthly & weekly same-sensor calendar, normal season, frozen week labels, S-NPP Nov 2 2026 end marker, raw/evaluated availability |
| **P3-B** | `../the-third-eye-P3-B` | `task/P3-B-001` | `5174` | `frontend/comparison/` | Third Eye comparison panel, deterministic reviewed-template summary, separate sensitivity / applicability / inference / practical-change dimensions, failure reasons |
| **P3-C** | `../the-third-eye-P3-C` | `task/P3-C-001` | `5175` | `frontend/evidence/` | Evidence/export views, FIRMS link + 2-sentence explainer, P0-late "Reported hotspots" view (Sat 20:00--Sun 12:00), landing headline metric + denominator, Quick Mission, keyboard/reduced-motion (`Story` is P2) |

---

## 3. Installed Frontend Skills Strategy (`team-kit/FRONTEND_SKILLS.md`)

All 60 skills are installed user-level (`~/.kiro/skills/` and `~/.agents/skills/`). Activate strictly by priority tier:
- **P0 Core Skills (Start Immediately):** `frontend-design`, `impeccable`, `web-design-guidelines`, `vercel-react-best-practices`, `playwright-cli`, `webapp-testing`.
- **P2 Polish Skills (ONLY after P0 + chosen P1 pass):** `r3f-*`, `threejs-*`, `gsap-*`, `motionstack`, `blender-skills`, `design-motion-principles`, `animate`.

---

## 4. Checkpoints & Optional Cloud Tooling

- **First 30--60 min:** Working Research Lab shell consuming P4's synthetic contract fixtures (visibly labelled `[SYNTHETIC DEV FIXTURE]`). Replace immediately once P2/P4 supply real sample JSON.
- **Saturday 20:00:** Complete static site (no backend) serving versioned JSON ($\le 10\text{ MB}$ compressed target). Landing screen shows area, calendar, 1 finding, 1 limit, plain status chip, and frozen headline metric + denominator (zero internal schema terms!).
- **Saturday 20:00 -- Sunday 12:00 (P0-Late, max 3h):** In-app "Reported hotspots" FIRMS view (raw counts only; clearly separated from grid rates).
- **Sunday 20:00:** Produce one-page judge summary, demo script, and raw screen captures with P5 using exact shipped results.
- **Optional Boxes.dev (`team-kit/BOXES.md`):** Use only for bounded Playwright headless verification on Linux if P4 approves a pilot box; keep local Vite builds working independently.

