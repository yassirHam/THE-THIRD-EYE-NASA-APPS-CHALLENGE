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
- Non-contract evidence documents (P1 Stage A real-data summary, see stage_a_evidence.py) live
  in a separate `evidence/` subtree, are listed under `evidence_entries`, are hashed and counted
  in the size report, and are never indexed or served as contract artifacts.
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
EVIDENCE_FORMATS = ("tte-stage-a-evidence-v1",)

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
    # P2 provenance (boundary, CRS, grid rule, source collections) by geometry_id, taken from
    # supplied ProvenanceManifests. Input manifests are provenance sources, not bundle files.
    _provenance: dict[str, ProvenanceManifest] = field(default_factory=dict, repr=False)
    replay_manifests: list[dict] = field(default_factory=list)
    replay_manifests_missing: list[dict] = field(default_factory=list)
    _inputs: list[ProvenanceManifest] = field(default_factory=list, repr=False)
    # Non-contract evidence documents (e.g. P1 Stage A real-data summary), served from `evidence/`.
    evidence_entries: list[dict] = field(default_factory=list)
    _evidence_payloads: dict[str, bytes] = field(default_factory=dict, repr=False)

    # ------------------------------------------------------------- building

    def add_evidence(self, evidence_id: str, document: dict) -> dict:
        """Add one JSON evidence document. It is not a contract artifact and never enters `entries`."""
        if document.get("evidence_format") not in EVIDENCE_FORMATS:
            raise BundleError(f"unknown evidence format {document.get('evidence_format')!r}")
        if document.get("evidence_id") != evidence_id:
            raise BundleError("evidence_id does not match the document")
        if any(e["evidence_id"] == evidence_id for e in self.evidence_entries):
            raise BundleError(f"evidence {evidence_id} already in the bundle; bump the bundle version instead")
        payload = json.dumps(document, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
                             allow_nan=False).encode("utf-8")
        sha = hashlib.sha256(payload).hexdigest()
        path = str(PurePosixPath("evidence", _safe_segment(self.bundle_version), _safe_segment(evidence_id),
                                 f"{evidence_id}.{sha[:16]}.json"))
        entry = {"evidence_id": evidence_id, "evidence_format": document["evidence_format"], "path": path,
                 "sha256": sha, "bytes": len(payload), "gzip_path": None, "gzip_bytes": None}
        self._evidence_payloads[path] = payload
        self.evidence_entries.append(entry)
        return entry

    def add(self, model: BaseModel) -> Optional[BundleEntry]:
        if isinstance(model, ProvenanceManifest):
            self._add_provenance(model)
            return None
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

    def _add_provenance(self, man: ProvenanceManifest) -> None:
        if man.contract_version != CONTRACT_VERSION:
            raise BundleError(f"provenance manifest contract {man.contract_version} != {CONTRACT_VERSION}")
        if man.data_classification != self.data_classification:
            raise BundleError(f"a {self.data_classification} bundle cannot use {man.data_classification} provenance")
        prior = self._provenance.get(man.geometry_id)
        if prior is not None and _provenance_fields(prior) != _provenance_fields(man):
            raise BundleError(f"conflicting provenance for geometry {man.geometry_id}")
        self._provenance.setdefault(man.geometry_id, man)
        self._inputs.append(man)

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
        for man in self._inputs:
            target = man.described_artifact_type
            described = self._models.get((target, man.cache_key().digest()))
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
        evidence: list[dict] = []
        for ev in self.evidence_entries:
            payload = self._evidence_payloads[ev["path"]]
            target = out_dir / ev["path"]
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(payload)
            gz_path = gz_bytes = None
            if gzip_copies:
                gz = gzip.compress(payload, compresslevel=9, mtime=0)
                gz_path = ev["path"] + ".gz"
                (out_dir / gz_path).write_bytes(gz)
                gz_bytes = len(gz)
            evidence.append({**ev, "gzip_path": gz_path, "gzip_bytes": gz_bytes})
        self.evidence_entries = evidence
        self._write_replay_manifests(out_dir)
        index = self.index()
        (out_dir / INDEX_NAME).write_bytes(json.dumps(index, indent=2, sort_keys=True).encode("utf-8") + b"\n")
        return index

    def _write_replay_manifests(self, out_dir: Path) -> None:
        """One ProvenanceManifest per bundle file, in the format P5-B's replay verifier reads.

        The manifest carries the described artifact's five-field identity, the file's path, size,
        sha256 and cache-key digest. Provenance (boundary, CRS, grid rule, sources) is copied from
        the P2 manifest supplied for the same geometry; without one, no manifest is written and
        the gap is listed (nothing is invented).
        """
        self.replay_manifests, self.replay_manifests_missing = [], []
        for e in self.entries:
            model = self._models[(e.family, e.cache_key_digest)]
            prov = self._provenance.get(e.cache_key["geometry_id"])
            if prov is None:
                self.replay_manifests_missing.append({"path": e.path, "family": e.family,
                                                      "reason": "no provenance manifest for this geometry"})
                continue
            manifest = _replay_manifest(self, e, model, prov)
            payload = canonical_json(manifest)
            ProvenanceManifest.model_validate_json(payload)
            assert_manifest_describes(manifest, model, e.family)  # type: ignore[arg-type]
            k = e.cache_key
            rel = str(PurePosixPath("manifests", *(k[n] for n in ("artifact_version", "geometry_id", "method_id",
                                                                 "policy_id", "period_spec")),
                                    f"{e.family}.manifest.json"))
            (out_dir / rel).parent.mkdir(parents=True, exist_ok=True)
            (out_dir / rel).write_bytes(payload)
            self.replay_manifests.append({"path": rel, "describes": e.path, "family": e.family,
                                          "sha256": hashlib.sha256(payload).hexdigest(), "bytes": len(payload)})

    def index(self) -> dict:
        total = sum(e.bytes for e in self.entries)
        compressed = [e.gzip_bytes for e in self.entries]
        total_gz = sum(compressed) if all(c is not None for c in compressed) else None
        ev_bytes = sum(e["bytes"] for e in self.evidence_entries)
        ev_compressed = [e["gzip_bytes"] for e in self.evidence_entries]
        ev_gz = sum(ev_compressed) if all(c is not None for c in ev_compressed) else None
        combined_gz = None if total_gz is None or ev_gz is None else total_gz + ev_gz
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
                "evidence_bytes": ev_bytes,
                "evidence_gzip_bytes": ev_gz,
                "combined_gzip_bytes": combined_gz,
                "p0_compressed_target_bytes": P0_COMPRESSED_TARGET_BYTES,
                "within_p0_target": None if combined_gz is None else combined_gz <= P0_COMPRESSED_TARGET_BYTES,
                "measured": "exact byte counts of the files written; load time is measured by P4-C smoke checks",
                # A synthetic bundle's size says nothing about the real P0 artifact size.
                "measurement_basis": ("synthetic development fixtures, not real P0 artifacts"
                                      if self.data_classification == "synthetic_dev_fixture"
                                      else "production artifacts in this bundle"),
            },
            "firms_separate": all(e.path.startswith("firms/") == (e.family == "firms_hotspots")
                                  for e in self.entries),
            # Replay manifests are not counted in size_report: they are provenance, not P0 payload.
            "replay_manifests": sorted(self.replay_manifests, key=lambda m: m["path"]),
            "replay_manifests_missing": sorted(self.replay_manifests_missing, key=lambda m: m["path"]),
            # Non-contract evidence documents; never indexed as grid or FIRMS artifacts.
            "evidence_entries": sorted(self.evidence_entries, key=lambda e: e["path"]),
        }


PROVENANCE_FIELDS = ("snpp_cutoff_status", "canonical_boundary", "boundary_source", "boundary_version", "crs",
                     "grid_inclusion_rule", "source_collections")


def _provenance_fields(man: ProvenanceManifest) -> dict:
    return {f: json.loads(json.dumps(getattr(man, f), default=lambda m: m.model_dump(mode="json")))
            for f in PROVENANCE_FIELDS}


def _row_count(model: BaseModel) -> int:
    """Calendar: number of period records. Other families: one artifact document."""
    if isinstance(model, CalendarArtifact):
        return sum(len(s.records) for s in [*model.monthly_series, *model.weekly_series])
    return 1


def _coverage_claim(model: BaseModel) -> str:
    """Never more than P2 certified. Only calendars carry a footprint certification."""
    if isinstance(model, CalendarArtifact) and model.footprint_certification is not None:
        return {"complete": "complete", "partial": "partial"}.get(model.footprint_certification.status, "unverified")
    return "unverified"


def _replay_manifest(bundle: "Bundle", e: BundleEntry, model: BaseModel, prov: ProvenanceManifest) -> ProvenanceManifest:
    compressed = e.gzip_bytes if e.gzip_bytes is not None else e.bytes
    if compressed > e.bytes:
        raise BundleError(f"{e.path}: gzip copy is larger than the file; report it instead of hiding it")
    k = e.cache_key
    data = {
        "contract_version": CONTRACT_VERSION,
        **k,
        "data_classification": bundle.data_classification,
        "fixture_label": model.fixture_label,  # type: ignore[attr-defined]
        "manifest_version": f"{bundle.bundle_version}:{e.family}",
        "described_artifact_type": e.family,
        "generated_at": prov.generated_at.strftime("%Y-%m-%dT%H:%M:%SZ"),  # from P2 input: deterministic
        **_provenance_fields(prov),
        "total_file_size_bytes": e.bytes,
        "compressed_bundle_size_bytes": compressed,
        "partitions": [{
            "file_path": e.path,
            "geometry_id": k["geometry_id"], "period_spec": k["period_spec"],
            "method_id": k["method_id"], "policy_id": k["policy_id"],
            "sensor": None,
            "row_count": _row_count(model),
            "file_size_bytes": e.bytes,
            "cache_key_sha256": e.cache_key_digest,
            "sha256_checksum": e.sha256,
            "coverage_status": _coverage_claim(model),
        }],
    }
    return ProvenanceManifest.model_validate_json(json.dumps(data))


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
    by_path = {e["path"]: e for e in index["entries"]}
    for m in index.get("replay_manifests", []):
        payload = (out_dir / m["path"]).read_bytes()
        if hashlib.sha256(payload).hexdigest() != m["sha256"] or len(payload) != m["bytes"]:
            raise BundleError(f"{m['path']}: replay manifest hash or size mismatch")
        man = ProvenanceManifest.model_validate_json(payload)
        e = by_path[m["describes"]]
        described = MODEL_BY_FAMILY[e["family"]].model_validate_json((out_dir / e["path"]).read_bytes())
        assert_manifest_describes(man, described, e["family"])  # type: ignore[arg-type]
        part = man.partitions[0]
        if (part.file_path, part.sha256_checksum, part.file_size_bytes) != (e["path"], e["sha256"], e["bytes"]):
            raise BundleError(f"{m['path']}: partition does not match the indexed file")
    for ev in index.get("evidence_entries", []):
        if not ev["path"].startswith("evidence/"):
            raise BundleError(f"{ev['path']}: evidence outside the evidence/ subtree")
        payload = (out_dir / ev["path"]).read_bytes()
        if hashlib.sha256(payload).hexdigest() != ev["sha256"] or len(payload) != ev["bytes"]:
            raise BundleError(f"{ev['path']}: evidence hash or size mismatch")
        if ev["gzip_path"] and gzip.decompress((out_dir / ev["gzip_path"]).read_bytes()) != payload:
            raise BundleError(f"{ev['gzip_path']}: gzip copy differs from the JSON")
        doc = json.loads(payload.decode("utf-8"))
        if (doc.get("evidence_format"), doc.get("evidence_id")) != (ev["evidence_format"], ev["evidence_id"]):
            raise BundleError(f"{ev['path']}: evidence identity differs from the index")
    return index


def build_from_models(models: Iterable[BaseModel], bundle_version: str, data_classification: str) -> Bundle:
    bundle = Bundle(bundle_version=bundle_version, data_classification=data_classification)
    for m in models:
        bundle.add(m)
    return bundle
