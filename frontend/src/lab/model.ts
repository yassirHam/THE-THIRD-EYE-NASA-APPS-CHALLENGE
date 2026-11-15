/** Presentation model only. P4's published artifact contract must be adapted here;
 * these types are not a scientific schema or an approval of any result. */
export type Sensor = 'MODIS' | 'VIIRS'
export type Resolution = 'month' | 'week'
export type Availability = 'available' | 'missing' | 'failed' | 'out-of-domain'
export type CalendarEntry = {
  period: string
  label: string
  sensor: Sensor
  resolution: Resolution
  value: number | null
  unit: string
  availability: Availability
  detail?: string
  /** Contract 1.4.0 coverage state of this sensor-period (partial periods carry no labels). */
  coverage?: 'complete' | 'partial' | 'unavailable'
  unusualLabel?: string
  criticalLabel?: string
  comparisonEligible?: boolean
  /** Contract 1.6.0: true when the period falls inside the artifact's declared sealed evaluation
   * window. Sealed periods are withheld from public evaluation, not missing data. */
  sealedPeriod?: boolean
}

/** Contract 1.4.0 five-field compound identity. A cached factor, baseline or result may be reused
 * only when all five fields match; never key a cache on the area alone. */
export type CacheKey = [artifactVersion: string, geometryId: string, periodSpec: string, methodId: string, policyId: string]

/** Contract 1.4.0 reviewed-summary categories and their plain-language labels. */
export type OutputCategory =
  | 'consistent_across_tested_corrections'
  | 'depends_on_the_correction'
  | 'not_enough_usable_evidence'
  | 'outside_evaluated_calibration'
  | 'calibration_check_failed'
  | 'calibration_check_failed_and_missing_evidence'
  | 'outside_evaluated_calibration_and_missing_evidence'
export const STATUS_LABELS: Record<OutputCategory, string> = {
  consistent_across_tested_corrections: 'Consistent across tested corrections',
  depends_on_the_correction: 'Depends on the correction',
  not_enough_usable_evidence: 'Not enough usable evidence',
  outside_evaluated_calibration: 'Outside evaluated calibration',
  calibration_check_failed: 'Calibration check failed',
  calibration_check_failed_and_missing_evidence: 'Calibration check failed and required evidence missing',
  outside_evaluated_calibration_and_missing_evidence: 'Outside evaluated calibration and required evidence missing',
}

export type PracticalChangeCategory =
  | 'meaningful_increase'
  | 'meaningful_decrease'
  | 'within_practical_margin'
  | 'inconsistent_across_variants'
  | 'unspecified'
  | 'unavailable'
export type PracticalChangeView = {
  category: PracticalChangeCategory
  /** Largest absolute tested change, in `units`. Shown as given, never rounded to zero. */
  magnitude?: number | null
  units?: string | null
  margin?: number | null
  observedSigns?: Array<'increase' | 'decrease' | 'no_change'>
}

export type AreaView = {
  id: string
  name: string
  rawOnly: boolean
  entries: CalendarEntry[]
  finding?: { text: string; evidenceUrl: string }
  limitation: string
  comparison?: ComparisonView
  normalSeason?: { text: string; evidenceUrl: string }
  artifactUrl?: string
  /** evaluated: comparison and finding may show; blocked: evaluated area whose evidence or
   * footprint does not allow a conclusion; raw_only: no evaluation for this area. */
  access?: 'evaluated' | 'blocked' | 'raw_only' | 'unavailable'
}
export type ComparisonView = {
  applicability: 'applicable' | 'failed' | 'missing' | 'out-of-domain'
  applicabilityDetail: string
  /** The artifact's own plain-language status label; shown as-is when present. */
  statusLabel?: string
  outputCategory?: OutputCategory
  cacheKey?: CacheKey
  sensitivity: string
  inference: string
  practicalChange: PracticalChangeView
  evidenceUrl: string
  /** Contract 1.6.0 geographic composition counterexamples from the claim audit record.
   * Each entry is preserved verbatim from the artifact; never recomputed or zero-filled. */
  counterexampleInterpretations?: Array<Record<string, unknown>>
}
export type LabView = { areas: AreaView[]; headline?: { text: string; denominator: string; evidenceUrl: string } }

const formatNumber = (value: number) => value.toLocaleString(undefined, { maximumSignificantDigits: 6 })
const withUnits = (value: number, units?: string | null) => `${formatNumber(value)}${units ? ` ${units}` : ''}`

/** Plain-language practical change. Within-margin results keep their size and any
 * opposite signs; they are never described as "No change". */
export function describePracticalChange(change: PracticalChangeView): string {
  const size = typeof change.magnitude === 'number' && Number.isFinite(change.magnitude) ? change.magnitude : null
  const signs = new Set(change.observedSigns ?? [])
  const opposite = signs.has('increase') && signs.has('decrease')
  switch (change.category) {
    case 'unavailable':
      return 'Unavailable'
    case 'within_practical_margin': {
      const parts = ['Within practical margin']
      if (size !== null) parts.push(`largest tested change ${withUnits(size, change.units)}`)
      if (typeof change.margin === 'number' && Number.isFinite(change.margin)) parts.push(`margin ${withUnits(change.margin, change.units)}`)
      let text = parts.length > 1 ? `${parts[0]}: ${parts.slice(1).join(', ')}` : parts[0]
      if (opposite) text += '. Tested corrections point in opposite directions'
      return text
    }
    case 'meaningful_increase':
      return size !== null ? `Meaningful increase: ${withUnits(size, change.units)}` : 'Meaningful increase'
    case 'meaningful_decrease':
      return size !== null ? `Meaningful decrease: ${withUnits(size, change.units)}` : 'Meaningful decrease'
    case 'inconsistent_across_variants':
      return 'Differs across tested corrections'
    case 'unspecified':
      return size !== null ? `Largest tested change ${withUnits(size, change.units)}; no practical margin registered` : 'No practical margin registered'
  }
}

// Real artifacts enter through src/lab/adapter.ts (contract 1.4.0). Keep this empty until
// approved, non-synthetic artifacts are available.
export const labView: LabView = { areas: [] }
