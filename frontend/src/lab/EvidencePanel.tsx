import { useMemo, useState } from 'react'
import { SENSOR_NAME, type Boundary, type Composition, type StageADetail, type Illustration, type PolicyView, type RegionEvidence, type SensorKey, type YearResult } from './evidence'
import { formatValue } from './view'

const f = (n: number) => formatValue(n)
const pct = (n: number) => `${n < 0 ? '\u2212' : ''}${Math.abs(n).toFixed(2)}%`
const share = (n: number) => n.toFixed(3)

/* ---------- yearly rates, one sensor per chart, sealed years kept apart ---------- */

type Slot = { year: number; sealed: boolean; value: number | null; note: string }

function YearBars({ sensor, slots, max }: { sensor: SensorKey; slots: Slot[]; max: number }) {
  const W = 560, H = 190, m = { l: 46, r: 8, t: 12, b: 28 }
  const iw = W - m.l - m.r, ih = H - m.t - m.b, sw = iw / slots.length, bw = sw * 0.6
  const y = (v: number) => m.t + ih - (v / max) * ih
  return (
    <figure className={`ev__chart ev__chart--${sensor}`}>
      <figcaption>{SENSOR_NAME[sensor]}</figcaption>
      <svg viewBox={`0 0 ${W} ${H}`} role="img" aria-label={`Yearly rate for ${SENSOR_NAME[sensor]}. ${slots.map((s) => `${s.year}: ${s.note}`).join('. ')}`}>
        <defs><pattern id={`ev-seal-${sensor}`} width="6" height="6" patternUnits="userSpaceOnUse" patternTransform="rotate(45)"><line x1="0" y1="0" x2="0" y2="6" className="wb__sealed-line" /></pattern></defs>
        {[0, 0.5, 1].map((t) => <g key={t} className="wb__tick"><line x1={m.l} x2={W - m.r} y1={y(t * max)} y2={y(t * max)} /><text x={m.l - 8} y={y(t * max) + 4} textAnchor="end">{f(t * max)}</text></g>)}
        {slots.map((s, i) => {
          const x0 = m.l + i * sw
          return <g key={s.year}>
            {s.sealed
              ? <rect x={x0 + 2} y={m.t} width={sw - 4} height={ih} fill={`url(#ev-seal-${sensor})`} className="wb__sealed" />
              : s.value === null
                ? <rect x={x0 + (sw - bw) / 2} y={m.t + ih - 7} width={bw} height={7} className="wb__gap" />
                : <rect x={x0 + (sw - bw) / 2} y={y(s.value)} width={bw} height={Math.max(1, m.t + ih - y(s.value))} className="ev__bar" />}
            {!s.sealed && s.value !== null && <text x={x0 + sw / 2} y={y(s.value) - 6} textAnchor="middle" className="ev__val">{f(s.value)}</text>}
            <text x={x0 + sw / 2} y={H - 9} textAnchor="middle" className="wb__xlabel">{s.year}</text>
          </g>
        })}
        <line x1={m.l} x2={W - m.r} y1={m.t + ih} y2={m.t + ih} className="wb__axis" />
      </svg>
    </figure>
  )
}

/* ---------- where mapped VIIRS would equal Aqua, against the tested corrections ---------- */

/** Plain heading built from the counts the file gives; the file's own title stays under Full wording. */
function boundaryTitle(b: Boundary, region: string): string {
  const outside = b.counts.a_break_outside_envelope, total = b.counts.periods
  if (!b.available) return `${region}: needed correction unavailable`
  if (typeof outside === 'number' && typeof total === 'number') return `${region}: the correction that would make VIIRS equal Aqua lies outside the tested range in ${outside} of ${total} periods`
  return `${region}: correction that would make VIIRS equal Aqua`
}

function BoundaryCard({ b, region }: { b: Boundary; region: string }) {
  const rows = b.periods
  const factors = rows.flatMap((p) => [1, ...(p.aBreak !== null ? [p.aBreak] : []), ...p.variants.map((v) => v.factor).filter((x): x is number => x !== null)])
  const lo = factors.length ? Math.min(...factors) : 0, hi = factors.length ? Math.max(...factors) : 1
  const pad = (hi - lo) * 0.08 || 0.1
  const W = 620, rowH = 38, L = 96, R = 14, top = 24
  const H = top + rows.length * rowH + 30
  const x = (v: number) => L + ((v - (lo - pad)) / (hi - lo + pad * 2)) * (W - L - R)
  const ticks = [0, 1, 2, 3, 4].map((i) => lo - pad + ((hi - lo + pad * 2) * i) / 4)
  return (
    <article className="ev__card">
      <h4>{boundaryTitle(b, region)}</h4>
      {!b.available || !rows.length
        ? <div className="ev__unavail"><b>Unavailable</b><p>No reading is shown and nothing is substituted. An unavailable result is missing evidence, not a failed check.</p></div>
        : <>
          <svg className="ev__strip" viewBox={`0 0 ${W} ${H}`} role="img" aria-label={`For each period, the correction that would make VIIRS equal Aqua compared with the tested corrections. ${rows.map((p) => `${p.period}: ${p.aBreak === null ? 'no value' : f(p.aBreak)}${p.inside === false ? ', outside the tested range' : p.inside ? ', inside the tested range' : ''}`).join('. ')}`}>
            {b.envelope && <rect x={x(b.envelope[0])} y={top - 6} width={Math.max(2, x(b.envelope[1]) - x(b.envelope[0]))} height={rows.length * rowH + 4} className="ev__band" />}
            {ticks.map((t) => <g key={t} className="wb__tick"><line x1={x(t)} x2={x(t)} y1={top - 6} y2={top + rows.length * rowH} /><text x={x(t)} y={H - 8} textAnchor="middle">{f(t)}</text></g>)}
            {rows.map((p, i) => {
              const cy = top + i * rowH + rowH / 2 - 4
              return <g key={p.period}>
                <text x={L - 12} y={cy + 4} textAnchor="end" className="ev__rowlabel">{p.period}</text>
                <line x1={L} x2={W - R} y1={cy} y2={cy} className="ev__rowline" />
                <circle cx={x(1)} cy={cy} r="5" className="ev__raw" />
                {p.variants.filter((v) => v.id !== 'raw' && v.factor !== null).map((v) => <circle key={v.id} cx={x(v.factor as number)} cy={cy} r="4" className="ev__variant" />)}
                {p.aBreak !== null && <path d={`M${x(p.aBreak)},${cy - 9} l8,9 -8,9 -8,-9 z`} className={`ev__break ${p.inside === false ? 'is-outside' : ''}`} />}
              </g>
            })}
          </svg>
          <ul className="wb__legend" aria-label="Legend">
            <li><i className="ev__key ev__key--raw" aria-hidden="true" />No correction</li>
            <li><i className="ev__key ev__key--variant" aria-hidden="true" />Tested correction</li>
            <li><i className="ev__key ev__key--break" aria-hidden="true" />Correction that would make VIIRS equal Aqua</li>
            <li><i className="ev__key ev__key--band" aria-hidden="true" />Range of tested corrections</li>
          </ul>
          <table className="lab__table ev__table">
            <caption className="sr-only">Equality readings by period</caption>
            <thead><tr><th scope="col">Period</th><th scope="col">Aqua rate</th><th scope="col">VIIRS rate</th><th scope="col">Needed correction</th><th scope="col">Against tested range</th></tr></thead>
            <tbody>{rows.map((p) => <tr key={p.period}><th scope="row">{p.period}</th><td>{f(p.aquaRate)}</td><td>{f(p.viirsRate)}</td><td>{p.aBreak === null ? 'Unavailable' : f(p.aBreak)}</td><td>{p.inside === null ? 'Not stated' : p.inside ? 'Inside' : 'Outside'}</td></tr>)}</tbody>
          </table>
        </>}
      <details className="ev__words"><summary>Full wording from the evidence file</summary>
        <p><b>{b.label}</b></p>
        <p>{b.interpretation}</p>
        {b.reasons.map((r) => <p key={r}>{r}</p>)}
        <ul>{b.limits.map((l) => <li key={l}>{l}</li>)}</ul>
      </details>
    </article>
  )
}

/* ---------- composition: share of usable observations by region, per sensor ---------- */

function CompositionCard({ c, regions }: { c: Composition; regions: RegionEvidence[] }) {
  const names = new Map(regions.map((r) => [r.code, r.name]))
  const codes = [...new Set((['aqua', 'viirs'] as const).flatMap((s) => c.bySensor[s].flatMap((y) => Object.keys(y.shares))))]
  return (
    <article className="ev__card">
      <h4>{c.label}</h4>
      <p className="lab__note">Each bar is the share of usable observations in one year. The two regions were fitted separately and are never combined.</p>
      {(['aqua', 'viirs'] as const).map((s) => <figure key={s} className={`ev__shares ev__shares--${s}`}>
        <figcaption>{SENSOR_NAME[s]}</figcaption>
        {c.bySensor[s].map((y) => <div key={y.year} className="ev__sharerow" role="img" aria-label={`${y.year}: ${codes.map((k) => `${names.get(k) ?? k} ${share(y.shares[k] ?? NaN)}`).join(', ')}`}>
          <span>{y.year}</span>
          <div>{codes.map((k, i) => y.shares[k] === undefined ? null : <i key={k} className={`ev__seg ev__seg--${i % 2}`} style={{ width: `${y.shares[k] * 100}%` }}>{share(y.shares[k])}</i>)}</div>
        </div>)}
      </figure>)}
      <ul className="wb__legend" aria-label="Regions">{codes.map((k, i) => <li key={k}><i className={`ev__key ev__seg--${i % 2}`} aria-hidden="true" />{names.get(k) ?? 'Region'}</li>)}</ul>
      <p className="lab__note">Pooled-rate identity holds in {c.identityHolds} of {c.identityTotal} sensor-years.</p>
      <details className="ev__words"><summary>Full wording from the evidence file</summary><p>{c.interpretation}</p><ul>{c.limits.map((l) => <li key={l}>{l}</li>)}</ul></details>
    </article>
  )
}

export function WorkedExample({ x }: { x: Illustration }) {
  return (
    <article className="ev__card ev__card--example">
      <p className="lab__eyebrow">Worked example, hand-computed, not observed data</p>
      <h4>{x.label}</h4>
      <div className="ev__pair">
        <div><span>Observed index</span><b>{f(x.observed[0])} <em>to</em> {f(x.observed[1])}</b><small>{pct(x.observedPct)}</small></div>
        <div><span>Same weights in both periods</span><b>{f(x.fixedWeight[0])} <em>to</em> {f(x.fixedWeight[1])}</b><small>{pct(x.fixedPct)}</small></div>
      </div>
      <details className="ev__words"><summary>Full wording from the evidence file</summary><p>{x.interpretation}</p><ul>{x.limits.map((l) => <li key={l}>{l}</li>)}</ul></details>
    </article>
  )
}

/* ---------- one region ---------- */

function PolicyBlock({ policy, region, ev }: { policy: PolicyView; region: RegionEvidence; ev: StageADetail }) {
  const years = policy.years
  const slots = useMemo(() => {
    if (!years.length) return []
    const first = Math.min(...years.map((y) => y.year)), last = Math.max(...years.map((y) => y.year))
    const out: Slot[] = []
    for (let yr = first; yr <= last; yr += 1) {
      const sealed = ev.sealedYears.includes(yr)
      out.push({ year: yr, sealed, value: null, note: sealed ? 'sealed evaluation year' : 'no result' })
    }
    return out
  }, [years, ev.sealedYears])
  const slotsFor = (s: SensorKey): Slot[] => slots.map((slot) => {
    const r = years.find((y) => y.year === slot.year)
    return r ? { ...slot, value: r[s].rate, note: f(r[s].rate) } : slot
  })
  const max = Math.max(0, ...years.flatMap((y) => [y.aqua.rate, y.viirs.rate])) * 1.15 || 1
  return (
    <section className="ev__policy" aria-label={`${region.name}, ${policy.label}`}>
      <div className="ev__policyhead"><h4>{policy.label}</h4><span className="lab__status">{policy.key === 'own_support' ? 'Historical correction' : 'Diagnostic only'}</span></div>
      {years.length > 0
        ? <>
          <div className="ev__charts"><YearBars sensor="aqua" slots={slotsFor('aqua')} max={max} /><YearBars sensor="viirs" slots={slotsFor('viirs')} max={max} /></div>
          <p className="lab__note">Rates are fire cell-days per 1,000 usable land cell-days. {ev.sealedYears.length > 0 && <>Hatched years ({ev.sealedYears.join(', ')}) are held back for the sealed evaluation: they are not missing data and not zero fire.</>}</p>
          <div className="lab__table-wrap"><table className="lab__table ev__table">
            <caption>Observed rates by year, {region.name}</caption>
            <thead><tr><th scope="col">Year</th><th scope="col">{SENSOR_NAME.aqua}</th><th scope="col">{SENSOR_NAME.viirs}</th><th scope="col">Aqua ÷ VIIRS</th><th scope="col">Weeks used</th><th scope="col">Check</th></tr></thead>
            <tbody>{years.map((y: YearResult) => <tr key={y.year}>
              <th scope="row">{y.year}</th><td>{f(y.aqua.rate)}</td><td>{f(y.viirs.rate)}</td><td>{y.ratio === null ? 'Unavailable' : f(y.ratio)}</td>
              <td>{y.weeks}{y.excludedWeeks !== null ? ` (${y.excludedWeeks} excluded)` : ''}</td><td>{y.verdict}</td></tr>)}</tbody>
          </table></div>
        </>
        : <div className="ev__unavail"><b>Unavailable</b><p>No yearly rates are available for this observation set.</p></div>}
      <h5>Correction tested on the training years</h5>
      <div className="lab__table-wrap"><table className="lab__table ev__table">
        <caption>Corrections fitted for {region.name}, {policy.label}</caption>
        <thead><tr><th scope="col">Correction</th><th scope="col">Factor</th><th scope="col">Training years</th><th scope="col">Aqua pooled rate</th><th scope="col">VIIRS pooled rate</th></tr></thead>
        <tbody>{policy.variants.map((v) => <tr key={v.id}>
          <th scope="row">{v.label}</th><td>{v.available && v.factor !== null ? f(v.factor) : 'Unavailable'}</td>
          <td>{v.trainingYears?.join(', ') ?? 'Not stated'}</td><td>{v.aquaPooledRate === undefined ? 'Unavailable' : f(v.aquaPooledRate)}</td><td>{v.viirsPooledRate === undefined ? 'Unavailable' : f(v.viirsPooledRate)}</td></tr>)}</tbody>
      </table></div>
      {policy.envelope
        ? <p className="lab__note">Tested corrections span {f(policy.envelope[0])} to {f(policy.envelope[1])}. {policy.envelopeNote}</p>
        : <p className="lab__note">No range of tested corrections is available, because none of the corrections could be fitted.</p>}
    </section>
  )
}

export default function EvidencePanel({ evidence }: { evidence: StageADetail }) {
  const [code, setCode] = useState(evidence.regions[0]?.code ?? '')
  const [policyKey, setPolicyKey] = useState<string>('own_support')
  const region = evidence.regions.find((r) => r.code === code)
  const policy = region?.policies.find((p) => p.key === policyKey) ?? region?.policies[0]
  const boundaries = region?.boundaries.filter((b) => b.policyKey === policy?.key) ?? []
  return (
    <section className="ev" aria-labelledby="ev-title">
      <header className="ev__head">
        <div><p className="lab__eyebrow">Real satellite data</p><h3 id="ev-title">{evidence.regions.map((r) => r.name).join(' and ')}</h3></div>
        <ul className="ev__chips" aria-label="Status of this evidence">
          {evidence.preliminary && <li className="is-warn">Preliminary: not yet approved for public claims</li>}
          <li>{evidence.replay.status === 'reproduced' ? 'Independent replay reproduced the numbers' : 'Replay status recorded in the file'}</li>
          {evidence.inference === 'not_established' && <li>No statistical inference is made</li>}
        </ul>
      </header>
      <p className="ev__lede">Two satellites measured the same ground in different ways. The charts show each satellite on its own, then test whether a correction can bring VIIRS in line with Aqua. {evidence.sealedYears.length > 0 && <>Years {evidence.sealedYears.join(' and ')} are sealed for the final test and have not been read.</>}</p>

      <div className="ev__tabs" role="group" aria-label="Region">
        {evidence.regions.map((r) => <button key={r.code} type="button" className="chip" aria-pressed={r.code === code} onClick={() => setCode(r.code)}>{r.name}</button>)}
      </div>
      {region && <>
        <div className="ev__tabs" role="group" aria-label="Observation set">
          {region.policies.map((p) => <button key={p.key} type="button" className="chip chip--quiet" aria-pressed={p.key === policy?.key} onClick={() => setPolicyKey(p.key)}>{p.label}</button>)}
        </div>
        {policy && <PolicyBlock policy={policy} region={region} ev={evidence} />}
        {boundaries.length > 0 && <div className="ev__grid">{boundaries.map((b) => <BoundaryCard key={b.id} b={b} region={region.name} />)}</div>}
        <details className="ev__words"><summary>Weeks used per year, {region.name}</summary>
          <table className="lab__table ev__table"><thead><tr><th scope="col">Year</th><th scope="col">Weeks used</th><th scope="col">Weeks excluded</th></tr></thead>
            <tbody>{region.eligibleWeeks.map((w) => <tr key={w.year}><th scope="row">{w.year}</th><td>{w.weeks}</td><td>{region.excludedWeeks.find((x) => x.year === w.year)?.weeks ?? 'None listed'}</td></tr>)}</tbody></table>
        </details>
      </>}

      {evidence.composition.length > 0 && <>
        <h4 className="ev__sub">Why regions are never averaged together</h4>
        <div className="ev__grid">
          {evidence.composition.map((c) => <CompositionCard key={c.id} c={c} regions={evidence.regions} />)}
        </div>
      </>}

      <footer className="ev__foot">
        <p>Unit: {evidence.unit}</p>
        <p>Source: {evidence.replay.sourceFile}, {evidence.replay.rows} weekly rows; replay differs by at most {evidence.replay.maxRelativeDifference.toExponential(1)} relative. FIRMS hotspot points are a separate view and are not part of these numbers.</p>
        <details className="ev__words"><summary>Release status, as written in the file</summary><p>{evidence.releaseStatus}</p></details>
      </footer>
    </section>
  )
}
