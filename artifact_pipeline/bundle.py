"""Deterministic, content-addressed static JSON bundle for the judge site (P4-A).

Input: contract 1.4.0 artifacts (validated Pydantic models). Output: a directory of
immutable JSON files (plus optional .json.gz) and `bundle_index.json`, with sha256 hashes
and measured sizes. No backend is needed to serve it.

Guards (fail closed):
- Every artifact is re-validated from its own serialized JSON before it is written.
- Files are addressed by the full five-field identity (artifact_version, geometry_id,
  period_spec, method_id, policy_id) plus the artifact family. Lookups require all five
  fields, so one area can never be served another area's factor, baseline or cache.
- One identity + family maps to one content hash; a different payload for the same key
  is refused (immutability).
- A bundle is either synthetic or production. Production bundles refuse synthetic
  artifacts and synthetic footprint certifications; synthetic bundles are labelled.
- Comparisons are served only for region options whose access is evaluated_comparison
  with the same method, policy and period. raw_only areas never inherit a comparison.
- A manifest must describe an artifact present in the bundle (assert_manifest_describes).
- FIRMS point artifacts live in a separate `firms/` subtree and are never indexed as
  grid artifacts.
- Production calendars must declare a registered sealed window (contract rule); in addition
  the bundle refuses any production calendar record dated inside that window that carries
  data, so sealed observations cannot reach a public bundle.
- Missing, failed and out-of-domain states are carried exactly as the contract stores them;
  the pipeline never rewrites values.
"""
from __future__ import annotations

import gzip
import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
from typing import Iterable, Optional

from pydantic import BaseModel

from contracts.schemas.calendar import month_bounds
from contracts.schemas import (
    CONTRACT_VERSION,
    CacheKey,
    CalendarArtifact,
    ClaimAuditRecord,
    ComparisonResult,
    EvaluationSummary,
    FirmsHotspotArtifact,
    ProvenanceManifest,
    RegionSelectorArtifact,
    assert_cache_key_match,
    assert_manifest_describes,
)

P0_COMPRESSED_TARGET_BYTES = 10 * 1024 * 1024  # plan: at most 10 MB compressed initial artifacts
INDEX_NAME = "bundle_index.json"
BUNDLE_FORMAT = "tte-static-bundle-v1"

FAMILIES: dict[type, str] = {
    CalendarArtifact: "calendar",
    ComparisonResult: "comparison",
    ClaimAuditRecord: "claim_audit",
    EvaluationSummary: "evaluation",
    RegionSelectorArtifact: "region_selector",
    FirmsHotspotArtifact: "firms_hotspots",
    ProvenanceManifest: "manifest",
}
MODEL_BY_FAMILY = {v: k for k, v in FAMILIES.items()}


class BundleError(ValueError):
    """The bundle would violate a contract or release guard."""


def canonical_json(model: BaseModel) -> bytes:
    """Stable bytes: sorted keys, no whitespace, UTF-8."""
    return json.dumps(model.model_dump(mode="json"), sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False).encode("utf-8")


def _safe_segment(value: str) -> str:
    if not value or value in (".", "..") or any(c in value for c in '/\\:*?"<>|') or value.strip() != value:
        raise BundleError(f"identity value {value!r} cannot be used as a path segment")
    return value


@dataclass(frozen=True)
class BundleEntry:
    family: str
    cache_key: dict
    cache_key_digest: str
    path: str
    sha256: str
    bytes: int
    gzip_path: Optional[str]
    gzip_bytes: Optional[int]
    data_classification: str


@dataclass
class Bundle:
    bundle_version: str
    data_classification: str  # "synthetic_dev_fixture" | "production"
    entries: list[BundleEntry] = field(default_factory=list)
    _payloads: dict[str, bytes] = field(default_factory=dict, repr=False)
    _models: dict[tuple[str, str], BaseModel] = field(default_factory=dict, repr=False)

    # ------------------------------------------------------------- building

    def add(self, model: BaseModel) -> BundleEntry:
        family = FAMILIES.get(type(model))
        if family is None:
            raise BundleError(f"{type(model).__name__} is not a contract artifact family")
        if model.contract_version != CONTRACT_VERSION:  # type: ignore[attr-defined]
            raise BundleError(f"artifact contract {model.contract_version} != {CONTRACT_VERSION}")  # type: ignore[attr-defined]
        if model.data_classification != self.data_classification:  # type: ignore[attr-defined]
            raise BundleError(f"a {self.data_classification} bundle cannot hold a "
                              f"{model.data_classification} artifact")  # type: ignore[attr-defined]
        payload = canonical_json(model)
        type(model).model_validate_json(payload)  # the written bytes must themselves validate
        if isinstance(model, CalendarArtifact) and self.data_classification == "production":
            _refuse_sealed_records(model)
        key: CacheKey = model.cache_key()  # type: ignore[attr-defined]
        digest = key.digest()
        slot = (family, digest)
        sha = hashlib.sha256(payload).hexdigest()
        if slot in self._models:
            existing = hashlib.sha256(canonical_json(self._models[slot])).hexdigest()
            if existing != sha:
                raise BundleError(f"{family} for this identity already has different content; "
                                  "artifacts are immutable, bump artifact_version instead")
            return next(e for e in self.entries if (e.family, e.cache_key_digest) == slot)
        root = "firms" if family == "firms_hotspots" else "artifacts"
        parts = [root] + [_safe_segment(getattr(key, n)) for n in
                          ("artifact_version", "geometry_id", "method_id", "policy_id", "period_spec")]
        path = str(PurePosixPath(*parts, f"{family}.{sha[:16]}.json"))
        entry = BundleEntry(family=family, cache_key=key.model_dump(), cache_key_digest=digest, path=path,
                            sha256=sha, bytes=len(payload), gzip_path=None, gzip_bytes=None,
                            data_classification=self.data_classification)
        self._models[slot] = model
        self._payloads[path] = payload
        self.entries.append(entry)
        return entry

    def get(self, family: str, requested: CacheKey) -> BaseModel:
        """Serve an artifact only for an exact five-field match."""
        model = self._models.get((family, requested.digest()))
        if model is None:
            raise BundleError(f"no {family} artifact for this exact identity; nothing is inherited")
        assert_cache_key_match(requested, model)  # type: ignore[arg-type]
        return model

    # ------------------------------------------------------------- checks

    def check(self) -> None:
        """Cross-artifact guards that need the whole bundle."""
        selectors = [m for (f, _), m in self._models.items() if f == "region_selector"]
        comparisons = [m for (f, _), m in self._models.items() if f == "comparison"]
        for comp in comparisons:
            option = None
            for sel in selectors:
                for opt in sel.options:  # type: ignore[attr-defined]
                    if opt.geometry_id == comp.geometry_id:  # type: ignore[attr-defined]
                        option = opt
            if option is None:
                raise BundleError(f"comparison for {comp.geometry_id} has no region option")  # type: ignore[attr-defined]
            if option.comparison_access_status != "evaluated_comparison":
                raise BundleError(f"{comp.geometry_id} is {option.comparison_access_status}; it cannot be "  # type: ignore[attr-defined]
                                  "served a comparison (no inherited factors)")
            evaluated = (option.evaluated_method_id, option.evaluated_policy_id, option.evaluated_period_spec)
            if evaluated != (comp.method_id, comp.policy_id, comp.period_spec):  # type: ignore[attr-defined]
                raise BundleError(f"comparison for {comp.geometry_id} does not match the area's evaluated "  # type: ignore[attr-defined]
                                  "method, policy and period")
        for (f, _), man in self._models.items():
            if f != "manifest":
                continue
            target = man.described_artifact_type  # type: ignore[attr-defined]
            described = self._models.get((target, man.cache_key().digest()))  # type: ignore[attr-defined]
            if described is None:
                raise BundleError(f"manifest describes a {target} that is not in the bundle")
            assert_manifest_describes(man, described, target)  # type: ignore[arg-type]

    # ------------------------------------------------------------- writing

    def write(self, out_dir: Path, *, gzip_copies: bool = True) -> dict:
        self.check()
        out_dir = Path(out_dir)
        if out_dir.exists() and any(out_dir.iterdir()):
            raise BundleError(f"{out_dir} is not empty; bundles are written to a fresh directory")
        written: list[BundleEntry] = []
        for entry in self.entries:
            payload = self._payloads[entry.path]
            target = out_dir / entry.path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(payload)
            gz_path = gz_bytes = None
            if gzip_copies:
                gz = gzip.compress(payload, compresslevel=9, mtime=0)
                gz_path = entry.path + ".gz"
                (out_dir / gz_path).write_bytes(gz)
                gz_bytes = len(gz)
            written.append(BundleEntry(**{**entry.__dict__, "gzip_path": gz_path, "gzip_bytes": gz_bytes}))
        self.entries = written
        index = self.index()
        (out_dir / INDEX_NAME).write_bytes(json.dumps(index, indent=2, sort_keys=True).encode("utf-8") + b"\n")
        return index

    def index(self) -> dict:
        total = sum(e.bytes for e in self.entries)
        compressed = [e.gzip_bytes for e in self.entries]
        total_gz = sum(compressed) if all(c is not None for c in compressed) else None
        return {
            "bundle_format": BUNDLE_FORMAT,
            "bundle_version": self.bundle_version,
            "contract_version": CONTRACT_VERSION,
            "data_classification": self.data_classification,
            "label": ("[SYNTHETIC DEV FIXTURE] not scientifically validated"
                      if self.data_classification == "synthetic_dev_fixture" else None),
            "entries": [e.__dict__ for e in sorted(self.entries, key=lambda e: e.path)],
            "size_report": {
                "total_bytes": total,
                "total_gzip_bytes": total_gz,
                "p0_compressed_target_bytes": P0_COMPRESSED_TARGET_BYTES,
                "within_p0_target": None if total_gz is None else total_gz <= P0_COMPRESSED_TARGET_BYTES,
                "measured": "exact byte counts of the files written; load time is measured by P4-C smoke checks",
                # A synthetic bundle's size says nothing about the real P0 artifact size.
                "measurement_basis": ("synthetic development fixtures, not real P0 artifacts"
                                      if self.data_classification == "synthetic_dev_fixture"
                                      else "production artifacts in this bundle"),
            },
            "firms_separate": all(e.path.startswith("firms/") == (e.family == "firms_hotspots")
                                  for e in self.entries),
        }


def _refuse_sealed_records(cal: CalendarArtifact) -> None:
    window = cal.sealed_window
    if window is None:
        raise BundleError("production calendar without a sealed window")
    for series in [*cal.monthly_series, *cal.weekly_series]:
        for rec in series.records:
            if hasattr(rec, "month"):
                start, end = month_bounds(rec.year, rec.month)
            else:
                start, end = rec.start_date, rec.end_date
            inside = window.start <= start and end <= window.end
            if inside and (rec.availability == "available" or rec.days_with_file):
                raise BundleError("a production calendar record inside the sealed window carries data")


def verify_bundle(out_dir: Path) -> dict:
    """Re-read a written bundle: hashes, sizes and contract validity of every file."""
    out_dir = Path(out_dir)
    index = json.loads((out_dir / INDEX_NAME).read_text(encoding="utf-8"))
    if index["contract_version"] != CONTRACT_VERSION:
        raise BundleError("bundle contract version differs from the installed contract")
    for e in index["entries"]:
        payload = (out_dir / e["path"]).read_bytes()
        if hashlib.sha256(payload).hexdigest() != e["sha256"] or len(payload) != e["bytes"]:
            raise BundleError(f"{e['path']}: hash or size mismatch")
        if e["gzip_path"]:
            if gzip.decompress((out_dir / e["gzip_path"]).read_bytes()) != payload:
                raise BundleError(f"{e['gzip_path']}: gzip copy differs from the JSON")
        model = MODEL_BY_FAMILY[e["family"]].model_validate_json(payload)
        if model.cache_key().digest() != e["cache_key_digest"]:  # type: ignore[attr-defined]
            raise BundleError(f"{e['path']}: identity differs from the index")
    return index


def build_from_models(models: Iterable[BaseModel], bundle_version: str, data_classification: str) -> Bundle:
    bundle = Bundle(bundle_version=bundle_version, data_classification=data_classification)
    for m in models:
        bundle.add(m)
    return bundle
