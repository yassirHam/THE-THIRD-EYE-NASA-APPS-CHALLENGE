# THE THIRD EYE: demo script

Owner: P3/P5. Raw screen capture recorded by Sunday 20:00 (local event time).

## Recording rules

- **Length**: the official demo video limit is 30 seconds
  ([challenge capture, Rules](../../challenge/CHALLENGE_CAPTURE.md#4-rules)). The
  script ends at 00:30. The in-app 60-90 second Quick Mission is a different thing.
- **Real data only**: record the deployed static site serving the frozen,
  independently replayed case. Every number on screen must match
  [ONE_PAGE_RESULTS.md](ONE_PAGE_RESULTS.md) and the landing page exactly.
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

## First 20 Seconds Showcase

All five beats happen on the Landing view (route `/`). The plan fixes this order:
area, then the sensor seam, then the headline metric, then one finding, then one limit.

### 00:00-00:04 | Beat 1: Region

- **Screen action**: the Landing view is already loaded with the primary area outlined on the map and its calendar beside it. The cursor rests on the area outline.

> **Narration:** "This is the fire calendar for [PENDING VERIFICATION: final region name], built from NASA satellite records."
>
> **On-screen text:** area name and the calendar's year range, as the app shows them.

### 00:04-00:08 | Beat 2: Seam

- **Screen action**: move the cursor to the labeled point on the calendar where the record switches satellites.

> **Narration:** "Here the record switches from the MODIS satellite to VIIRS. A switch like this can fake a trend."
>
> **On-screen text:** the app's seam label at [PENDING VERIFICATION: registered seam date].

### 00:08-00:12 | Beat 3: Headline Metric

- **Screen action**: move the cursor to the headline result line on the Landing view.

> **Narration:** "We tested fake switches on held-out years. Raw comparisons pointed the wrong way in [PENDING MEASURED RUN] of [PENDING MEASURED RUN] cases."
>
> **On-screen text:** the full headline sentence with its units: [PENDING MEASURED RUN] regions, [PENDING MEASURED RUN] test years, [PENDING MEASURED RUN] blocks reported separately.

### 00:12-00:16 | Beat 4: Finding

- **Screen action**: move the cursor to the plain-English finding and its status label.

> **Narration:** "For this area's peak burning months, the result is: [PENDING MEASURED RUN]."
>
> **On-screen text:** the app's finding sentence and status label: [PENDING MEASURED RUN].

### 00:16-00:20 | Beat 5: Limitation

- **Screen action**: move the cursor to the limit sentence directly under the finding.

> **Narration:** "This measures satellite fire detections per observed area, not individual fires. Other areas are not calibrated."
>
> **On-screen text:** the app's limit sentence, as shown.

## Walkthrough

Each step names a view the deployed site must actually have. Before recording,
P5 opens each route on the deployed site and fills in the "Shipped" line. If a view
is not shipped, cut its step and give its seconds to Research Lab. Never show a mode
that is not finished.

### 00:00-00:20 | Step 1: Landing

- **Route**: `/`
- **Shipped**: [PENDING VERIFICATION]
- **Screen action**: the First 20 Seconds Showcase above, unchanged.

### 00:20-00:23 | Step 2: Story chapters

- **Route**: `/story`
- **Shipped**: [PENDING VERIFICATION]. Story is the lowest delivery tier and is cut first.
- **Screen action**: click "Story", then click through the chapter list: the two satellite views, then the review chapter.

> **Narration:** "Story mode walks through the same case from each satellite's point of view."

### 00:23-00:27 | Step 3: Research Lab

- **Route**: `/lab`
- **Shipped**: [PENDING VERIFICATION]
- **Screen action**: click "Research Lab". The same area and calendar load. Click the finding to open its evidence panel and scroll once to the test results.

> **Narration:** "In the Lab, every finding opens to its evidence, including the cases where it failed."

### 00:27-00:30 | Step 4: Evidence Export

- **Route**: [PENDING VERIFICATION]
- **Shipped**: [PENDING VERIFICATION]
- **Screen action**: click the export button and show the downloaded file name in the browser's download bar.

> **Narration:** "Download the record and replay the result yourself."

## After recording

- Watch the file once at normal speed and confirm it ends at or before 00:30.
- Compare every on-screen number against [ONE_PAGE_RESULTS.md](ONE_PAGE_RESULTS.md).
- Run the incognito playback test in [PORTAL_CHECKLIST.md](PORTAL_CHECKLIST.md).
