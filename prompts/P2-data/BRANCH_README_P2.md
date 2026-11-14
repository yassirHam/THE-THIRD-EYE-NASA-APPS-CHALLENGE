# P2 — NASA Data, Geography & Source Quality (12:00 AM Branch & Worktree Setup)

**Role Owner:** P2 (NASA Data & Geography Lead)  
**Primary Role Branch:** `p2/data`  
**Mandatory Science Authorities:** `AGENTS.md`, `THE_THIRD_EYE_FINAL_PLAN_GEOGRAPHIC_ACCESS_UPDATED.txt`, `THE_THIRD_EYE_EXECUTION_SPEC.md`, `THE_THIRD_EYE_FIVE_PERSON_ASSIGNMENTS.txt`

---

## 1. 12:00 AM Git Checkout & 3-Worktree Initialization

```powershell
New-Item -ItemType Directory -Force "$HOME\projects" | Out-Null
Set-Location "$HOME\projects"
git clone https://github.com/yassirHam/THE-THIRD-EYE-NASA-APPS-CHALLENGE.git the-third-eye-team
Set-Location the-third-eye-team
git fetch origin

git checkout p2/data
git rev-parse HEAD
Get-FileHash THE_THIRD_EYE_FINAL_PLAN_GEOGRAPHIC_ACCESS_UPDATED.txt -Algorithm SHA256

# Spawn 3 isolated worktrees
git worktree add -b task/P2-A-001 ../the-third-eye-P2-A p2/data
git worktree add -b task/P2-B-001 ../the-third-eye-P2-B p2/data
git worktree add -b task/P2-C-001 ../the-third-eye-P2-C p2/data
git worktree list
```

---

## 2. Worktree Lane Ownership

| Lane | Worktree Folder | Branch | Editable Paths | Core Responsibility |
|---|---|---|---|---|
| **P2-A** | `../the-third-eye-P2-A` | `task/P2-A-001` | `pipeline/masks/`, `pipeline/grid/` | `MODIS/061/MYD14A1` & `NASA/VIIRS/002/VNP14A1` class mapping, aligned UTC daily 1 km grid, `D`/`O` cell-day counts, block reconciliation & observation-opportunity QA |
| **P2-B** | `../the-third-eye-P2-B` | `task/P2-B-001` | `pipeline/acquisition/`, `pipeline/exports/` | Sample & resumable historical block-level exports in priority order, versioned Parquet outputs, availability manifests & SHA256 checksums |
| **P2-C** | `../the-third-eye-P2-C` | `task/P2-C-001` | `data/manifests/` | Source/collection versions, canonical boundaries & sub-area geometry IDs, outage/quality registry (S-NPP cessation Nov 2, 2026), feasibility & FIRMS link/extract (`P0-late`) |

---

## 3. Critical Priority Export Order (Hour 1 Launch)

1. Finalize Primary & Backup candidate regions with P1 under pre-event feasibility rules (no outcome peeking).
2. Submit GEE daily block-level exports split per sensor and year/span in **strict priority order**:
   - **Priority 1:** `2016--2024` both sensors (`MYD14A1` + `VNP14A1`) — required core.
   - **Priority 2:** `Aqua MYD14A1` `2003--2015`.
   - **Priority 3:** `S-NPP VNP14A1` `2012--2015`.
3. **Holdout Isolation:** Route `2020--2021` evaluation partitions directly to **P5-controlled storage** with separate permissions. Development sessions never inspect `2020--2021` outcomes.
4. **Saturday 13:00 Feasibility Gate:** If early spans (`2003--2015`) lag, activate the plan's fallback: ship complete `2016--2024` core + complete earlier years returning before `Saturday 20:00`. Never present partial years as complete.
5. **P0-Late In-App Hotspots (Sat 20:00 -- Sun 12:00, max 3h):** Bounded FIRMS point extract (server-side credentials only; strictly isolated from `D`, `O`, baselines, and factors).

---

## 4. Storage & Cloud Tooling Boundaries

- **Earth Engine stays in Earth Engine:** Compute cloud-cleared daily 1 km block `D` and `O` reductions server-side in GEE; export compact aggregated Parquet tables/CSV manifests, never multi-terabyte raw rasters.
- **InstaBox (`team-kit/INSTABOX.md`):** Use only for bounded Parquet schema & checksum validation if needed. Never upload GEE private keys or sealed 2020--2021 holdouts onto InstaBox or into Git.

