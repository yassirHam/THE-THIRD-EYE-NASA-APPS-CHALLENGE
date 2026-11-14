# THE THIRD EYE - current multi-agent playbook

Updated 14 November 2026. Five humans; every laptop runs the same three CLI tools, each with
one fixed job (Kiro codes, Codex judges, Antigravity runs Git and the relay).
Earlier playbooks are retired; only this file applies.

## Verdict and authority

The calendar-first plan is ready for its feasibility experiment, not yet a
validated scientific result. Its strongest milestone is the held-out sensor-switch
experiment plus an independently replayed evidence package. Stop expanding scope.

Read AGENTS.md, then THE_THIRD_EYE_FINAL_PLAN_GEOGRAPHIC_ACCESS_UPDATED.txt (scientific authority),
THE_THIRD_EYE_EXECUTION_SPEC.md (checkpoints), this playbook and the teammate guide.
P1/P2 resolve scientific conflicts; P4 versions contracts and reissues affected
 tasks. Old final plans, PDFs, project guides and art/stack proposals are historical
context only. They cannot reactivate AI reporting, Fire Witness, IoT or GOES.

## Weekend scope and gates

The scientific plan's WEEKEND BUILD BRIEF is authoritative for P0, P1, P2,
checkpoints and cut order. P0: monthly/weekly same-sensor calendar, normal
season and frozen week labels, primary region plus predeclared raw sub-areas,
FIRMS link and explainer, Stage A, frozen held-out benchmark, static site,
evidence and replay. In-app FIRMS hotspot view is P0-late (Saturday 20:00 to
Sunday 12:00), cut only after all P1/P2. Preserve missing versus zero, summed counts, masks,
applicability, sealed holdouts and honest nulls. P1 starts per owner after their
own P0 work is checked, without using P1/P2 scientific-owner or P5 evaluation
capacity needed for P0; no P1 claim ships without P0 evaluation. P1 includes
daily drill-down, extra evaluated areas, wider raw domain, browser
Parquet, diagnostics and user task. P2 tier follows P0 and chosen P1. All code
and data are event-built (team choice; see plan Section 0 rule sources); each feature keeps its scientific gates.

## Tool roles on every laptop

Roles are fixed, not interchangeable. Each human runs all three tools.

| Tool | Job | Does | Never does |
|---|---|---|---|
| Kiro CLI (`kiro-cli`) | Coder: the only writer of project files | Edits the owner's allowed paths in a task worktree, runs the acceptance commands, commits on the task branch | Push, merge, write verdicts, edit outside allowed paths |
| Codex (`codex`) | Analyst and judge | Reads diffs, test output and incoming verdicts; writes verdicts and fix orders | Edit project files (runs in the read-only sandbox), push |
| Antigravity CLI (`agy`) | Git operator and relay | Fetches, pulls, branches, pushes task branches, commits handoff files, opens PRs, merges where allowed, starts Codex and Kiro runs | Edit project source, change a verdict or fix order, force push |

Editable paths per owner. Each column is a separate task worktree; one Kiro
session writes in a worktree at a time. Codex and agy serve all of an owner's worktrees.

| Owner | Worktree A | Worktree B | Worktree C |
|---|---|---|---|
| P1 science | science/methods/ | science/calendar/ | tests/science/: independent fixtures/review |
| P2 data | pipeline/masks/, pipeline/grid/ | pipeline/acquisition/, pipeline/exports/ | data/manifests/ |
| P3 frontend | frontend/calendar/ | frontend/comparison/ | frontend/evidence/ |
| P4 integration | artifact pipeline/ | contracts/ | static deploy/ and CI |
| P5 independent QA | eval/ | tests/e2e/ | docs/submission/ |

These are proposed boundaries, not an existing application scaffold. P4 maps them
to actual files before issuing tasks. Shared shells, lockfiles and types have ONE
named task owner. Start with one Kiro writer per person until interfaces are frozen;
add a second or third Kiro session only in another worktree with disjoint paths
and human review capacity. Only agy starts Codex and Kiro runs, and only through
the loop below; Codex and Kiro do not start sub-agents. Agents cannot approve science.
P1/P2 approve measurement claims; P5 verifies; P4 integrates serially.

## Automatic review-and-fix loop

Verdicts travel from tester to owner, fixes travel back, and no human steps in
unless a stop rule fires.

Handoff channel: the `handoff` branch on origin. Only agy writes it. Files are
append-only and never edited or deleted:

- `handoff/verdicts/<to-owner>/<task-id>/r<round>-<from>.md`: a verdict
- `handoff/fixed/<owner>/<task-id>/r<round>.md`: "fixed in <SHA>, ready to retest"
- `handoff/escalations/<owner>/<task-id>-r<round>.md`: a human decision is needed

agy pushes with `git pull --rebase` then `git push`, retrying when rejected. File
names are unique, so these rebases do not conflict. Never `--force`.

A verdict states: from, to, task ID, branch, tested SHA, round, PASS or FAIL, and
for each finding an ID, file, the command run, actual versus expected output, and
severity. A fix order (written by the owner's Codex) lists accepted findings,
rejected findings with reasons, the files to change and the acceptance commands.

Example: P5 tests P3's work and finds errors.

1. P5 tests P3's pushed task branch at SHA X. P5's Codex turns the test output
   into a FAIL verdict.
2. P5's agy commits it as `handoff/verdicts/P3/P3-A-004/r1-P5.md` and pushes.
3. P3's agy watcher sees the new file on its next `git fetch` and pulls it.
4. P3's agy runs P3's Codex on the verdict and the task diff. Codex checks every
   finding against the plan, the contract and the code, and writes the fix order.
5. If no stop rule fires, P3's agy runs P3's Kiro headless in that task worktree
   with the fix order. Kiro fixes, runs the acceptance commands and commits.
6. P3's Codex checks Kiro's commit against the fix order. On PASS, P3's agy pushes
   the task branch and writes `handoff/fixed/P3/P3-A-004/r1.md` for P5. On FAIL,
   the fix order goes back to Kiro; that counts as a round.
7. P5's agy sees the fixed note, and P5 retests the new SHA. Repeat until PASS.
8. On a P5 PASS for that exact SHA, P4's agy merges it (merge rules below).

The same loop runs between any two owners, for example P4's integration checks
against P2's exports, or P1's fixture review against P1 or P2 code.

Stop rules. agy writes an escalation file, stops that task and leaves it for the
human owner when:

- three rounds on the same task end without PASS;
- Codex rejects a finding, so the tester and the owner's judge disagree;
- the fix would touch paths outside the allowed list, a shared file or lockfile
  owned by someone else, a contract, a schema, or any scientific definition,
  threshold, mask, policy or measurement claim;
- the verdict concerns a held-out or sealed evaluation result. These are never
  routed automatically: an automatic fix aimed at a holdout failure is tuning on
  the holdout;
- acceptance commands cannot run, a rebase or merge conflicts, or a CLI exits
  non-zero or times out;
- a credential, sealed data or out-of-domain data appears in a diff or verdict.

Merge rules. Only P4's agy merges, one branch at a time, into `integration`. A
task branch merges at a SHA that has a P5 PASS verdict for that exact SHA and an
owner's Codex PASS, and only if the combined checks pass after the merge. If they
fail, agy reverts the merge commit and escalates to P4. Promotion from
`integration` to `main` (the public, judged site) stays a P4 human decision. Other
laptops' agy only push their own task branches and handoff files.

Commands (help output checked 14 November 2026 on kiro-cli 3.2.0, codex-cli 0.167.0
and agy 1.5.3; recheck on each laptop in the dry run):

```powershell
# Codex judges: read-only sandbox, verdict on stdin, fix order written to a file
Get-Content $verdict | codex exec --sandbox read-only -C $worktree -o $fixOrder "Judge each finding in this verdict against the plan, contract and code. Write a fix order."

# Kiro fixes: headless, in the task worktree, fix order on stdin
Set-Location $worktree
Get-Content $fixOrder | kiro-cli chat --v3 --no-interactive --agent the-third-eye-coder

# agy runs one Git or routing step and returns JSON with a status field
agy -p "<step>" --output-format json --print-timeout 15m
```

- Kiro headless needs `KIRO_API_KEY` in the environment (kiro.dev/docs/cli/headless).
  It cannot ask for tool approval, so the `the-third-eye-coder` agent config must
  allow the tools it needs. Use `--trust-all-tools` only inside an isolated task worktree.
- Codex `exec` is read-only by default; keep it that way for judging.
- agy print mode cannot prompt; it needs permission rules or
  `--dangerously-skip-permissions`, and the latter only in that laptop's own clones.
- Watching costs no model calls: the watcher is a plain `git fetch` loop every
  two minutes, and it calls agy only when a new handoff file is addressed to its owner.
  P4 writes this watcher before the dry run. Each laptop's watcher keeps its list
  of handled files outside the repository.
- No keys in Git, handoff files or logs.

Models per role. No tool changes its own model mid-run, and none switches models
by phase (details and sources in plan_f.txt at the repository root). Pin a model
per call instead: `--model` for kiro-cli and agy, `-m` for codex exec, or a `model`
field in the Kiro agent config. If a pinned Kiro model is unavailable, the first
prompt can fail instead of falling back; the watcher treats that as a CLI failure.

## Task protocol

Each task uses team-kit/AGENT_START.md with a task ID, human owner, worktree,
branch, base SHA, plan hash, contract version, exact editable paths, dependencies,
input artifacts, time budget and acceptance commands. Never assign all sessions
"build the project." Agents start only through the loop above.

Lifecycle: queued -> assigned -> working -> ready for review -> in fix loop ->
merged to integration -> accepted; blocked and escalated are explicit. Human
owners accept work. P4 maintains the board; handoff files carry verdicts, not
concurrent edits to a shared status file.

One writer per worktree: Kiro. Kiro commits its own changes and reports actual test
commands/results. agy pushes task branches; P4's agy merges serially into
`integration` under the merge rules and reruns combined checks. Never force push;
nothing reaches `main` without P4.
Across laptops use the shared Git remote and the `handoff` branch, not assumed shared chat
memory. Git worktrees isolate local files; they do not synchronize computers.

P5 keeps sealed evaluation data OUTSIDE development workspaces and permissions.
A prompt saying "do not read holdouts" is not access control. Share immutable
permitted artifacts by ID/hash; never commit credentials or sealed labels.
Verdicts on the shared remote contain only public fixtures and test output.
The loop needs only Git, the three CLIs and the watcher; no hooks, MCP servers
or hosted orchestration service.

## Required checks

During the event, freeze contracts and P0 fixtures before parallel consumers: missing versus zero, mask
classes, policy compatibility, scalar invariance, equality-threshold edge cases,
unvalidated-region behavior; test geographic composition if shipped. P5 checks fixtures from
the written definitions, not copied implementation outputs. UI tests preserve
artifact IDs and honest labels. Distinguish bundle replay from NASA regeneration.

## Schedule

| Checkpoint | Evidence |
|---|---|
| First hour | P2 launches primary and backup region block exports for both sensors |
| Saturday 13:00 | Feasibility, sample and registered shorter-span fallback if needed |
| Saturday 20:00 | Monthly/weekly calendar, raw area selector, FIRMS link, Stage A and static site |
| Saturday 23:00 | Frozen sensor-switch evaluation including failures |
| Sunday 12:00 | Public core and independent flagship replay |
| Sunday 20:00 | One-page results, demo script and raw screen capture |
| Sunday 22:00 | Final freeze/internal submission target |
| Sunday 11:59 PM local | Stated official cutoff; verify portal timezone/precision |

Optional stop gates are not a general 17:00/19:00 work cutoff. Deadlines never
justify manufactured findings or weakened gates.

## Readiness

The team completed the multi-agent coordination dry run before the event; its
demo files are retired. That run predates the automatic loop, so before the event
each laptop needs: all three CLIs signed in (plus `KIRO_API_KEY` for Kiro headless),
its task worktrees working (teammate guide), the watcher running, and one full
round trip on a throwaway task: verdict -> Codex fix order -> Kiro fix -> fixed
note -> retest -> PASS, plus one forced stop rule that produces an escalation.

Official Codex isolation reference:
https://learn.chatgpt.com/docs/environments/git-worktrees
Headless references: https://kiro.dev/docs/cli/headless/ and
https://learn.chatgpt.com/docs/non-interactive-mode. Re-check each CLI's
`--help` after updates instead of assuming flags.

## Geographic access and automatic summaries

Follow the current plan's two tiers: available raw observations versus individually
evaluated comparisons. P2 owns geometry identity and summed counts; P1 owns
region/policy applicability; P3/P4 cannot reuse parent factors on a clipped map.
Preserve failed checks separately from missing/out-of-domain evidence. Summaries
use frozen selection rules and reviewed templates, not a runtime LLM. Record all
eligible outcomes and tested denominators. Recency and wider raw coverage remain
conditional; the presence of a world basemap never implies worldwide data.

## Optional cloud computer

Boxes.dev is an optional alternative for isolated agent workspaces and unattended
jobs. Read [team-kit/BOXES.md](team-kit/BOXES.md). Trial it with the existing
throwaway demo before considering Pro; no purchase or migration is authorized
by this recommendation. P4 owns the pilot. It does not add agent lanes, model
quota, scientific evidence or permission to access P5's sealed holdouts.

InstaBox may help P4 run bounded Linux checks or P5 replay approved public evidence.
Read team-kit/INSTABOX.md first: free capacity, account membership and enforced
pauses mean it is not a fifteen-agent host or guaranteed public demo service.
Use the same owned-worktree protocol. Start one heavy job at a time, retain local
fallback, and export verified results. No account, paid upgrade or third-party
skill installation is automatic. No cloud credentials or sealed holdouts in Git.
Documentation verified; no actual InstaBox deployment has been tested.

Current detailed role allocation and short task timeboxes: THE_THIRD_EYE_FIVE_PERSON_ASSIGNMENTS.txt.
This sheet refines the lane map without changing the scientific gates.

## Frontend skills

The installed frontend skill set (60 skills for Kiro, Codex and Antigravity), with
source commits, licenses and exclusions, is in team-kit/FRONTEND_SKILLS.md. P3
starts with frontend-design, impeccable, web-design-guidelines,
vercel-react-best-practices and playwright-cli. 3D, GSAP, Motion and Blender
skills are for P2 visual work only.
