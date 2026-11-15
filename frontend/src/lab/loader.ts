/** Loader for the static artifact bundle produced by artifact_pipeline/bundle.py.
 * Contract 1.6.0. All artifacts are immutable and content-addressed.
 *
 * The bundle is copied byte-for-byte from artifact_pipeline/build/bundle/ into public/artifacts/.
 * Evidence documents are shown only when their bytes match the sha256 in bundle_index.json.
 * If bundle_index.json is absent (bundles not yet produced), the loader resolves with
 * an empty LabView; the Lab falls back to its placeholder state without error.
 *
 * Rules carried from the contract:
 * - Each area uses only its own calendar and comparison; no factors are inherited.
 * - Only regions whose comparison_access_status = 'evaluated_comparison' get a comparison.
 * - Sealed periods are labelled as such; no observation is substituted.
 * - The loader never rewrites, rounds, or zero-fills any value.
 */
import type { CalendarArtifact, ComparisonResult, RegionSelectorArtifact } from '../contracts/types.ts'
import { CONTRACT_VERSION, EVIDENCE_FORMAT, areaFromArtifacts, evidenceFromDocument } from './adapter.ts'
import { evidenceFromJson } from './evidence.ts'
import type { EvidenceView, LabView } from './model.ts'

/** Minimal shape of bundle_index.json (tte-static-bundle-v1). */
interface BundleEntry {
  family: string
  artifact_version: string
  geometry_id: string
  period_spec: string
  method_id: string
  policy_id: string
  path: string
}
interface EvidenceEntry {
  evidence_id: string
  evidence_format: string
  path: string
  sha256: string
}
interface BundleIndex {
  bundle_format: string
  bundle_version: string
  contract_version?: string
  data_classification: string
  entries: BundleEntry[]
  evidence_entries?: EvidenceEntry[]
}

function key(e: { geometry_id: string; period_spec: string; method_id: string; policy_id: string }): string {
  return [e.geometry_id, e.period_spec, e.method_id, e.policy_id].join('|')
}

/** Fetch a JSON file from the bundle. Returns null on network/parse error. */
async function fetchJson(base: string, path: string): Promise<unknown> {
  try {
    const r = await fetch(`${base}${path}`)
    if (!r.ok) return null
    return await r.json()
  } catch {
    return null
  }
}

const hex = (buf: ArrayBuffer) => Array.from(new Uint8Array(buf), (b) => b.toString(16).padStart(2, '0')).join('')

/** Fetch an evidence document and check its bytes against the index's sha256. A document whose
 * hash cannot be checked (no Web Crypto) or does not match is not shown. */
async function fetchVerified(base: string, entry: EvidenceEntry): Promise<unknown> {
  try {
    if (!globalThis.crypto?.subtle) return null
    const r = await fetch(`${base}${entry.path}`)
    if (!r.ok) return null
    const bytes = await r.arrayBuffer()
    if (hex(await crypto.subtle.digest('SHA-256', bytes)) !== entry.sha256.toLowerCase()) return null
    return JSON.parse(new TextDecoder().decode(bytes))
  } catch {
    return null
  }
}

async function loadEvidence(base: string, index: BundleIndex): Promise<EvidenceView[]> {
  const out: EvidenceView[] = []
  for (const entry of index.evidence_entries ?? []) {
    if (entry.evidence_format !== EVIDENCE_FORMAT) continue
    const doc = await fetchVerified(base, entry)
    if (!doc || typeof doc !== 'object') continue
    try {
      const view = evidenceFromDocument(doc as Record<string, unknown>, `${base}${entry.path}`)
      // Per-region numbers are shown now, labelled preliminary while the file is not released (team decision).
      // The reader still refuses a file that read sealed years.
      try { view.detail = evidenceFromJson(doc) } catch { /* detail refused: summary only */ }
      out.push(view)
    } catch {
      // Format or contract mismatch: the document is skipped, never partially shown.
    }
  }
  return out
}

/**
 * Load the static artifact bundle and build the LabView.
 *
 * @param base  Base URL for the artifacts directory (e.g. `${import.meta.env.BASE_URL}artifacts/`).
 * @returns     Populated LabView, or an empty one if the bundle is absent or invalid.
 */
export async function loadBundle(base: string): Promise<LabView> {
  const index = await fetchJson(base, 'bundle_index.json') as BundleIndex | null
  if (!index || index.bundle_format !== 'tte-static-bundle-v1' || (index.contract_version !== undefined && index.contract_version !== CONTRACT_VERSION)) {
    // Bundle not present, format or contract mismatch: fall back to empty view without error.
    return { areas: [] }
  }

  const evidence = await loadEvidence(base, index)

  const byFamily: Record<string, BundleEntry[]> = {}
  for (const e of index.entries) {
    if (!byFamily[e.family]) byFamily[e.family] = []
    byFamily[e.family].push(e)
  }

  // Load the region selector first: it drives area construction.
  const selectorEntry = byFamily['region_selector']?.[0]
  if (!selectorEntry) return { areas: [], evidence }

  const selectorRaw = await fetchJson(base, selectorEntry.path)
  if (!selectorRaw) return { areas: [], evidence }
  const selector = selectorRaw as RegionSelectorArtifact

  // Load each option's calendar and comparison (by matching geometry_id and identity fields).
  const calendarEntries = byFamily['calendar'] ?? []
  const comparisonEntries = byFamily['comparison'] ?? []

  const calByKey = new Map<string, BundleEntry>()
  for (const e of calendarEntries) calByKey.set(e.geometry_id, e)

  const compByKey = new Map<string, BundleEntry>()
  for (const e of comparisonEntries) compByKey.set(key(e), e)

  const areas = []
  for (const option of selector.options) {
    const calEntry = calByKey.get(option.geometry_id)
    let calendar: CalendarArtifact | undefined
    if (calEntry) {
      const raw = await fetchJson(base, calEntry.path)
      if (raw) calendar = raw as CalendarArtifact
    }

    // A comparison is loaded only for evaluated areas with a matching identity.
    let comparison: ComparisonResult | undefined
    if (option.comparison_access_status === 'evaluated_comparison' && option.evaluated_method_id && option.evaluated_policy_id && option.evaluated_period_spec) {
      const ck = key({ geometry_id: option.geometry_id, period_spec: option.evaluated_period_spec, method_id: option.evaluated_method_id, policy_id: option.evaluated_policy_id })
      const compEntry = compByKey.get(ck)
      if (compEntry) {
        const raw = await fetchJson(base, compEntry.path)
        if (raw) comparison = raw as ComparisonResult
      }
    }

    try {
      areas.push(areaFromArtifacts(option, calendar, comparison))
    } catch {
      // Identity mismatch or contract error: skip the area, do not substitute.
      // The Lab will show it as unavailable rather than serving wrong data.
    }
  }

  return { areas, evidence }
}
