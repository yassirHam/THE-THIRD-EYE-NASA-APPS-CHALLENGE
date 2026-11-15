// Quick Mission tests on the real published evidence bundle (public/artifacts).
// Run: node --experimental-strip-types --test scripts/mission.test.ts
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { evidenceFromJson, type StageADetail } from '../src/lab/evidence.ts'
import { FULL_TRAINING, missionCase, pct } from '../src/lab/mission.ts'

const artifacts = new URL('../public/artifacts/', import.meta.url)
const index = JSON.parse(readFileSync(new URL('bundle_index.json', artifacts), 'utf8'))
const entry = index.evidence_entries.find((e: { evidence_format: string }) => e.evidence_format === 'tte-stage-a-evidence-v1')
const raw = () => JSON.parse(readFileSync(new URL(entry.path, artifacts), 'utf8'))
const detail = (): StageADetail => evidenceFromJson(raw())
const SCHEMA_TERMS = ['own_support', 'common_support', 'not_established', 'applicability_status', 'inference_status', 'calibration_sensitivity', 'raw_only', 'evaluated_calibration', 'a_break', 'full_training', 'ex_201', 'mapped_rate', 'pooled_relative_error']

for (const code of ['826', '3218']) {
  test(`mission case ${code} copies the evidence file's own numbers`, () => {
    const d = detail()
    const c = missionCase(d, code)!
    assert.ok(c, 'case exists')
    assert.equal(c.policy.key, 'own_support')
    const full = c.policy.variants.find((v) => v.id === FULL_TRAINING)!
    assert.equal(c.factor, full.factor)
    assert.deepEqual(c.envelope, c.policy.envelope)
    for (const y of c.years) {
      const src = c.policy.years.find((x) => x.year === y.year)!
      assert.equal(y.aqua, src.aqua.rate)
      assert.equal(y.viirs, src.viirs.rate)
      assert.equal(y.gap, src.variants.find((v) => v.id === FULL_TRAINING)?.pooledRelativeError)
      assert.equal(y.rawGap, src.variants.find((v) => v.id === 'raw')?.pooledRelativeError)
    }
    const gaps = c.years.map((y) => y.gap!)
    assert.deepEqual(c.gapRange, [Math.min(...gaps), Math.max(...gaps)])
    assert.ok(c.correction.includes(pct(c.gapRange![0])) && c.correction.includes(pct(c.gapRange![1])))
  })

  test(`mission case ${code} never shows a sealed year`, () => {
    const d = detail()
    const c = missionCase(d, code)!
    assert.deepEqual(c.sealedYears, [2020, 2021])
    for (const y of c.years) assert.ok(!d.sealedYears.includes(y.year), String(y.year))
    assert.ok(!/2020|2021/.test(c.finding + c.correction + c.boundaryText))
  })

  test(`mission case ${code} text has no internal schema terms`, () => {
    const c = missionCase(detail(), code)!
    const text = [c.finding, c.correction, c.boundaryText, c.limit].join(' ')
    for (const t of SCHEMA_TERMS) assert.ok(!text.includes(t), t)
  })
}

test('British Columbia: the remaining gap changes direction, and the text says so', () => {
  const c = missionCase(detail(), '826')!
  assert.deepEqual(c.boundary, { outside: 5, periods: 5, above: 2, below: 3 })
  assert.match(c.boundaryText, /outside the tested range in 5 of 5 years/)
  assert.match(c.boundaryText, /above Aqua in 2 years and below in 3/)
  assert.ok(c.rawAlwaysBelow)
})

test('California: every tested correction lands above Aqua, and the text says so', () => {
  const c = missionCase(detail(), '3218')!
  assert.deepEqual(c.boundary, { outside: 5, periods: 5, above: 5, below: 0 })
  assert.match(c.boundaryText, /above Aqua in all 5 years/)
})

test('an area with no fitted correction gets no mission case, never a borrowed one', () => {
  const doc = raw()
  for (const p of Object.values(doc.stage_a_summary.regions['826'].policies) as Array<{ variants: Record<string, { factor: unknown; status: string }> }>) {
    for (const v of Object.values(p.variants)) { v.factor = null; v.status = 'unavailable' }
  }
  const d = evidenceFromJson(doc)
  assert.equal(missionCase(d, '826'), null)
  assert.ok(missionCase(d, '3218'), 'the other area is unaffected')
})

test('an unknown area gets no mission case', () => {
  assert.equal(missionCase(detail(), 'nowhere'), null)
})

test('a missing yearly gap stays unavailable, never zero', () => {
  const doc = raw()
  const y = doc.stage_a_summary.regions['3218'].policies.own_support.applicability['2024']
  delete y.by_variant[FULL_TRAINING].pooled_relative_error
  const c = missionCase(evidenceFromJson(doc), '3218')!
  assert.equal(c.years.find((x) => x.year === 2024)!.gap, undefined)
  assert.ok(!c.years.some((x) => x.gap === 0))
})
