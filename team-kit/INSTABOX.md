# Optional InstaBox workspace

Assessed 14 November 2026 from official documentation. Recommended as an optional
Linux verification/workspace resource, not a dependency of THE THIRD EYE science.
No account, installation or cloud machine was created or tested in this review.

## Verified offer and limitations

The current [limits table](https://instabox.sh/docs/account/limits) lists one free
machine, up to 4 vCPU / 8 GiB, a fixed 20 GiB machine disk, five snapshots,
100 GiB monthly egress and three workspace members. The 200 GiB stored-data cap
is NOT a 200 GiB working disk. Check the actual account before allocating work.

The [lifecycle documentation](https://instabox.sh/docs/machines/auto-pause)
describes automatic idle pauses, enforced maximum runs and cooldowns. Some numeric
duration fields were absent in the fetched page; record actual `maxRunMinutes`
and idle settings from the account rather than promising unlimited runtime.
Background jobs do not make these limits disappear. Older unlimited-usage
marketing is not an availability guarantee.

## Best use for this project

P4 can use it for a fresh Linux clone, bounded integration tests or a private
preview. P5 can independently replay a frozen public evidence bundle on a clean
environment. This is a useful OS/dependency check, not additional scientific
observations or automatic independent scientific approval.

Start with one heavy task at a time. Three lightweight editing sessions may fit,
but three builds, browser suites or data jobs need measurement before approval.
Keep separate task worktrees and ports. Do not put all fifteen agents on one box.
The three-member free workspace does not accommodate five humans as members;
use an individually owned optional resource with Git handoffs, not shared logins
or extra accounts created to bypass limits. Local work remains fully supported.

Earth Engine processing stays in Earth Engine. This machine does not grant NASA
permissions, export quota, LLM subscriptions or model credits. Avoid storing a
global raster archive on its small disk. Use bounded frozen bundles, checkpoints
and verified exports back to the team's approved storage. It must not be the
only copy of a result or the sole public judging deployment.

## Optional setup, performed by its human owner

The [official quickstart](https://instabox.sh/docs/quickstart) documents creating
a machine and SSH/exec access. Its bootstrap also installs agent skills. Prefer
the CLI-only installation path described in the [official documentation index](https://instabox.sh/pricing)
if those integrations are unnecessary; review the package/version first. Pin the
verified CLI version in the team's environment record after the smoke test.

```text
npm install -g instabox@<VERIFIED_VERSION>
instabox --help
instabox create --name the-third-eye-check
instabox ssh the-third-eye-check
```

Complete authentication through the supported account flow; never paste tokens
into task prompts. Before creation, confirm the free plan, member access and
current quota. Do not activate paid upgrades or change billing automatically.

Inside the machine, clone the team's repository into `/data/the-third-eye`, check
out the exact agreed commit and install the committed runtime versions/locks.
Preinstalled versions are
not the project lockfile. Record OS, tool versions, free disk/RAM and output.
Then replay a small approved scientific bundle when one exists.

Test interrupted-job recovery and verify that a committed artifact can be
retrieved with the same hash. Copy reports off-machine before ending the session.
Snapshots may contain credentials; keep them private and do not use them to
distribute development environments containing secrets or sealed holdout data.

## Preview and access policy

[Published ports](https://instabox.sh/docs/access/ports) are public by default;
use a private port or SSH forwarding for team previews. Private preview links
contain access tokens and belong outside Git and public reports.

```text
instabox port publish the-third-eye-check 3000 --private
instabox port unpublish the-third-eye-check 3000
```

Only publish the intended application service, never a repository directory,
credential store or holdout files. Check failed/waking/offline states. Maintain
the separately deployed immutable flagship fallback for judges.

## Activation checklist

- Owner/account entitlement, actual lifecycle limits and quota recorded.
- Exact project commit and pinned runtime tested; no unreviewed skill injection.
- One bounded workload completes; interrupted/retried work does not corrupt data.
- Artifact export/hash verification passes; local fallback remains available.
- No sealed evaluation labels in a developer-accessible cloud workspace.

If any check fails, omit the cloud resource. No scientific requirement depends
on it, and no performance or cost benefit has yet been measured for THE THIRD EYE.
