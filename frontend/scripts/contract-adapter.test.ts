// Contract 1.4.0 adapter tests on [SYNTHETIC DEV FIXTURE] data.
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
  findingVisible,
  footprintStatus,
  inactivePlatforms,
} from '../src/lab/adapter.ts'

const dir = new URL('../test-fixtures/contract-1.4.0/', import.meta.url)
const load = (name: string) => JSON.parse(readFileSync(new URL(name, dir), 'utf8'))
const cal = () => load('sample_calendar.json')
const unverified = () => load('sample_calendar_unverified_footprint.json')
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

test('wrong contract version is refused', () => {
  assert.throws(() => calendarEntries({ ...cal(), contract_version: '1.3.0' }), IdentityMismatch)
})
