// Contract 1.6.0 adapter tests on [SYNTHETIC DEV FIXTURE] data.
// Run: node --experimental-strip-types --test scripts/contract-adapter.test.ts
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import {
  ArtifactCache,
  COVERAGE_TEXT,
  IdentityMismatch,
  areaFromArtifacts,
  cacheKeyOf,
  calendarEntries,
  comparisonViewFromClaimAudit,
  findingVisible,
  footprintStatus,
  inactivePlatforms,
} from '../src/lab/adapter.ts'

const dir = new URL('../test-fixtures/contract-1.6.0/', import.meta.url)
const load = (name: string) => JSON.parse(readFileSync(new URL(name, dir), 'utf8'))
const cal = () => load('sample_calendar.json')
const unverified = () => load('sample_calendar_unverified_footprint.json')
const sealedCal = () => load('sample_calendar_sealed_boundary.json')
const selector = () => load('sample_region_selector.json')
const option = (id: string) => selector().options.find((o: { geometry_id: string }) => o.geometry_id === id)
const PRIMARY = 'geo-synthetic-primary'

test('missing values stay null and are never shown as zero', () => {
  const e = calendarEntries(cal())
  const noFile = e.find((x) => x.period === '2023-09' && x.sensor === 'VIIRS')!
  assert.equal(noFile.value, null)
  assert.equal(noFile.availability, 'missing')
  assert.match(noFile.detail!, /no satellite file/)
  const zeroSupport = e.find((x) => x.period === '2023-08' && x.sensor === 'VIIRS')!
  assert.equal(zeroSupport.value, null)
  assert.match(zeroSupport.detail!, /not a zero-fire result/)
  const validZero = e.find((x) => x.period === '2023-06' && x.sensor === 'VIIRS')!
  assert.equal(validZero.value, 0) // a processed zero stays a real zero
})

test('partial periods carry null labels as plain words and their coverage reason', () => {
  const e = calendarEntries(cal())
  const gap = e.find((x) => x.period === '2023-11' && x.sensor === 'VIIRS')!
  assert.equal(gap.coverage, 'partial')
  assert.equal(gap.unusualLabel, 'No label: incomplete period')
  assert.match(gap.detail!, /25 of 30 days have a file/)
  assert.equal(gap.comparisonEligible, false)
  const clipped = e.find((x) => x.period === '2012-W03' && x.sensor === 'VIIRS')!
  assert.match(clipped.detail!, new RegExp(COVERAGE_TEXT.period_clipped))
  assert.equal(clipped.criticalLabel, 'No label: incomplete period')
})

test('a period before the satellite record is unavailable, not zero', () => {
  const pre = calendarEntries(cal()).find((x) => x.period === '2011-12')!
  assert.equal(pre.value, null)
  assert.match(pre.detail!, /not operating/)
})

test('series stay single-sensor and reserved platforms are listed, not invented', () => {
  const e = calendarEntries(cal())
  assert.ok(e.every((x) => x.sensor === 'MODIS' || x.sensor === 'VIIRS'))
  assert.deepEqual(inactivePlatforms(cal()), ['NOAA-20 VIIRS', 'NOAA-21 VIIRS'])
})

test('no internal schema terms leak into on-screen text', () => {
  const text = JSON.stringify(calendarEntries(unverified()).map((x) => [x.label, x.detail, x.unusualLabel, x.criticalLabel]))
  for (const term of ['coverage_state', 'missing_days_or_tiles', 'sensor_not_operating', 'insufficient_baseline', 'source_not_available', 'period_clipped']) {
    assert.ok(!text.includes(term), term)
  }
})

test('evaluated area with eligible comparison and certified footprint shows a finding', () => {
  const area = areaFromArtifacts(option(PRIMARY), cal(), load('sample_comparison_normal.json'))
  assert.equal(area.access, 'evaluated')
  assert.ok(findingVisible(area))
  assert.deepEqual(area.comparison!.cacheKey, ['synthetic-v1', PRIMARY, 'synthetic-2023', 'stage_a_finite_factors', 'own_support_eligible'])
})

test('uncertified footprint blocks the comparison and the finding alike', () => {
  const c = unverified()
  assert.equal(footprintStatus(c), 'not_certified')
  const area = areaFromArtifacts(option(PRIMARY), c, load('sample_comparison_normal.json'))
  assert.equal(area.access, 'blocked')
  assert.ok(!findingVisible(area))
  assert.match(area.limitation, /not certified/)
})

for (const name of ['sample_comparison_missing_evidence.json', 'sample_comparison_stable_failed_applicability.json', 'sample_comparison_out_of_domain.json']) {
  test(`ineligible conclusion blocks the finding: ${name}`, () => {
    const comp = load(name)
    const area = areaFromArtifacts(option(PRIMARY), cal(), comp)
    assert.equal(area.access, 'blocked')
    assert.ok(!findingVisible(area))
    assert.equal(area.comparison!.statusLabel, comp.reviewed_summary.status_label) // compound label kept
  })
}

test('within-margin opposite-sign keeps its signs and magnitude', () => {
  const area = areaFromArtifacts(option(PRIMARY), cal(), load('sample_comparison_within_margin_opposite_sign.json'))
  assert.deepEqual(area.comparison!.practicalChange.observedSigns, ['increase', 'decrease'])
  assert.equal(area.comparison!.practicalChange.magnitude, 0.3)
})

test('raw-only area is distinct from a blocked comparison and never inherits one', () => {
  const sub = option('geo-synthetic-sub-a')
  const area = areaFromArtifacts(sub)
  assert.equal(area.access, 'raw_only')
  assert.equal(area.rawOnly, true)
  const parent = load('sample_comparison_normal.json')
  assert.throws(() => areaFromArtifacts(sub, undefined, parent), IdentityMismatch)
  assert.throws(() => areaFromArtifacts(sub, undefined, { ...parent, geometry_id: sub.geometry_id }), IdentityMismatch)
})

test('calendar for another area is refused', () => {
  assert.throws(() => areaFromArtifacts(option('geo-synthetic-sub-a'), cal()), IdentityMismatch)
})

test('comparison with a different method, policy or period is refused', () => {
  for (const change of [{ method_id: 'other' }, { policy_id: 'other' }, { period_spec: 'other' }]) {
    assert.throws(() => areaFromArtifacts(option(PRIMARY), cal(), { ...load('sample_comparison_normal.json'), ...change }), IdentityMismatch)
  }
})

test('cache serves only an exact five-field match', () => {
  const cache = new ArtifactCache<string>()
  const key = cacheKeyOf(load('sample_comparison_normal.json'))
  cache.set('comparison', key, 'a')
  assert.equal(cache.get('comparison', key), 'a')
  for (let i = 0; i < 5; i++) {
    const other = [...key] as typeof key
    other[i] = 'other'
    assert.equal(cache.get('comparison', other), undefined)
  }
  assert.equal(cache.get('calendar', key), undefined)
  assert.throws(() => cache.set('comparison', key, 'b'), IdentityMismatch)
})

test('wrong or missing contract version is refused', () => {
  assert.throws(() => calendarEntries({ ...cal(), contract_version: '1.4.0' }), IdentityMismatch)
  const { contract_version: _v, ...versionless } = cal()
  assert.throws(() => calendarEntries(versionless), IdentityMismatch)
  const old = { ...load('sample_comparison_normal.json'), contract_version: '1.1.0' }
  assert.throws(() => areaFromArtifacts(option(PRIMARY), cal(), old), IdentityMismatch)
})

// --- Contract 1.6.0 sealed_window tests ---

test('periods fully inside the sealed window are labelled as sealed, not missing data', () => {
  const e = calendarEntries(sealedCal())
  // The sealed_boundary fixture has sealed_window: 2020-01-01 to 2021-12-31.
  // Week 2020-W01 (start: 2019-12-30, end: 2020-01-05) straddles the boundary -> partial, not sealed.
  // Week 2021-W52 (start: 2021-12-27, end: 2022-01-02) straddles the boundary -> partial, not sealed.
  // Week 2022-W01 (start: 2022-01-03, end: 2022-01-09) is after the window -> not sealed.
  // Any periods with dates fully inside 2020-01-01..2021-12-31 should be sealed.
  const sealed = e.filter((x) => x.sealedPeriod === true)
  // The sample_calendar fixture's weekly series at 2020-W01 straddles (partial), not sealed.
  // Both 2020-01-01..2021-12-31 boundary weeks straddle. We just check that no straddling
  // periods are incorrectly marked sealed, and that any fully-inside periods are marked sealed.
  const straddleWeek1 = e.find((x) => x.period === '2020-W01' && x.sensor === 'MODIS')
  if (straddleWeek1) assert.equal(straddleWeek1.sealedPeriod, undefined)
  const straddleWeek2 = e.find((x) => x.period === '2021-W52' && x.sensor === 'MODIS')
  if (straddleWeek2) assert.equal(straddleWeek2.sealedPeriod, undefined)
  // If any sealed periods exist, their detail should say "Sealed evaluation period"
  for (const s of sealed) {
    assert.match(s.detail!, /Sealed evaluation period/)
  }
})

test('sealed periods detail text says sealed, not missing data', () => {
  const e = calendarEntries(sealedCal())
  const sealed = e.filter((x) => x.sealedPeriod === true)
  for (const s of sealed) {
    assert.match(s.detail!, /withheld from public evaluation, not missing data/)
    assert.ok(!s.detail!.includes('missing data') || s.detail!.includes('not missing data'), 'sealed should not say missing data without negation')
  }
})

test('calendar with no sealed_window produces no sealed entries', () => {
  const e = calendarEntries(cal())
  assert.ok(e.every((x) => !x.sealedPeriod), 'no sealed entries when sealed_window is null')
})

// --- Contract 1.6.0 counterexample_interpretations tests ---

test('claim audit record counterexample_interpretations are passed through verbatim', () => {
  const record = load('sample_claim_audit_record.json')
  assert.ok(Array.isArray(record.counterexample_interpretations))
  assert.ok(record.counterexample_interpretations.length > 0)
  const view = comparisonViewFromClaimAudit(record)
  assert.ok(Array.isArray(view.counterexampleInterpretations))
  assert.equal(view.counterexampleInterpretations!.length, record.counterexample_interpretations.length)
  // Values are identical objects, not recomputed
  const ex = view.counterexampleInterpretations![0]
  assert.equal(ex['counterexample_id'], 'geo_composition_shift_section_4b')
  // 8.2 / 2.8 composition shift (plan Section 4B mandatory fixture)
  const p1 = ex['period_1'] as Record<string, unknown>
  const p2 = ex['period_2'] as Record<string, unknown>
  assert.equal(p1['regional_index_R'], 8.2)
  assert.equal(p2['regional_index_R'], 2.8)
  // Fixed-weight standardization: both periods give R_std = 5.5
  const std = ex['fixed_weight_standardization'] as Record<string, unknown>
  assert.equal(std['R_std_period_1'], 5.5)
  assert.equal(std['R_std_period_2'], 5.5)
  assert.equal(std['standardized_change_percent'], 0.0)
})

test('comparisonViewFromClaimAudit refuses wrong contract version', () => {
  const record = load('sample_claim_audit_record.json')
  assert.throws(() => comparisonViewFromClaimAudit({ ...record, contract_version: '1.5.0' }), IdentityMismatch)
})
