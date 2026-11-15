// Contract 1.6.0 adapter tests on [SYNTHETIC DEV FIXTURE] data.
// Run: node --experimental-strip-types --test scripts/contract-adapter.test.ts
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { existsSync, readFileSync } from 'node:fs'
import { createHash } from 'node:crypto'
import {
  ArtifactCache,
  COVERAGE_TEXT,
  EVIDENCE_FORMAT,
  IdentityMismatch,
  areaFromArtifacts,
  cacheKeyOf,
  calendarEntries,
  comparisonViewFromClaimAudit,
  counterexampleView,
  evidenceFromDocument,
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

test('the declared sealed window is shown as sealed, never as missing, zero or no file', () => {
  const c = sealedCal()
  assert.deepEqual([c.sealed_window.start, c.sealed_window.end], ['2020-01-01', '2021-12-31'])
  const weeks = calendarEntries(c).filter((x) => x.sensor === 'MODIS' && x.resolution === 'week')
  const sealed = weeks.filter((x) => x.availability === 'sealed')
  assert.equal(sealed.length, 1)
  const s = sealed[0]
  assert.equal(s.sealedPeriod, true)
  assert.equal(s.value, null) // no value is shown for the sealed window
  assert.equal(s.label, '2020-01-01 to 2021-12-31')
  assert.match(s.detail!, /not missing data/)
  assert.doesNotMatch(s.detail!, /no satellite file|zero-fire|Unavailable:/)
  // Placed between the last week before the window and the first week after it starts.
  const order = weeks.map((x) => x.period)
  assert.deepEqual(order.slice(order.indexOf('2020-W01'), order.indexOf('2020-W01') + 3), ['2020-W01', s.period, '2021-W52'])
  // Straddling weeks keep their own values and say part of them is held back.
  for (const p of ['2020-W01', '2021-W52']) {
    const w = weeks.find((x) => x.period === p)!
    assert.equal(w.availability, 'available')
    assert.equal(w.sealedPeriod, undefined)
    assert.match(w.detail!, new RegExp(COVERAGE_TEXT.partition_boundary))
  }
  // Nothing in this artifact is rendered as missing because of the window.
  assert.ok(weeks.every((x) => x.availability !== 'missing'))
})

test('every series that spans the window gets its own sealed row; others get none', () => {
  const e = calendarEntries(sealedCal())
  const rows = e.filter((x) => x.availability === 'sealed').map((x) => `${x.sensor}/${x.resolution}`).sort()
  // MODIS weekly (2015-2022), MODIS monthly (2002-2023), VIIRS monthly (2011-2023) span the window.
  assert.deepEqual(rows, ['MODIS/month', 'MODIS/week', 'VIIRS/month'])
  const proposed = sealedCal()
  proposed.sealed_window = { start: '2020-01-01', end: '2021-12-31', registration_status: 'proposed_unregistered', registration_ref: null, decision_date: null }
  const p = calendarEntries(proposed).find((x) => x.availability === 'sealed')!
  assert.match(p.detail!, /proposed and not yet registered/)
})

test('a record wholly inside the sealed window is refused, so its value never reaches the screen', () => {
  const c = sealedCal()
  const series = c.weekly_series[0]
  series.records.push({ ...series.records[0], year: 2020, week_number: 30, start_date: '2020-07-20', end_date: '2020-07-26' })
  assert.throws(() => calendarEntries(c), IdentityMismatch)
})

test('calendar with no sealed_window produces no sealed entries', () => {
  const e = calendarEntries(cal())
  assert.ok(e.every((x) => !x.sealedPeriod && x.availability !== 'sealed'), 'no sealed entries when sealed_window is null')
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


test('claim-audit counterexample normalises to 8.2/2.8 observed and 5.5/5.5 fixed-weight', () => {
  const [item] = load('sample_claim_audit_record.json').counterexample_interpretations
  const v = counterexampleView(item)!
  assert.equal(v.kind, 'synthetic')
  assert.deepEqual(v.observed, { first: 8.2, second: 2.8, changePercent: -65.85 })
  assert.deepEqual(v.standardized, { first: 5.5, second: 5.5, changePercent: 0, weights: 'A 0.5, B 0.5' })
  assert.deepEqual(v.blockRates, [{ id: 'A', rate: 10 }, { id: 'B', rate: 1 }])
  assert.ok(!v.text!.startsWith('[SYNTHETIC DEV FIXTURE]'))
})

test('a counterexample with missing numbers stays unavailable, never zero', () => {
  const [item] = load('sample_claim_audit_record.json').counterexample_interpretations
  const v = counterexampleView({ ...item, period_2: { observation_shares: {} }, fixed_weight_standardization: undefined })!
  assert.equal(v.observed, undefined)
  assert.equal(v.standardized, undefined)
})

// --- Static bundle from artifact_pipeline/ (public/artifacts) ---

const artifacts = new URL('../public/artifacts/', import.meta.url)
const pipelineBundle = new URL('../../artifact_pipeline/build/bundle/', import.meta.url)
const bundleIndex = () => JSON.parse(readFileSync(new URL('bundle_index.json', artifacts), 'utf8'))

test('public/artifacts is a byte-for-byte copy of the latest artifact_pipeline bundle', { skip: !existsSync(new URL('bundle_index.json', pipelineBundle)) && 'artifact_pipeline bundle not in this checkout' }, () => {
  const index = bundleIndex()
  const files = ['bundle_index.json', ...index.evidence_entries.flatMap((e: { path: string; gzip_path: string }) => [e.path, e.gzip_path]), ...index.entries.map((e: { path: string }) => e.path)]
  for (const f of files) assert.ok(readFileSync(new URL(f, artifacts)).equals(readFileSync(new URL(f, pipelineBundle))), `stale copy: ${f}`)
})

test('bundle evidence matches its sha256 and contract 1.6.0', () => {
  const index = bundleIndex()
  assert.equal(index.bundle_format, 'tte-static-bundle-v1')
  assert.equal(index.contract_version, '1.6.0')
  assert.ok(index.evidence_entries.length > 0)
  for (const e of index.evidence_entries) {
    assert.equal(createHash('sha256').update(readFileSync(new URL(e.path, artifacts))).digest('hex'), e.sha256)
  }
})

test('bundle evidence shows the Section 4B illustration and withholds unreleased real-data checks', () => {
  const entry = bundleIndex().evidence_entries.find((e: { evidence_format: string }) => e.evidence_format === EVIDENCE_FORMAT)
  const doc = JSON.parse(readFileSync(new URL(entry.path, artifacts), 'utf8'))
  const view = evidenceFromDocument(doc)
  assert.equal(view.released, false) // document says not_released
  assert.equal(view.inference, 'Not established')
  const fixture = view.counterexamples.find((x) => x.id === 'geo_composition_shift_section_4b')!
  assert.equal(fixture.kind, 'illustration')
  assert.deepEqual([fixture.observed!.first, fixture.observed!.second], [8.2, 2.8])
  assert.deepEqual([fixture.standardized!.first, fixture.standardized!.second], [5.5, 5.5])
  assert.equal(fixture.standardized!.changePercent, 0)
  // Real-data items are counted but never rendered before approval.
  const real = doc.counterexample_interpretations.filter((x: { data_kind: string }) => x.data_kind.startsWith('real_data'))
  assert.equal(view.withheldCount, real.length)
  assert.equal(view.counterexamples.length, doc.counterexample_interpretations.length - real.length)
  assert.ok(!JSON.stringify(view.counterexamples).includes('British Columbia'))
})

test('evidence with another format or contract version is refused', () => {
  const entry = bundleIndex().evidence_entries[0]
  const doc = JSON.parse(readFileSync(new URL(entry.path, artifacts), 'utf8'))
  assert.throws(() => evidenceFromDocument({ ...doc, evidence_format: 'other' }), IdentityMismatch)
  assert.throws(() => evidenceFromDocument({ ...doc, contract_version_installed: '1.5.0' }), IdentityMismatch)
})
