"""Build the static bundle from a directory of contract JSON artifacts.

    python -m artifact_pipeline.build --src contracts/fixtures --out build/bundle \
        --bundle-version synthetic-dev-1 --classification synthetic_dev_fixture [--files a.json ...]

Every input file is validated against the contract family inferred from its file name
prefix (as in contracts/fixtures). Without --files, the coherent synthetic P0 set below is
used: the contract fixture directory also holds alternative variants that share one identity
on purpose (for example several comparison edge cases), and an immutable bundle holds one
payload per identity. The command prints the size report.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .bundle import MODEL_BY_FAMILY, Bundle, BundleError, verify_bundle

PREFIXES = {
    "sample_calendar": "calendar",
    "sample_comparison": "comparison",
    "sample_claim_audit": "claim_audit",
    "sample_evaluation": "evaluation",
    "sample_region_selector": "region_selector",
    "sample_firms": "firms_hotspots",
    "sample_manifest": "manifest",
}


def family_for(path: Path) -> str:
    for prefix, family in PREFIXES.items():
        if path.stem.startswith(prefix):
            return family
    raise BundleError(f"cannot tell the artifact family of {path.name}")


# One artifact per family with mutually consistent identities (synthetic, contract 1.4.0).
P0_SYNTHETIC_SET = (
    "sample_calendar.json",
    "sample_manifest.json",
    "sample_region_selector.json",
    "sample_comparison_normal.json",
    "sample_claim_audit_record.json",
    "sample_evaluation_summary.json",
    "sample_firms_hotspots.json",
)


def load_files(src: Path, names: tuple[str, ...] | list[str], bundle: Bundle) -> None:
    for name in names:
        path = Path(src) / name
        model = MODEL_BY_FAMILY[family_for(path)].model_validate_json(path.read_text(encoding="utf-8"))
        bundle.add(model)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--src", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--bundle-version", required=True)
    ap.add_argument("--classification", required=True, choices=["synthetic_dev_fixture", "production"])
    ap.add_argument("--no-gzip", action="store_true")
    ap.add_argument("--files", nargs="+", default=list(P0_SYNTHETIC_SET))
    args = ap.parse_args(argv)
    bundle = Bundle(bundle_version=args.bundle_version, data_classification=args.classification)
    try:
        load_files(args.src, args.files, bundle)
        bundle.write(args.out, gzip_copies=not args.no_gzip)
        index = verify_bundle(args.out)
    except BundleError as exc:
        print(f"bundle refused: {exc}", file=sys.stderr)
        return 2
    print(json.dumps({"entries": len(index["entries"]), **index["size_report"]}, indent=2))
    if index["size_report"]["within_p0_target"] is False:
        print("compressed size exceeds the 10 MB P0 target", file=sys.stderr)
        return 3
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
