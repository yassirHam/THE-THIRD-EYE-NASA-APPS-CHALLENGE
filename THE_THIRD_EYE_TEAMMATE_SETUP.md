# THE THIRD EYE - package to send every teammate

Send a link to ONE repository and an agreed commit SHA. Do not distribute five
independently edited ZIP copies. The multi-agent coordination dry run is done;
this guide covers setting up each PC for the event.

## What to include

Required, at the same commit:

- `AGENTS.md`
- `THE_THIRD_EYE_FINAL_PLAN_GEOGRAPHIC_ACCESS_UPDATED.txt`
- `THE_THIRD_EYE_EXECUTION_SPEC.md`
- `THE_THIRD_EYE_AI_AGENTS_PLAYBOOK.md`
- This guide and `team-kit/AGENT_START.md`
- `THE_THIRD_EYE_FIVE_PERSON_ASSIGNMENTS.txt`, with actual names assigned
  to P-roles, plus task-specific editable paths and acceptance commands.
- Built during the event: schemas, fixtures, dependency lockfiles, version pins,
  `.env.example` with placeholder names only, small licensed demo artifacts and
  their manifest/checksums.

Do not share passwords, tokens, Earth Engine credentials or sealed test labels.

## Requirements per PC

| Requirement | Ready when |
|---|---|
| Git | Version command works; personal repository access tested |
| Python | Python 3.11+ available |
| Node/package manager | Matches P4's committed version pin and lockfile for the app |
| Agent clients | Installed from official vendor source, individually signed in |
| Agent skills | Frontend skills installed per `team-kit/FRONTEND_SKILLS.md` (P3 at least) |
| Accounts/quotas | Each person can run their assigned sessions; no shared logins |
| Disk/RAM/network | Three workspaces can run without paging/crashing; reduce concurrency if needed |
| NASA access | P2 completes Earth Engine/Earthdata authorization |
| Deployment access | P4 verifies access; no need to give production secrets to everyone |

Install application packages from committed locks during the event; do not
install latest versions independently on five PCs.

## Windows setup: one clone, three worktrees

P4 supplies the agreed SHA. Replace placeholders below.

```powershell
git --version
python --version
node --version
git clone <TEAM_REPOSITORY_URL> the-third-eye-team
Set-Location the-third-eye-team
git fetch origin
git status --short
git rev-parse HEAD
```

Example for P1; other teammates replace P1 with their role. Use unique task branch
names on later tasks. BASE_SHA is the exact agreed commit, not a moving branch.

```powershell
git worktree add -b task/P1-A-001 ../the-third-eye-P1-A BASE_SHA
git worktree add -b task/P1-B-001 ../the-third-eye-P1-B BASE_SHA
git worktree add -b task/P1-C-001 ../the-third-eye-P1-C BASE_SHA
git worktree list
Get-FileHash THE_THIRD_EYE_FINAL_PLAN_GEOGRAPHIC_ACCESS_UPDATED.txt -Algorithm SHA256
```

Use the same shell/OS environment for Git and dependencies. Do not mix Windows
and WSL installs in one workspace. Each worktree needs its own virtual environment
and frontend dependencies. Do not run three dev servers on the same port; P4
assigns ports per task.

Open A in Codex, B in Kiro, C in Antigravity (or three available tool sessions).
Paste the completed `team-kit/AGENT_START.md` into EACH session, explicitly giving
the instruction paths; do not depend on identical automatic discovery across products.

## Daily working loop

1. Human claims task; dependencies/contracts must already be accepted.
2. Start agent in its own worktree using the task prompt.
3. Agent returns bounded diff, commit and actual test output.
4. Human reviews; P4 fetches the authorized branch and integrates serially.
5. Combined tests pass before consumers move to the new base/contract.

P1/P2 sign off science and P5 independently verifies. Nobody lets an agent tune
against sealed holdouts. Optional experiments require an explicit human assignment
under the existing budget. Sessions do not automatically send work to each other.

## Readiness record to return to P4

```text
Name / P-role:
OS / shell:
Git / Python / Node versions:
Client A / B / C versions and successful login (no credentials):
Repository base SHA / plan hash:
Three worktree paths and branches:
Frontend skills installed (P3):
NASA/deployment access if required for role:
Blockers / safe concurrency level:
```

## Optional cloud workspace

`team-kit/INSTABOX.md` covers InstaBox for Linux checks and bounded replay. It is
not required on every laptop, and its free workspace member limit is smaller than
this five-person team. Do not share logins.
