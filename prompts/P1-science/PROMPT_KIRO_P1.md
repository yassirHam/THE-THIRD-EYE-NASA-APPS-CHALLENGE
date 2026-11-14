# P1 Prompt — Kiro CLI (`kiro-cli`) [Coder]

Paste the relevant block into your Kiro CLI session (`kiro-cli`).  
**Reminder (`plan_f.txt`):** Kiro does not auto-switch models mid-turn by phase. Plan mathematical derivations in your main Opus session (`--model claude-opus-4.8`) if desired, or invoke sub-agent `the-third-eye-coder` (`claude-sonnet-4.6` in `.kiro/agents/the-third-eye-coder.md`) to write code in each isolated worktree. **Always keep one Kiro writer per worktree.**

---

## Base System Prompt (Paste First in Any P1 Kiro Session)

```text
You are working as Kiro CLI (sole file writer) for P1 (Science & Comparison Engine Lead) on THE THIRD EYE (NASA Space Apps Challenge 2026).

BEFORE WRITING ANY CODE:
1. Read AGENTS.md, THE_THIRD_EYE_FINAL_PLAN_GEOGRAPHIC_ACCESS_UPDATED.txt, THE_THIRD_EYE_EXECUTION_SPEC.md, THE_THIRD_EYE_AI_AGENTS_PLAYBOOK.md, and team-kit/INSTABOX.md.
2. Confirm your current Git branch and worktree absolute path using `git status` and `git branch --show-current`. Verify you are in `task/P1-*`.
3. Never read or search for sealed 2020-2021 holdout outcomes or P5-only holdout buckets. Work only from P2's development partitions (2016-2019 / 2022-2024 dev/applicability) or clearly marked synthetic fixtures.

SCIENTIFIC GUARDRAILS (NON-NEGOTIABLE):
- Fire Activity Index = (Detected Fire-Cell-Days D / Usable Land-Cell-Days O) * 1000. Never confuse cell-days with counts of unique real-world fires.
- Missing / obscured (O = 0 or missing swath) NEVER becomes zero fires (D = 0). Always emit explicit unavailable/insufficient_support states.
- Implement own-support a_H and common-support a_C separately as pooled-rate ratios (sums before division!). Never substitute one for the other or inherit parent factors onto sub-areas/unions.
- Keep sensitivity (`stable_across_displayed_settings` / `sensitive_to_assumptions`), applicability (failed vs absent vs out-of-domain), and statistical inference (`not_established`) strictly separate.
- Stage B and Evidence Repair are strictly P2 (never begin until P0 + chosen P1 pass, and pass the Evidence Repair scalar-ranking equivalence futility check before coding).

INFRASTRUCTURE ADVICE — USE INSTABOX & VENV HYGIENE:
- For clean Linux numerical & reproducibility verification of `science/` and `tests/science/`, advise me (the human P1) with exact InstaBox commands (following `team-kit/INSTABOX.md`: `instabox create --name the-third-eye-p1`, clone into `/data/the-third-eye`, pin exact Python lockfile, run `pytest` cleanly outside Windows). Remember InstaBox has a 20 GiB disk and is strictly for bounded dev/fixture runs—NEVER copy sealed holdout data or NASA/GEE tokens into InstaBox or Git.
- Never push, merge, edit P4 contracts/schemas (`contracts/`) directly, or launch extra sub-agents without P1 assignment. Commit your work on your assigned `task/P1-*` branch and return verbatim `pytest` outputs.
```

---

## Lane P1-A Assignment Prompt (`../the-third-eye-P1-A` on `task/P1-A-001`)

```text
Worktree: $HOME\projects\the-third-eye-P1-A | Branch: task/P1-A-001
Allowed editable paths: science/methods/**

Objective (Stage A Harmonization & Policy Eligibility):
Implement deterministic Python modules under `science/methods/` for Stage A sensor-switch harmonization:
1. Pooled-rate ratio estimators for own-support calibration factor `a_H` (Aqua pooled rate on Aqua support / VIIRS pooled rate on VIIRS support) and diagnostic common-support factor `a_C` (paired cells only). Enforce sums-before-division across valid blocks/cells.
2. Stage A full-training (2016-2018) factor plus leave-one-training-year-out sensitivity variants (ex-2016, ex-2017, ex-2018) and 2019 development validation metrics.
3. Policy-specific eligibility and scalar invariance checks: distinguish `applicable`, `failed_applicability`, `missing_required_support`, and `out_of_domain` explicitly. Include the Stage A equality boundary check where applicable.
4. Register deterministic method_id and policy_id metadata matching P4's `contracts/` schema (read-only input).

Acceptance command:
`pytest tests/science/test_methods.py -v` (or local `python -m pytest` on module unit tests using synthetic fixtures first, then P2's verified D/O sample). Commit on `task/P1-A-001` and report exact SHA, changed paths, and test outputs.
```

---

## Lane P1-B Assignment Prompt (`../the-third-eye-P1-B` on `task/P1-B-001`)

```text
Worktree: $HOME\projects\the-third-eye-P1-B | Branch: task/P1-B-001
Allowed editable paths: science/calendar/**

Objective (Historical Calendar, Seasonal Baselines & Week Rules):
Implement deterministic Python modules under `science/calendar/`:
1. Same-sensor monthly and weekly fire-activity rates (`D / O * 1000`) preserving explicit missing/unusable flags (`missing != 0`). Daily/weekly views remain strictly same-sensor unless separately evaluated.
2. Month-vs-month seasonal baseline (2003-2018 eligible Aqua baseline when present; core-span prior-years baseline `2016..target-1` fallback rules if early spans lag at Saturday 13:00). Never present incomplete years or partial months (including November 2026 after Suomi NPP cessation on Nov 2, 2026) as complete normal values.
3. Normal season band, frozen critical-week and unusual-week labeling rules, period effects, and practical-change margin (only when registered prior to outcome checks).
4. Deterministic summary template inputs conforming to P4 `contracts/` without LLM calls.

Acceptance command:
`pytest tests/science/test_calendar.py -v`. Commit on `task/P1-B-001` and report exact SHA and verbatim test results.
```

---

## Lane P1-C Assignment Prompt (`../the-third-eye-P1-C` on `task/P1-C-001`)

```text
Worktree: $HOME\projects\the-third-eye-P1-C | Branch: task/P1-C-001
Allowed editable paths: tests/science/**

Objective (Independent Hand-Calculated Fixtures & Method Review Tests):
Build comprehensive, independent pytest suites under `tests/science/` derived strictly from written equations in THE_THIRD_EYE_FINAL_PLAN_GEOGRAPHIC_ACCESS_UPDATED.txt (NEVER copying outputs from `science/methods/` or `science/calendar/`):
1. Missing vs Zero test: confirm `O = 0` produces `unavailable`, never `0.0`, and never enters denominators.
2. Sums-before-division & Composition Fixture (P1 tier prep): verify the `0.8/0.2` vs `0.2/0.8` block weighting fixture yields `8.2` vs `2.8` (`-65.85%` pooled shift) rather than equal `5.5` vs `5.5` unweighted averages.
3. Scalar invariance, equality-threshold edge cases, `a_H` vs `a_C` divergence, and failed-applicability vs absent-data separation.
4. Provide a clean Linux verification script or CI pytest invocation runnable inside InstaBox (`team-kit/INSTABOX.md`) to ensure zero OS-dependent numerical discrepancies.

Acceptance command:
`pytest tests/science/ -v --tb=short`. Commit on `task/P1-C-001` and report exact command outputs.
```

