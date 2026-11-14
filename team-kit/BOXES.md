# Optional Boxes.dev workspace

Assessed 14 November 2026 using official public documentation. No account,
purchase, installation or remote run was performed. The authenticated app was
not inspected. This is an optional alternative to the local/InstaBox workflow.

## Recommendation for THE THIRD EYE

Start with the trial on the throwaway demo. Consider one Pro seat for the person
actually running sustained remote tasks only after the pilot succeeds and a
human approves the cost. Do not migrate all five people just for the hackathon.

Useful assignments: P4 integration/build checks, P3 bounded browser checks, and
P5 clean replay of released evidence. Use a fresh task branch and checkout per
writer; reviewers inspect the immutable submitted commit. Human owners and P4
retain acceptance and serial integration responsibilities. A cloud machine does
not make review independent if the reviewer merely repeats the author's logic.

## Verified service facts

The [product page](https://boxes.dev/) describes isolated Linux devboxes,
snapshots, remote agent operation while the laptop is disconnected, and native
Codex/Claude Code integrations using the user's own subscription or API access.
Kiro and Antigravity compatibility, requested model availability and reasoning
settings are unverified here. An Opus model in Claude Code is not the same
workflow or entitlement as Opus through Kiro. Do not silently substitute clients.

The [billing guide](https://boxes.dev/help/plans-and-box-hours) lists:

| Plan | Price | Included standard box-hours | Awake devboxes per user |
|---|---|---|---|
| Trial | Free | 20 | 3 |
| Starter | $19/seat/month | 50 | 5 |
| Pro | $99/seat/month | 300 | 12 |

Limits exclude the Template box, but its awake time also consumes usage. A
standard box has 4 vCPU/8 GiB; larger sizes consume hours faster. Paid overage
is $0.40 per box-hour from prepaid credit. Sleeping boxes do not consume active
hours. Seats and allowances are per person; one Pro seat is not five seats.
Verify current account pricing, limits and model costs before buying.

## Team budget examples (our calculations)

- Three standard boxes awake for 48 hours use 144 box-hours, plus template time.
- Six standard boxes awake for 48 hours use 288, leaving little of Pro's 300
  for setup/template use or larger machines.
- Twelve standard boxes awake for 48 hours use 576; Pro's included allowance
  would be exceeded by 276 hours before template time ($110.40 at the listed
  overage rate, in addition to the seat and model costs).
- Five Pro seats cost $495/month before extras. This is not the recommended
  starting purchase.

Use only assigned tasks, monitor usage and sleep idle machines. Set a human-
approved spend ceiling; leave automatic credit purchases off unless separately
approved. Model rate limits still apply even when compute capacity is available.

## P4 pilot and adoption gate

Use generic tooling and the throwaway demo in accordance with the plan's
pre-event rule. Target 30-45 minutes; defer adoption if setup remains unresolved.

1. Confirm the intended client's login, exact model and effort setting work.
2. Prepare a clean template containing only approved repo files and tooling.
   Review uploads: do not migrate the entire home directory, credential stores
   or sealed scientific outcomes. Authorize only required account connections.
3. Create a demo task branch, run one bounded coding task and have a separate
   reviewer inspect its resulting commit. Return SHA, diff and check output.
4. Disconnect the laptop and reconnect; verify the task/result persisted and
   inspect actual box-hour consumption. Do not assume sleeping jobs continue.
5. Verify Linux dependencies and browser rendering. No GPU or Blender/WebGL
   performance benefit is established by the listed CPU/RAM configuration.
6. Retrieve artifacts through the approved Git/storage handoff and confirm the
   local fallback still works. Promote only if this saves effort in practice.

Use Git commits and task records for communication; do not assume agents in
different boxes share memory or current files. Keep one writer per task checkout
and retain the existing three lanes per human. Cloud capacity does not authorize
more agents, automatic merges or unattended changes to scientific definitions.

Earth Engine jobs and quotas remain in Earth Engine. Keep P5's sealed evaluation
outside developer templates and permissions. This service is not the sole copy
of results or the required public submission host. A preview URL may be public;
publish only intended demonstration content. Use the ordinary deployment path
for the final judge site.
