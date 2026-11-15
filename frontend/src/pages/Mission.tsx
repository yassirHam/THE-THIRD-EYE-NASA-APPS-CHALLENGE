import { useCallback, useEffect, useMemo, useRef, useState, type ReactNode } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import Hud from '../components/Hud'
import { BoundaryCard, CompositionCard, YearBars, type Slot } from '../lab/EvidencePanel'
import Harmony from '../lab/Harmony'
import RegionMap, { type MapMarker } from '../lab/RegionMap'
import type { SensorKey, StageADetail } from '../lab/evidence'
import { loadBundle } from '../lab/loader'
import { missionCase, pct, type MissionCase } from '../lab/mission'
import type { EvidenceView, LabView } from '../lab/model'
import { SHOW_REVIEW_NOTICES } from '../lab/presentation'
import { formatValue } from '../lab/view'
import './lab.css'
import './workbench.css'
import './evidence.css'
import './mission.css'

/* Quick Mission: one real case in a few short steps. The reader picks the area; everything after
   that is read from the published evidence file, the same one the Research Lab uses. Nothing is
   computed live, no correction is chosen by the reader, and sealed years are never shown. */

const STEPS = [
  ['area', 'Area'],
  ['record', 'Record'],
  ['test', 'Switch test'],
  ['finding', 'Finding'],
  ['review', 'Third Eye'],
  ['alone', 'Each area alone'],
  ['evidence', 'Evidence'],
] as const

/** Rough marker positions for the map only, the same as the Lab. Nothing is computed from them. */
const MARKER_AT: Record<string, [number, number]> = { '3218': [-119.4, 37.2], '826': [-125.0, 54.0] }
const NORTH_AMERICA = { cx: -112, cy: 46, w: 70 }
const f = (n: number) => formatValue(n)

function slots(detail: StageADetail, c: MissionCase, sensor: SensorKey): Slot[] {
  const ys = [...c.policy.years.map((y) => y.year), ...detail.sealedYears]
  if (!ys.length) return []
  const out: Slot[] = []
  for (let y = Math.min(...ys); y <= Math.max(...ys); y += 1) {
    if (detail.sealedYears.includes(y)) { out.push({ year: y, sealed: true, value: null, note: 'sealed evaluation year' }); continue }
    const r = c.years.find((x) => x.year === y)
    out.push(r ? { year: y, sealed: false, value: r[sensor], note: f(r[sensor]) } : { year: y, sealed: false, value: null, note: 'no yearly value in this file' })
  }
  return out
}

export default function Mission() {
  const [params, setParams] = useSearchParams()
  const [live, setLive] = useState<LabView>({ areas: [] })
  const [loaded, setLoaded] = useState(false)
  const stage = useRef<HTMLDivElement>(null)
  useEffect(() => { document.title = 'Quick Mission - THE THIRD EYE' }, [])
  useEffect(() => {
    loadBundle(`${import.meta.env.BASE_URL}artifacts/`).then(setLive).catch(() => { /* stay empty */ }).finally(() => setLoaded(true))
  }, [])

  const doc: EvidenceView | undefined = live.evidence?.find((e) => e.detail)
  const detail = doc?.detail
  const regions = detail?.regions ?? []
  const code = regions.some((r) => r.code === params.get('area')) ? params.get('area')! : undefined
  const c = useMemo(() => (detail && code ? missionCase(detail, code) : null), [detail, code])
  const requested = STEPS.findIndex(([id]) => id === params.get('step'))
  // Without a chosen area only the first step can be shown.
  const step = c ? Math.max(0, requested) : 0
  const go = useCallback((i: number, area?: string) => {
    setParams((p) => { const n = new URLSearchParams(p); if (area) n.set('area', area); if (i <= 0) n.delete('step'); else n.set('step', STEPS[i][0]); return n }, { replace: false })
    stage.current?.scrollTo({ top: 0 })
  }, [setParams])
  const last = STEPS.length - 1

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const t = e.target as HTMLElement | null
      if (t && /^(INPUT|SELECT|TEXTAREA)$/.test(t.tagName)) return
      if (!c) return
      if (e.key === 'ArrowRight' && step < last) { e.preventDefault(); go(step + 1) }
      if (e.key === 'ArrowLeft' && step > 0) { e.preventDefault(); go(step - 1) }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [c, step, last, go])

  // Move focus to the new step's heading, so keyboard and screen-reader users follow along.
  const heading = useRef<HTMLHeadingElement>(null)
  useEffect(() => { if (step > 0) heading.current?.focus() }, [step, code])

  const statusChip = !loaded ? 'Loading' : !detail ? 'Data unavailable' : doc?.released ? 'Released' : SHOW_REVIEW_NOTICES ? 'Preliminary real data' : 'Real satellite data'
  const markers: MapMarker[] = regions.filter((r) => MARKER_AT[r.code]).map((r) => ({ id: r.code, name: r.name, lon: MARKER_AT[r.code][0], lat: MARKER_AT[r.code][1], status: statusChip }))
  const lab = (tab?: string) => `/lab?${new URLSearchParams({ ...(code ? { area: code } : {}), ...(tab ? { tab } : {}) })}`
  const labLink = (tab: string, text = 'Open this in the Research Lab') => <Link className="mi__lablink" to={lab(tab)}>{text}</Link>

  let body: ReactNode
  if (!loaded) body = <div className="lab__empty"><h4>Loading the published data</h4><p>Reading the evidence file and checking its fingerprint.</p></div>
  else if (!detail) body = <div className="lab__empty"><h4>The evidence file could not be read</h4><p>Nothing is shown in its place, and nothing is drawn as zero. The Research Lab shows the same unavailable state.</p><Link className="chip" to="/lab">Open the Research Lab</Link></div>
  else if (step === 0 || !c) body = (
    <div className="mi__area">
      <div>
        <p className="lab__eyebrow">Step 1 of {STEPS.length}</p>
        <h2 className="mi__title">Pick an area.</h2>
        <p className="mi__lede">Two satellites watched the same land for years: MODIS on Aqua and VIIRS on Suomi NPP. Do their fire records agree, and can one be put on the other&apos;s scale? Choose where to look.</p>
        <ul className="mi__choices" aria-label="Areas with published data">
          {regions.map((r) => {
            const rc = missionCase(detail, r.code)
            return <li key={r.code}><button type="button" className="mi__choice" aria-pressed={r.code === code} disabled={!rc} onClick={() => go(1, r.code)}>
              <b>{r.name}</b><span>{rc ? `${rc.years.length} years compared, ${detail.sealedYears.length} sealed` : 'No correction in the evidence file'}</span>
            </button></li>
          })}
        </ul>
        <p className="lab__note">Each area is checked on its own. Only areas in the published evidence file are listed.</p>
      </div>
      <RegionMap markers={markers} selected={code} onSelect={(id) => go(1, id)} home={NORTH_AMERICA} compact />
    </div>
  )
  else {
    const name = c.region.name
    const max = Math.max(0, ...c.years.flatMap((y) => [y.aqua, y.viirs])) * 1.15 || 1
    const sealed = c.sealedYears.join(' and ')
    const beats: Record<typeof STEPS[number][0], ReactNode> = {
      area: null,
      record: <>
        <h2 className="mi__title" tabIndex={-1} ref={heading}>{name}: two satellites, one area.</h2>
        <p className="mi__lede">Fire activity rate per year: grid cell-days with detected fire for every 1,000 land cell-days each satellite could actually see. Same weeks, same land. Each chart is one satellite on its own scale.</p>
        <div className="ev__charts"><YearBars sensor="aqua" slots={slots(detail, c, 'aqua')} max={max} /><YearBars sensor="viirs" slots={slots(detail, c, 'viirs')} max={max} /></div>
        <p className="lab__note">Hatched: {sealed}, sealed and unread, held back for the sensor-switch test. Training years {c.trainingYears.join(', ')} are only given pooled, so they have no yearly bar. {labLink('calendar')}</p>
      </>,
      test: <>
        <h2 className="mi__title" tabIndex={-1} ref={heading}>The sensor-switch test</h2>
        <p className="mi__headline"><span className="status-chip">Result not published yet</span> The years {sealed} are held back, unread.</p>
        <p className="mi__lede">Those years are kept for a held-out test of whether comparisons across the change from MODIS to VIIRS point the right way. Its result is published whatever it shows. Until then, this mission makes no claim about it, and nothing here was tuned on those years.</p>
        <p className="lab__note">Sealed years are not missing data and not zero fire. {labLink('calendar', 'See them in the Lab record')}</p>
      </>,
      finding: <>
        <div className="mi__findhead"><h2 className="mi__title" tabIndex={-1} ref={heading}>What the record shows</h2><span className="lab__status">{statusChip}</span></div>
        <dl className="mi__finding">
          <div><dt>Finding</dt><dd>{c.finding} {c.correction}</dd></div>
          <div><dt>Limit</dt><dd>{c.limit}</dd></div>
        </dl>
        <p className="lab__note">Both sentences are filled in from the evidence file by fixed templates. You did not pick the correction, and neither did the page. {labLink('trends', 'Full harmonized table in the Lab')}</p>
      </>,
      review: <>
        <h2 className="mi__title" tabIndex={-1} ref={heading}>The Third Eye review: does the correction hold?</h2>
        <p className="mi__lede">{c.factor !== null ? <>VIIRS is multiplied by <b>{f(c.factor)}</b>, fitted on {c.trainingYears.join(', ')}.{c.envelope ? <> Refitted with one training year left out, it stays between {f(c.envelope[0])} and {f(c.envelope[1])}.</> : null}</> : 'No correction could be fitted for this area.'} {c.boundaryText}</p>
        <Harmony detail={detail} region={c.region} policy={c.policy} compact />
        <div className="lab__table-wrap"><table className="lab__table ev__table">
          <caption>Gap from MODIS / Aqua, relative to Aqua, as given in the evidence file</caption>
          <thead><tr><th scope="col">Year</th><th scope="col">Role</th><th scope="col">Before correction</th><th scope="col">After correction</th></tr></thead>
          <tbody>{c.years.map((y) => <tr key={y.year}><th scope="row">{y.year}</th><td>{y.role === 'development' ? 'Check year, not fitted on' : 'Later year'}</td><td>{y.rawGap === undefined ? 'Unavailable' : pct(y.rawGap)}</td><td>{y.gap === undefined ? 'Unavailable' : pct(y.gap)}</td></tr>)}</tbody>
        </table></div>
        <details className="lab__more"><summary>Where the two would be equal</summary>
          {c.region.boundaries.filter((b) => b.policyKey === c.policy.key).map((b) => <BoundaryCard key={b.id} b={b} region={name} />)}
        </details>
        <p className="lab__note">A stable correction is not proof that the satellites agree, and this is not a long-term trend across the satellite change. {labLink('compare')}</p>
      </>,
      alone: <>
        <h2 className="mi__title" tabIndex={-1} ref={heading}>Why each area is fitted alone</h2>
        <p className="mi__lede">Pooling the two areas into one rate would mix them in different proportions each year, and that mix alone can move the pooled number. So {name} keeps its own correction and is never averaged with the other area.</p>
        {c.composition ? <CompositionCard c={c.composition} regions={detail.regions} /> : <p className="lab__note">The evidence file has no composition check.</p>}
        <p className="lab__note">{labLink('claims', 'Check a claim in the Lab')}</p>
      </>,
      evidence: <>
        <h2 className="mi__title" tabIndex={-1} ref={heading}>The evidence behind this mission</h2>
        <p className="mi__lede">Everything you saw came from one published file, read as it is. This page ran no new analysis.</p>
        <dl className="lab__source">
          <div><dt>Evidence file</dt><dd><code>{detail.id}</code>, fingerprint (sha256) checked in your browser before use</dd></div>
          <div><dt>Source data</dt><dd><code>{detail.replay.sourceFile}</code>, {detail.replay.rows} weekly rows</dd></div>
          <div><dt>Independent replay</dt><dd>{detail.replay.status === 'reproduced' ? `Reproduced; largest relative difference ${detail.replay.maxRelativeDifference.toExponential(1)}` : 'Not reproduced'}</dd></div>
          <div><dt>Years read</dt><dd>{detail.replay.yearsRead.join(', ')}</dd></div>
          <div><dt>Sealed, not read</dt><dd>{detail.sealedYears.join(', ')}</dd></div>
          <div><dt>Unit</dt><dd>{detail.unit}</dd></div>
          {SHOW_REVIEW_NOTICES && <div><dt>Release</dt><dd>{doc?.releaseText}</dd></div>}
        </dl>
        <div className="mi__actions">
          <a className="chip" href={doc!.evidenceUrl} download={`${detail.id}.json`}>Download the evidence file</a>
          <Link className="chip" to={lab()}>Open {name} in the Research Lab</Link>
          <Link className="chip chip--quiet" to={lab('downloads')}>All downloads</Link>
        </div>
        <p className="lab__note">Gaps in the table: {c.gapRange ? `${pct(c.gapRange[0])} to ${pct(c.gapRange[1])} after correction` : 'unavailable after correction'}{c.rawGapRange ? `, ${pct(c.rawGapRange[0])} to ${pct(c.rawGapRange[1])} before` : ''}. The Lab shows the same values.</p>
      </>,
    }
    body = <div className="mi__beat" key={`${code}-${step}`}>
      <p className="lab__eyebrow">Step {step + 1} of {STEPS.length} · {name}</p>
      {beats[STEPS[step][0]]}
    </div>
  }

  return (
    <Hud className="lab mi" objective={{ title: 'Quick Mission', hint: 'One real case, start to finish.' }}
      top={<span className="lab__top">THE THIRD EYE / QUICK MISSION</span>}
      bottom={<><Link className="chip chip--quiet" to="/">Back to start</Link><Link className="chip chip--quiet" to={lab()}>Research Lab</Link></>}>
      <div className="lab__scroll mi__scroll" ref={stage}>
        {SHOW_REVIEW_NOTICES && doc && !doc.released && <p className="lab__synthetic" role="note"><b>Preliminary</b>Real satellite data, not yet approved by the science leads or independently verified.</p>}
        <nav className="mi__steps" aria-label="Mission steps">
          <ol>{STEPS.map(([id, label], i) => <li key={id}><button type="button" aria-current={i === step ? 'step' : undefined} disabled={!c && i > 0} onClick={() => go(i)}><span>{String(i + 1).padStart(2, '0')}</span>{label}</button></li>)}</ol>
        </nav>
        {body}
        {c && <div className="mi__nav">
          <button type="button" className="chip chip--quiet" disabled={step === 0} onClick={() => go(step - 1)}>Back</button>
          <span className="mi__keys" aria-hidden="true">← → to move</span>
          {step < last ? <button type="button" className="chip" onClick={() => go(step + 1)}>Next: {STEPS[step + 1][1]}</button>
            : <Link className="chip" to={lab()}>Continue in the Research Lab</Link>}
        </div>}
      </div>
    </Hud>
  )
}
