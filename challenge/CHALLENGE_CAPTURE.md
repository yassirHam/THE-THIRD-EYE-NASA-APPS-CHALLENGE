# Official challenge capture: NASA Space Apps 2026

Owner: P5 (Lane C). Written during the event on 2026-11-14.
Workstation retrieval time for every source below: `2026-11-14T14:14Z` (UTC).

Each restriction below is labeled with the plan Section 0 source type:

- **VERIFIED SPACE APPS RULE**: read on an official spaceappschallenge.org page, URL given.
- **LOCAL EVENT RULE**: written guidance from our local organizer.
- **TEAM CHOICE**: a restriction the team adopted voluntarily. A team choice is never
  presented as a Space Apps or NASA rule in the submission or the demo.

## Capture method and its limits

Direct page downloads failed from this workstation. Every HTTPS request (fetch tool,
`Invoke-WebRequest`, `curl`) failed certificate validation with `SEC_E_UNTRUSTED_ROOT`,
which points to a network device intercepting TLS. Certificate checks were not disabled.
The rule text below comes from the search index's copies of the official pages. It is
paraphrased, with short quotes only. A human must open each URL in a normal browser,
confirm the wording, and tick the "Confirmed in browser" column.

| Source | URL | Confirmed in browser |
|---|---|---|
| 2026 event page (dates, submission window) | <https://www.spaceappschallenge.org/2026/> | [PENDING VERIFICATION] |
| Challenge page | <https://www.spaceappschallenge.org/2026/challenges/modis-and-viirs-hot-spots/> | [PENDING VERIFICATION] |
| Project submission guide | <https://www.spaceappschallenge.org/resources/project-submission-guide/> | [PENDING VERIFICATION] |
| Judging and awards guide | <https://www.spaceappschallenge.org/resources/judging-awards-guide/> | [PENDING VERIFICATION] |
| Local judging guidance (PDF) | <https://assets.spaceappschallenge.org/media/documents/WEB_PDF_Instructional_Guidance_for_Judging__-_Local_Judging_WPqgn1r.pdf> | [PENDING VERIFICATION] |
| Participant FAQ | <https://www.spaceappschallenge.org/resources/participant-faqs/> | [PENDING VERIFICATION] |
| Team formation guide | <https://www.spaceappschallenge.org/resources/team-formation-guide/> | [PENDING VERIFICATION] |
| Legal terms | <https://spaceappschallenge.org/legal> | [PENDING VERIFICATION] |

## 1. Challenge statement

- **Title**: Harmonization of MODIS and VIIRS Hot Spots (the title used in the repository
  [README](../README.md) and in the challenge URL slug).
- **Challenge category / subject tags**: [PENDING VERIFICATION]. These were not
  present in any retrieved snippet.
- **Verbatim statement, objectives and resource list**: NOT CAPTURED. [PENDING VERIFICATION]
  The search index returned no snippet of the challenge page body. Paste the full text
  below, with the browser retrieval time, before the Section 4C requirement matrix is frozen.

```text
[PENDING VERIFICATION] Paste the official challenge statement, objectives and resource list here.
```

Until that text is pasted, the requirement terms the team is working against come from
the team plan (Section 4C) and are **unverified against the official wording**: a calendar
based on active-fire hotspots for a user-picked area, normal season, unusual days,
critical weeks, hotspot point data, history length, and continuity after MODIS and S-NPP.
A public repository from another team uses the same "normal season, unusual days,
critical weeks" phrasing ([Kiln Watch](https://github.com/Aalvee-Aarham/kiln-watch)),
which suggests these terms come from the official statement. That is secondary evidence,
not a capture.

## 2. Deadline and cutoff precision

- **VERIFIED SPACE APPS RULE**: project submission opens Saturday November 14 at 9:00 AM
  and closes Sunday November 15 at **11:59 PM local time**
  ([2026 event page](https://www.spaceappschallenge.org/2026/)).
- **VERIFIED SPACE APPS RULE**: for teams registered at the Universal Event, "local time"
  means the local time of the Team Owner's area of residence
  ([submission guide](https://www.spaceappschallenge.org/resources/project-submission-guide/)).
- **Precision**: the official pages state the cutoff to the minute, 11:59 PM. They do not
  state seconds. Treat 11:59 PM as the last safe minute. The older team-specified
  23:59:59 is not the official deadline and gives no extra time.
- **UTC offset**: [PENDING VERIFICATION]. Our local event page and its timezone have not
  been recorded yet. The only measured value is this workstation's clock: Windows zone
  `Morocco Standard Time`, which Windows computes as UTC+00:00 for 2026-11-15 23:59. A
  laptop setting is not evidence of the event's timezone. Record the local event URL and
  its stated timezone here, then compute the UTC instant of the cutoff.

| Field | Value |
|---|---|
| Local event page URL | [PENDING TEAM INPUT] |
| Event timezone as stated by organizer | [PENDING VERIFICATION] |
| UTC offset on 2026-11-15 | [PENDING VERIFICATION] |
| Official cutoff as a UTC instant | [PENDING VERIFICATION] |
| Internal freeze (TEAM CHOICE) | Sunday 22:00 local event time |

- **VERIFIED SPACE APPS RULE**: the submission page can be saved repeatedly before the end
  of the hackathon. Saved changes are visible only to the team until the project is
  submitted for judging ([submission guide](https://www.spaceappschallenge.org/resources/project-submission-guide/)).

## 3. Judging criteria

The local judging guidance PDF lists criteria as questions. Wording below is paraphrased
except where quoted.

| Criterion | What judges ask (paraphrased from the official PDF) | Snippet retrieved |
|---|---|---|
| Impact | [PENDING VERIFICATION] | No |
| Creativity | [PENDING VERIFICATION] | No |
| Validity | Is the solution "scientifically valid"? Will it do what it sets out to do, and can it work in the real world? | Yes |
| Relevance | Does the project respond to its challenge? Is it complete, technically feasible, and usable? | Yes |
| Presentation | How well did the team communicate the challenge, the solution, and why it matters? | Yes |

The five names match the team plan (Section 1), which cites a 2026 local-event page.
Impact and Creativity wording was not in any retrieved snippet; confirm them in the PDF.

## 4. Rules

- **VERIFIED SPACE APPS RULE**: teams may have no more than six members. All teammates,
  including the Team Owner, must be registered for the same Local Event. Local Event
  teams need at least one person to be eligible for global judging
  ([judging and awards guide](https://www.spaceappschallenge.org/resources/judging-awards-guide/)).
- **VERIFIED SPACE APPS RULE**: the demo is either a slide presentation with a 7-slide limit
  (title and intro slides included) or a video with a **30-second limit**
  ([judging and awards guide](https://www.spaceappschallenge.org/resources/judging-awards-guide/)).
  The plan's 60-90 second Quick Mission is an in-app design target, not the submission video.
- **VERIFIED SPACE APPS RULE**: members may be added until the hackathon ends on
  November 15, 2026 at 11:59 PM local time
  ([team formation guide](https://www.spaceappschallenge.org/resources/team-formation-guide/)).
- **VERIFIED SPACE APPS RULE**: a participant who works for a U.S. Federal Government
  support contractor may not reference that fact, and event work may not be charged
  under such a contract ([legal terms](https://spaceappschallenge.org/legal)).
- **Pre-event work**: the legal page has not been read in full for what it says about work
  done before the event. [PENDING VERIFICATION]
- **TEAM CHOICE**: all project code, data extracts, fixtures and artifacts are built
  during November 14-15. This stays a team choice until the legal page confirms it.
- **TEAM CHOICE**: sealed 2020-2021 holdouts under P5, no outcome inspection before
  method freeze, a static judge site, and a Sunday 22:00 internal freeze. These are
  scientific and delivery safeguards, not Space Apps or NASA rules.
- **LOCAL EVENT RULE**: none recorded. [PENDING TEAM INPUT]

## 5. Youth media rules

- **VERIFIED SPACE APPS RULE**: participants under 18 must be registered by a parent or
  legal guardian and accompanied by one at all times during the event
  ([participant FAQ](https://www.spaceappschallenge.org/resources/participant-faqs/),
  [legal terms](https://spaceappschallenge.org/legal)).
- **VERIFIED SPACE APPS RULE**: the FAQ lists, as something under-18 participants must not
  do, using "photo, video, voices, or likenesses of themselves or others under the age of
  18" in the project demonstration or submission
  ([participant FAQ](https://www.spaceappschallenge.org/resources/participant-faqs/)).
- Consequence for this team: the demo is a screen capture of the app. If any member is
  under 18, it has no face, voice or likeness of that member. Narration is recorded by a
  member aged 18 or over, or replaced by on-screen text.
- Any members under 18: [PENDING TEAM INPUT]

## 6. Regional analyst question and published claim

### Primary region

- Region ID: `geo-canonical-primary-angola`, defined in [`data/manifests/canonical_regions.geojson`](../data/manifests/canonical_regions.geojson) (artifact_id `primary-region`, git blob SHA256 `0d6574ad87942d343d124386357337c6d2a12a30003c88efa4e24528b843f1f1` at commit `71a37b13e8557723f3f5a4f20b8c77d7441f5c57`).
- **Boundary caveat**: the geometry is a longitude/latitude rectangle (11.5 E to 24.0 E,
  18.0 S to 4.5 S), not Angola's administrative boundary. By plain geography the
  rectangle also covers parts of neighboring countries, at least the Democratic Republic of the
  Congo. The plan requires a clean administrative boundary. P2 must confirm or replace
  this geometry before any finding is labeled "Angola". Feasibility sign-off for this
  region: [PENDING VERIFICATION]

### Analyst question

Illustrative user, not a recruited partner: an air-quality analyst choosing which past
burning seasons to investigate. NASA Earth Observatory reports that smoke from seasonal
burning in August and September is carried across several southern African countries,
including Angola ([Fire and Smoke in Angola](https://science.nasa.gov/earth/earth-observatory/fire-and-smoke-in-angola-13816/)).

> Which months form the normal burning season in the primary region, and did burning in
> the peak months rise or fall between the Aqua-only years and the VIIRS years, or does
> that answer depend on the satellite change?

THE THIRD EYE's auditable version uses the fire-cell-day rate (detected fire cell-days
per thousand usable land cell-days, 1 km daily grids). It does not count individual
fires, hotspot points or burned area. The registered period pair is set by P1:
[PENDING VERIFICATION]

User consequence of each outcome:

| Outcome | What the analyst does |
|---|---|
| Confirmed: the direction holds across the registered calibration variants | Prioritizes the indicated years for smoke investigation, citing the evidence record |
| Qualified: the direction depends on the calibration variant | Treats those years as unresolved and does not rank them by fire-cell-day rate alone |
| Withheld: evidence missing or outside the evaluated domain | Uses each sensor era only on its own scale and does not compare across the seam |

### Published claim (flagship)

| Field | Value |
|---|---|
| source_id | `nasa-eo-fires-in-angola-18655` |
| Source | NASA Earth Observatory, "Fires in Angola": <https://science.nasa.gov/earth/earth-observatory/fires-in-angola-18655/> |
| Original statement (paraphrased) | In Angola, burning often begins around May, spreads through mid-year, and tapers off in September or October. |
| Original publication date | [PENDING VERIFICATION] (the indexed date reflects the page's site migration, not first publication) |
| Region | Angola (national scale) |
| Original measurement | Satellite imagery with MODIS active-fire detections, described qualitatively |
| source_method_status | unknown: the page does not give counting rules |
| Adjustments used by the source | unknown |
| evidence_relationship | `related_indicator_analysis` |
| reproduction_status | not attempted; a qualitative statement has no number to reproduce |

Corroborating source with the same seasonal window: NOAA NESDIS describes Angola's dry
season, with satellite-visible fires, as running from May to October
([NESDIS](https://www.nesdis.noaa.gov/news/fires-dot-the-landscape-angolas-dry-season)).

Why `related_indicator_analysis`: THE THIRD EYE examines the same regional question
(season timing) with a different named measurement. A matching or differing normal
season in our calendar neither verifies nor refutes the Earth Observatory description.
The analysis label is fixed now, before any audit result exists.

### Source screening log

| Source | Statement (paraphrased) | Decision |
|---|---|---|
| NASA EO "Fires in Angola" | Season begins around May, ends September or October | Selected: names the region and a calendar pattern our calendar measures |
| NOAA NESDIS dry-season article | Angola's dry season runs May to October | Kept as corroboration |
| NASA EO "Fire and Smoke in Angola" | August-September smoke is carried across southern Africa | Kept as user context for the analyst question |
| NASA EO "Seasonal Fires are Burning in Angola" (<https://science.nasa.gov/earth/earth-observatory/seasonal-fires-are-burning-in-angola-145530/>) | On one August 2019 day, VIIRS night-band detections made Angola look like the most fire-active place worldwide | `outside_scope`: a single-day, worldwide ranking that the regional monthly grid cannot assess |
| NASA image article on Angola and DRC agricultural fires (<https://www.nasa.gov/image-article/both-angola-democratic-republic-of-congo-experiencing-high-numbers-of-agricultural-fires/>) | Reports a one-week count of VIIRS fire alerts from Global Forest Watch | `outside_scope` for grid verdicts: a weekly point-alert count; usable only in the separately labeled hotspot view |

The flagship was chosen for analyst relevance before any audit. It is not replaced if
its result turns out stable or undramatic.
