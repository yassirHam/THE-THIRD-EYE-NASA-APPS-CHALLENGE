"""Assemble the static skeleton: site files + a verified bundle, no backend.

    python -m deploy.build_site --out deploy/dist            (synthetic development bundle)

The output directory must be new or empty. Nothing is deployed or published here.
"""
from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

from artifact_pipeline.build import P0_SYNTHETIC_SET, load_files
from artifact_pipeline.bundle import Bundle, verify_bundle

ROOT = Path(__file__).resolve().parents[1]
SITE = Path(__file__).resolve().parent / "site"
FIXTURES = ROOT / "contracts" / "fixtures"
SKELETON_MARKER = "SKELETON - NOT SCIENTIFICALLY VALIDATED"


def build_site(out: Path, bundle_version: str = "synthetic-dev-1") -> dict:
    out = Path(out)
    if out.exists() and any(out.iterdir()):
        raise SystemExit(f"{out} is not empty")
    out.mkdir(parents=True, exist_ok=True)
    for f in SITE.iterdir():
        shutil.copy2(f, out / f.name)
    if SKELETON_MARKER not in (out / "index.html").read_text(encoding="utf-8"):
        raise SystemExit("index.html lost its skeleton label")
    bundle = Bundle(bundle_version=bundle_version, data_classification="synthetic_dev_fixture")
    load_files(FIXTURES, P0_SYNTHETIC_SET, bundle)
    bundle.write(out / "bundle")
    return verify_bundle(out / "bundle")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", type=Path, default=Path(__file__).resolve().parent / "dist")
    ap.add_argument("--bundle-version", default="synthetic-dev-1")
    args = ap.parse_args(argv)
    index = build_site(args.out, args.bundle_version)
    print(json.dumps(index["size_report"], indent=2))
    return 0 if index["size_report"]["within_p0_target"] else 3


if __name__ == "__main__":
    raise SystemExit(main())
