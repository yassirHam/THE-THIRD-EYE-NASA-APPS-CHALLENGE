# THE THIRD EYE: Frontend Design System and Build Rules

This file is binding for every coding agent (Kiro, Codex, Antigravity) that builds or extends the frontend.
The existing Landing, Intro and Story screens are the reference. New screens (Research Lab, Quick Mission,
Evidence, Comparison, Calendar) must look like they were built by the same hand, not as a separate dashboard.

Read before editing:
- `../THE_THIRD_EYE_FRONTEND_CONTRACT.md` (scientific wording and parity: this wins over style)
- `src/styles/global.css` (tokens and shared primitives)
- `src/components/Hud.tsx`, `src/art/Eye.tsx`, `src/components/Keep.tsx`
- `unslop_the_design.txt` (20 anti-slop principles, all mandatory)

---

## 1. Identity in one paragraph

Editorial science fiction with a game interface feel (reference: Citizen Sleeper 2, SIGNALIS, Control, Outer Wilds,
NASA Worldview for real-data controls). Near-black void and thin ivory rules. Warm amber light. Asymmetric layouts.
Dense information, carefully ordered. Ancient observatory, satellites, fire and parallax: two sensor "eyes" (MODIS,
VIIRS) and a vertical "third eye" that reviews both. **It is NOT** a generic NASA dashboard, an AI startup landing page,
a glowing orb, glassmorphism or a rounded-card grid.

---

## 2. Color tokens (use variables only, never raw hex in components)

| Token | Value | Meaning / use |
|---|---|---|
| `--void` | `#080b0d` | Page background |
| `--void-2` | `#0e1316` | Raised surface (panels) |
| `--void-3` | `#151b1f` | Second raised level, input wells |
| `--ivory` | `#e5d9bc` | Primary text, frames, **the third eye** (combined review) |
| `--ivory-dim` | `rgba(229,217,188,.74)` | Secondary text, meta labels |
| `--ivory-faint` | `rgba(229,217,188,.26)` | Quiet borders, kbd frames, disabled |
| `--rule` | `rgba(229,217,188,.62)` | 1px HUD rules |
| `--amber` | `#e5a43b` | **MODIS** (coarse eye), accent, focus ring, hints, selection |
| `--oxide` | `#9b5240` | MODIS secondary, warm atmospheric gradients, failure-tinted warnings |
| `--teal` | `#729c9e` | **VIIRS** (fine eye), cool secondary |

Semantic rules that must never be broken:
- MODIS is always amber. VIIRS is always teal. Combined/third-eye is ivory. No swapping, no new sensor colors.
- Amber is the single accent. Do not introduce blue, purple, green or neon.
- Status states (sensitivity / applicability / inference / practical change) use **shape + text label**, not color alone.
  Use ivory frame + text; amber for attention; oxide for failed; faint ivory for missing / not established.
  Missing data is never drawn as zero and never shares the "no fire" style.
- Background atmosphere = large, very low-opacity radial gradients of oxide (warm, low-left) and teal (cool, right)
  over `--void` (see `.hud` and `.gate::before`). Opacity 0.05–0.16. No other gradients.

---

## 3. Typography

| Token | Family | Use |
|---|---|---|
| `--ui` | Chakra Petch 400/500/600/700 | Default UI: labels, chips, nav, HUD, titles in uppercase |
| `--display` | Cormorant Garamond 500/600 | Big headlines, hero, chapter heads |
| `--prose` | Cormorant Garamond 500 | Narrative and explanatory body, objective hints |
| `--sans` | IBM Plex Sans 400/500 | Compact plain reading text (cards, dense panels, tables) |

Fonts load through `@fontsource` imports in `src/main.tsx`. Do not add Google Fonts links or new families.

Rules:
- UI labels: uppercase, `letter-spacing: 0.06em`–`0.3em` (wider for smaller text), size 11–13px.
- Display headlines: weight 500, tight `line-height` 0.82–0.98, negative tracking `-0.015em` to `-0.02em`,
  `text-wrap: balance`, sizes via `clamp()` (e.g. `clamp(38px, 5vw, 86px)`).
- Body reading text: 17px, `line-height: 1.6`, `max-width: 46ch`, ivory at ~0.78 opacity.
- Numbers in tables, counters, rates, calendars: `font-variant-numeric: tabular-nums`.
- No decorative italics. No monospace except code, IDs, hashes and SHA values.
- Proper names (`THE THIRD EYE`, `Suomi NPP`) go through `<Name>` / `<Keep>` so machine translation cannot mangle them.
  Split/animated text uses `<Animated>` so translators and screen readers get the whole sentence.

---

## 4. Layout and frame

- Every non-landing screen is wrapped in `<Hud>`: four triangular corner wedges, top and bottom 1px rules, an
  objective box (square play-glyph tab + uppercase title + amber prose hint) and the stage between.
- Spacing scale is fluid: `--frame-inset: clamp(14px, 2.2vw, 34px)`; use `vh`/`vw` + `clamp()` for large spacing.
- Group with whitespace, not boxes. Borders are 1px (1.5px for the objective tab). **No border-radius on panels,
  buttons, chips or cards** (square corners are part of the identity). The only existing exceptions are true circles
  (`border-radius: 50%`: the cursor dot and small story markers). If a nested radius is ever required,
  inner = outer − padding.
- Asymmetric compositions: illustration/scene on one side, narration and choices on the other. Alternate
  `chapter--left/right/center`. Do not reuse the same slide template for every view.
- Body has `overflow: hidden`; scrolling screens own their scroll container (Lenis on the landing).
- Mobile: full-width scene, normal heading (no vertical-title gutter). Verify at **360px and 390px**. Captions and
  readouts sit in separate rows; overlays must never cover the data they explain.

---

## 5. Components and primitives (reuse, do not reinvent)

| Primitive | Where | Rule |
|---|---|---|
| `<Hud>` | `components/Hud.tsx` | Frame for every screen |
| `.objective` | `global.css` | One per screen: what the user is doing + one-line hint |
| `.chip` | `global.css` | The only button style. 1px ivory frame, uppercase 13px. Hover/pressed = inverted (ivory bg, void text). `.chip--quiet` for secondary; still framed, never bare text |
| `kbd` | `global.css` | Keyboard hints next to choices (1, 2, 3...) |
| `<Eye tone="modis|viirs|third">` | `art/Eye.tsx` | Line-art SVG eye. Iris pixel grid: coarse 4 (MODIS), fine 9 (VIIRS), 6 (third). Third eye is vertical. Every eye blinks on click (`blink()` from `lib/pointer.ts`) |
| `<Pips>` | `components/Pips.tsx` | Numbered chapter markers |
| `.sw--modis / .sw--viirs` | `landing.css` | 22×2px color swatches inside meta lines |
| `.illustration-note` | `global.css` | 12px label that MUST sit beside any illustrative or synthetic data |
| `<Cursor>` | `components/Cursor.tsx` | Custom cursor; set `data-cursor="Verb"` on interactive elements (Choose, Answer, Blink, Return) |
| `<Loader>` | `components/Loader.tsx` | Real progress for heavy assets; never a fake spinner |
| `playSfx()` | `lib/sfx.ts` | Mode change / skip / wrong answer cues only. Audio must be optional and never autoplay with sound before a user gesture |

New data screens add components in their own lane folder (`frontend/calendar/`, `frontend/comparison/`,
`frontend/evidence/` per branch README) and import shared primitives from `src/`. Do not fork global styles.

---

## 6. Motion

Libraries: GSAP 3 (+ `@gsap/react` `useGSAP`, `ScrollTrigger`, `SplitText`) and Lenis for smooth scroll.

- Signature ease: CSS `--ease-out: cubic-bezier(0.22, 1, 0.36, 1)`; GSAP `expo.out` for entrances,
  `power3.in` for exits before navigation.
- Hover/press transitions 160ms. Underline reveals 400ms (scaleX from right, exit to left).
- Headline entrances: `SplitText` into chars (hero) or masked lines (chapters), staggered, `toggleActions:
  'play reverse play reverse'`.
- Scroll: Lenis `lerp: 0.085`, driven from `gsap.ticker`; kill ScrollTriggers and destroy Lenis on unmount.
- Motion must carry meaning (state change, transition, confirmation). No idle floating blobs, no endless pulses
  except the single scroll cue.
- **Reduced motion is mandatory**: check `prefersReducedMotion()` (`lib/random.ts`) before any GSAP timeline, skip
  Lenis, and jump straight to the end state or navigate immediately. `global.css` already neutralises CSS animation.

---

## 7. 3D (React Three Fiber)

Stack: `three`, `@react-three/fiber`, `@react-three/drei`, `@react-three/postprocessing`.

- Canvas: `dpr={[1, 1.75]}`, `antialias: false`, `powerPreference: 'high-performance'`, ACES tone mapping,
  background and fog = `#050708`. Use `frameloop="never"` when the scene is hidden or paused.
- Post-processing in `three/Effects.tsx`: Bloom `luminanceThreshold 0.78`, `radius 0.6`, Vignette, light Noise
  (~0.07 overlay). Keep bloom restrained; silhouettes must read **without** bloom.
- Lighting: warm key `#ffcf8f` from upper-left, teal rim `#7fb6b8` from lower-right, low ambient (0.08).
- Fires are recognisable ember clusters on real terrain relief. Sensor cells are thin, translucent projected
  footprints, never opaque blocks. Never imply pixel size alone decides detection.
- Authored geometry over particle spam. Do not add floating rings or orbs to fill space.
- Heavy scenes are lazy-loaded; page chunks are split in `routes.ts`; vendor chunks split in `vite.config.ts`.
- Textures ship as `.webp` in `public/tex/`; source originals stay in `source-textures/`.

---

## 8. Copy and scientific honesty (from the frontend contract)

- Plain, specific language. No "AI-powered", "next-gen", "revolutionary", emojis or filler badges.
- Never call a value a count of real fires: it is fire-cell-days per usable land-cell-day.
- Missing or obscured is shown as missing, not zero. Failed applicability is shown separately from missing evidence
  and from out-of-domain.
- Grid calibration factors and thresholds are never applied to FIRMS point hotspots. FIRMS "Reported hotspots"
  is a separate view with raw counts and its own label.
- Every illustration or synthetic fixture is labelled on screen (`Illustration`, `Illustration: made-up numbers`,
  `[SYNTHETIC DEV FIXTURE]`). Real imagery carries provenance (e.g. "VIIRS true colour, NASA GIBS, date").
- Unbuilt features show an honest placeholder (see `pages/Pending.tsx`), never a fake chart.
- No internal schema terms in the judge-facing UI (`a_H`, `a_C`, enum names). Use the contract's plain wording.
- Mark the S-NPP end (2 Nov 2026) on any VIIRS timeline.

---

## 9. Mandatory Data-State & Routing Contract Specifications

Every coding agent working on `frontend/` must adhere to these structural data presentation rules from `PROMPT_KIRO_P3.md`:

1. **First Screen & Video Presentation Layout:**
   - The initial landing / Research Lab viewport must explicitly display:
     * Area selector
     * Calendar view
     * Exactly One Finding statement
     * Exactly One Limitation statement
     * Plain status chip + Frozen Headline Metric with its explicit denominator (e.g., `N_eval` count of units)
   - Zero internal schema names (`a_H`, `a_C`, `O`, `D`, `raw_only`) on this screen.

2. **Predeclared Sub-Area Badge:**
   - Any sub-area rendered without its own independent calibration model must carry the exact plain badge:
     `[Raw observations only]`

3. **Four Explicit Applicability Status Labels:**
   - Applicability is represented across four distinct plain-language states. Never collapse them into a single generic `UNRESOLVED` badge:
     * `Applicable` (ivory frame/text)
     * `Failed Applicability` (oxide frame/text)
     * `Missing Required Support` (faint ivory / dimmed frame)
     * `Out of Domain` (faint ivory / dashed frame)

4. **Direct Route Bypass:**
   - Direct URLs `/?mode=lab` and `/lab` must immediately open the functional Research Lab shell, bypassing the Story prologue and 3D intro animation.

5. **Static / Offline Fallback Banner:**
   - When running from frozen static JSON artifacts without a backend or external network, the UI must render an explicit top/status banner:
     `[Static offline bundle — verified frozen release]`

6. **FIRMS Mandatory Two-Sentence Explainer:**
   - Any external NASA FIRMS link or FIRMS point-overlay toggle must be accompanied verbatim by this statement:
     > *"1-km grids come from the same active-fire detection algorithms as FIRMS points and add a usable-observation denominator; point hotspots never enter D, O, baselines, calibration factors, or verdicts."*

7. **Regional Cache & State Isolation:**
   - State and cached calculations must be keyed strictly by unique `geometry_id`.
   - Changing the selected region must wipe/reset all calibration factors, cached comparisons, and baseline curves. Never reuse one region's factors or baseline for another.

8. **Five Registered Edge-Case Fixture Layouts (Lane P3-B):**
   - The Third Eye comparison panel must explicitly implement dedicated, non-broken visual layouts for all 5 contract edge cases:
     * `stable-but-failed-applicability`: displays stable comparison ratio alongside prominent failure reason banner.
     * `missing-required-evidence`: displays unavailable metric with explicit missing support indicator (`missing != 0`).
     * `raw-only`: shows raw observation series with disabled calibration comparison and `Raw observations only` chip.
     * `unavailable`: rendered when baseline or observations are absent, displaying neutral placeholder note.
     * `within-margin opposite-sign`: displays qualified finding note indicating the apparent trend is within uncertainty margin $\tau$.

---

## 10. Accessibility

- Every interactive element is a real `<button>` or `<a>`/`<Link>`, keyboard reachable, with `:focus-visible`
  amber 2px outline (global).
- Number keys select listed choices (pattern in `Landing.tsx` and the Story answers); show them with `<kbd>`.
- Live narration uses `aria-live="polite"`. Decorative SVG/3D is `aria-hidden`. Meaningful images have labels.
- Contrast: secondary text never below `--ivory-dim` on `--void`. Text over 3D gets the dark text-shadow stack
  used by `.chapter__body`. Measure contrast; do not assume.
- `document.title` is set per page as `<Page> - THE THIRD EYE`.

---

## 11. Performance budget

- Judge site is static with no backend. Total deploy target ≤ 10 MB compressed.
- Audio: compressed `.mp3` in `public/audio/`; `.wav` sources stay in `source-audio/` (not shipped).
- Landing must render the gate before prefetching other routes (`prefetchRoutes()`).
- No new heavy dependency without P3 human approval. Lockfile and `package.json` are edited only in lane P3-A.

---

## 12. Forbidden

- Rounded cards, pill buttons, glassmorphism, drop-shadow stacks, purple/blue gradients, glowing orbs.
- Tailwind, CSS-in-JS libraries, UI kits (MUI, Chakra, shadcn), icon packs that clash with the line-art style.
- New colours, new fonts, monospace body text, decorative italics.
- Opaque sensor blocks, giant vertical titles that overpower the scene, overlays covering the artifact.
- Fake data, fake loading, fake "verified" badges.

---

## 13. Definition of done for any frontend task

1. `npm run build` and `npm run lint` pass; paste the actual output.
2. Fresh desktop (1440px) and mobile (390px, 360px) captures of every changed view, uniquely named.
3. Keyboard-only run-through and a reduced-motion run-through recorded.
4. Illustration / synthetic labels visible beside every non-real visual.
5. Report edited paths, commands and results, and unresolved issues. Do not call the work perfect or verified on
   self-review alone; Codex review and P5 parity checks decide.
