"""P5 independent UI parity suite.

Contract Parity Mode (default, always runs)
    Verifies the 18 contract 1.1.0 fixtures against contracts/generated/types.ts,
    checks that every view's data source (Landing, Research Lab, Quick Mission,
    Evidence view, Export download) carries the same identity and statuses for a
    case, verifies the five frozen edge cases, and enforces the two compound
    statuses. Expected values come from P5's reading of the plan (Section 7, 9A,
    5A) and the frontend contract, not from P4's implementation. P4's Pydantic
    models are run in a separate process only to confirm they agree with P5.

Live Browser Mode (only when $env:E2E_BASE_URL is set)
    Uses Playwright against the deployed static site: routes /, /story, /lab,
    keyboard focus, prefers-reduced-motion, the S-NPP 2026-11-02 marker, the
    FIRMS link and explainer, no backend calls, and no internal status IDs on
    the first screen.

All data is public synthetic fixture data. Nothing here reads sealed holdouts.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import textwrap
from copy import deepcopy
from pathlib import Path

import pytest

# ----------------------------------------------------------------- P5 expectations

EXPECTED_FIXTURES = {
    "sample_calendar": "CalendarArtifact",
    "sample_claim_audit_missing_evidence": "ClaimAuditRecord",
    "sample_claim_audit_out_of_domain": "ClaimAuditRecord",
    "sample_claim_audit_record": "ClaimAuditRecord",
    "sample_claim_audit_sensitive": "ClaimAuditRecord",
    "sample_claim_audit_stable_failed_applicability": "ClaimAuditRecord",
    "sample_claim_audit_within_margin_opposite_sign": "ClaimAuditRecord",
    "sample_comparison_missing_evidence": "ComparisonResult",
    "sample_comparison_normal": "ComparisonResult",
    "sample_comparison_out_of_domain": "ComparisonResult",
    "sample_comparison_sensitive": "ComparisonResult",
    "sample_comparison_stable_failed_applicability": "ComparisonResult",
    "sample_comparison_within_margin_opposite_sign": "ComparisonResult",
    "sample_evaluation_summary": "EvaluationSummary",
    "sample_evaluation_unavailable": "EvaluationSummary",
    "sample_firms_hotspots": "FirmsHotspotArtifact",
    "sample_manifest": "ProvenanceManifest",
    "sample_region_selector": "RegionSelectorArtifact",
}

# Lab / Landing / Quick Mission read the comparison; Evidence view / Export read
# the claim audit record of the same case.
CASE_PAIRS = {
    "normal": ("sample_comparison_normal", "sample_claim_audit_record"),
    "sensitive": ("sample_comparison_sensitive", "sample_claim_audit_sensitive"),
    "stable_failed_applicability": (
        "sample_comparison_stable_failed_applicability",
        "sample_claim_audit_stable_failed_applicability",
    ),
    "missing_evidence": ("sample_comparison_missing_evidence", "sample_claim_audit_missing_evidence"),
    "out_of_domain": ("sample_comparison_out_of_domain", "sample_claim_audit_out_of_domain"),
    "within_margin_opposite_sign": (
        "sample_comparison_within_margin_opposite_sign",
        "sample_claim_audit_within_margin_opposite_sign",
    ),
}

IDENTITY_FIELDS = ("contract_version", "artifact_version", "geometry_id", "period_spec", "policy_id")
STATUS_FIELDS = (
    "sensitivity_status",
    "applicability_status",
    "inference_status",
    "practical_change",
    "applicability_checks",
    "missing_evidence_reasons",
    "conclusion_eligible",
    "reviewed_summary",
)
VIEWS = ("Landing", "Research Lab", "Quick Mission", "Evidence view", "Export download")

# P5's frozen plain-language labels. Each must name every adverse condition it covers.
P5_LABELS = {
    "consistent_across_tested_corrections": "Consistent across tested corrections",
    "depends_on_the_correction": "Depends on the correction",
    "not_enough_usable_evidence": "Not enough usable evidence",
    "outside_evaluated_calibration": "Outside evaluated calibration",
    "calibration_check_failed": "Calibration check failed",
    "calibration_check_failed_and_missing_evidence": "Calibration check failed and required evidence missing",
    "outside_evaluated_calibration_and_missing_evidence": "Outside evaluated calibration and required evidence missing",
}
COMPOUND = (
    "calibration_check_failed_and_missing_evidence",
    "outside_evaluated_calibration_and_missing_evidence",
)
GENERIC_MISSING_LABEL = "Not enough usable evidence"
INTERNAL_IDS_FOR_FIRST_SCREEN = (
    "stable_across_displayed_settings", "sensitive_to_assumptions", "failed_applicability",
    "missing_required_support", "out_of_domain", "not_established", "raw_only",
    "evaluated_comparison", "calibration_check_failed_and_missing_evidence",
    "outside_evaluated_calibration_and_missing_evidence", "own_support", "a_H", "geometry_id",
)


def p5_expected_category(applicability: str, sensitivity: str, complete: bool) -> str:
    """Plan Section 7: missing evidence takes unresolved precedence, but a failed
    or out-of-domain check is never hidden by it, and neither is hidden by a
    stable variant set."""
    adverse = {"failed_applicability": "calibration_check_failed",
               "out_of_domain": "outside_evaluated_calibration"}.get(applicability)
    if adverse:
        return adverse if complete else f"{adverse}_and_missing_evidence"
    if not complete or applicability == "missing_required_support" or sensitivity == "unavailable":
        return "not_enough_usable_evidence"
    return "depends_on_the_correction" if sensitivity == "sensitive_to_assumptions" else "consistent_across_tested_corrections"


def evidence_complete(artifact: dict) -> bool:
    required = set(artifact.get("required_variant_ids", []))
    supplied = {v["variant_id"] for v in artifact.get("registered_variants", [])}
    return (
        required <= supplied
        and not artifact.get("missing_evidence_reasons")
        and not any(c["status"] == "missing" for c in artifact["applicability_checks"])
        and artifact["applicability_status"] != "missing_required_support"
    )


# ----------------------------------------------------------------- TS type checker


def parse_ts_interfaces(source: str) -> dict[str, dict[str, tuple[bool, str]]]:
    interfaces = {}
    for name, body in re.findall(r"export interface (\w+) \{(.*?)\n\}", source, re.DOTALL):
        fields = {}
        for line in body.strip().splitlines():
            m = re.match(r"\s*(\w+)(\??):\s*(.+);\s*$", line)
            if m:
                fields[m.group(1)] = (m.group(2) == "?", m.group(3).strip())
        interfaces[name] = fields
    return interfaces


def _split_union(type_str: str) -> list[str]:
    parts, depth, quoted, cur = [], 0, False, ""
    for ch in type_str:
        if ch == '"':
            quoted = not quoted
        elif not quoted and ch in "<([":
            depth += 1
        elif not quoted and ch in ">)]":
            depth -= 1
        if ch == "|" and depth == 0 and not quoted:
            parts.append(cur.strip())
            cur = ""
        else:
            cur += ch
    parts.append(cur.strip())
    return [p for p in parts if p]


def ts_errors(value, type_str: str, interfaces: dict, path: str) -> list[str]:
    alternatives = _split_union(type_str)
    best: list[str] | None = None
    for alt in alternatives:
        errs = _ts_alt_errors(value, alt, interfaces, path)
        if not errs:
            return []
        if best is None or len(errs) < len(best):
            best = errs
    return best or [f"{path}: no type alternative in {type_str!r}"]


def _ts_alt_errors(value, alt: str, interfaces: dict, path: str) -> list[str]:
    if alt == "null":
        return [] if value is None else [f"{path}: expected null"]
    if alt.startswith('"'):
        return [] if value == alt.strip('"') else [f"{path}: {value!r} is not {alt}"]
    if alt in ("true", "false"):
        return [] if value is (alt == "true") else [f"{path}: expected {alt}"]
    if alt == "number":
        return [] if isinstance(value, (int, float)) and not isinstance(value, bool) else [f"{path}: expected number"]
    if alt == "string":
        return [] if isinstance(value, str) else [f"{path}: expected string"]
    if alt == "boolean":
        return [] if isinstance(value, bool) else [f"{path}: expected boolean"]
    if alt.startswith("Record<"):
        return [] if isinstance(value, dict) else [f"{path}: expected object"]
    inner = None
    if alt.endswith("[]"):
        inner = alt[:-2]
        if inner.startswith("(") and inner.endswith(")"):
            inner = inner[1:-1]
    elif alt.startswith("Array<") and alt.endswith(">"):
        inner = alt[6:-1]
    if inner is not None:
        if not isinstance(value, list):
            return [f"{path}: expected array"]
        return [e for i, v in enumerate(value) for e in ts_errors(v, inner, interfaces, f"{path}[{i}]")]
    if alt in interfaces:
        if not isinstance(value, dict):
            return [f"{path}: expected {alt} object"]
        return interface_errors(value, alt, interfaces, path)
    return [f"{path}: unsupported TS type {alt!r}"]


def interface_errors(obj: dict, name: str, interfaces: dict, path: str = "$") -> list[str]:
    fields = interfaces[name]
    errs = [f"{path}.{k}: not declared in TS {name}" for k in obj if k not in fields]
    for key, (optional, type_str) in fields.items():
        if key not in obj:
            if not optional:
                errs.append(f"{path}.{key}: required by TS {name} but missing")
            continue
        errs.extend(ts_errors(obj[key], type_str, interfaces, f"{path}.{key}"))
    return errs


@pytest.fixture(scope="session")
def ts(contracts):
    return parse_ts_interfaces(contracts.types_ts.read_text(encoding="utf-8"))


# ----------------------------------------------------------------- Contract Parity Mode


def test_contract_source_is_1_1_0(contracts):
    assert contracts.fixtures.is_dir(), contracts.description


def test_all_18_fixtures_present(fixtures):
    assert set(fixtures) == set(EXPECTED_FIXTURES), (
        f"missing {sorted(set(EXPECTED_FIXTURES) - set(fixtures))}, "
        f"unexpected {sorted(set(fixtures) - set(EXPECTED_FIXTURES))}"
    )


@pytest.mark.parametrize("stem", sorted(EXPECTED_FIXTURES))
def test_fixture_matches_typescript_type(stem, fixtures, ts):
    interface = EXPECTED_FIXTURES[stem]
    assert interface in ts, f"types.ts lacks interface {interface}"
    errors = interface_errors(fixtures[stem], interface, ts)
    assert not errors, "\n".join(errors[:20])


@pytest.mark.parametrize("stem", sorted(EXPECTED_FIXTURES))
def test_fixture_is_visibly_synthetic_and_versioned(stem, fixtures):
    f = fixtures[stem]
    assert f["contract_version"] == "1.1.0"
    assert f["data_classification"] == "synthetic_dev_fixture"
    assert f["fixture_label"] == "[SYNTHETIC DEV FIXTURE]"


def test_identity_is_single_case_across_all_fixtures(fixtures):
    for field in ("artifact_version", "geometry_id", "period_spec", "policy_id"):
        values = {f[field] for f in fixtures.values()}
        assert len(values) == 1, f"{field} differs across fixtures: {sorted(values)}"


def view_state(view: str, comparison: dict, audit: dict, evaluation: dict) -> dict:
    """What each view must show for one case, per the frontend contract."""
    source = audit if view in ("Evidence view", "Export download") else comparison
    if view == "Export download":
        source = json.loads(json.dumps(source, sort_keys=True))  # what the user downloads
    state = {k: source[k] for k in IDENTITY_FIELDS + STATUS_FIELDS}
    if view == "Landing":
        state["headline"] = evaluation["landing_headline_metric"]
    return state


@pytest.mark.parametrize("case", sorted(CASE_PAIRS))
def test_case_parity_across_views(case, fixtures):
    comparison, audit = (fixtures[s] for s in CASE_PAIRS[case])
    evaluation = fixtures["sample_evaluation_summary"]
    states = {v: view_state(v, comparison, audit, evaluation) for v in VIEWS}
    reference = {k: v for k, v in states["Research Lab"].items()}
    for view, state in states.items():
        for key in IDENTITY_FIELDS + STATUS_FIELDS:
            assert state[key] == reference[key], f"{case}: {view} differs from Research Lab on {key}"
    assert comparison["artifact_version"] in audit["evidence_artifact_versions"], (
        f"{case}: evidence record does not cite the comparison artifact it explains"
    )


def test_export_roundtrip_is_byte_stable(fixtures):
    for stem in (p for pair in CASE_PAIRS.values() for p in pair):
        once = json.dumps(fixtures[stem], sort_keys=True, ensure_ascii=False)
        twice = json.dumps(json.loads(once), sort_keys=True, ensure_ascii=False)
        assert once == twice, stem


@pytest.mark.parametrize("stem", [s for s, t in EXPECTED_FIXTURES.items() if t in ("ComparisonResult", "ClaimAuditRecord")])
def test_status_label_follows_p5_rule(stem, fixtures):
    f = fixtures[stem]
    expected = p5_expected_category(f["applicability_status"], f["sensitivity_status"], evidence_complete(f))
    summary = f["reviewed_summary"]
    assert summary["output_category"] == expected
    assert summary["status_label"] == P5_LABELS[expected]
    if f["applicability_status"] != "applicable" or not evidence_complete(f):
        assert f["conclusion_eligible"] is False


# ---- compound statuses (contract 1.1.0)


def test_compound_statuses_declared_in_typescript(ts):
    category_type = ts["ReviewedTemplateSummary"]["output_category"][1]
    label_type = ts["ReviewedTemplateSummary"]["status_label"][1]
    for cat in COMPOUND:
        assert f'"{cat}"' in category_type, f"types.ts output_category lacks {cat}"
        assert f'"{P5_LABELS[cat]}"' in label_type, f"types.ts status_label lacks {P5_LABELS[cat]!r}"


@pytest.mark.parametrize("cat", COMPOUND)
def test_compound_label_names_both_conditions(cat):
    label = P5_LABELS[cat]
    assert label != GENERIC_MISSING_LABEL
    assert "required evidence missing" in label
    assert ("failed" in label) if cat.startswith("calibration_check_failed") else label.startswith("Outside evaluated calibration")


def _to_missing_evidence(base: dict, category: str, label: str, applicability: str | None = None) -> dict:
    """P5-built case: drop two required variants so evidence is incomplete."""
    case = deepcopy(base)
    if "registered_variants" in case:
        case["registered_variants"] = [v for v in case["registered_variants"] if v["variant_id"] == "full_training"]
        case["headline_direction"] = "unavailable"
    case["missing_evidence_reasons"] = ["Required variants ex_2016 and ex_2017 are missing."]
    case["sensitivity_status"] = "unavailable"
    case["practical_change"] = {"category": "unavailable"}
    case["conclusion_eligible"] = False
    case["reviewed_summary"] = {**case["reviewed_summary"], "output_category": category, "status_label": label}
    if applicability:
        case["applicability_status"] = applicability
    return case


def compound_cases(fixtures: dict) -> list[tuple[str, str, dict, bool]]:
    """(case_id, model, payload, P5 expects schema to accept)."""
    cases = []
    sources = {
        "calibration_check_failed_and_missing_evidence": (
            "sample_comparison_stable_failed_applicability", "sample_claim_audit_stable_failed_applicability"),
        "outside_evaluated_calibration_and_missing_evidence": (
            "sample_comparison_out_of_domain", "sample_claim_audit_out_of_domain"),
    }
    for cat, stems in sources.items():
        for stem, model in zip(stems, ("ComparisonResult", "ClaimAuditRecord")):
            base = fixtures[stem]
            cases.append((f"{stem}+missing:full-label", model, _to_missing_evidence(base, cat, P5_LABELS[cat]), True))
            cases.append((f"{stem}+missing:collapsed-generic", model,
                          _to_missing_evidence(base, "not_enough_usable_evidence", GENERIC_MISSING_LABEL), False))
            cases.append((f"{stem}+missing:generic-label-only", model,
                          _to_missing_evidence(base, cat, GENERIC_MISSING_LABEL), False))
            cases.append((f"{stem}+missing:status-masked", model,
                          _to_missing_evidence(base, "not_enough_usable_evidence", GENERIC_MISSING_LABEL,
                                               applicability="missing_required_support"), False))
    return cases


def test_p5_rule_assigns_compound_categories(fixtures):
    for case_id, _, payload, accept in compound_cases(fixtures):
        if not accept:
            continue
        cat = p5_expected_category(payload["applicability_status"], payload["sensitivity_status"], evidence_complete(payload))
        assert cat in COMPOUND, case_id
        assert payload["reviewed_summary"]["status_label"] == P5_LABELS[cat]


_VALIDATOR = textwrap.dedent(
    """
    import json, sys
    sys.path.insert(0, sys.argv[1])
    import contracts.schemas as s
    out = []
    for case_id, model, payload in json.load(sys.stdin):
        try:
            getattr(s, model).model_validate_json(json.dumps(payload))
            out.append([case_id, True, ""])
        except Exception as exc:
            out.append([case_id, False, str(exc).splitlines()[0][:200]])
    print(json.dumps(out))
    """
)


def run_p4_schema(contracts, items: list[tuple[str, str, dict]]) -> dict[str, tuple[bool, str]]:
    pytest.importorskip("pydantic")
    proc = subprocess.run(
        [sys.executable, "-c", _VALIDATOR, str(contracts.root)],
        input=json.dumps(items), capture_output=True, text=True, timeout=120,
        cwd=contracts.root, env={**os.environ, "PYTHONPATH": ""},
    )
    assert proc.returncode == 0, proc.stderr[-2000:]
    return {cid: (ok, msg) for cid, ok, msg in json.loads(proc.stdout)}


def test_p4_schema_accepts_all_fixtures(contracts, fixtures):
    results = run_p4_schema(contracts, [(s, EXPECTED_FIXTURES[s], fixtures[s]) for s in sorted(EXPECTED_FIXTURES)])
    rejected = {k: v[1] for k, v in results.items() if not v[0]}
    assert not rejected, rejected


def test_p4_schema_agrees_with_p5_on_compound_statuses(contracts, fixtures):
    cases = compound_cases(fixtures)
    results = run_p4_schema(contracts, [(cid, model, payload) for cid, model, payload, _ in cases])
    disagreements = [
        f"{cid}: P5 expects {'accept' if accept else 'reject'}, schema {'accepted' if results[cid][0] else 'rejected'} {results[cid][1]}"
        for cid, _, _, accept in cases if results[cid][0] != accept
    ]
    assert not disagreements, "\n".join(disagreements)


# ---- the five frozen edge cases


def test_edge_stable_but_failed_applicability(fixtures):
    for stem in ("sample_comparison_stable_failed_applicability", "sample_claim_audit_stable_failed_applicability"):
        f = fixtures[stem]
        assert f["sensitivity_status"] == "stable_across_displayed_settings"
        assert f["applicability_status"] == "failed_applicability"
        assert any(c["status"] == "failed" for c in f["applicability_checks"])
        assert f["conclusion_eligible"] is False
        label = f["reviewed_summary"]["status_label"]
        assert "failed" in label.lower() and label not in (P5_LABELS["consistent_across_tested_corrections"], GENERIC_MISSING_LABEL)
    assert fixtures["sample_comparison_stable_failed_applicability"]["headline_direction"] == "unavailable"


def test_edge_missing_evidence(fixtures):
    for stem in ("sample_comparison_missing_evidence", "sample_claim_audit_missing_evidence"):
        f = fixtures[stem]
        assert f["missing_evidence_reasons"], "missing evidence must say what is missing"
        assert f["practical_change"]["category"] == "unavailable"
        assert f["practical_change"].get("magnitude") is None, "missing evidence must not publish a magnitude"
        assert f["conclusion_eligible"] is False
        assert f["reviewed_summary"]["status_label"] == GENERIC_MISSING_LABEL
    cmp_ = fixtures["sample_comparison_missing_evidence"]
    assert cmp_["headline_direction"] == "unavailable"
    assert not set(cmp_["required_variant_ids"]) <= {v["variant_id"] for v in cmp_["registered_variants"]}


def test_edge_region_selector(fixtures):
    opts = fixtures["sample_region_selector"]["options"]
    ids = [o["geometry_id"] for o in opts]
    assert len(ids) == len(set(ids)), "geometry IDs must be unique"
    assert sum(o["geometry_role"] == "primary_region" for o in opts) == 1
    for o in opts:
        evaluated = o["comparison_access_status"] == "evaluated_comparison"
        bound = (o["evaluated_method_id"], o["evaluated_policy_id"], o["evaluated_period_spec"])
        if evaluated:
            assert all(bound), f"{o['geometry_id']}: evaluated area must name its own method/policy/period"
        else:
            assert not any(bound), f"{o['geometry_id']}: non-evaluated area inherits evaluation identity"
        if o["geometry_role"] == "predeclared_sub_area":
            assert o["comparison_access_status"] in ("raw_only", "unavailable"), "sub-areas never inherit calibration"
        if o["raw_data_status"] == "unavailable" or o["comparison_access_status"] == "unavailable":
            assert o["unavailable_reason"], f"{o['geometry_id']}: unavailable needs a reason"
        else:
            assert o["unavailable_reason"] is None


def test_edge_evaluation_unavailable(fixtures):
    ev = fixtures["sample_evaluation_unavailable"]
    head = ev["landing_headline_metric"]
    assert head["status"] == "unavailable" and head["unavailable_reason"]
    for key in ("registered_case_count", "raw_wrong_way_count", "corrected_wrong_way_count",
                "flagged_remaining_error_count", "abstained_count"):
        assert head[key] is None, f"{key} must be null when unavailable, never zero"
    units = head["independent_units"]
    assert {"blocks", "regions", "test_years", "dependence_note"} <= set(units)
    assert head["denominator_statement"]
    for name in ("baseline_a_raw_handover", "baseline_b_point_a_h", "baseline_c_uncertainty_aware",
                 "baseline_d_stage_a_finite_audit"):
        b = ev[name]
        assert b["status"] == "unavailable" and b["unavailable_reason"]
        for metric in ("mean_reference_relative_error", "directional_error_count", "decision_coverage_percent"):
            assert b[metric] is None, f"{name}.{metric} must be null, not a number"


def test_edge_within_margin_opposite_sign(fixtures):
    f = fixtures["sample_comparison_within_margin_opposite_sign"]
    pc = f["practical_change"]
    assert f["headline_direction"] == "within_practical_margin", "must not be reported as no_change"
    assert {"increase", "decrease"} <= set(pc["observed_signs"]), "opposite signs must stay visible"
    assert pc["magnitude"] <= pc["practical_margin_tau"]
    assert {v["direction"] for v in f["registered_variants"]} == set(pc["observed_signs"])
    assert "not equivalence" in f["reviewed_summary"]["limit_sentence"].lower()


def test_headline_reports_independent_units(fixtures):
    for stem in ("sample_evaluation_summary", "sample_evaluation_unavailable"):
        units = fixtures[stem]["landing_headline_metric"]["independent_units"]
        for key in ("blocks", "regions", "test_years"):
            assert isinstance(units[key], int) and not isinstance(units[key], bool)
        assert "dependent" in units["dependence_note"].lower()


def test_snpp_cessation_marker_in_contract(fixtures):
    assert fixtures["sample_calendar"]["snpp_delivery_end_at"].startswith("2026-11-02")
    assert fixtures["sample_manifest"]["snpp_cessation_date"] == "2026-11-02"


def test_firms_view_isolated_from_grid_science(fixtures):
    f = fixtures["sample_firms_hotspots"]
    assert f["view_name"] == "Reported hotspots"
    assert f["feeds_grid_math"] is False and f["inherits_grid_calibration"] is False
    assert f["cross_sensor_trend_allowed"] is False
    assert f["firms_link"]["url"].startswith("https://firms.modaps.eosdis.nasa.gov/")


# ----------------------------------------------------------------- Live Browser Mode

BASE_URL = os.environ.get("E2E_BASE_URL", "").rstrip("/")
live = pytest.mark.skipif(not BASE_URL, reason="Live Browser Mode needs $env:E2E_BASE_URL")


@pytest.fixture(scope="module")
def browser():
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        pytest.fail("E2E_BASE_URL is set but Playwright is not installed: pip install playwright && playwright install chromium")
    with sync_playwright() as p:
        b = p.chromium.launch()
        yield b
        b.close()


def _open(browser, path: str, **context_args):
    ctx = browser.new_context(**context_args)
    page = ctx.new_page()
    errors, requests = [], []
    page.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.on("request", lambda r: requests.append((r.method, r.url, r.resource_type)))
    resp = page.goto(BASE_URL + path, wait_until="networkidle")
    return ctx, page, resp, errors, requests


@live
@pytest.mark.parametrize("path", ["/", "/story", "/lab"])
def test_live_route_loads_without_errors(browser, path):
    ctx, page, resp, errors, _ = _open(browser, path)
    try:
        assert resp is not None and resp.ok, f"{path} returned {resp.status if resp else 'no response'}"
        assert not errors, f"{path} console errors: {errors[:5]}"
    finally:
        ctx.close()


@live
def test_live_keyboard_reaches_controls(browser):
    ctx, page, *_ = _open(browser, "/lab")
    try:
        reached = set()
        for _ in range(20):
            page.keyboard.press("Tab")
            reached.add(page.evaluate("document.activeElement && document.activeElement.tagName"))
        assert reached - {"BODY", None}, "Tab never moved focus to a control"
        assert reached & {"A", "BUTTON", "SELECT", "INPUT"}, f"focus reached only {reached}"
    finally:
        ctx.close()


@live
def test_live_reduced_motion_stops_looping_animation(browser):
    ctx, page, *_ = _open(browser, "/", reduced_motion="reduce")
    try:
        page.wait_for_timeout(1500)
        looping = page.evaluate(
            "document.getAnimations().filter(a => a.playState === 'running' && "
            "a.effect && a.effect.getTiming().iterations === Infinity).length"
        )
        assert looping == 0, f"{looping} infinite animations run under prefers-reduced-motion"
    finally:
        ctx.close()


@live
def test_live_snpp_marker_and_firms(browser):
    ctx, page, *_ = _open(browser, "/lab")
    try:
        text = page.inner_text("body")
        assert re.search(r"2 November 2026|November 2, 2026|2026-11-02", text), "S-NPP cessation date not shown"
        links = page.eval_on_selector_all(
            "a[href^='https://firms.modaps.eosdis.nasa.gov']", "els => els.map(e => e.href)")
        assert links, "no FIRMS link"
        assert "denominator" in text.lower(), "grid-versus-points explainer missing"
        assert re.search(r"never enter|separate", text, re.IGNORECASE), "explainer must say points stay separate"
    finally:
        ctx.close()


@live
def test_live_static_no_backend(browser):
    for path in ("/", "/lab"):
        ctx, page, resp, _, requests = _open(browser, path)
        try:
            origin = re.match(r"^(https?://[^/]+)", BASE_URL).group(1)
            backend = [u for m, u, _ in requests if u.startswith(origin) and ("/api/" in u or m not in ("GET", "HEAD"))]
            assert not backend, f"{path} called a backend: {backend[:5]}"
        finally:
            ctx.close()


@live
def test_live_first_screen_has_no_internal_ids(browser):
    ctx, page, *_ = _open(browser, "/")
    try:
        text = page.inner_text("body")
        leaked = [t for t in INTERNAL_IDS_FOR_FIRST_SCREEN if t in text]
        assert not leaked, f"first screen shows internal terms: {leaked}"
    finally:
        ctx.close()
