/** Loader for the static artifact bundle produced by artifact_pipeline/bundle.py.
 * Contract 1.6.0. All artifacts are immutable and content-addressed.
 *
 * The bundle is placed in public/artifacts/ during the build.
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
import { areaFromArtifacts } from './adapter.ts'
import { evidenceFromJson, type EvidenceView } from './evidence.ts'
import type { LabView } from './model.ts'

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
/** Entry of evidence_entries (tte-stage-a-evidence-v1). */
interface EvidenceEntry {
  evidence_format: string
  evidence_id: string
  path: string
  sha256: string
}
interface BundleIndex {
  bundle_format: string
  bundle_version: string
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

async function sha256Hex(bytes: ArrayBuffer): Promise<string | null> {
  if (typeof crypto === 'undefined' || !crypto.subtle) return null
  const digest = new Uint8Array(await crypto.subtle.digest('SHA-256', bytes))
  return Array.from(digest, (b) => b.toString(16).padStart(2, '0')).join('')
}

/** Load the evidence documents listed in evidence_entries. A document whose hash differs from the
 * index, or that the evidence reader refuses (wrong format, not real data, sealed years read), is
 * skipped; nothing is substituted. */
async function loadEvidence(base: string, entries: EvidenceEntry[]): Promise<EvidenceView[]> {
  const out: EvidenceView[] = []
  for (const e of entries) {
    if (e.evidence_format !== 'tte-stage-a-evidence-v1') continue
    try {
      const r = await fetch(`${base}${e.path}`)
      if (!r.ok) continue
      const bytes = await r.arrayBuffer()
      const hash = await sha256Hex(bytes)
      if (hash !== null && hash !== e.sha256) continue
      out.push(evidenceFromJson(JSON.parse(new TextDecoder().decode(bytes))))
    } catch {
      // unreadable or refused evidence: leave it out rather than show something wrong
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
  if (!index || index.bundle_format !== 'tte-static-bundle-v1') {
    // Bundle not present or format mismatch: fall back to empty view without error.
    return { areas: [] }
  }

  const evidence = await loadEvidence(base, index.evidence_entries ?? [])
  const withEvidence = (areas: LabView['areas']): LabView => (evidence.length ? { areas, evidence } : { areas })

  const byFamily: Record<string, BundleEntry[]> = {}
  for (const e of index.entries ?? []) {
    if (!byFamily[e.family]) byFamily[e.family] = []
    byFamily[e.family].push(e)
  }

  // Load the region selector first — it drives area construction.
  const selectorEntry = byFamily['region_selector']?.[0]
  if (!selectorEntry) return withEvidence([])

  const selectorRaw = await fetchJson(base, selectorEntry.path)
  if (!selectorRaw) return withEvidence([])
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

  return withEvidence(areas)
}
