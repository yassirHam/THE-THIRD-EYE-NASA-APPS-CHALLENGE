// Copy (or --check) the P4 generated contract types and the synthetic test fixtures used by
// scripts/contract-adapter.test.ts. Source: ../contracts (present after P4-B is integrated).
//   node scripts/sync-contract.mjs          copy
//   node scripts/sync-contract.mjs --check  exit 1 if the vendored copies differ
import { existsSync, readFileSync, writeFileSync } from 'node:fs'

const check = process.argv.includes('--check')
const root = new URL('../../contracts/', import.meta.url)
const fixtures = [
  'sample_calendar.json', 'sample_calendar_unverified_footprint.json', 'sample_region_selector.json',
  'sample_comparison_normal.json', 'sample_comparison_missing_evidence.json',
  'sample_comparison_stable_failed_applicability.json', 'sample_comparison_out_of_domain.json',
  'sample_comparison_within_margin_opposite_sign.json',
]
const pairs = [
  [new URL('generated/types.ts', root), new URL('../src/contracts/types.ts', import.meta.url)],
  ...fixtures.map((n) => [new URL(`fixtures/${n}`, root), new URL(`../test-fixtures/contract-1.4.0/${n}`, import.meta.url)]),
]
if (!existsSync(new URL('generated/types.ts', root))) {
  console.log('SKIPPED: ../contracts is not in this checkout (P4-B not integrated yet)')
  process.exit(0)
}
const norm = (s) => s.replace(/\r\n/g, '\n')
let stale = 0
for (const [src, dst] of pairs) {
  const want = norm(readFileSync(src, 'utf8'))
  const have = existsSync(dst) ? norm(readFileSync(dst, 'utf8')) : null
  if (want === have) continue
  if (check) { console.error(`stale: ${dst.pathname}`); stale++ } else { writeFileSync(dst, want); console.log(`wrote ${dst.pathname}`) }
}
if (stale) process.exit(1)
console.log(check ? 'contract copies are current' : 'sync done')
