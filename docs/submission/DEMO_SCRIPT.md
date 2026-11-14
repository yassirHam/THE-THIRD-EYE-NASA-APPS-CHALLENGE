# THE THIRD EYE: demo script

Owner: P3/P5. Raw screen capture recorded by Sunday 20:00 (local event time).

UI source: P3 `frontend/src/main.tsx`, `pages/Landing.tsx`, `pages/Lab.tsx` and
`lab/Comparison.tsx` at `origin/p3/frontend` commit `a755829`. Element names and quoted
text below come from that commit. Re-check them if P3 changes these files.

## Recording rules

- **Length**: the official demo video limit is 30 seconds
  ([challenge capture, Rules](../../challenge/CHALLENGE_CAPTURE.md#4-rules)). The
  script ends at 00:30. The in-app 60-90 second Quick Mission is a different thing.
- **Real data only**: record the deployed static site serving the frozen,
  independently replayed case. Every number on screen must match
  [ONE_PAGE_RESULTS.md](ONE_PAGE_RESULTS.md) and the Research Lab view exactly.
- **Show what the app does**: the video contains clicks, scrolls and cuts between
  views. Nothing is added in editing except cuts. "On-screen text" below means text
  the app itself displays.
- **Plain language**: narration and on-screen text use no internal identifiers, no
  factor values, no method names and no tutorial.
- **Youth media rule**: if any member is under 18, no face, voice or likeness of
  that member appears. Narration then comes from a member aged 18 or over, or is
  left out and the app's own text carries the story.
- **Frozen artifact, not live analysis**: the narration never says the app is
  computing a result live.
- **Values not yet measured** are shown as [PENDING MEASURED RUN]. Replace them with
  the frozen evaluation values before recording; do not record with markers visible.
- **Recording is blocked until real data loads**: at commit `a755829` the Lab's data
  provider is empty (`labView = { areas: [] }`), so the Area dropdown reads "Awaiting
  area data" and every panel reads "Unavailable". Record only after P3 connects the
  P4-approved artifact adapter: [PENDING VERIFICATION: Lab shows the frozen case].

## First 20 Seconds Showcase

The opening screen is the flagship area view in the Research Lab, opened directly at
`/?mode=lab` (same page as `/lab`). The plain `/` route is the mode gate (Story /
Lab / Mission selector) and is not shown in the opening. All five beats are on this
one page, in the order the plan fixes: area, sensor seam, headline metric, finding,
limit.

Page layout at `a755829`: the left column is the "Fire calendar" section with the
sensor note at its foot. The right column (the "Finding and limitations" aside) holds,
top to bottom, the "Finding", "Limit", "Normal season" and "Sensor-switch test" cards.
The cursor therefore moves down to the Sensor-switch test card in beat 3 and back up
to the Finding card in beat 4.

### 00:00-00:04 | Beat 1: Region

- **Screen action**: the Lab is loaded at `/?mode=lab` with the flagship area chosen. The cursor rests on the Area dropdown next to the "Fire calendar" heading (`h3#calendar-title`), with the monthly calendar below it.

> **Narration:** "This is the fire calendar for [PENDING VERIFICATION: final region name], built from NASA satellite records."
>
> **On-screen text:** the "Fire calendar" heading and the area name shown in the Area dropdown.

### 00:04-00:08 | Beat 2: Seam

- **Screen action**: change the Satellite dropdown from "MODIS / Aqua" to "VIIRS / Suomi NPP", then move the cursor to the note under the calendar. The calendar at `a755829` has no seam label, so the seam is shown by this switch: [PENDING VERIFICATION: P3 adds a labeled seam on the calendar, or the team accepts this switch as the seam beat].

> **Narration:** "The record comes from two satellites, one at a time. Switching between them can fake a trend."
>
> **On-screen text:** "Each calendar uses one sensor at a time. Suomi NPP data ended 2 November 2026; NOAA-20 is a separate platform."

### 00:08-00:12 | Beat 3: Headline Metric

- **Screen action**: move the cursor down the right column to the "Sensor-switch test" card and rest it on the bold result line and the statement under it.

> **Narration:** "We tested fake switches on held-out years. Raw comparisons pointed the wrong way in [PENDING MEASURED RUN] of [PENDING MEASURED RUN] cases."
>
> **On-screen text:** the card's result line, then its denominator statement: [PENDING MEASURED RUN] regions, [PENDING MEASURED RUN] test years, [PENDING MEASURED RUN] blocks reported separately. If the evaluation is not frozen, the card reads "Unavailable" and "Result and number of evaluated cases are not available yet." Record that text instead.

### 00:12-00:16 | Beat 4: Finding

- **Screen action**: move the cursor back up the right column to the "Finding" card at its top and rest it on the finding heading.

> **Narration:** "For this area's peak burning months, the result is: [PENDING MEASURED RUN]."
>
> **On-screen text:** the Finding card's heading: [PENDING MEASURED RUN]. If no evaluated finding exists, it reads "No finding available yet." The Finding card at `a755829` shows no status label; the plain-language status badge is in the "Compare perspectives" section further down: [PENDING VERIFICATION: P3 places the status label in the Finding card, or this beat shows the finding sentence only].

### 00:16-00:20 | Beat 5: Limitation

- **Screen action**: move the cursor to the "Limit" card directly beneath the Finding card.

> **Narration:** "This measures satellite fire detections per observed area, not individual fires."
>
> **On-screen text:** the Limit card's sentence for the flagship area. With no area-specific limit, the app shows "Satellite observations do not count individual fires. Missing observations and failed checks must remain visible."

## Walkthrough

Each step names a view the deployed site must actually have. Before recording,
P5 opens each route on the deployed site and fills in the "Shipped" line. If a view
is not shipped, cut its step and give its seconds to Research Lab. Never show a mode
that is not finished. At `a755829` the mode gate labels the Research Lab and Quick
Mission cards "Being built".

### 00:00-00:20 | Step 1: Landing

- **Route**: `/?mode=lab` (equivalent: `/lab`). This opens the Research Lab flagship area view, not the `/` mode gate.
- **Shipped**: [PENDING VERIFICATION]
- **Screen action**: the First 20 Seconds Showcase above, unchanged.

### 00:20-00:23 | Step 2: Story chapters

- **Route**: `/story/seam`, the "Find the seam" chapter. Story Mode is also reachable from the mode gate at `/?mode=story`.
- **Shipped**: [PENDING VERIFICATION]. Story is the lowest delivery tier and is cut first.
- **Screen action**: cut to the "Find the seam" chapter and hold on its first screen. Other chapters at `a755829`: "Open the third eye", "Compare the two eyes", "Count only what was seen".

> **Narration:** "Story mode walks through the same switch from each satellite's point of view."

### 00:23-00:27 | Step 3: Research Lab

- **Route**: `/lab`
- **Shipped**: [PENDING VERIFICATION]
- **Screen action**: cut back to the Lab and scroll once to the "Compare perspectives" section. Rest the cursor on its status badge, then on "Inspect comparison evidence".

> **Narration:** "In the Lab, every finding opens to its evidence, including the checks it failed."
>
> **On-screen text:** the full status badge for the flagship case: [PENDING VERIFICATION: P3 badge shows the complete plain-language status, including the two-part labels].

### 00:27-00:30 | Step 4: Evidence Export

- **Route**: the "Open area artifact" link in the "Source and evidence" section: [PENDING VERIFICATION]
- **Shipped**: [PENDING VERIFICATION]
- **Screen action**: scroll to "Source and evidence", click "Open area artifact" and show the downloaded file name in the browser's download bar.

> **Narration:** "Download the record and replay the result yourself."

## After recording

- Watch the file once at normal speed and confirm it ends at or before 00:30.
- Compare every on-screen number against [ONE_PAGE_RESULTS.md](ONE_PAGE_RESULTS.md).
- Run the incognito playback test in [PORTAL_CHECKLIST.md](PORTAL_CHECKLIST.md).
