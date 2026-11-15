import type { PolicyView, RegionEvidence, StageADetail } from './evidence'
import { formatValue } from './view'
import { SHOW_REVIEW_NOTICES } from './presentation'

/** VIIRS put on the MODIS / Aqua scale with the correction fitted on the training years, next to
 * Aqua and raw VIIRS. Every number is the evidence file's own (mapped_rate, pooled_relative_error);
 * nothing is rescaled here. Lines never cross the sealed years, and no trend, peak or anomaly
 * verdict is drawn: the correction has not yet been tested on the sealed years. */
const FULL = 'full_training_2016_2017_2018'
const f = (n: number) => formatValue(n)
const pct = (n: number) => `${n > 0 ? '+' : n < 0 ? '\u2212' : ''}${Math.abs(n * 100).toFixed(1)}%`

type Row = { year: number; sealed: boolean; aqua?: number; viirs?: number; mapped?: number; lo?: number; hi?: number; error?: number; rawError?: number; role?: string }

function rowsFor(detail: StageADetail, policy: PolicyView): Row[] {
  const years = policy.years.map((y) => y.year)
  if (!years.length) return []
  const first = Math.min(...years), last = Math.max(...years)
  const out: Row[] = []
  for (let y = first; y <= last; y += 1) {
    if (detail.sealedYears.includes(y)) { out.push({ year: y, sealed: true }); continue }
    const r = policy.years.find((x) => x.year === y)
    if (!r) { out.push({ year: y, sealed: false }); continue }
    const full = r.variants.find((v) => v.id === FULL)
    const raw = r.variants.find((v) => v.id === 'raw')
    const tested = r.variants.filter((v) => v.id !== 'raw' && v.mappedRate !== undefined).map((v) => v.mappedRate as number)
    out.push({
      year: y, sealed: false, aqua: r.aqua.rate, viirs: r.viirs.rate,
      mapped: full?.mappedRate, lo: tested.length ? Math.min(...tested) : undefined, hi: tested.length ? Math.max(...tested) : undefined,
      error: full?.pooledRelativeError, rawError: raw?.pooledRelativeError, role: r.role,
    })
  }
  return out
}

export function harmonyAvailable(policy: PolicyView | undefined): boolean {
  return !!policy?.years.some((y) => y.variants.some((v) => v.id === FULL && v.mappedRate !== undefined))
}

export default function Harmony({ detail, region, policy, compact }: { detail: StageADetail; region: RegionEvidence; policy: PolicyView; compact?: boolean }) {
  const rows = rowsFor(detail, policy)
  if (!harmonyAvailable(policy)) return (
    <section className="hm hm--none" aria-label="Harmonized view">
      <h3>Harmonized view unavailable for this observation set</h3>
      <p className="lab__note">None of the corrections could be fitted for {policy.label.toLowerCase()}, so VIIRS cannot be put on the Aqua scale here. Nothing is substituted. Choose own-area observations.</p>
    </section>
  )
  const W = compact ? 620 : 900, H = compact ? 230 : 320, m = { l: 56, r: 16, t: 18, b: 32 }
  const iw = W - m.l - m.r, ih = H - m.t - m.b, sw = iw / rows.length
  const top = Math.max(...rows.flatMap((r) => [r.aqua ?? 0, r.viirs ?? 0, r.hi ?? 0, r.mapped ?? 0])) * 1.12 || 1
  const x = (i: number) => m.l + i * sw + sw / 2
  const y = (v: number) => m.t + ih - (v / top) * ih
  // a line segment only joins two neighbouring years that both have a value
  const path = (key: 'aqua' | 'viirs' | 'mapped') => rows.map((r, i) => {
    const v = r[key]
    if (v === undefined) return ''
    const prev = rows[i - 1]?.[key]
    return `${prev === undefined ? 'M' : 'L'}${x(i)},${y(v)}`
  }).join(' ')
  const band = rows.map((r, i) => (r.lo !== undefined && r.hi !== undefined ? <rect key={r.year} x={x(i) - sw * 0.18} y={y(r.hi)} width={sw * 0.36} height={Math.max(1.5, y(r.lo) - y(r.hi))} className="hm__band" /> : null))
  const factor = policy.variants.find((v) => v.id === FULL)?.factor

  return (
    <section className={`hm ${compact ? 'hm--compact' : ''}`} aria-label="Harmonized view">
      <div className="hm__head">
        <div><p className="lab__eyebrow">Harmonized view{SHOW_REVIEW_NOTICES ? ' · preliminary' : ''}</p><h3>{region.name}: VIIRS on the Aqua scale</h3></div>
        {SHOW_REVIEW_NOTICES ? <span className="lab__status lab__status--synthetic">Not yet tested on sealed years</span> : <span className="lab__status">MODIS / Aqua scale</span>}
      </div>
      <p className="hm__lede">VIIRS multiplied by the correction fitted on 2016 to 2018{typeof factor === 'number' ? <> (<b>× {f(factor)}</b>)</> : null}, shown next to MODIS / Aqua. If the correction holds, the two gold lines sit together.</p>
      <svg viewBox={`0 0 ${W} ${H}`} className="hm__svg" role="img" aria-label={`${region.name}. ${rows.map((r) => r.sealed ? `${r.year}: sealed` : r.aqua === undefined ? `${r.year}: no yearly value` : `${r.year}: Aqua ${f(r.aqua)}, VIIRS corrected ${r.mapped === undefined ? 'unavailable' : f(r.mapped)}, VIIRS raw ${f(r.viirs!)}`).join('. ')}`}>
        <defs><pattern id={`hm-seal-${region.code}`} width="6" height="6" patternUnits="userSpaceOnUse" patternTransform="rotate(45)"><line x1="0" y1="0" x2="0" y2="6" className="wb__sealed-line" /></pattern></defs>
        {[0, 0.25, 0.5, 0.75, 1].map((t) => <g key={t} className="wb__tick"><line x1={m.l} x2={W - m.r} y1={y(t * top)} y2={y(t * top)} /><text x={m.l - 8} y={y(t * top) + 4} textAnchor="end">{f(t * top)}</text></g>)}
        {rows.map((r, i) => r.sealed ? <g key={r.year}><rect x={m.l + i * sw + 2} y={m.t} width={sw - 4} height={ih} fill={`url(#hm-seal-${region.code})`} className="wb__sealed" /><text x={x(i)} y={m.t + 14} textAnchor="middle" className="hm__sealtext">sealed</text></g> : null)}
        {band}
        <path d={path('viirs')} className="hm__line hm__line--raw" />
        <path d={path('aqua')} className="hm__line hm__line--aqua" />
        <path d={path('mapped')} className="hm__line hm__line--mapped" />
        {rows.map((r, i) => <g key={r.year}>
          {r.viirs !== undefined && <circle cx={x(i)} cy={y(r.viirs)} r="3.5" className="hm__pt hm__pt--raw"><title>{r.year} VIIRS raw: {f(r.viirs)}</title></circle>}
          {r.aqua !== undefined && <circle cx={x(i)} cy={y(r.aqua)} r="5" className="hm__pt hm__pt--aqua"><title>{r.year} MODIS / Aqua: {f(r.aqua)}</title></circle>}
          {r.mapped !== undefined && <rect x={x(i) - 4.5} y={y(r.mapped) - 4.5} width="9" height="9" transform={`rotate(45 ${x(i)} ${y(r.mapped)})`} className="hm__pt hm__pt--mapped"><title>{r.year} VIIRS corrected: {f(r.mapped)}</title></rect>}
          <text x={x(i)} y={H - 10} textAnchor="middle" className="wb__xlabel">{r.year}</text>
        </g>)}
        <line x1={m.l} x2={W - m.r} y1={m.t + ih} y2={m.t + ih} className="wb__axis" />
      </svg>
      <ul className="wb__legend" aria-label="Legend">
        <li><i className="hm__key hm__key--aqua" aria-hidden="true" />MODIS / Aqua (reference)</li>
        <li><i className="hm__key hm__key--mapped" aria-hidden="true" />VIIRS corrected to the Aqua scale</li>
        <li><i className="hm__key hm__key--raw" aria-hidden="true" />VIIRS as recorded</li>
        <li><i className="hm__key hm__key--band" aria-hidden="true" />Range of tested corrections</li>
        <li><i className="wb__key wb__key--sealed" aria-hidden="true" />Sealed years, not read</li>
      </ul>
      {!compact && <div className="lab__table-wrap"><table className="lab__table ev__table">
        <caption>Fire cell-days per 1,000 usable land cell-days, as given in the evidence file</caption>
        <thead><tr><th scope="col">Year</th><th scope="col">MODIS / Aqua</th><th scope="col">VIIRS corrected</th><th scope="col">Gap after correction</th><th scope="col">VIIRS as recorded</th><th scope="col">Gap before correction</th><th scope="col">Tested-correction range</th></tr></thead>
        <tbody>{rows.map((r) => <tr key={r.year} data-sealed={r.sealed ? 'true' : undefined}><th scope="row">{r.year}</th>{r.sealed
          ? <td colSpan={6}>Sealed for the sensor-switch test, not read</td>
          : r.aqua === undefined ? <td colSpan={6}>No yearly value in this file</td>
            : <><td>{f(r.aqua)}</td><td>{r.mapped === undefined ? 'Unavailable' : f(r.mapped)}</td><td>{r.error === undefined ? 'Unavailable' : pct(r.error)}</td><td>{f(r.viirs!)}</td><td>{r.rawError === undefined ? 'Unavailable' : pct(r.rawError)}</td><td>{r.lo === undefined || r.hi === undefined ? 'Unavailable' : `${f(r.lo)} to ${f(r.hi)}`}</td></>}</tr>)}</tbody>
      </table></div>}
      <p className="lab__note">Gap = how far VIIRS is from Aqua, relative to Aqua.{SHOW_REVIEW_NOTICES ? ' 2019 checks the correction on a year it was not fitted on; 2022 to 2025 have no registered pass rule, so they are shown, not judged. Training years 2016 to 2018 are pooled and have no yearly point. This is not a harmonized long-term trend, and no rise, peak or anomaly is claimed across the satellite change.' : ' 2019 checks the correction on a year it was not fitted on. Training years 2016 to 2018 are pooled and have no yearly point.'}</p>
    </section>
  )
}
