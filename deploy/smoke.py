"""Local smoke check and local fallback server for the static site.

    python -m deploy.smoke --site deploy/dist          (check, then exit)
    python -m deploy.smoke --site deploy/dist --serve  (local fallback, 127.0.0.1 only)

The server binds to 127.0.0.1 only; no public port is opened. The check fetches every page
and bundle file over HTTP, verifies sha256 and sizes against bundle_index.json, measures
fetch times, and checks that the pages reference no server API or third-party origin.
"""
from __future__ import annotations

import argparse
import functools
import hashlib
import http.server
import json
import re
import threading
import time
import urllib.request
from pathlib import Path

from deploy.build_site import SKELETON_MARKER

LOOPBACK = "127.0.0.1"
FORBIDDEN = [re.compile(p) for p in (r"https?://(?!127\.0\.0\.1)", r"/api/", r"\bws://", r"\bwss://")]


class _Quiet(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *args) -> None:  # keep test output clean
        pass


def start_server(site: Path, port: int = 0) -> http.server.ThreadingHTTPServer:
    handler = functools.partial(_Quiet, directory=str(site))
    server = http.server.ThreadingHTTPServer((LOOPBACK, port), handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server


def _get(url: str) -> tuple[bytes, float]:
    t0 = time.perf_counter()
    with urllib.request.urlopen(url, timeout=10) as r:  # noqa: S310 - loopback URL built here
        body = r.read()
    return body, time.perf_counter() - t0


def smoke(site: Path) -> dict:
    site = Path(site)
    server = start_server(site)
    base = f"http://{LOOPBACK}:{server.server_address[1]}"
    problems: list[str] = []
    timings: dict[str, float] = {}
    try:
        for page in ("index.html", "app.js", "style.css"):
            body, dt = _get(f"{base}/{page}")
            timings[page] = dt
            text = body.decode("utf-8")
            for pat in FORBIDDEN:
                if pat.search(text):
                    problems.append(f"{page} references {pat.pattern}")
        if SKELETON_MARKER not in (site / "index.html").read_text(encoding="utf-8"):
            problems.append("index.html is missing the skeleton label")
        raw, dt = _get(f"{base}/bundle/bundle_index.json")
        timings["bundle/bundle_index.json"] = dt
        index = json.loads(raw)
        total_gz = 0
        t_all = time.perf_counter()
        for e in index["entries"]:
            body, _ = _get(f"{base}/bundle/{e['path']}")
            if hashlib.sha256(body).hexdigest() != e["sha256"] or len(body) != e["bytes"]:
                problems.append(f"{e['path']}: served bytes differ from the index")
            if e.get("gzip_path"):
                gz, _ = _get(f"{base}/bundle/{e['gzip_path']}")
                total_gz += len(gz)
        timings["all_bundle_files"] = time.perf_counter() - t_all
        if index["size_report"]["total_gzip_bytes"] != total_gz:
            problems.append("served gzip total differs from the size report")
        if index["data_classification"] != "production" and not (index.get("label") or "").startswith(
                "[SYNTHETIC DEV FIXTURE]"):
            problems.append("a non-production bundle must carry the synthetic label")
    finally:
        server.shutdown()
        server.server_close()
    return {
        "ok": not problems,
        "problems": problems,
        "served_gzip_bytes": total_gz,
        "p0_target_bytes": index["size_report"]["p0_compressed_target_bytes"],
        "within_p0_target": total_gz <= index["size_report"]["p0_compressed_target_bytes"],
        "loopback_fetch_seconds": {k: round(v, 4) for k, v in timings.items()},
        "note": "Loopback timings only; they are not a measure of public network load time.",
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--site", type=Path, required=True)
    ap.add_argument("--serve", action="store_true")
    ap.add_argument("--port", type=int, default=8000)
    args = ap.parse_args(argv)
    if args.serve:
        server = start_server(args.site, args.port)
        print(f"local fallback at http://{LOOPBACK}:{server.server_address[1]}/ (Ctrl+C to stop)")
        try:
            threading.Event().wait()
        except KeyboardInterrupt:
            server.shutdown()
        return 0
    report = smoke(args.site)
    print(json.dumps(report, indent=2))
    return 0 if report["ok"] and report["within_p0_target"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
