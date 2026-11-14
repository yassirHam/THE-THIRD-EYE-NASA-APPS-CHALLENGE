"""P4-C static skeleton tests (synthetic bundle, loopback only)."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from deploy.build_site import SKELETON_MARKER, build_site
from deploy.smoke import FORBIDDEN, LOOPBACK, smoke, start_server

SITE_SRC = Path(__file__).resolve().parents[1] / "site"


@pytest.fixture()
def site(tmp_path: Path) -> Path:
    build_site(tmp_path / "site")
    return tmp_path / "site"


def test_built_site_passes_the_smoke_check(site: Path) -> None:
    report = smoke(site)
    assert report["ok"], report["problems"]
    assert report["within_p0_target"] is True
    assert report["served_gzip_bytes"] > 0


def test_skeleton_is_labelled_not_validated() -> None:
    html = (SITE_SRC / "index.html").read_text(encoding="utf-8")
    assert SKELETON_MARKER in html
    assert "no result is shown" in html


def test_site_sources_reference_no_backend_or_third_party() -> None:
    for f in SITE_SRC.iterdir():
        text = f.read_text(encoding="utf-8")
        for pat in FORBIDDEN:
            assert not pat.search(text), (f.name, pat.pattern)


def test_first_screen_has_no_internal_schema_terms() -> None:
    html = (SITE_SRC / "index.html").read_text(encoding="utf-8")
    for term in ("coverage_state", "applicability_status", "sensitivity_status", "geometry_id",
                 "method_id", "policy_id", "not_established", "out_of_domain"):
        assert term not in html


def test_smoke_detects_a_tampered_file(site: Path) -> None:
    index = json.loads((site / "bundle" / "bundle_index.json").read_text(encoding="utf-8"))
    target = site / "bundle" / index["entries"][0]["path"]
    target.write_bytes(target.read_bytes() + b" ")
    report = smoke(site)
    assert not report["ok"] and any("differ" in p for p in report["problems"])


def test_smoke_detects_a_missing_label(site: Path) -> None:
    html = site / "index.html"
    html.write_text(html.read_text(encoding="utf-8").replace(SKELETON_MARKER, "Welcome"), encoding="utf-8")
    assert not smoke(site)["ok"]


def test_server_binds_loopback_only(site: Path) -> None:
    server = start_server(site)
    try:
        assert server.server_address[0] == LOOPBACK
    finally:
        server.shutdown()
        server.server_close()


def test_build_refuses_a_non_empty_directory(tmp_path: Path) -> None:
    (tmp_path / "x").mkdir()
    (tmp_path / "x" / "old.txt").write_text("old")
    with pytest.raises(SystemExit):
        build_site(tmp_path / "x")
