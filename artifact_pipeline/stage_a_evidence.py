"""Stage A real-data evidence document for the static bundle (P4-A).

    python -m artifact_pipeline.stage_a_evidence [--out artifact_pipeline/build/bundle] \
        [--summary science/methods/frozen/stage_a_real_CA_BC_summary.json] [--data-dir DIR] \
        [--no-replay] [--replace] [--bundle-version stage-a-real-CA-BC-1]

Input: P1's frozen Stage A summary (science.methods.stage_a_real output). When
$THE_THIRD_EYE_DATA_DIR/focus_weekly_CA_BC.parquet is available, the summary is replayed:
the parquet sha256 must equal the summary's source hash, rows are read only through
science.methods.stage_a_real.load_rows (row filter drops ISO years 2020-2021 before rows
reach Python, then re-checked), and the recomputed summary must match the frozen one.

Output: one `stage_a_evidence` document in the bundle's `evidence/` subtree. It carries the
P1 summary verbatim (no value is rewritten), the replay result, the populated
counterexample_interpretations, and the reasons no contract ComparisonResult / ClaimAuditRecord
is emitted for real data. Interpretations are deterministic templates over P1's numbers; they
are descriptive and never turn insufficient_evidence into passed or failed.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import shutil
import sys
from pathlib import Path
from typing import Any, Mapping, Optional, Sequence

from contracts.schemas import CONTRACT_VERSION
from contracts.schemas.status_mapping import load_mapping
from science.methods import stage_a_real

from .bundle import INDEX_NAME, Bundle, BundleError, verify_bundle

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SUMMARY = REPO_ROOT / "science" / "methods" / "frozen" / "stage_a_real_CA_BC_summary.json"
DEFAULT_OUT = Path(__file__).resolve().parent / "build" / "bundle"
EVIDENCE_FORMAT = "tte-stage-a-evidence-v1"
EVIDENCE_ID = "stage_a_real_CA_BC"
SEALED_YEARS = tuple(stage_a_real.SEALED_YEARS)  # (2020, 2021)
# Replay tolerance: float summation order only. Counts, statuses and structure compare exactly.
REPLAY_FLOAT_REL_TOL = 1e-9
CONSISTENCY_REL_TOL = 1e-9


class EvidenceError(BundleError):
    """The Stage A summary cannot be turned into bundle evidence without breaking a guard."""


# ---------------------------------------------------------------------------- loading and guards


def load_summary(path: Path) -> tuple[dict, str]:
    path = Path(path)
    if not path.is_file():
        raise EvidenceError(f"Stage A summary {path} not found")
    raw = path.read_bytes()
    return json.loads(raw.decode("utf-8")), hashlib.sha256(raw).hexdigest()


_SEALED_KEY = re.compile(r"(?:^|_)(%s)$" % "|".join(str(y) for y in SEALED_YEARS))
_YEAR_LIST_KEYS = {"years", "training_years", "iso_years_in_eligible_weeks", "training",
                   "applicability", "development"}


def refuse_sealed_content(summary: Mapping[str, Any]) -> None:
    """Fail if any part of the summary other than splits.sealed_not_read names 2020 or 2021."""
    splits = summary.get("splits") or {}
    if sorted(splits.get("sealed_not_read") or []) != sorted(SEALED_YEARS):
        raise EvidenceError("summary does not declare 2020-2021 as sealed and not read")

    def walk(node: Any, path: str) -> None:
        if isinstance(node, dict):
            for k, v in node.items():
                p = f"{path}/{k}"
                if p == "/splits/sealed_not_read":
                    continue
                if _SEALED_KEY.search(str(k)):
                    raise EvidenceError(f"summary carries sealed-window content at {p}")
                if k in _YEAR_LIST_KEYS:
                    years = v if isinstance(v, list) else [v]
                    if any(isinstance(y, int) and y in SEALED_YEARS for y in years):
                        raise EvidenceError(f"summary lists a sealed year at {p}")
                walk(v, p)
        elif isinstance(node, list):
            for i, v in enumerate(node):
                walk(v, f"{path}[{i}]")

    walk(summary, "")
    if (summary.get("status_dimensions") or {}).get("inference_status") != "not_established":
        raise EvidenceError("inference_status must stay not_established")


# ---------------------------------------------------------------------------- replay


def _compare(a: Any, b: Any, path: str, worst: list[float]) -> None:
    if isinstance(a, float) and isinstance(b, float):
        if not math.isclose(a, b, rel_tol=REPLAY_FLOAT_REL_TOL, abs_tol=0.0):
            raise EvidenceError(f"replay differs at {path}: {a!r} vs frozen {b!r}")
        if a != b:
            worst[0] = max(worst[0], abs(a - b) / max(abs(a), abs(b)))
        return
    if type(a) is not type(b):
        raise EvidenceError(f"replay differs at {path}: type {type(a).__name__} vs {type(b).__name__}")
    if isinstance(a, dict):
        if set(a) != set(b):
            raise EvidenceError(f"replay differs at {path}: keys {sorted(set(a) ^ set(b))}")
        for k in a:
            _compare(a[k], b[k], f"{path}/{k}", worst)
    elif isinstance(a, list):
        if len(a) != len(b):
            raise EvidenceError(f"replay differs at {path}: length {len(a)} vs {len(b)}")
        for i, (x, y) in enumerate(zip(a, b)):
            _compare(x, y, f"{path}[{i}]", worst)
    elif a != b:
        raise EvidenceError(f"replay differs at {path}: {a!r} vs frozen {b!r}")


def replay(summary: Mapping[str, Any], data_dir: Optional[str]) -> dict:
    """Recompute the summary from the weekly parquet when it is available; never reads 2020-2021."""
    path = stage_a_real.default_parquet_path(data_dir)
    if path is None or not path.is_file():
        return {"status": "not_run",
                "reason": f"{stage_a_real.PARQUET_NAME} not available (set ${stage_a_real.DATA_DIR_ENV}); "
                          "the frozen summary is used as committed by P1"}
    source = summary.get("source") or {}
    if path.name != source.get("file"):
        raise EvidenceError(f"summary describes {source.get('file')!r}, not {path.name!r}")
    sha = stage_a_real.sha256_file(path)
    if sha != source.get("sha256"):
        raise EvidenceError(f"{path.name} sha256 {sha} differs from the frozen summary's source "
                            f"{source.get('sha256')}; the summary does not describe this file")
    rows = stage_a_real.load_rows(path)  # pyarrow row filter excludes ISO 2020-2021; re-checked inside
    years_read = sorted({int(r["iso_year"]) for r in rows})
    if set(years_read) & set(SEALED_YEARS):
        raise EvidenceError("sealed ISO years reached the replay")
    sel = summary["selection"]
    recomputed = stage_a_real.run_stage_a(rows, c_min=sel["c_min"],
                                          attest_common_pairing=sel["common_pairing_attested"],
                                          source=source)
    recomputed = json.loads(json.dumps(recomputed, sort_keys=True, allow_nan=False))
    worst = [0.0]
    _compare(recomputed, json.loads(json.dumps(summary)), "", worst)
    return {
        "status": "reproduced",
        "parquet_file": path.name,
        "parquet_sha256": sha,
        "rows_loaded": len(rows),
        "iso_years_read": years_read,
        "sealed_years_read": [],
        "comparison": "integer counts, statuses and structure exact; floats within relative "
                      f"{REPLAY_FLOAT_REL_TOL:g} (summation order only)",
        "max_float_relative_difference": worst[0],
    }


# ---------------------------------------------------------------------------- contract export gap


def contract_export_gaps(summary: Mapping[str, Any]) -> dict:
    """Why no contract ComparisonResult / ClaimAuditRecord is emitted for this real-data summary."""
    mapping = load_mapping()
    reasons: list[str] = []
    if not mapping.get("registered"):
        reasons.append("P1-A status mapping (contracts/config/p1a_status_mapping.json) is not registered; "
                       "production export of contract statuses is refused")
    found = sorted({rec["applicability_status"]
                    for reg in summary["regions"].values() if "policies" in reg
                    for pol in reg["policies"].values()
                    for rec in pol["applicability"].values()})
    for status in found:
        if mapping["applicability"].get(status, "unknown") is None:
            reasons.append(f"P1 applicability status {status!r} has no agreed contract target; it is not "
                           "folded into missing_required_support, failed_applicability or out_of_domain")
    return {"contract_artifacts_emitted": [] if reasons else None,
            "status": "not_emitted" if reasons else "eligible_for_contract_export",
            "reasons": reasons, "p1_applicability_statuses": found}


# ---------------------------------------------------------------------------- interpretations


def _close(a: float, b: float) -> bool:
    return math.isclose(a, b, rel_tol=CONSISTENCY_REL_TOL, abs_tol=1e-15)


def _side(delta: float) -> str:
    return "mapped_above_aqua" if delta > 0 else "mapped_below_aqua" if delta < 0 else "equal"


def composition_fixture_interpretation(summary: Mapping[str, Any]) -> dict:
    fx = summary["composition_fixture_section_4b"]
    r1, r2 = fx["observed"]
    s1, s2 = fx["fixed_weight_0.5_0.5"]
    if not _close(fx["observed_pct_change"], 100.0 * (r2 - r1) / r1):
        raise EvidenceError("Section 4B fixture percent change does not match its rates")
    return {
        "counterexample_id": "geo_composition_shift_section_4b",
        "kind": "geographic_composition_shift",
        "data_kind": "plan_fixture_hand_computed",
        "source": "plan Section 4B fixture, computed by science.methods.stage_a_real.composition_counterexample",
        "label": f"Composition shift: observed {fx['observed_pct_change']:.2f}% with unchanged block rates",
        "blocks": [{"block_id": "high", "block_rate_r": 10.0}, {"block_id": "low", "block_rate_r": 1.0}],
        "observed_regional_index_R": [r1, r2],
        "observed_pct_change": fx["observed_pct_change"],
        "fixed_weights": {"high": 0.5, "low": 0.5},
        "fixed_weight_R_std": [s1, s2],
        "fixed_weight_pct_change": 100.0 * (s2 - s1) / s1,
        "identity_holds": fx["identity_holds"],
        "missing_block_result": fx["missing_block_result"],
        "missing_block_reasons": fx["missing_block_reasons"],
        "zero_support_result": fx["zero_support_result"],
        "zero_support_reasons": fx["zero_support_reasons"],
        "interpretation": (
            f"Block rates stay 10 and 1 per 1000 usable land-cell-days in both periods. Only the share of "
            f"usable observations moves (0.8/0.2 to 0.2/0.8), and the pooled index moves from {r1:g} to "
            f"{r2:g} ({fx['observed_pct_change']:.2f}%). Fixed 0.5/0.5 weights give {s1:g} in both periods. "
            "A missing or zero-support block makes the fixed-weight result unavailable; weights are never "
            "renormalized and missing is never zero."),
        "limits": ["Hand-computed fixture, not observed data.",
                   "Equal weights are illustrative, not a registered default; R_std is a different estimand."],
    }


def real_composition_interpretation(summary: Mapping[str, Any]) -> dict:
    comp = summary["composition_identity_real_own_support"]
    regions = summary["regions"]
    codes = sorted(regions, key=int)
    per_sensor: dict[str, Any] = {}
    holds = fails = unavailable = 0
    for key in sorted(comp):
        sensor, year = key.rsplit("_", 1)
        rec = comp[key]
        if rec["identity_holds"] is True:
            holds += 1
        elif rec["identity_holds"] is False:
            fails += 1
        else:
            unavailable += 1
        s = per_sensor.setdefault(sensor, {"years": {}})
        s["years"][year] = {"o_shares": rec["o_shares"], "blocks_sum_D": rec["blocks_sum_D"],
                            "blocks_sum_O": rec["blocks_sum_O"], "identity_holds": rec["identity_holds"]}
    first = codes[0]
    for sensor, s in per_sensor.items():
        shares = {y: v["o_shares"][first] for y, v in s["years"].items() if v["o_shares"][first] is not None}
        lo_y, hi_y = min(shares, key=shares.get), max(shares, key=shares.get)
        s["share_range_region"] = first
        s["share_min"], s["share_min_year"] = shares[lo_y], int(lo_y)
        s["share_max"], s["share_max_year"] = shares[hi_y], int(hi_y)
    name = regions[first]["name"]
    a, v = per_sensor.get("aqua"), per_sensor.get("viirs")
    ranges = "; ".join(f"{sensor}: {s['share_min']:.3f} ({s['share_min_year']}) to {s['share_max']:.3f} "
                       f"({s['share_max_year']})" for sensor, s in (("Aqua", a), ("VIIRS", v)) if s)
    n = holds + fails + unavailable
    return {
        "counterexample_id": "real_composition_shares_CA_BC_own_support",
        "kind": "geographic_composition_accounting",
        "data_kind": "real_data_descriptive",
        "source": "stage_a_summary.composition_identity_real_own_support",
        "label": f"{' + '.join(regions[c]['name'] for c in codes)}: usable-observation shares move between years",
        "regions": {c: regions[c]["name"] for c in codes},
        "per_sensor": per_sensor,
        "identity_counts": {"holds": holds, "fails": fails, "unavailable": unavailable, "sensor_years": n},
        "interpretation": (
            f"{name}'s share of the combined usable land-cell-days changes by year ({ranges}). A pooled "
            "two-region rate therefore weights the regions differently each year, which alone can move it "
            f"(plan Section 4B). The pooled-rate identity holds in {holds} of {n} sensor-years"
            + (f", fails in {fails}" if fails else "") + (f", unavailable in {unavailable}" if unavailable else "")
            + ". Each region was fitted separately; no union factor was fitted or evaluated."),
        "limits": ["Accounting check of summed counts, not a calibrated or evaluated union.",
                   "Shares are of usable land-cell-days in eligible weeks, not of fires or FIRMS points."],
    }


def equality_boundary_interpretation(summary: Mapping[str, Any], code: str, policy: str) -> dict:
    reg = summary["regions"][code]
    pol = reg["policies"][policy]
    base = {
        "counterexample_id": f"stage_a_equality_boundary_{code}_{policy}",
        "kind": "stage_a_equality_boundary",
        "data_kind": "real_data_descriptive",
        "source": f"stage_a_summary.regions.{code}.policies.{policy}",
        "region_code": code, "region_name": reg["name"], "policy": policy, "factor_name": pol["factor_name"],
        "factor_role": pol["role"],
        "effect_definition": ("Delta(a) = a*V - B; B = Aqua pooled rate, V = raw VIIRS pooled rate, both "
                              "1000*sum(D)/sum(O) over the same eligible weeks; a_break = B/V"),
    }
    variants = pol["variants"]
    unavailable = {vid: v for vid, v in variants.items() if v["status"] != "available"}
    if unavailable:
        reasons = sorted({r for v in unavailable.values() for r in v["reasons"]})
        return {**base, "status": "unavailable", "unavailable_variants": sorted(unavailable),
                "reasons": reasons, "periods": [],
                "label": f"{reg['name']}, {pol['factor_name']}: unavailable",
                "interpretation": (f"No equality-boundary reading for {pol['factor_name']}: "
                                   f"{len(unavailable)} of {len(variants)} registered variants are unavailable. "
                                   "Nothing is substituted, and a_H is not used in its place."),
                "limits": ["Unavailable is missing evidence, not a failed check."]}

    lo, hi = pol["variant_envelope"]
    periods = []
    blocks = [("development", "2019", pol["development_2019"])] + \
             [("applicability", y, rec) for y, rec in sorted(pol["applicability"].items())]
    for role, year, rec in blocks:
        B, V = rec["aqua"]["rate"], rec["viirs"]["rate"]
        if B is None or V is None or V <= 0:
            periods.append({"period": year, "role": role, "status": "unavailable",
                            "reason": "no usable support for one sensor"})
            continue
        a_break = B / V
        if rec["observed_ratio_A_over_V"] is not None and not _close(a_break, rec["observed_ratio_A_over_V"]):
            raise EvidenceError(f"{code}/{policy}/{year}: a_break disagrees with P1's observed ratio")
        rows = []
        for vid in ["raw"] + sorted(variants):
            bv = rec["by_variant"][vid]
            delta = bv["factor"] * V - B
            if not _close(delta, bv["pooled_error"]):
                raise EvidenceError(f"{code}/{policy}/{year}/{vid}: Delta(a) disagrees with P1's pooled_error")
            rows.append({"variant_id": vid, "factor": bv["factor"], "delta": delta, "side": _side(delta),
                         "pooled_relative_error": bv["pooled_relative_error"], "weekly_mae": bv["weekly_mae"]})
        sides = {r["side"] for r in rows if r["variant_id"] != "raw"}
        periods.append({
            "period": year, "role": role, "status": "available", "n_weeks": rec["n_weeks"],
            "excluded_weeks": rec.get("excluded_weeks"),
            "aqua_rate_B": B, "viirs_rate_V": V, "a_break": a_break,
            "a_break_inside_variant_envelope": lo <= a_break <= hi,
            "registered_variants_side": next(iter(sides)) if len(sides) == 1 else "straddle_equality",
            "raw_side": rows[0]["side"], "by_variant": rows,
            "applicability_status": rec.get("applicability_status"),
            "applicability_passed": rec.get("applicability_passed"),
        })
    avail = [p for p in periods if p["status"] == "available"]
    count = lambda key, val: sum(1 for p in avail if p[key] == val)
    above, below = count("registered_variants_side", "mapped_above_aqua"), count("registered_variants_side", "mapped_below_aqua")
    straddle = count("registered_variants_side", "straddle_equality")
    outside = sum(1 for p in avail if not p["a_break_inside_variant_envelope"])
    raw_below = count("raw_side", "mapped_below_aqua")
    n = len(avail)
    return {
        **base, "status": "available", "variant_envelope": [lo, hi],
        "variant_envelope_note": pol["variant_envelope_note"], "periods": periods,
        "counts": {"periods": n, "a_break_outside_envelope": outside, "variants_above": above,
                   "variants_below": below, "variants_straddle": straddle, "raw_below": raw_below},
        "label": f"{reg['name']}, {pol['factor_name']}: equality value outside the variant range in {outside} of {n} periods",
        "interpretation": (
            f"{reg['name']}, {policy.replace('_', '-')} {pol['factor_name']}: the registered variants span "
            f"{lo:.4f} to {hi:.4f}. The factor that would make mapped VIIRS equal Aqua (a_break = B/V) lies "
            f"outside that span in {outside} of {n} periods (2019 development, 2022-2025 applicability). "
            f"Every variant maps VIIRS above Aqua in {above}, below in {below}, and the variants straddle "
            f"equality in {straddle}. Without a correction (a = 1) VIIRS is below Aqua in {raw_below} of {n}."),
        "limits": [
            "Descriptive. No applicability criterion is registered, so 2022-2025 stay insufficient_evidence: "
            "neither passed nor failed.",
            "The variant span is a leave-one-year-out sensitivity set, not a confidence interval or physical bound.",
            "Rates are fire-cell-days per 1000 usable land-cell-days, not fire counts or FIRMS points.",
            "inference_status: not_established.",
        ],
    }


def counterexample_interpretations(summary: Mapping[str, Any]) -> list[dict]:
    out = [composition_fixture_interpretation(summary), real_composition_interpretation(summary)]
    for code in sorted(summary["regions"], key=int):
        reg = summary["regions"][code]
        if "policies" not in reg:
            out.append({"counterexample_id": f"stage_a_equality_boundary_{code}", "kind": "stage_a_equality_boundary",
                        "data_kind": "real_data_descriptive", "region_code": code, "region_name": reg["name"],
                        "status": "unavailable", "reasons": [reg.get("reason", "region unavailable")], "periods": []})
            continue
        for policy in ("own_support", "common_support"):
            out.append(equality_boundary_interpretation(summary, code, policy))
    return out


# ---------------------------------------------------------------------------- document and bundle


def build_evidence(summary: dict, summary_sha256: str, summary_ref: str, replay_info: dict) -> dict:
    refuse_sealed_content(summary)
    return {
        "evidence_format": EVIDENCE_FORMAT,
        "evidence_id": EVIDENCE_ID,
        "contract_version_installed": CONTRACT_VERSION,
        "data_kind": "real_data",
        "release_status": "not_released: P1/P2 claim approval and P5 verification required before public use",
        "unit": summary["unit"],
        "stage_a_summary_ref": {"path": summary_ref, "sha256": summary_sha256,
                                "summary_id": summary["summary_id"], "module_version": summary["module_version"],
                                "parquet_source": summary["source"]},
        "replay": replay_info,
        "status_dimensions": summary["status_dimensions"],
        "contract_export": contract_export_gaps(summary),
        "counterexample_interpretations": counterexample_interpretations(summary),
        "stage_a_summary": summary,
    }


def _summary_ref(path: Path) -> str:
    try:
        return Path(path).resolve().relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return Path(path).name


def build_bundle(summary_path: Path = DEFAULT_SUMMARY, *, data_dir: Optional[str] = None,
                 run_replay: bool = True, bundle_version: str = "stage-a-real-CA-BC-1") -> Bundle:
    summary, sha = load_summary(summary_path)
    refuse_sealed_content(summary)
    info = replay(summary, data_dir) if run_replay else {"status": "not_run", "reason": "--no-replay"}
    doc = build_evidence(summary, sha, _summary_ref(summary_path), info)
    bundle = Bundle(bundle_version=bundle_version, data_classification="production")
    bundle.add_evidence(EVIDENCE_ID, doc)
    return bundle


def main(argv: Optional[Sequence[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--summary", type=Path, default=DEFAULT_SUMMARY)
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    ap.add_argument("--data-dir", default=None, help=f"default ${stage_a_real.DATA_DIR_ENV}")
    ap.add_argument("--bundle-version", default="stage-a-real-CA-BC-1")
    ap.add_argument("--no-replay", action="store_true")
    ap.add_argument("--no-gzip", action="store_true")
    ap.add_argument("--replace", action="store_true",
                    help="remove --out first, only if it already holds a bundle (bundle_index.json)")
    args = ap.parse_args(argv)
    try:
        if args.replace and args.out.exists():
            if not (args.out / INDEX_NAME).is_file():
                raise BundleError(f"{args.out} is not a bundle directory; refusing to remove it")
            shutil.rmtree(args.out)
        bundle = build_bundle(args.summary, data_dir=args.data_dir, run_replay=not args.no_replay,
                              bundle_version=args.bundle_version)
        bundle.write(args.out, gzip_copies=not args.no_gzip)
        index = verify_bundle(args.out)
    except BundleError as exc:
        print(f"bundle refused: {exc}", file=sys.stderr)
        return 2
    [ev] = index["evidence_entries"]
    doc = json.loads((args.out / ev["path"]).read_text(encoding="utf-8"))
    print(json.dumps({"out": str(args.out), "evidence": ev["path"], "replay": doc["replay"]["status"],
                      "counterexample_interpretations": [c["counterexample_id"]
                                                         for c in doc["counterexample_interpretations"]],
                      "contract_export": doc["contract_export"]["status"], **index["size_report"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
