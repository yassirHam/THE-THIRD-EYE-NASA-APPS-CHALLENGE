/** Adapter from contract 1.6.0 artifacts (src/contracts/types.ts) to the Lab presentation
 * model. Presentation only: no value is recomputed, rounded to zero or inherited. */
import type {
  CalendarArtifact,
  ClaimAuditRecord,
  ComparisonResult,
  MonthRecord,
  RegionSelectorOption,
  SealedWindow,
  WeekRecord,
} from '../contracts/types.ts'
import type { AreaView, CacheKey, CalendarEntry, ComparisonView, CounterexampleView, EvidenceView, Sensor } from './model.ts'

export const CONTRACT_VERSION = '1.6.0'

type ContractSensor = MonthRecord['sensor']
type CoverageReason = MonthRecord['coverage_reasons'][number]
type UnavailableReason = NonNullable<MonthRecord['unavailable_reason']>

const SENSOR: Partial<Record<ContractSensor, Sensor>> = { MODIS_Aqua: 'MODIS', VIIRS_SNPP: 'VIIRS' }
const MONTHS = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December']

/** Plain-language coverage reasons (no internal terms on screen). */
export const COVERAGE_TEXT: Record<CoverageReason, string> = {
  period_clipped: 'part of the period is outside the satellite record',
  partition_boundary: 'part of the period is held back for the sealed evaluation',
  missing_days_or_tiles: 'some days have no satellite file',
  low_processed_coverage: 'part of the area was not processed',
  no_file: 'no satellite file for this period',
  sensor_not_operating: 'the satellite was not operating',
}

const UNAVAILABLE_TEXT: Record<UnavailableReason, string> = {
  zero_usable_support: 'no usable observations (this is not a zero-fire result)',
  source_not_available: 'no satellite file',
  incomplete_footprint: 'the area was not fully extracted',
  qa_unusable: 'observations failed the quality check',
  sensor_not_operating: 'the satellite was not operating',
}

const LABEL_TEXT = {
  unusual: 'Unusual',
  not_unusual: 'Not unusual',
  critical: 'Critical week',
  not_critical: 'Not a critical week',
  insufficient_baseline: 'Not enough baseline years',
  not_applicable: 'No label',
} as const

export class IdentityMismatch extends Error {}

export function cacheKeyOf(a: { artifact_version: string; geometry_id: string; period_spec: string; method_id: string; policy_id: string }): CacheKey {
  return [a.artifact_version, a.geometry_id, a.period_spec, a.method_id, a.policy_id]
}

/** Exact five-field cache: nothing is served for a partial match. */
export class ArtifactCache<T> {
  private readonly items = new Map<string, T>()
  private static id(family: string, key: CacheKey): string { return JSON.stringify([family, ...key]) }
  set(family: string, key: CacheKey, value: T): void {
    const id = ArtifactCache.id(family, key)
    if (this.items.has(id) && this.items.get(id) !== value) throw new IdentityMismatch('artifacts are immutable for one identity')
    this.items.set(id, value)
  }
  get(family: string, key: CacheKey): T | undefined { return this.items.get(ArtifactCache.id(family, key)) }
}

function labelText(status: MonthRecord['unusual_status'] | WeekRecord['critical_status']): string {
  // A null label belongs to an incomplete period: say so instead of showing a decision.
  return status === null ? 'No label: incomplete period' : LABEL_TEXT[status]
}

/** Classify a period against the declared sealed window by dates only (mirrors
 * contracts/schemas/calendar.py sealed_window_period_status). ISO dates compare as strings. */
function sealedStatus(periodStart: string, periodEnd: string, window: SealedWindow): 'outside' | 'partial' | 'inside' {
  if (periodEnd < window.start || periodStart > window.end) return 'outside'
  if (periodStart >= window.start && periodEnd <= window.end) return 'inside'
  return 'partial'
}

/** The single placeholder row standing for the declared sealed window in one series. It has no
 * value: the window is withheld for the independent sensor-switch test, not missing data. */
function sealedEntry(window: SealedWindow, sensor: Sensor, resolution: 'month' | 'week'): CalendarEntry {
  const pending = window.registration_status === 'registered' ? '' : ' The sealed window is proposed and not yet registered.'
  return {
    period: `sealed-${window.start}-${window.end}`,
    label: `${window.start} to ${window.end}`,
    sensor, resolution, value: null,
    unit: 'detected fire cell-days per 1,000 usable land cell-days',
    availability: 'sealed',
    detail: `Held back for the independent sensor-switch test. This is not missing data; values are not shown here.${pending}`,
    sealedPeriod: true,
  }
}

/** Derive the start and end date strings for a MonthRecord or WeekRecord (ISO YYYY-MM-DD). */
function periodDates(rec: MonthRecord | WeekRecord): { start: string; end: string } {
  if ('week_number' in rec) {
    return { start: (rec as WeekRecord).start_date, end: (rec as WeekRecord).end_date }
  }
  const mr = rec as MonthRecord
  const year = mr.year
  const month = mr.month
  const start = `${year}-${String(month).padStart(2, '0')}-01`
  // Last day of month: get day 0 of next month
  const nextMonth = month === 12 ? new Date(year + 1, 0, 0) : new Date(year, month, 0)
  const end = `${year}-${String(month).padStart(2, '0')}-${String(nextMonth.getDate()).padStart(2, '0')}`
  return { start, end }
}

function coverageNote(rec: MonthRecord | WeekRecord): string | undefined {
  if (rec.coverage_state === 'complete') return undefined
  const reasons = rec.coverage_reasons.map((r) => COVERAGE_TEXT[r]).join('; ')
  const days = rec.coverage_state === 'partial' ? ` (${rec.days_with_file} of ${rec.days_in_period} days have a file)` : ''
  return `${rec.coverage_state === 'partial' ? 'Partial period' : 'Unavailable'}: ${reasons}${days}`
}

function entry(rec: MonthRecord | WeekRecord, period: string, label: string, resolution: 'month' | 'week'): CalendarEntry | null {
  const sensor = SENSOR[rec.sensor]
  if (!sensor) return null // reserved platforms carry no records in this phase
  const value = rec.availability === 'available' && typeof rec.fire_activity_index === 'number' ? rec.fire_activity_index : null
  const why = rec.availability === 'unavailable' && rec.unavailable_reason ? UNAVAILABLE_TEXT[rec.unavailable_reason] : undefined
  const isWeek = 'week_number' in rec
  return {
    period, label, sensor, resolution, value,
    unit: 'detected fire cell-days per 1,000 usable land cell-days',
    availability: value === null ? 'missing' : 'available',
    detail: [why, coverageNote(rec)].filter(Boolean).join('. ') || undefined,
    coverage: rec.coverage_state,
    unusualLabel: labelText(rec.unusual_status),
    criticalLabel: isWeek ? labelText((rec as WeekRecord).critical_status) : undefined,
    comparisonEligible: rec.comparison_eligible,
  }
}

/** One series' entries. When the artifact declares a sealed window that overlaps the series'
 * span, one sealed row is placed where the window begins. A record wholly inside the window
 * breaks the contract (such periods are excluded, not represented) and is refused, so a sealed
 * value can never reach the screen. */
function seriesEntries(records: Array<MonthRecord | WeekRecord>, label: (r: MonthRecord | WeekRecord) => [string, string], resolution: 'month' | 'week', window: SealedWindow | null): CalendarEntry[] {
  const out: CalendarEntry[] = []
  let sealedAt = -1
  let first: string | undefined
  let last: string | undefined
  for (const r of records) {
    const [period, text] = label(r)
    const e = entry(r, period, text, resolution)
    if (!e) continue
    const { start, end } = periodDates(r)
    if (window) {
      if (sealedStatus(start, end, window) === 'inside') throw new IdentityMismatch(`${period} lies wholly inside the sealed window; the artifact must exclude it`)
      if (sealedAt < 0 && start >= window.start) sealedAt = out.length
    }
    if (first === undefined || start < first) first = start
    if (last === undefined || end > last) last = end
    out.push(e)
  }
  if (window && out.length && first !== undefined && last !== undefined && sealedStatus(first, last, window) !== 'outside') {
    out.splice(sealedAt < 0 ? out.length : sealedAt, 0, sealedEntry(window, out[0].sensor, resolution))
  }
  return out
}

/** All monthly and weekly entries, one sensor per series, never merged across sensors. */
export function calendarEntries(cal: CalendarArtifact): CalendarEntry[] {
  // Required since contract 1.4.0 (8edec46): a missing or older version is refused, never assumed.
  if (cal.contract_version !== CONTRACT_VERSION) throw new IdentityMismatch(`contract ${String(cal.contract_version)} is not ${CONTRACT_VERSION}`)
  const window = cal.sealed_window ?? null
  const month = (r: MonthRecord | WeekRecord): [string, string] => { const m = r as MonthRecord; return [`${m.year}-${String(m.month).padStart(2, '0')}`, `${MONTHS[m.month - 1]} ${m.year}`] }
  const week = (r: MonthRecord | WeekRecord): [string, string] => { const w = r as WeekRecord; return [`${w.year}-W${String(w.week_number).padStart(2, '0')}`, `Week ${w.week_number}, ${w.year} (${w.start_date} to ${w.end_date})`] }
  const out: CalendarEntry[] = []
  for (const s of cal.monthly_series) out.push(...seriesEntries(s.records, month, 'month', window))
  for (const s of cal.weekly_series) out.push(...seriesEntries(s.records, week, 'week', window))
  return out
}

/** Platforms the vocabulary knows but this artifact has no data for. */
export function inactivePlatforms(cal: CalendarArtifact): string[] {
  const names: Record<ContractSensor, string> = { MODIS_Aqua: 'Aqua MODIS', VIIRS_SNPP: 'Suomi NPP VIIRS', VIIRS_NOAA20: 'NOAA-20 VIIRS', VIIRS_NOAA21: 'NOAA-21 VIIRS' }
  return cal.sensor_coverage.filter((c) => c.status === 'reserved_inactive').map((c) => names[c.sensor])
}

/** Footprint certification in plain words. Only a P2 complete certification counts. */
export function footprintStatus(cal: CalendarArtifact): 'certified' | 'not_certified' {
  return cal.footprint_certification?.status === 'complete' ? 'certified' : 'not_certified'
}

export type ComparisonAccess = 'evaluated' | 'blocked' | 'raw_only' | 'unavailable'

const APPLICABILITY: Record<ComparisonResult['applicability_status'], ComparisonView['applicability']> = {
  applicable: 'applicable', failed_applicability: 'failed', missing_required_support: 'missing', out_of_domain: 'out-of-domain',
}
const SENSITIVITY: Record<ComparisonResult['sensitivity_status'], string> = {
  stable_across_displayed_settings: 'Stable across the tested corrections',
  sensitive_to_assumptions: 'Depends on the correction',
  unavailable: 'Unavailable',
}

/** Build one area. The calendar and comparison must carry this option's own geometry, and a
 * comparison only attaches to an evaluated area with the same method, policy and period. */
export function areaFromArtifacts(option: RegionSelectorOption, calendar?: CalendarArtifact, comparison?: ComparisonResult): AreaView & { access: ComparisonAccess } {
  if (calendar && calendar.geometry_id !== option.geometry_id) throw new IdentityMismatch('calendar belongs to another area')
  if (comparison && comparison.contract_version !== CONTRACT_VERSION) throw new IdentityMismatch('comparison is not contract ' + CONTRACT_VERSION)
  if (comparison && comparison.geometry_id !== option.geometry_id) throw new IdentityMismatch('comparison belongs to another area; factors are never inherited')
  const evaluated = option.comparison_access_status === 'evaluated_comparison'
  if (comparison && !evaluated) throw new IdentityMismatch('this area has no evaluated comparison')
  if (comparison && (comparison.method_id !== option.evaluated_method_id || comparison.policy_id !== option.evaluated_policy_id || comparison.period_spec !== option.evaluated_period_spec)) {
    throw new IdentityMismatch('comparison does not match the area\'s evaluated method, policy and period')
  }
  const entries = calendar ? calendarEntries(calendar) : []
  const certified = calendar ? footprintStatus(calendar) === 'certified' : false
  let access: ComparisonAccess
  if (option.raw_data_status === 'unavailable' || option.comparison_access_status === 'unavailable') access = 'unavailable'
  else if (!evaluated) access = 'raw_only'
  else if (!comparison || !comparison.conclusion_eligible || !certified) access = 'blocked'
  else access = 'evaluated'
  const view: ComparisonView | undefined = comparison ? {
    applicability: APPLICABILITY[comparison.applicability_status],
    applicabilityDetail: comparison.applicability_checks.map((c) => c.detail).join(' '),
    statusLabel: comparison.reviewed_summary.status_label,
    outputCategory: comparison.reviewed_summary.output_category,
    cacheKey: cacheKeyOf(comparison),
    sensitivity: SENSITIVITY[comparison.sensitivity_status],
    inference: 'Not established',
    practicalChange: {
      category: comparison.practical_change.category,
      magnitude: comparison.practical_change.magnitude ?? null,
      units: comparison.practical_change.effect_units ?? null,
      margin: comparison.practical_change.practical_margin_tau ?? null,
      observedSigns: comparison.practical_change.observed_signs ?? [],
    },
    evidenceUrl: '',
  } : undefined
  const limitation = !certified ? 'The whole area is not certified as fully observed, so no whole-area comparison is shown.' : comparison?.reviewed_summary.limit_sentence ?? 'Satellite observations do not count individual fires.'
  return {
    id: option.geometry_id, name: option.display_name, rawOnly: !evaluated, entries,
    finding: access === 'evaluated' && comparison ? { text: comparison.reviewed_summary.finding_sentence, evidenceUrl: '' } : undefined,
    limitation, comparison: view, access,
  }
}

/** Build a comparison view from a ClaimAuditRecord (contract 1.6.0).
 * counterexample_interpretations are passed through verbatim — never recomputed. */
export function comparisonViewFromClaimAudit(record: ClaimAuditRecord): ComparisonView {
  if (record.contract_version !== CONTRACT_VERSION) throw new IdentityMismatch('claim audit is not contract ' + CONTRACT_VERSION)
  return {
    applicability: APPLICABILITY[record.applicability_status],
    applicabilityDetail: record.applicability_checks.map((c) => c.detail).join(' '),
    statusLabel: record.reviewed_summary.status_label,
    outputCategory: record.reviewed_summary.output_category,
    cacheKey: cacheKeyOf(record),
    sensitivity: SENSITIVITY[record.sensitivity_status],
    inference: 'Not established',
    practicalChange: {
      category: record.practical_change.category,
      magnitude: record.practical_change.magnitude ?? null,
      units: record.practical_change.effect_units ?? null,
      margin: record.practical_change.practical_margin_tau ?? null,
      observedSigns: record.practical_change.observed_signs ?? [],
    },
    evidenceUrl: '',
    counterexampleInterpretations: record.counterexample_interpretations,
  }
}

/** Findings pass the same gate as comparisons: evaluated area, eligible conclusion, certified footprint. */
export function findingVisible(area: { access?: ComparisonAccess; finding?: unknown }): boolean {
  return area.access === 'evaluated' && area.finding !== undefined
}

// --- Geographic composition counterexamples (plan Section 4B) ---

type Raw = Record<string, unknown>
const num = (v: unknown): number | undefined => (typeof v === 'number' && Number.isFinite(v) ? v : undefined)
const str = (v: unknown): string | undefined => (typeof v === 'string' && v.length ? v : undefined)
const obj = (v: unknown): Raw | undefined => (v && typeof v === 'object' && !Array.isArray(v) ? v as Raw : undefined)
const pair = (v: unknown): [number, number] | undefined => (Array.isArray(v) && v.length === 2 && num(v[0]) !== undefined && num(v[1]) !== undefined ? [v[0] as number, v[1] as number] : undefined)
const weightsText = (v: unknown): string | undefined => {
  const w = obj(v)
  if (!w) return undefined
  const parts = Object.entries(w).filter(([, x]) => num(x) !== undefined).map(([k, x]) => `${k} ${String(x)}`)
  return parts.length ? parts.join(', ') : undefined
}

/** Kinds of counterexample that are worked illustrations, not observations. */
const ILLUSTRATION_KINDS = new Set(['plan_fixture_hand_computed'])
const SYNTHETIC_KINDS = new Set(['synthetic_dev_fixture'])

/** Normalise one counterexample for display. Two artifact shapes are read:
 * the claim-audit shape (period_1 / period_2 / fixed_weight_standardization) and the Stage A
 * evidence shape (observed_regional_index_R / fixed_weight_R_std). Real-data items return null:
 * they are not illustrations and need their own approval before they are shown. */
export function counterexampleView(item: Raw, index = 0): CounterexampleView | null {
  const dataKind = str(item['data_kind']) ?? str(item['data_classification'])
  const kind: CounterexampleView['kind'] | null = dataKind && ILLUSTRATION_KINDS.has(dataKind) ? 'illustration' : dataKind && SYNTHETIC_KINDS.has(dataKind) ? 'synthetic' : null
  if (!kind) return null
  const id = str(item['counterexample_id']) ?? `counterexample-${index}`
  const label = str(item['label']) ?? 'Geographic composition counterexample'
  const limits = Array.isArray(item['limits']) ? (item['limits'] as unknown[]).filter((x): x is string => typeof x === 'string') : []

  let observed: CounterexampleView['observed']
  let standardized: CounterexampleView['standardized']
  const evidenceR = pair(item['observed_regional_index_R'])
  const evidenceStd = pair(item['fixed_weight_R_std'])
  if (evidenceR) observed = { first: evidenceR[0], second: evidenceR[1], changePercent: num(item['observed_pct_change']) }
  if (evidenceStd) standardized = { first: evidenceStd[0], second: evidenceStd[1], changePercent: num(item['fixed_weight_pct_change']), weights: weightsText(item['fixed_weights']) }
  const p1 = num(obj(item['period_1'])?.['regional_index_R'])
  const p2 = num(obj(item['period_2'])?.['regional_index_R'])
  if (!observed && p1 !== undefined && p2 !== undefined) observed = { first: p1, second: p2, changePercent: num(item['apparent_change_percent']) }
  const std = obj(item['fixed_weight_standardization'])
  const s1 = num(std?.['R_std_period_1'])
  const s2 = num(std?.['R_std_period_2'])
  if (!standardized && s1 !== undefined && s2 !== undefined) standardized = { first: s1, second: s2, changePercent: num(std?.['standardized_change_percent']), weights: weightsText(std?.['fixed_weights']) }

  const blockRates = Array.isArray(item['blocks'])
    ? (item['blocks'] as unknown[]).map(obj).filter((b): b is Raw => !!b && !!str(b['block_id']) && num(b['block_rate_r']) !== undefined).map((b) => ({ id: b['block_id'] as string, rate: b['block_rate_r'] as number }))
    : undefined
  const note = str(std?.['note']) ?? str(item['missing_block_rule'])
  return {
    id, label, kind, limits,
    text: str(item['interpretation']) ?? str(item['description'])?.replace(/^\[SYNTHETIC DEV FIXTURE\]\s*/, ''),
    observed, standardized,
    blockRates: blockRates && blockRates.length ? blockRates : undefined,
    note,
  }
}

/** Stage A evidence document format accepted from the static bundle. */
export const EVIDENCE_FORMAT = 'tte-stage-a-evidence-v1'

/** Build the evidence view from a Stage A evidence document. The document's own release status
 * decides what is shown: worked illustrations always, real-data items only once released. */
export function evidenceFromDocument(doc: Raw, evidenceUrl = ''): EvidenceView {
  if (doc['evidence_format'] !== EVIDENCE_FORMAT) throw new IdentityMismatch(`evidence format ${String(doc['evidence_format'])} is not ${EVIDENCE_FORMAT}`)
  if (doc['contract_version_installed'] !== CONTRACT_VERSION) throw new IdentityMismatch(`evidence contract ${String(doc['contract_version_installed'])} is not ${CONTRACT_VERSION}`)
  const releaseStatus = str(doc['release_status']) ?? 'not_released'
  const released = releaseStatus === 'released' || releaseStatus.startsWith('released:')
  const items = Array.isArray(doc['counterexample_interpretations']) ? (doc['counterexample_interpretations'] as unknown[]).map(obj).filter((x): x is Raw => !!x) : []
  const counterexamples: CounterexampleView[] = []
  let withheldCount = 0
  items.forEach((item, i) => {
    const view = counterexampleView(item, i)
    if (view) counterexamples.push(view)
    else withheldCount++ // real-data items: not shown until approved and verified
  })
  const inference = obj(doc['status_dimensions'])?.['inference_status']
  return {
    id: str(doc['evidence_id']) ?? 'evidence',
    released,
    releaseText: released ? 'Released' : 'Not released: awaiting scientific approval and independent verification',
    unit: str(doc['unit']),
    inference: inference === 'not_established' || inference === undefined ? 'Not established' : 'Recorded in the evidence file',
    counterexamples, withheldCount, evidenceUrl,
  }
}
