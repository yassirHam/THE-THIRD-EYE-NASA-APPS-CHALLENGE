# THE THIRD EYE: portal submission checklist

Owner: P5. Internal freeze: **Sunday 22:00 local event time** (TEAM CHOICE).
Official cutoff: **Sunday November 15, 11:59 PM local time**, minute precision, no
extra seconds ([deadline capture](../../challenge/CHALLENGE_CAPTURE.md#2-deadline-and-cutoff-precision)).
After 22:00, only portal verification and critical corrections are allowed.

Run `python docs/submission/check_submission_readiness.py` before each section sign-off.

## A. Before Sunday 20:00

- [ ] Official challenge page, judging PDF, FAQ and legal page opened in a normal browser; every "Confirmed in browser" cell in [CHALLENGE_CAPTURE.md](../../challenge/CHALLENGE_CAPTURE.md) filled in.
- [ ] Local event timezone and the cutoff as a UTC instant recorded in the capture file.
- [ ] Verbatim challenge statement pasted into the capture file, with retrieval time.
- [ ] Every member registered at the same local event; team has at most six members.
- [ ] Members under 18 identified, and the demo follows the youth media rule.
- [ ] Frozen evaluation values copied into [ONE_PAGE_RESULTS.md](ONE_PAGE_RESULTS.md) from the frozen report, with its artifact ID and SHA256.
- [ ] Raw screen capture recorded from [DEMO_SCRIPT.md](DEMO_SCRIPT.md), ending at or before 00:30.

## B. Sunday 22:00 internal freeze

- [ ] Readiness script passes with zero failures.
- [ ] `[PENDING MEASURED RUN]` markers: none remain in submission text, or each remaining one is disclosed as an unavailable result.
- [ ] Same headline number, denominator and units on landing page, project page, video and one-page results.
- [ ] Release commit SHA and evidence bundle SHA256 recorded here: [PENDING MEASURED RUN]
- [ ] Planned features are not described as implemented; challenge gaps are disclosed on the project page.
- [ ] Team choices are not described as Space Apps or NASA rules anywhere.

## C. Link accessibility

Open every link in a private (incognito) browser window, signed out of all accounts.

| Link | URL | Opens without login | Checked at |
|---|---|---|---|
| Public app | [PENDING TEAM INPUT] | [ ] | [PENDING VERIFICATION] |
| Real-data demo route | [PENDING TEAM INPUT] | [ ] | [PENDING VERIFICATION] |
| Source repository | [PENDING TEAM INPUT] | [ ] | [PENDING VERIFICATION] |
| Evidence bundle download | [PENDING TEAM INPUT] | [ ] | [PENDING VERIFICATION] |
| Full evaluation report | [PENDING TEAM INPUT] | [ ] | [PENDING VERIFICATION] |
| Demo video | [PENDING TEAM INPUT] | [ ] | [PENDING VERIFICATION] |

- [ ] In-app FIRMS link opens the selected area and date, or the app explains the manual step.
- [ ] No link needs a login, a private share or a credential.

## D. Incognito video playback test

- [ ] Video plays from start to end in a private window while signed out.
- [ ] Tested in a second browser and on a phone.
- [ ] Duration shown by the player is at or under 30 seconds.
- [ ] Sharing setting is public or unlisted, not private.
- [ ] Narration is audible, or the app's on-screen text carries the story without sound.

## E. Data citations and DOIs

Open each DOI and confirm it resolves to the product version actually used.

| Product | Version | DOI | Resolves |
|---|---|---|---|
| Aqua MODIS MYD14A1 | 6.1 | `10.5067/MODIS/MYD14A1.061` | [ ] |
| Suomi NPP VIIRS VNP14A1 | 2 | `10.5067/VIIRS/VNP14A1.002` | [ ] |
| NOAA-20 VIIRS VJ114A1 (only if processed) | 2 | `10.5067/VIIRS/VJ114A1.002` | [ ] |
| FIRMS MODIS hotspot points (only if shown in app) | [PENDING VERIFICATION] | [PENDING VERIFICATION] | [ ] |
| FIRMS VIIRS hotspot points (only if shown in app) | [PENDING VERIFICATION] | [PENDING VERIFICATION] | [ ] |

- [ ] Product pages cited: [MYD14A1](https://earthdata.nasa.gov/data/catalog/lpcloud-myd14a1-061), [VNP14A1 in Earth Engine](https://developers.google.com/earth-engine/datasets/catalog/NASA_VIIRS_002_VNP14A1), [VJ114A1](https://earthdata.nasa.gov/data/catalog/lpcloud-vj114a1-002).
- [ ] Suomi NPP data cessation cited with the NOAA/NESDIS notice and the confirmed last VNP14A1 date.

## F. Licenses and disclosures

- [ ] Repository license chosen by P4 and committed: [PENDING TEAM INPUT]
- [ ] NASA data use and citation terms recorded for each product above: [PENDING VERIFICATION]
- [ ] Google Earth Engine terms of service recorded, if exports came from Earth Engine: [PENDING VERIFICATION]
- [ ] Basemap tile provider and its license and attribution shown in the app: [PENDING TEAM INPUT]
- [ ] Third-party software licenses listed from the committed lockfiles (Python and frontend): [PENDING TEAM INPUT]
- [ ] AI-assistance disclosure on the project page: Kiro CLI, Codex and Antigravity were used for engineering; model names per tool: [PENDING TEAM INPUT]. This lane's Kiro session ran on `claude-opus-5.5`; the repository's custom Kiro agent config pins `claude-sonnet-4.6`. The product has no runtime AI.
- [ ] Planning documents written before kickoff are labeled as planning, not event work.

## G. Final submit (before 11:59 PM local)

- [ ] Project page fields filled per the official form at submission time.
- [ ] Demo field holds the video link (30 seconds or less) or slides (7 or fewer).
- [ ] Submitted, not only saved; the confirmation is screenshotted.
- [ ] Submitted project page reopened in a private window to confirm it shows.

## Sign-off

| Check | Name | Local time |
|---|---|---|
| Internal freeze (section B) | [PENDING TEAM INPUT] | [PENDING TEAM INPUT] |
| Links and video (sections C, D) | [PENDING TEAM INPUT] | [PENDING TEAM INPUT] |
| Final submit (section G) | [PENDING TEAM INPUT] | [PENDING TEAM INPUT] |
