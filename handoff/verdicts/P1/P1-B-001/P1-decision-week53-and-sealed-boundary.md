# P1 Policy Decision: Week Definition, Week 53 Baselines & Sealed-Window Boundaries

See the authoritative decision recorded in [P1-decision-week-definition-and-week53.md](../../escalations/P1/P1-decision-week-definition-and-week53.md).

### Summary for P1-B
- **Week Definition:** UTC ISO weeks (`utc_iso_week`).
- **Week 53 Unusual Baseline:** Requires >= 3 complete, supported eligible prior ISO week-53 observations per sensor/policy; no substitution with week 52 or 1. Otherwise `insufficient_baseline` and null label.
- **Sealed 2020–2021 Boundary:** Permitted days only; marked partial and comparison-ineligible with null labels. Never read sealed days.
- **Open Settings:** Critical ranking for week 53, critical-week parameters, Stage A strata/thresholds, coverage tolerance, and P1-A status mappings remain open.
