/** Quick Mission: one real case, read from the same evidence file as the Research Lab.
 *
 * Presentation only. Every number is copied from the evidence document as given (rates,
 * mapped rates, pooled relative errors, factors, boundary counts). Nothing is fitted,
 * re-weighted or averaged here, and no region borrows another region's correction.
 * Sealed years are never read. The finding and limit sentences are built from those values
 * by fixed templates, so the mission and the Lab cannot disagree. */
import type { Boundary, Composition, PolicyView, RegionEvidence, StageADetail } from './evidence.ts'
import { formatValue } from './view.ts'

export const FULL_TRAINING = 'full_training_2016_2017_2018'

export type MissionYear = {
  year: number
  aqua: number
  viirs: number
  /** VIIRS on the Aqua scale with the all-training-years correction. Undefined = not in the file. */
  mapped?: number
  /** (VIIRS - Aqua) / Aqua, before correction, as given. */
  rawGap?: number
  /** (corrected VIIRS - Aqua) / Aqua, as given. */
  gap?: number
  role: 'development' | 'applicability'
}

export type MissionCase = {
  region: RegionEvidence
  policy: PolicyView
  years: MissionYear[]
  sealedYears: number[]
  trainingYears: number[]
  factor: number | null
  envelope: [number, number] | null
  rawGapRange: [number, number] | null
  gapRange: [number, number] | null
  /** True only when VIIRS reads below Aqua in every year shown. */
  rawAlwaysBelow: boolean
  boundary: { outside: number; periods: number; above: number; below: number } | null
  composition?: Composition
  finding: string
  correction: string
  boundaryText: string
  limit: string
}

/** Signed percentage, one decimal, the same rounding as the Lab's harmonized table. */
export const pct = (n: number) => `${n > 0 ? '+' : n < 0 ? '\u2212' : ''}${Math.abs(n * 100).toFixed(1)}%`
const mag = (n: number) => `${Math.abs(n * 100).toFixed(1)}%`
const f = (n: number) => formatValue(n)
const range = (xs: number[]): [number, number] | null => (xs.length ? [Math.min(...xs), Math.max(...xs)] : null)
const yearsText = (ys: number[]) => (ys.length > 1 ? `${ys[0]} to ${ys[ys.length - 1]}` : ys.length ? String(ys[0]) : 'no years')

/** The observation set the mission uses: own-area observations when a correction exists for
 * them, otherwise the first set that has one. Null when no set in this region has a correction. */
export function missionPolicy(region: RegionEvidence): PolicyView | null {
  const has = (p: PolicyView) => p.variants.some((v) => v.id === FULL_TRAINING && v.available && v.factor !== null)
  return region.policies.find((p) => p.key === 'own_support' && has(p)) ?? region.policies.find(has) ?? null
}

function boundaryCounts(b: Boundary | undefined): MissionCase['boundary'] {
  if (!b || !b.available) return null
  const { a_break_outside_envelope: outside, periods, variants_above: above, variants_below: below } = b.counts
  if ([outside, periods, above, below].some((n) => typeof n !== 'number')) return null
  return { outside, periods, above, below }
}

export function missionCase(detail: StageADetail, code: string): MissionCase | null {
  const region = detail.regions.find((r) => r.code === code)
  if (!region) return null
  const policy = missionPolicy(region)
  if (!policy) return null
  const sealed = new Set(detail.sealedYears)
  const full = policy.variants.find((v) => v.id === FULL_TRAINING)
  const factor = full?.available && full.factor !== null ? full.factor : null
  const years: MissionYear[] = policy.years.filter((y) => !sealed.has(y.year)).map((y) => {
    const m = y.variants.find((v) => v.id === FULL_TRAINING)
    const raw = y.variants.find((v) => v.id === 'raw')
    return { year: y.year, role: y.role, aqua: y.aqua.rate, viirs: y.viirs.rate, mapped: m?.mappedRate, gap: m?.pooledRelativeError, rawGap: raw?.pooledRelativeError }
  })
  const rawGaps = years.map((y) => y.rawGap).filter((x): x is number => x !== undefined)
  const gaps = years.map((y) => y.gap).filter((x): x is number => x !== undefined)
  const rawGapRange = range(rawGaps)
  const gapRange = range(gaps)
  const rawAlwaysBelow = rawGaps.length === years.length && rawGaps.length > 0 && rawGaps.every((g) => g < 0)
  const boundary = boundaryCounts(region.boundaries.find((b) => b.policyKey === policy.key))
  const composition = detail.composition.find((c) => c.bySensor.aqua.length > 0)
  const listed = years.map((y) => y.year)
  const shown = listed.length > 1 ? `${listed.slice(0, -1).join(', ')} and ${listed[listed.length - 1]}` : listed.join('')
  const training = yearsText(detail.trainingYears)

  const finding = rawGapRange && rawAlwaysBelow
    ? `In ${region.name}, VIIRS records a fire activity rate ${mag(rawGapRange[1])} to ${mag(rawGapRange[0])} lower than MODIS / Aqua in every year shown (${shown}), over the same weeks and land.`
    : rawGapRange
      ? `In ${region.name}, VIIRS and MODIS / Aqua differ by ${pct(rawGapRange[0])} to ${pct(rawGapRange[1])} over the same weeks and land (${shown}).`
      : `In ${region.name}, the evidence file gives no year-by-year gap between the two satellites.`
  const correction = factor !== null && gapRange
    ? `Put on the Aqua scale (VIIRS \u00d7 ${f(factor)}, fitted on ${training}), the gap is ${pct(gapRange[0])} to ${pct(gapRange[1])}.`
    : 'No correction could be fitted for this area, so VIIRS is not put on the Aqua scale. Nothing is substituted.'
  const boundaryText = !boundary
    ? 'The file gives no reading of which correction would make the two satellites agree.'
    : `The correction that would make corrected VIIRS equal Aqua falls outside the tested range in ${boundary.outside} of ${boundary.periods} years. `
      + (boundary.above === boundary.periods ? `Every tested correction puts VIIRS above Aqua in all ${boundary.periods} years.`
        : boundary.below === boundary.periods ? `Every tested correction puts VIIRS below Aqua in all ${boundary.periods} years.`
          : `Every tested correction puts VIIRS above Aqua in ${boundary.above} years and below in ${boundary.below}, so the direction of the remaining gap changes from year to year.`)
  const limit = 'These rates count grid cell-days with detected fire, not fires or FIRMS points, and the tested corrections vary only the training years, not every possible sensor difference.'

  return { region, policy, years, sealedYears: detail.sealedYears, trainingYears: detail.trainingYears, factor, envelope: policy.envelope, rawGapRange, gapRange, rawAlwaysBelow, boundary, composition, finding, correction, boundaryText, limit }
}
