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
import type { AreaView, CacheKey, CalendarEntry, ComparisonView, Sensor } from './model.ts'

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

/** Check whether a calendar period date range falls fully inside the declared sealed window.
 * Periods that cross a boundary have partial_period_reason = crosses_sealed_evaluation_boundary
 * in coverage_reasons; fully-inside periods are set aside and labelled as sealed.
 * Date strings are ISO-8601 (YYYY-MM-DD). No observation value is read.
 */
function isInsideSealedWindow(periodStart: string, periodEnd: string, window: SealedWindow): boolean {
  return periodStart >= window.start && periodEnd <= window.end
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

function coverageNote(rec: MonthRecord | WeekRecord, sealed: boolean): string | undefined {
  if (rec.coverage_state === 'complete') return undefined
  const reasons = rec.coverage_reasons.map((r) => COVERAGE_TEXT[r]).join('; ')
  const days = rec.coverage_state === 'partial' ? ` (${rec.days_with_file} of ${rec.days_in_period} days have a file)` : ''
  if (sealed) {
    // The period is fully inside the sealed evaluation window: label it sealed, not missing data.
    return `Sealed evaluation period: withheld from public evaluation, not missing data${days}`
  }
  return `${rec.coverage_state === 'partial' ? 'Partial period' : 'Unavailable'}: ${reasons}${days}`
}

function entry(rec: MonthRecord | WeekRecord, period: string, label: string, resolution: 'month' | 'week', sealedWindow: SealedWindow | null): CalendarEntry | null {
  const sensor = SENSOR[rec.sensor]
  if (!sensor) return null // reserved platforms carry no records in this phase
  const value = rec.availability === 'available' && typeof rec.fire_activity_index === 'number' ? rec.fire_activity_index : null
  const why = rec.availability === 'unavailable' && rec.unavailable_reason ? UNAVAILABLE_TEXT[rec.unavailable_reason] : undefined
  const isWeek = 'week_number' in rec

  // Determine if this period is fully inside the declared sealed window.
  let sealed = false
  if (sealedWindow) {
    const { start, end } = periodDates(rec)
    sealed = isInsideSealedWindow(start, end, sealedWindow)
  }

  return {
    period, label, sensor, resolution, value,
    unit: 'detected fire cell-days per 1,000 usable land cell-days',
    availability: value === null ? 'missing' : 'available',
    detail: [why, coverageNote(rec, sealed)].filter(Boolean).join('. ') || undefined,
    coverage: rec.coverage_state,
    unusualLabel: labelText(rec.unusual_status),
    criticalLabel: isWeek ? labelText((rec as WeekRecord).critical_status) : undefined,
    comparisonEligible: rec.comparison_eligible,
    sealedPeriod: sealed || undefined,
  }
}

/** All monthly and weekly entries, one sensor per series, never merged across sensors. */
export function calendarEntries(cal: CalendarArtifact): CalendarEntry[] {
  // Required since contract 1.4.0 (8edec46): a missing or older version is refused, never assumed.
  if (cal.contract_version !== CONTRACT_VERSION) throw new IdentityMismatch(`contract ${String(cal.contract_version)} is not ${CONTRACT_VERSION}`)
  const sealedWindow = cal.sealed_window ?? null
  const out: CalendarEntry[] = []
  for (const s of cal.monthly_series) for (const r of s.records) {
    const e = entry(r, `${r.year}-${String(r.month).padStart(2, '0')}`, `${MONTHS[r.month - 1]} ${r.year}`, 'month', sealedWindow)
    if (e) out.push(e)
  }
  for (const s of cal.weekly_series) for (const r of s.records) {
    const e = entry(r, `${r.year}-W${String(r.week_number).padStart(2, '0')}`, `Week ${r.week_number}, ${r.year} (${r.start_date} to ${r.end_date})`, 'week', sealedWindow)
    if (e) out.push(e)
  }
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
    id: option.geometry_id, name: option.display_name, rawOnly: !evaluated, role: option.geometry_role, entries,
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
