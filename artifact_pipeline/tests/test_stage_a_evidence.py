"""P4-A Stage A real-data evidence: P1 frozen summary -> static bundle evidence document.

Most tests use only the committed frozen summary (no parquet, no sealed data). The replay test
runs only when $THE_THIRD_EYE_DATA_DIR holds focus_weekly_CA_BC.parquet, and reads it only through
science.methods.stage_a_real.load_rows, which filters ISO years 2020-2021 out before rows load.
"""
from __future__ import annotations

import copy
import json
import math
from pathlib import Path

import pytest

from artifact_pipeline import stage_a_evidence as sae
from artifact_pipeline.bundle import INDEX_NAME, Bundle, BundleError, verify_bundle
from science.methods import stage_a_real

SUMMARY, SUMMARY_SHA = sae.load_summary(sae.DEFAULT_SUMMARY)


def doc(summary: dict | None = None, replay: dict | None = None) -> dict:
    return sae.build_evidence(copy.deepcopy(summary or SUMMARY), SUMMARY_SHA, "frozen.json",
                              replay or {"status": "not_run", "reason": "test"})


def by_id(d: dict) -> dict:
    return {c["counterexample_id"]: c for c in d["counterexample_interpretations"]}


# ------------------------------------------------------------------ content


def test_interpretations_are_populated_for_every_region_and_policy() -> None:
    ids = set(by_id(doc()))
    assert {"geo_composition_shift_section_4b", "real_composition_shares_CA_BC_own_support"} <= ids
    for code in ("3218", "826"):
        for policy in ("own_support", "common_support"):
            assert f"stage_a_equality_boundary_{code}_{policy}" in ids
    for c in doc()["counterexample_interpretations"]:
        assert c["interpretation"] and c["data_kind"] in ("plan_fixture_hand_computed", "real_data_descriptive")


def test_section_4b_fixture_numbers_come_from_the_summary() -> None:
    c = by_id(doc())["geo_composition_shift_section_4b"]
    assert c["observed_regional_index_R"] == [8.2, 2.8]
    assert math.isclose(c["observed_pct_change"], -65.85365853658537)
    assert c["fixed_weight_R_std"] == [5.5, 5.5] and c["fixed_weight_pct_change"] == 0.0
    assert c["missing_block_result"] is None and c["zero_support_result"] is None  # never zero-filled


def test_equality_boundary_matches_p1_numbers() -> None:
    d = doc()
    for code in ("3218", "826"):
        c = by_id(d)[f"stage_a_equality_boundary_{code}_own_support"]
        pol = SUMMARY["regions"][code]["policies"]["own_support"]
        assert c["variant_envelope"] == pol["variant_envelope"]
        assert [p["period"] for p in c["periods"]] == ["2019", "2022", "2023", "2024", "2025"]
        for p in c["periods"]:
            src = pol["development_2019"] if p["period"] == "2019" else pol["applicability"][p["period"]]
            assert math.isclose(p["a_break"], src["observed_ratio_A_over_V"], rel_tol=1e-12)
            for row in p["by_variant"]:
                assert math.isclose(row["delta"], src["by_variant"][row["variant_id"]]["pooled_error"],
                                    rel_tol=1e-9, abs_tol=1e-15)
            lo, hi = pol["variant_envelope"]
            assert p["a_break_inside_variant_envelope"] == (lo <= p["a_break"] <= hi)
            if p["role"] == "applicability":
                # P1 status carried unchanged: insufficient evidence is neither passed nor failed.
                assert (p["applicability_status"], p["applicability_passed"]) == ("insufficient_evidence", None)
                assert src["descriptive_ratio_inside_variant_envelope"] == p["a_break_inside_variant_envelope"]


def test_common_support_without_pairing_attestation_is_unavailable_not_substituted() -> None:
    for code in ("3218", "826"):
        c = by_id(doc())[f"stage_a_equality_boundary_{code}_common_support"]
        assert c["status"] == "unavailable" and c["periods"] == []
        assert any("pairing_validated=False" in r for r in c["reasons"])
        assert "variant_envelope" not in c


def test_summary_is_carried_verbatim_and_inference_not_established() -> None:
    d = doc()
    assert d["stage_a_summary"] == SUMMARY
    assert d["status_dimensions"]["inference_status"] == "not_established"
    assert d["stage_a_summary_ref"]["sha256"] == SUMMARY_SHA
    assert "not fire counts" in d["unit"]


def test_no_contract_artifact_is_emitted_while_mapping_is_unregistered() -> None:
    gap = doc()["contract_export"]
    assert gap["status"] == "not_emitted" and gap["contract_artifacts_emitted"] == []
    assert any("not registered" in r for r in gap["reasons"])
    assert any("insufficient_evidence" in r for r in gap["reasons"])


def test_real_composition_is_an_accounting_check_only() -> None:
    c = by_id(doc())["real_composition_shares_CA_BC_own_support"]
    assert c["identity_counts"] == {"holds": 16, "fails": 0, "unavailable": 0, "sensor_years": 16}
    assert "no union factor" in c["interpretation"]


def test_inconsistent_summary_numbers_are_refused() -> None:
    bad = copy.deepcopy(SUMMARY)
    bad["regions"]["3218"]["policies"]["own_support"]["applicability"]["2022"]["by_variant"]["ex_2016"][
        "pooled_error"] *= -1
    with pytest.raises(sae.EvidenceError, match="pooled_error"):
        doc(bad)


# ------------------------------------------------------------------ sealed guards


@pytest.mark.parametrize("mutate", [
    lambda s: s["regions"]["3218"]["eligible_weeks_by_year"].__setitem__("2020", 52),
    lambda s: s["composition_identity_real_own_support"].__setitem__("aqua_2021", {}),
    lambda s: s["regions"]["826"]["policies"]["own_support"]["variants"]["ex_2016"]["training_years"].append(2020),
    lambda s: s["splits"].__setitem__("sealed_not_read", []),
    lambda s: s["status_dimensions"].__setitem__("inference_status", "supported"),
], ids=["sealed-year-key", "sealed-composition-key", "sealed-training-year", "no-sealed-declaration",
        "inference-upgraded"])
def test_sealed_or_upgraded_content_is_refused(mutate) -> None:
    bad = copy.deepcopy(SUMMARY)
    mutate(bad)
    with pytest.raises(sae.EvidenceError):
        sae.refuse_sealed_content(bad)


def test_parquet_with_another_hash_is_refused_before_rows_are_read(tmp_path: Path, monkeypatch) -> None:
    (tmp_path / stage_a_real.PARQUET_NAME).write_bytes(b"not the frozen source")
    monkeypatch.setattr(stage_a_real, "load_rows", lambda p: pytest.fail("rows must not be read"))
    with pytest.raises(sae.EvidenceError, match="sha256"):
        sae.replay(SUMMARY, str(tmp_path))


def test_absent_parquet_means_replay_not_run(tmp_path: Path) -> None:
    info = sae.replay(SUMMARY, str(tmp_path))
    assert info["status"] == "not_run" and stage_a_real.PARQUET_NAME in info["reason"]


_PARQUET = stage_a_real.default_parquet_path()


@pytest.mark.skipif(_PARQUET is None or not _PARQUET.is_file(), reason="weekly parquet not available")
def test_replay_reproduces_the_frozen_summary_without_sealed_years() -> None:
    info = sae.replay(SUMMARY, None)
    assert info["status"] == "reproduced" and info["sealed_years_read"] == []
    assert not set(info["iso_years_read"]) & {2020, 2021}
    assert info["rows_loaded"] == SUMMARY["selection"]["rows_loaded"]


# ------------------------------------------------------------------ bundle


def test_bundle_write_verify_and_determinism(tmp_path: Path) -> None:
    for name in ("a", "b"):
        sae.build_bundle(run_replay=False).write(tmp_path / name)
    files = lambda d: {p.relative_to(d): p.read_bytes() for p in d.rglob("*") if p.is_file()}
    assert files(tmp_path / "a") == files(tmp_path / "b")
    index = verify_bundle(tmp_path / "a")
    [ev] = index["evidence_entries"]
    assert ev["path"].startswith("evidence/") and index["entries"] == []
    assert index["size_report"]["combined_gzip_bytes"] == ev["gzip_bytes"]
    assert index["size_report"]["within_p0_target"] is True
    written = json.loads((tmp_path / "a" / ev["path"]).read_text(encoding="utf-8"))
    assert written["counterexample_interpretations"] and written["replay"]["status"] == "not_run"


def test_verify_detects_tampered_evidence(tmp_path: Path) -> None:
    index = sae.build_bundle(run_replay=False).write(tmp_path / "b")
    p = tmp_path / "b" / index["evidence_entries"][0]["path"]
    p.write_bytes(p.read_bytes().replace(b"insufficient_evidence", b"applicable_evidence__", 1))
    with pytest.raises(BundleError, match="evidence hash"):
        verify_bundle(tmp_path / "b")


def test_duplicate_or_unknown_evidence_is_refused() -> None:
    b = Bundle(bundle_version="v", data_classification="production")
    b.add_evidence(sae.EVIDENCE_ID, doc())
    with pytest.raises(BundleError, match="already"):
        b.add_evidence(sae.EVIDENCE_ID, doc())
    with pytest.raises(BundleError, match="format"):
        b.add_evidence("x", {"evidence_format": "other", "evidence_id": "x"})


def test_cli_replace_only_removes_a_previous_bundle(tmp_path: Path, capsys) -> None:
    out = tmp_path / "bundle"
    assert sae.main(["--out", str(out), "--no-replay"]) == 0
    assert sae.main(["--out", str(out), "--no-replay"]) == 2  # refuses a non-empty directory
    assert sae.main(["--out", str(out), "--no-replay", "--replace"]) == 0
    assert (out / INDEX_NAME).is_file()
    other = tmp_path / "not_a_bundle"
    other.mkdir()
    (other / "keep.txt").write_text("x")
    assert sae.main(["--out", str(other), "--no-replay", "--replace"]) == 2
    assert (other / "keep.txt").exists()
    report = json.loads(capsys.readouterr().out.split("\n}\n")[0] + "\n}")
    assert report["contract_export"] == "not_emitted"
