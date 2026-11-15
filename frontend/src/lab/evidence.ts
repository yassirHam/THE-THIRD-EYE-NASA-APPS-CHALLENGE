/** Stage A real-data evidence document (tte-stage-a-evidence-v1) read into a display model.
 *
 * Presentation only. Values are copied as given: a null stays null (never zero), a variant that
 * is unavailable stays unavailable, nothing is recomputed, averaged or merged across regions or
 * sensors. Years held back for the sealed evaluation are listed as sealed, not as missing.
 * The document is refused when it was not read under the sealed-data rules. */

export const EVIDENCE_FORMAT = 'tte-stage-a-evidence-v1'
export const EVIDENCE_CONTRACT = '1.6.0'

export type SensorKey = 'aqua' | 'viirs'
export type Rate = { D: number; O: number; rate: number }
export type VariantResult = {
  id: string
  label: string
  /** null = no factor could be fitted. Shown as unavailable, never as 1 or 0. */
  factor: number | null
  available: boolean
  mappedRate?: number
  pooledRelativeError?: number
  weeklyMae?: number
  trainingYears?: number[]
  aquaPooledRate?: number
  viirsPooledRate?: number
  reasons: string[]
}
export type YearResult = {
  year: number
  role: 'development' | 'applicability'
  aqua: Rate
  viirs: Rate
  weeks: number
  excludedWeeks: number | null
  /** Observed Aqua / VIIRS ratio, as given. */
  ratio: number | null
  verdict: string
  variants: VariantResult[]
}
export type PolicyView = {
  key: string
  label: string
  factorName: string
  role: string
  envelope: [number, number] | null
  envelopeNote: string
  variants: VariantResult[]
  years: YearResult[]
}
export type BoundaryPeriod = {
  period: string
  role: string
  aquaRate: number
  viirsRate: number
  aBreak: number | null
  inside: boolean | null
  side: string
  variants: Array<{ id: string; label: string; factor: number | null; side: string }>
}
export type Boundary = {
  id: string
  label: string
  regionCode: string
  policyKey: string
  factorName: string
  available: boolean
  envelope: [number, number] | null
  counts: Record<string, number>
  periods: BoundaryPeriod[]
  interpretation: string
  limits: string[]
  reasons: string[]
}
export type ShareYear = { year: number; shares: Record<string, number>; identityHolds: boolean }
export type Composition = {
  id: string
  label: string
  interpretation: string
  limits: string[]
  identityHolds: number
  identityTotal: number
  bySensor: Record<SensorKey, ShareYear[]>
}
export type Illustration = {
  id: string
  label: string
  interpretation: string
  limits: string[]
  observed: [number, number]
  fixedWeight: [number, number]
  observedPct: number
  fixedPct: number
}
export type RegionEvidence = {
  code: string
  name: string
  eligibleWeeks: Array<{ year: number; weeks: number }>
  excludedWeeks: Array<{ year: number; weeks: number }>
  policies: PolicyView[]
  boundaries: Boundary[]
}
export type EvidenceView = {
  id: string
  unit: string
  releaseStatus: string
  replay: { status: string; rows: number; maxRelativeDifference: number; yearsRead: number[]; sourceFile: string }
  sealedYears: number[]
  trainingYears: number[]
  developmentYear: number | null
  applicabilityYears: number[]
  inference: string
  regions: RegionEvidence[]
  composition: Composition[]
  illustrations: Illustration[]
  /** True when the whole document is not approved for public claims. */
  preliminary: boolean
}

export class EvidenceRefused extends Error {}

type Obj = Record<string, unknown>
const isObj = (v: unknown): v is Obj => typeof v === 'object' && v !== null && !Array.isArray(v)
const obj = (v: unknown): Obj => (isObj(v) ? v : {})
const list = (v: unknown): unknown[] => (Array.isArray(v) ? v : [])
const numOrNull = (v: unknown): number | null => (typeof v === 'number' && Number.isFinite(v) ? v : null)
const str = (v: unknown, fallback = ''): string => (typeof v === 'string' ? v : fallback)
const nums = (v: unknown): number[] => list(v).filter((x): x is number => typeof x === 'number' && Number.isFinite(x))
const strs = (v: unknown): string[] => list(v).filter((x): x is string => typeof x === 'string')

/** Plain-language names for the identifiers the document uses. */
export const POLICY_LABEL: Record<string, string> = {
  own_support: 'Own-area observations',
  common_support: 'Paired common observations (diagnostic only)',
}
export const SENSOR_NAME: Record<SensorKey, string> = { aqua: 'MODIS / Aqua', viirs: 'VIIRS / Suomi NPP' }
const VERDICT: Record<string, string> = {
  insufficient_evidence: 'Insufficient evidence: no pass rule is registered, so the check is neither passed nor failed',
}

export function variantLabel(id: string): string {
  if (id === 'raw') return 'No correction'
  if (id === 'full_training_2016_2017_2018') return 'All training years (2016 to 2018)'
  const m = /^ex_(\d{4})$/.exec(id)
  return m ? `Training without ${m[1]}` : 'Other correction'
}

function rate(v: unknown): Rate | null {
  const o = obj(v)
  const D = numOrNull(o.D), O = numOrNull(o.O), r = numOrNull(o.rate)
  return D === null || O === null || r === null ? null : { D, O, rate: r }
}

function variantFrom(id: string, a: Obj, b: Obj = {}): VariantResult {
  const factor = numOrNull(a.factor)
  const status = str(a.status) || str(b.status)
  return {
    id, label: variantLabel(id), factor, available: status === 'available' && factor !== null,
    mappedRate: numOrNull(a.mapped_rate) ?? undefined,
    pooledRelativeError: numOrNull(a.pooled_relative_error) ?? undefined,
    weeklyMae: numOrNull(a.weekly_mae) ?? undefined,
    trainingYears: nums(b.training_years).length ? nums(b.training_years) : undefined,
    aquaPooledRate: numOrNull(b.aqua_pooled_rate) ?? undefined,
    viirsPooledRate: numOrNull(b.viirs_pooled_rate) ?? undefined,
    reasons: strs(b.reasons),
  }
}

function yearResult(year: number, role: YearResult['role'], v: unknown, sealed: Set<number>): YearResult | null {
  if (sealed.has(year)) return null
  const o = obj(v)
  const aqua = rate(o.aqua), viirs = rate(o.viirs)
  if (!aqua || !viirs) return null
  const byVariant = obj(o.by_variant)
  const status = str(o.applicability_status)
  return {
    year, role, aqua, viirs, weeks: numOrNull(o.n_weeks) ?? 0, excludedWeeks: numOrNull(o.excluded_weeks),
    ratio: numOrNull(o.observed_ratio_A_over_V),
    verdict: role === 'development' ? 'Development year, used to check the correction' : VERDICT[status] ?? 'Status recorded in the evidence file',
    variants: Object.keys(byVariant).map((id) => variantFrom(id, obj(byVariant[id]))),
  }
}

function policyFrom(key: string, v: unknown, sealed: Set<number>): PolicyView {
  const o = obj(v)
  const variants = obj(o.variants)
  const env = nums(o.variant_envelope)
  const years: YearResult[] = []
  const dev = yearResult(2019, 'development', o.development_2019, sealed)
  if (dev) years.push(dev)
  const app = obj(o.applicability)
  for (const y of Object.keys(app).map(Number).sort((a, b) => a - b)) {
    const r = yearResult(y, 'applicability', app[String(y)], sealed)
    if (r) years.push(r)
  }
  return {
    key, label: POLICY_LABEL[key] ?? 'Other observation set', factorName: str(o.factor_name), role: str(o.role),
    envelope: env.length === 2 ? [env[0], env[1]] : null, envelopeNote: str(o.variant_envelope_note),
    variants: Object.keys(variants).map((id) => variantFrom(id, obj(variants[id]), obj(variants[id]))),
    years,
  }
}

function boundaryFrom(c: Obj): Boundary {
  const env = nums(c.variant_envelope)
  return {
    id: str(c.counterexample_id), label: str(c.label), regionCode: str(c.region_code), policyKey: str(c.policy),
    factorName: str(c.factor_name), available: str(c.status) === 'available',
    envelope: env.length === 2 ? [env[0], env[1]] : null,
    counts: Object.fromEntries(Object.entries(obj(c.counts)).filter(([, n]) => typeof n === 'number')) as Record<string, number>,
    periods: list(c.periods).map((p) => {
      const o = obj(p)
      return {
        period: str(o.period), role: str(o.role), aquaRate: numOrNull(o.aqua_rate_B) ?? NaN, viirsRate: numOrNull(o.viirs_rate_V) ?? NaN,
        aBreak: numOrNull(o.a_break), inside: typeof o.a_break_inside_variant_envelope === 'boolean' ? o.a_break_inside_variant_envelope : null,
        side: str(o.registered_variants_side),
        variants: list(o.by_variant).map((x) => ({ id: str(obj(x).variant_id), label: variantLabel(str(obj(x).variant_id)), factor: numOrNull(obj(x).factor), side: str(obj(x).side) })),
      }
    }).filter((p) => Number.isFinite(p.aquaRate) && Number.isFinite(p.viirsRate)),
    interpretation: str(c.interpretation), limits: strs(c.limits), reasons: strs(c.reasons),
  }
}

function compositionFrom(c: Obj): Composition {
  const out: Record<SensorKey, ShareYear[]> = { aqua: [], viirs: [] }
  for (const s of ['aqua', 'viirs'] as const) {
    const years = obj(obj(obj(c.per_sensor)[s]).years)
    out[s] = Object.keys(years).map(Number).sort((a, b) => a - b).map((year) => {
      const y = obj(years[String(year)])
      const shares = Object.fromEntries(Object.entries(obj(y.o_shares)).filter(([, n]) => typeof n === 'number')) as Record<string, number>
      return { year, shares, identityHolds: y.identity_holds === true }
    })
  }
  const idc = obj(c.identity_counts)
  return { id: str(c.counterexample_id), label: str(c.label), interpretation: str(c.interpretation), limits: strs(c.limits), identityHolds: numOrNull(idc.holds) ?? 0, identityTotal: numOrNull(idc.sensor_years) ?? 0, bySensor: out }
}

function illustrationFrom(c: Obj): Illustration | null {
  const observed = nums(c.observed_regional_index_R), fixed = nums(c.fixed_weight_R_std)
  const op = numOrNull(c.observed_pct_change), fp = numOrNull(c.fixed_weight_pct_change)
  if (observed.length !== 2 || fixed.length !== 2 || op === null || fp === null) return null
  return { id: str(c.counterexample_id), label: str(c.label), interpretation: str(c.interpretation), limits: strs(c.limits), observed: [observed[0], observed[1]], fixedWeight: [fixed[0], fixed[1]], observedPct: op, fixedPct: fp }
}

const byYear = (o: unknown) => Object.entries(obj(o)).map(([y, w]) => ({ year: Number(y), weeks: typeof w === 'number' ? w : NaN })).filter((x) => Number.isFinite(x.year) && Number.isFinite(x.weeks)).sort((a, b) => a.year - b.year)

export function evidenceFromJson(raw: unknown): EvidenceView {
  const doc = obj(raw)
  if (doc.evidence_format !== EVIDENCE_FORMAT) throw new EvidenceRefused('unknown evidence format')
  if (doc.contract_version_installed !== EVIDENCE_CONTRACT) throw new EvidenceRefused(`evidence is not contract ${EVIDENCE_CONTRACT}`)
  if (doc.data_kind !== 'real_data') throw new EvidenceRefused('evidence is not real data')
  const replay = obj(doc.replay)
  // Sealed evaluation years must never have been read. Refuse the whole document otherwise.
  if (list(replay.sealed_years_read).length > 0) throw new EvidenceRefused('sealed years were read')
  const summary = obj(doc.stage_a_summary)
  const splits = obj(summary.splits)
  const sealedYears = nums(splits.sealed_not_read)
  const sealed = new Set(sealedYears)
  const regionsRaw = obj(summary.regions)
  const ces = list(doc.counterexample_interpretations).map(obj)
  const regions: RegionEvidence[] = Object.keys(regionsRaw).map((code) => {
    const r = obj(regionsRaw[code])
    const policies = obj(r.policies)
    return {
      code, name: str(r.name, code),
      eligibleWeeks: byYear(r.eligible_weeks_by_year).filter((x) => !sealed.has(x.year)),
      excludedWeeks: byYear(r.excluded_weeks_by_year).filter((x) => !sealed.has(x.year)),
      policies: Object.keys(policies).map((k) => policyFrom(k, policies[k], sealed)),
      boundaries: ces.filter((c) => c.kind === 'stage_a_equality_boundary' && str(c.region_code) === code).map(boundaryFrom),
    }
  })
  const dims = obj(doc.status_dimensions)
  return {
    id: str(doc.evidence_id), unit: str(doc.unit), releaseStatus: str(doc.release_status),
    replay: { status: str(replay.status), rows: numOrNull(replay.rows_loaded) ?? 0, maxRelativeDifference: numOrNull(replay.max_float_relative_difference) ?? NaN, yearsRead: nums(replay.iso_years_read), sourceFile: str(replay.parquet_file) },
    sealedYears, trainingYears: nums(splits.training), developmentYear: numOrNull(splits.development), applicabilityYears: nums(splits.applicability),
    inference: str(dims.inference_status),
    regions,
    composition: ces.filter((c) => c.kind === 'geographic_composition_accounting').map(compositionFrom),
    illustrations: ces.filter((c) => c.kind === 'geographic_composition_shift').map(illustrationFrom).filter((x): x is Illustration => x !== null),
    preliminary: str(doc.release_status).toLowerCase().startsWith('not_released'),
  }
}
