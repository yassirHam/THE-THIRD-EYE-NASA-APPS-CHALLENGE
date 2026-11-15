import { useEffect, useMemo, useState, type ReactNode } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import Hud from '../components/Hud'
import { Name } from '../components/Keep'
import Counterexamples from '../lab/Counterexamples'
import { BoundaryCard, CompositionCard, YearBars, type Slot } from '../lab/EvidencePanel'
import Harmony, { harmonyAvailable } from '../lab/Harmony'
import RegionMap, { type MapMarker } from '../lab/RegionMap'
import { SENSOR_NAME, type PolicyView, type RegionEvidence, type SensorKey, type StageADetail } from '../lab/evidence'
import { FIRMS_COUNTRIES, FIRMS_DATASET, FIRMS_RETRIEVED, FIRMS_SEALED, FIRMS_SENSOR_LABEL, FIRMS_SOURCE, REGION_COUNTRY, type FirmsSensor, type FirmsYear } from '../lab/firms'
import { loadBundle } from '../lab/loader'
import { SHOW_REVIEW_NOTICES } from '../lab/presentation'
import { labView as placeholderView, type EvidenceView, type LabView } from '../lab/model'
import { formatValue } from '../lab/view'
import { DATA_CREDITS, NASA_BRANDING_RULE, SI_USE } from '../lib/credits'
import './lab.css'
import './workbench.css'
import './evidence.css'

const TABS = [
  ['overview', 'Overview'],
  ['calendar', 'Calendar'],
  ['trends', 'Trends'],
  ['compare', 'Compare'],
  ['claims', 'Check a claim'],
  ['hotspots', 'Hotspots'],
  ['downloads', 'Downloads'],
  ['evidence', 'Evidence'],
] as const
type Tab = typeof TABS[number][0]

const GLOSSARY: [string, string][] = [
  ['Fire activity rate', 'Grid cell-days with detected fire for every 1,000 land cell-days the satellite could actually see. Not a count of fires.'],
  ['Grid cell-day', 'One 1 km grid cell on one day. It counts as "with detected fire" if at least one fire was flagged in it.'],
  ['Usable land cell-days', 'Cell-days seen clearly over land. Cloudy or missing cells are left out, never counted as no fire.'],
  ['Correction', 'A factor that scales VIIRS so it can be read on the MODIS / Aqua scale. Fitted on training years only.'],
  ['Tested corrections', 'The same correction fitted again with one training year left out. Their spread is a sensitivity check, not a confidence interval.'],
  ['Sealed years', 'Years held back, unread, for the final sensor-switch test. They are not missing data and not zero fire.'],
  ['Sensor-switch test', 'A held-out test of whether comparisons across the change from MODIS to VIIRS point the right way. Published whatever it shows.'],
  ['Reported hotspots', 'Individual detections from NASA FIRMS. A separate view, never used in the rates, corrections or conclusions.'],
]
/** Rough marker positions for the map only. Not boundaries; nothing is computed from them. */
const MARKER_AT: Record<string, [number, number]> = { '3218': [-119.4, 37.2], '826': [-125.0, 54.0] }
const NORTH_AMERICA = { cx: -112, cy: 46, w: 70 }

const f = (n: number) => formatValue(n)

function yearSlots(detail: StageADetail, policy: PolicyView | undefined, sensor: SensorKey, from: number, to: number): Slot[] {
  const out: Slot[] = []
  for (let y = from; y <= to; y += 1) {
    if (detail.sealedYears.includes(y)) { out.push({ year: y, sealed: true, value: null, note: 'sealed evaluation year' }); continue }
    const r = policy?.years.find((x) => x.year === y)
    if (r) out.push({ year: y, sealed: false, value: r[sensor].rate, note: f(r[sensor].rate) })
    else out.push({ year: y, sealed: false, value: null, note: detail.trainingYears.includes(y) ? 'training year, pooled only' : 'no value in this file' })
  }
  return out
}

function csv(rows: (string | number | null)[][]): string {
  return rows.map((r) => r.map((c) => (c === null ? '' : /[",\n]/.test(String(c)) ? `"${String(c).replace(/"/g, '""')}"` : String(c))).join(',')).join('\n')
}
function download(name: string, body: string, type: string) {
  const url = URL.createObjectURL(new Blob([body], { type }))
  const a = document.createElement('a'); a.href = url; a.download = name; a.click()
  setTimeout(() => URL.revokeObjectURL(url), 1000)
}

export default function Lab() {
  const [params, setParams] = useSearchParams()
  const set = (patch: Record<string, string | null>) => setParams((p) => { const n = new URLSearchParams(p); for (const [k, v] of Object.entries(patch)) { if (v === null || v === '') n.delete(k); else n.set(k, v) } return n }, { replace: true })
  const tab = (TABS.some(([t]) => t === params.get('tab')) ? params.get('tab') : 'overview') as Tab
  const [live, setLive] = useState<LabView>(placeholderView)
  const [loaded, setLoaded] = useState(false)
  useEffect(() => { document.title = 'Research Lab - THE THIRD EYE' }, [])
  useEffect(() => {
    loadBundle(`${import.meta.env.BASE_URL}artifacts/`).then(setLive).catch(() => { /* stay empty */ }).finally(() => setLoaded(true))
  }, [])

  const doc: EvidenceView | undefined = live.evidence?.find((e) => e.detail)
  const detail = doc?.detail
  const regions = detail?.regions ?? []
  const region: RegionEvidence | undefined = regions.find((r) => r.code === params.get('area')) ?? regions[0]
  // Harmonized (VIIRS on the Aqua scale) is the default view; each satellite on its own is one click away.
  const satView: 'harmonized' | SensorKey = params.get('sensor') === 'viirs' ? 'viirs' : params.get('sensor') === 'aqua' ? 'aqua' : 'harmonized'
  const sensor: SensorKey = satView === 'viirs' ? 'viirs' : 'aqua'
  const policy = region?.policies.find((p) => p.key === params.get('set')) ?? region?.policies.find((p) => p.key === 'own_support') ?? region?.policies[0]
  const allYears = useMemo(() => {
    if (!detail || !region) return []
    const ys = new Set<number>([...region.eligibleWeeks.map((w) => w.year), ...detail.sealedYears, ...(policy?.years.map((y) => y.year) ?? [])])
    const list = [...ys].sort((a, b) => a - b)
    return list.length ? Array.from({ length: list[list.length - 1] - list[0] + 1 }, (_, i) => list[0] + i) : []
  }, [detail, region, policy])
  const from = allYears.includes(Number(params.get('from'))) ? Number(params.get('from')) : allYears[0] ?? 0
  const to = allYears.includes(Number(params.get('to'))) && Number(params.get('to')) >= from ? Number(params.get('to')) : allYears[allYears.length - 1] ?? 0
  const rows = policy?.years.filter((y) => y.year >= from && y.year <= to) ?? []
  const slots = (s: SensorKey) => (detail ? yearSlots(detail, policy, s, from, to) : [])
  const max = Math.max(0, ...rows.flatMap((y) => [y.aqua.rate, y.viirs.rate])) * 1.15 || 1
  const boundaries = region?.boundaries.filter((b) => b.policyKey === policy?.key) ?? []
  const country = FIRMS_COUNTRIES.find((c) => c.country === (region ? REGION_COUNTRY[region.code] : ''))
  const [firmsSensor, setFirmsSensor] = useState<FirmsSensor>('modis')
  const firmsYears = country?.bySensor[firmsSensor] ?? []
  const statusChip = !loaded ? 'Loading' : !detail ? 'Data unavailable' : doc?.released ? 'Released' : SHOW_REVIEW_NOTICES ? 'Preliminary real data' : 'Real satellite data'
  const markers: MapMarker[] = regions.filter((r) => MARKER_AT[r.code]).map((r) => ({ id: r.code, name: r.name, lon: MARKER_AT[r.code][0], lat: MARKER_AT[r.code][1], status: SHOW_REVIEW_NOTICES ? 'Real data, preliminary' : 'Real satellite data' }))
  const choose = (code: string) => set({ area: code, from: null, to: null })
  const base = `${(region?.name ?? 'area').toLowerCase().replace(/[^a-z0-9]+/g, '-')}-${from}-${to}`

  const Headline = <section id="sensor-switch" className="lab__headline"><h4>Sensor-switch test</h4><p><span className="status-chip">Not run yet</span> The sealed years {detail?.sealedYears.join(' and ') ?? '2020 and 2021'} are still unread. The numbers on this page come from the other years and are preliminary.</p></section>
  const empty = <div className="lab__empty"><h4>{loaded ? 'No real data in this bundle yet' : 'Loading the published data'}</h4><p>{loaded ? 'Results appear here when the artifact bundle contains them. Nothing is drawn in the meantime, and nothing is shown as zero.' : 'Reading the artifact bundle.'}</p></div>
  const yearTable = region && policy && <div className="lab__table-wrap"><table className="lab__table ev__table">
    <caption>Fire activity rate by year, {region.name}, {policy.label.toLowerCase()} (fire cell-days per 1,000 usable land cell-days)</caption>
    <thead><tr><th scope="col">Year</th><th scope="col">{SENSOR_NAME.aqua}</th><th scope="col">{SENSOR_NAME.viirs}</th><th scope="col">Weeks used</th><th scope="col">Role</th></tr></thead>
    <tbody>{Array.from({ length: to - from + 1 }, (_, i) => from + i).map((y) => {
      const r = policy.years.find((x) => x.year === y)
      const sealed = detail!.sealedYears.includes(y)
      const weeks = region.eligibleWeeks.find((w) => w.year === y)?.weeks
      return <tr key={y} data-sealed={sealed ? 'true' : undefined}><th scope="row">{y}</th>
        <td>{sealed ? 'Sealed' : r ? f(r.aqua.rate) : 'No yearly value'}</td><td>{sealed ? 'Sealed' : r ? f(r.viirs.rate) : 'No yearly value'}</td>
        <td>{sealed ? 'Not read' : weeks ?? 'None listed'}</td>
        <td>{sealed ? 'Held back for the sensor-switch test' : detail!.trainingYears.includes(y) ? 'Training (pooled only)' : y === detail!.developmentYear ? 'Development' : detail!.applicabilityYears.includes(y) ? 'Applicability' : 'Not used'}</td></tr>
    })}</tbody></table></div>

  const panels: Record<Tab, ReactNode> = {
    overview: (
      <div className="lab__overview">
        <section className="lab__where" aria-label="Where">
          <RegionMap markers={markers} selected={region?.code} onSelect={choose} home={NORTH_AMERICA} />
          <ul className="lab__places" aria-label="Regions with data">
            {regions.length ? regions.map((r) => (
              <li key={r.code}><button type="button" aria-pressed={r.code === region?.code} onClick={() => choose(r.code)}>
                <span className="lab__place-name">{r.name}</span>
                <span className="lab__place-meta">Region fitted on its own· {SHOW_REVIEW_NOTICES ? (doc?.released ? 'released' : 'preliminary') : 'harmonized'}</span>
              </button></li>
            )) : <li className="lab__note">{loaded ? 'No region with data has been published yet.' : 'Loading regions.'}</li>}
          </ul>
        </section>
        <section className="lab__summary" aria-label="Summary">
          <div className="lab__sectionhead"><h3>{region?.name ?? 'No area yet'}</h3><span className={`lab__status ${SHOW_REVIEW_NOTICES && doc && !doc.released ? 'lab__status--synthetic' : ''}`}>{statusChip}</span></div>
          {region && detail && <p className="lab__meta">{from} to {to} · {SENSOR_NAME.aqua} and {SENSOR_NAME.viirs}, each on its own scale · sealed {detail.sealedYears.join(', ')}</p>}
          {detail && <dl className="lab__aside">
            {SHOW_REVIEW_NOTICES ? <>
            <div><dt>Finding</dt><dd>No finding yet. Statistical inference is not established, and no pass rule is registered for 2022 to 2025.</dd></div>
            <div><dt>Limit</dt><dd>Rates count fire cell-days, not fires or FIRMS points. Tested corrections vary the training years only, not every possible sensor bias.</dd></div>
            </> : <>
            <div><dt>Harmonization</dt><dd>{(() => { const fv = policy?.variants.find((v) => v.id === 'full_training_2016_2017_2018'); return fv?.factor != null ? <>VIIRS × {f(fv.factor)}, fitted on 2016 to 2018{policy?.envelope ? <>; tested corrections {f(policy.envelope[0])} to {f(policy.envelope[1])}</> : null}.</> : 'No correction could be fitted for this observation set.' })()}</dd></div>
            <div><dt>Unit</dt><dd>Fire cell-days per 1,000 usable land cell-days. Not a count of fires or FIRMS points.</dd></div>
            </>}
          </dl>}
          {region && policy && detail ? <>
            {satView === 'harmonized' && harmonyAvailable(policy)
              ? <><Harmony detail={detail} region={region} policy={policy} compact /><p className="lab__note"><button type="button" className="lab__link" onClick={() => set({ tab: 'trends' })}>Full harmonized table</button> · <button type="button" className="lab__link" onClick={() => set({ tab: 'calendar' })}>Each satellite on its own</button></p></>
              : <><YearBars sensor={sensor} slots={slots(sensor)} max={max} /><p className="lab__note">Hatched years are sealed for the final test. Training years 2016 to 2018 are only given pooled, so they have no yearly bar. <button type="button" className="lab__link" onClick={() => set({ tab: 'calendar' })}>Full record</button></p></>}
          </> : empty}
          {SHOW_REVIEW_NOTICES && Headline}
        </section>
      </div>
    ),
    calendar: region && policy && detail ? (
      <section className="lab__calendar" aria-labelledby="calendar-title">
        <div className="lab__sectionhead"><h3 id="calendar-title">Fire record by year</h3><span className="lab__status">{statusChip}</span></div>
        {satView === 'harmonized' && <Harmony detail={detail} region={region} policy={policy} />}
        <div className="ev__charts"><YearBars sensor="aqua" slots={slots('aqua')} max={max} /><YearBars sensor="viirs" slots={slots('viirs')} max={max} /></div>
        {yearTable}
        <details className="lab__more"><summary>Weeks used and excluded per year</summary>
          <div className="lab__table-wrap"><table className="lab__table ev__table"><thead><tr><th scope="col">Year</th><th scope="col">Weeks used</th><th scope="col">Weeks excluded</th></tr></thead>
            <tbody>{region.eligibleWeeks.map((w) => <tr key={w.year}><th scope="row">{w.year}</th><td>{w.weeks}</td><td>{region.excludedWeeks.find((x) => x.year === w.year)?.weeks ?? 'None listed'}</td></tr>)}</tbody></table></div>
        </details>
        <p className="lab__note">One satellite per chart. Monthly and weekly calendars appear when their artifacts are published; this file holds yearly totals. <Name>Suomi NPP</Name> data ended 2 November 2026; NOAA-20 is a separate platform.</p>
      </section>
    ) : empty,
    trends: region && policy && detail ? (
      <div className="lab__trends">
        <Harmony detail={detail} region={region} policy={policy} />
        <section aria-label="Aqua to VIIRS ratio">
          <h3>Aqua ÷ VIIRS, year by year</h3>
          <p className="lab__note">How much higher the MODIS / Aqua rate is than the VIIRS rate in each year, over the same eligible weeks. As given in the evidence file.</p>
          <div className="lab__table-wrap"><table className="lab__table ev__table"><thead><tr><th scope="col">Year</th><th scope="col">Aqua ÷ VIIRS</th><th scope="col">Check</th></tr></thead>
            <tbody>{rows.map((y) => <tr key={y.year}><th scope="row">{y.year}</th><td>{y.ratio === null ? 'Unavailable' : f(y.ratio)}</td><td>{y.verdict}</td></tr>)}</tbody></table></div>
        </section>
      </div>
    ) : empty,
    compare: region && policy && detail ? (
      <div className="lab__comparewrap">
        <section aria-labelledby="cmp-corr">
          <h3 id="cmp-corr">Correction fitted on the training years</h3>
          <div className="lab__table-wrap"><table className="lab__table ev__table">
            <caption>{region.name}, {policy.label.toLowerCase()}</caption>
            <thead><tr><th scope="col">Correction</th><th scope="col">Factor</th><th scope="col">Training years</th><th scope="col">Aqua pooled rate</th><th scope="col">VIIRS pooled rate</th></tr></thead>
            <tbody>{policy.variants.map((v) => <tr key={v.id}><th scope="row">{v.label}</th><td>{v.available && v.factor !== null ? f(v.factor) : 'Unavailable'}</td><td>{v.trainingYears?.join(', ') ?? 'Not stated'}</td><td>{v.aquaPooledRate === undefined ? 'Unavailable' : f(v.aquaPooledRate)}</td><td>{v.viirsPooledRate === undefined ? 'Unavailable' : f(v.viirsPooledRate)}</td></tr>)}</tbody>
          </table></div>
          <p className="lab__note">{policy.envelope ? <>Tested corrections span {f(policy.envelope[0])} to {f(policy.envelope[1])}. {policy.envelopeNote}</> : 'No range of tested corrections: none of them could be fitted. Nothing is substituted.'}</p>
        </section>
        {boundaries.length > 0 ? <div className="ev__grid">{boundaries.map((b) => <BoundaryCard key={b.id} b={b} region={region.name} />)}</div> : <p className="lab__note">No equality reading for this observation set.</p>}
      </div>
    ) : empty,
    claims: (
      <div className="lab__claims">
        <header className="lab__claims-head">
          <h3>Check a claim</h3>
          <p>"Fire activity fell sharply across the two regions." A pooled rate over several regions can move when only the mix of observed land changes. These checks show why each region is evaluated on its own.</p>
        </header>
        <Counterexamples items={live.evidence?.flatMap((e) => e.counterexamples) ?? []} />
        {detail?.composition.map((c) => <CompositionCard key={c.id} c={c} regions={detail.regions} />)}
        {!detail && empty}
      </div>
    ),
    hotspots: (
      <section className="lab__firms" aria-label="Reported hotspots">
        <div>
          <h3>Reported hotspots</h3>
          <p>MODIS and VIIRS hotspots come from the same active-fire detection algorithms as the daily 1 km grids used here. The grids also record which cells were actually observed, which is why the rates use them.</p>
          <p>FIRMS points are a separate view. They are never used in the rates, the corrections or any conclusion. One point is one detection, not one fire.</p>
          <p className="lab__note">{FIRMS_DATASET}. Files retrieved {FIRMS_RETRIEVED.slice(0, 10)}. Counts are for the whole country, not the region.</p>
          <a className="chip" href="https://firms.modaps.eosdis.nasa.gov/map/" target="_blank" rel="noreferrer">Open NASA FIRMS</a>
        </div>
        <div>
          {country ? <>
            <div className="lab__switch" role="group" aria-label="FIRMS sensor">{(['modis', 'viirs-snpp'] as const).map((s) => <button key={s} type="button" className="chip" aria-pressed={firmsSensor === s} onClick={() => setFirmsSensor(s)}>{FIRMS_SENSOR_LABEL[s]}</button>)}</div>
            <FirmsBars years={firmsYears} sensor={firmsSensor} country={country.label} />
          </> : <div className="lab__empty"><h4>No hotspot counts for this area</h4><p>Use NASA FIRMS for points. They never change the rates.</p></div>}
        </div>
      </section>
    ),
    downloads: (
      <section className="lab__downloads" aria-label="Downloads">
        <div className="lab__sectionhead"><h3>Downloads</h3><span className="lab__status">{detail ? statusChip : 'Unavailable'}</span></div>
        <p className="lab__note">{region?.name ?? 'No area'} · {from} to {to}. Unavailable and sealed values stay empty, never zero.</p>
        <ul className="lab__files">
          <File disabled={!policy} title="Yearly rates (CSV)" what="One row per year and satellite. Not joined." onClick={() => policy && region && download(`${base}-yearly-rates.csv`, csv([['region', 'year', 'satellite', 'D_fire_cell_days', 'O_usable_cell_days', 'rate_per_1000', 'status'], ...Array.from({ length: to - from + 1 }, (_, i) => from + i).flatMap((y) => (['aqua', 'viirs'] as const).map((s) => { const r = policy.years.find((x) => x.year === y); const sealed = detail!.sealedYears.includes(y); return [region.name, y, SENSOR_NAME[s], sealed || !r ? null : r[s].D, sealed || !r ? null : r[s].O, sealed || !r ? null : r[s].rate, sealed ? 'sealed' : r ? (SHOW_REVIEW_NOTICES && !doc?.released ? 'preliminary' : 'observed') : 'no yearly value'] }))]), 'text/csv')} />
          <File disabled={!policy} title="Corrections (CSV)" what="Fitted factors and their training years." onClick={() => policy && region && download(`${base}-corrections.csv`, csv([['region', 'correction', 'factor', 'training_years'], ...policy.variants.map((v) => [region.name, v.label, v.available ? v.factor : null, v.trainingYears?.join(' ') ?? null])]), 'text/csv')} />
          <File disabled={!country} title="Hotspot counts (CSV)" what="FIRMS yearly detection counts, country-wide. Separate from the rates." onClick={() => country && download(`${country.label.toLowerCase().replace(/ /g, '-')}-firms-yearly-counts.csv`, csv([['country', 'sensor', 'year', 'detections', 'reference_platform_detections', 'vegetation_detections', 'status'], ...(['modis', 'viirs-snpp'] as const).flatMap((s) => country.bySensor[s].map((y) => [country.label, s, y.year, y.rows, y.platformRows, y.vegetationRows, y.sealed ? 'sealed' : 'ok']))]), 'text/csv')} />
          <File disabled={!doc} title="Evidence file (JSON)" what="The published evidence file exactly as received." onClick={() => doc && fetch(doc.evidenceUrl).then((r) => r.text()).then((t) => download(`${doc.id}.json`, t, 'application/json'))} />
        </ul>
      </section>
    ),
    evidence: (
      <div className="lab__evidence">
        <section className="lab__comparison" id="lab-source"><div className="lab__sectionhead"><h3>Source and evidence</h3><span className="lab__status">{statusChip}</span></div>
          {detail ? <dl className="lab__source">
            <div><dt>Evidence file</dt><dd><code>{detail.id}</code></dd></div>
            {SHOW_REVIEW_NOTICES && <div><dt>Release</dt><dd>{doc?.releaseText}</dd></div>}
            <div><dt>Source data</dt><dd><code>{detail.replay.sourceFile}</code>, {detail.replay.rows} weekly rows</dd></div>
            <div><dt>Independent replay</dt><dd>{detail.replay.status === 'reproduced' ? `Reproduced; largest relative difference ${detail.replay.maxRelativeDifference.toExponential(1)}` : detail.replay.status}</dd></div>
            <div><dt>Years read</dt><dd>{detail.replay.yearsRead.join(', ')}</dd></div>
            <div><dt>Sealed, not read</dt><dd>{detail.sealedYears.join(', ')}</dd></div>
            <div><dt>Training / development / applicability</dt><dd>{detail.trainingYears.join(', ')} / {detail.developmentYear ?? 'none'} / {detail.applicabilityYears.join(', ')}</dd></div>
            <div><dt>Unit</dt><dd>{detail.unit}</dd></div>
            <div><dt>Hotspot source</dt><dd><a href={FIRMS_SOURCE} target="_blank" rel="noreferrer">{FIRMS_DATASET}</a>; sealed {FIRMS_SEALED.join(', ')}</dd></div>
          </dl> : <p>The source is listed here once it is published.</p>}
          {doc?.evidenceUrl && <a className="chip" href={doc.evidenceUrl}>Open evidence file</a>}
        </section>
        <section className="lab__glossary lab__si" aria-labelledby="si-title">
          <h3 id="si-title">Credits and use of Super Intelligence (SI)</h3>
          <dl>{SI_USE.map((u) => <div key={u.what}><dt>{u.what}</dt><dd>{u.how}</dd></div>)}<div><dt>NASA branding</dt><dd>{NASA_BRANDING_RULE}</dd></div><div><dt>Data and imagery</dt><dd>{DATA_CREDITS}</dd></div></dl>
        </section>
        <section className="lab__glossary" aria-labelledby="glossary-title"><h3 id="glossary-title">What the terms mean</h3>
          <dl>{GLOSSARY.map(([t, d]) => <div key={t}><dt>{t}</dt><dd>{d}</dd></div>)}</dl>
        </section>
      </div>
    ),
  }

  return (
    <Hud className="lab" objective={{ title: 'Research Lab', hint: 'Read the record, keep the uncertainty.' }}
      top={<span className="lab__top">THE THIRD EYE / RESEARCH LAB</span>}
      bottom={<><Link className="chip chip--quiet" to="/">Back to start</Link><Link className="chip chip--quiet" to="/mission">Quick Mission</Link></>}>
      <div className="lab__scroll">
        <div className="lab__bar">
          <div className="lab__toolbar" role="group" aria-label="Selection">
            <label>Area <select disabled={!regions.length} value={region?.code ?? ''} onChange={(e) => choose(e.target.value)} aria-label="Area">{regions.length ? regions.map((r) => <option key={r.code} value={r.code}>{r.name}</option>) : <option value="">{loaded ? 'No area data yet' : 'Loading'}</option>}</select></label>
            <label>Satellite <select disabled={!detail} value={satView} onChange={(e) => set({ sensor: e.target.value === 'harmonized' ? null : e.target.value })}><option value="harmonized">Harmonized (VIIRS on the Aqua scale)</option><option value="aqua">{SENSOR_NAME.aqua}</option><option value="viirs">{SENSOR_NAME.viirs}</option></select></label>
            <label>Observations <select disabled={!region} value={policy?.key ?? ''} onChange={(e) => set({ set: e.target.value })}>{region?.policies.map((p) => <option key={p.key} value={p.key}>{p.label}</option>) ?? <option value="">-</option>}</select></label>
            <label>From <select disabled={!allYears.length} value={from || ''} onChange={(e) => set({ from: e.target.value })}>{allYears.length ? allYears.map((y) => <option key={y} value={y}>{y}</option>) : <option value="">-</option>}</select></label>
            <label>To <select disabled={!allYears.length} value={to || ''} onChange={(e) => set({ to: e.target.value })}>{allYears.filter((y) => y >= from).map((y) => <option key={y} value={y}>{y}</option>)}{!allYears.length && <option value="">-</option>}</select></label>
            {SHOW_REVIEW_NOTICES && doc && !doc.released && <p className="lab__synthetic lab__synthetic--bar" role="note"><b>Preliminary</b>Real satellite data, not yet approved by the science leads or independently verified.</p>}
          </div>
          <div className="lab__tabs" role="tablist" aria-label="Research Lab sections">
            {TABS.map(([id, label]) => <button key={id} type="button" role="tab" id={`tab-${id}`} aria-selected={tab === id} aria-controls={`panel-${id}`} tabIndex={tab === id ? 0 : -1}
              onClick={() => set({ tab: id === 'overview' ? null : id })}
              onKeyDown={(e) => { const i = TABS.findIndex(([t]) => t === id); const n = e.key === 'ArrowRight' ? (i + 1) % TABS.length : e.key === 'ArrowLeft' ? (i + TABS.length - 1) % TABS.length : -1; if (n >= 0) { e.preventDefault(); set({ tab: TABS[n][0] === 'overview' ? null : TABS[n][0] }); document.getElementById(`tab-${TABS[n][0]}`)?.focus() } }}>{label}</button>)}
          </div>
        </div>
        <div className="lab__panel" role="tabpanel" id={`panel-${tab}`} aria-labelledby={`tab-${tab}`}>{panels[tab]}</div>
      </div>
    </Hud>
  )
}

function File({ title, what, onClick, disabled, note }: { title: string; what: string; onClick: () => void; disabled?: boolean; note?: string }) {
  return <li><button type="button" className="lab__file" onClick={onClick} disabled={disabled}><b>{title}</b><span>{note ?? (disabled ? 'Unavailable for this selection' : what)}</span></button></li>
}

/** Yearly FIRMS detection counts for one sensor, country-wide. Sealed years carry no count. */
function FirmsBars({ years, sensor, country }: { years: FirmsYear[]; sensor: FirmsSensor; country: string }) {
  if (!years.length) return <p className="lab__note">No FIRMS files for this sensor.</p>
  const W = 640, H = 220, m = { l: 62, r: 8, t: 14, b: 28 }
  const iw = W - m.l - m.r, ih = H - m.t - m.b, sw = iw / years.length
  const top = Math.max(1, ...years.map((y) => y.vegetationRows ?? 0)) * 1.1
  const y = (v: number) => m.t + ih - (v / top) * ih
  return <>
    <figure className={`ev__chart ev__chart--${sensor === 'modis' ? 'aqua' : 'viirs'}`}>
      <figcaption>Vegetation-fire detections per year, {country}</figcaption>
      <svg viewBox={`0 0 ${W} ${H}`} role="img" aria-label={`FIRMS vegetation-fire detections per year in ${country}. ${years.map((x) => `${x.year}: ${x.sealed ? 'held back' : x.vegetationRows ?? 'no count'}`).join('. ')}`}>
        <defs><pattern id="firms-seal" width="6" height="6" patternUnits="userSpaceOnUse" patternTransform="rotate(45)"><line x1="0" y1="0" x2="0" y2="6" className="wb__sealed-line" /></pattern></defs>
        {[0, 0.5, 1].map((t) => <g key={t} className="wb__tick"><line x1={m.l} x2={W - m.r} y1={y(t * top)} y2={y(t * top)} /><text x={m.l - 8} y={y(t * top) + 4} textAnchor="end">{Math.round(t * top).toLocaleString()}</text></g>)}
        {years.map((x, i) => {
          const x0 = m.l + i * sw
          return <g key={x.year}><title>{x.year}: {x.sealed ? 'held back for the sealed test' : x.vegetationRows === null ? 'no count' : `${x.vegetationRows.toLocaleString()} vegetation-fire detections`}</title>
            {x.sealed ? <rect x={x0 + 1} y={m.t} width={sw - 2} height={ih} fill="url(#firms-seal)" className="wb__sealed" />
              : x.vegetationRows === null ? <rect x={x0 + sw * 0.2} y={m.t + ih - 6} width={sw * 0.6} height={6} className="wb__gap" />
                : <rect x={x0 + sw * 0.2} y={y(x.vegetationRows)} width={sw * 0.6} height={Math.max(1, m.t + ih - y(x.vegetationRows))} className="ev__bar" />}
            {(i % 2 === 0 || years.length < 14) && <text x={x0 + sw / 2} y={H - 9} textAnchor="middle" className="wb__xlabel">{String(x.year).slice(2)}</text>}
          </g>
        })}
        <line x1={m.l} x2={W - m.r} y1={m.t + ih} y2={m.t + ih} className="wb__axis" />
      </svg>
    </figure>
    <details className="lab__more"><summary>Counts table</summary>
      <div className="lab__table-wrap"><table className="lab__table ev__table"><thead><tr><th scope="col">Year</th><th scope="col">All detections</th><th scope="col">Reference platform</th><th scope="col">Vegetation fires</th></tr></thead>
        <tbody>{years.map((x) => <tr key={x.year}><th scope="row">{x.year}</th>{x.sealed ? <td colSpan={3}>Held back for the sealed test</td> : <><td>{x.rows?.toLocaleString() ?? 'No count'}</td><td>{x.platformRows?.toLocaleString() ?? 'No count'}</td><td>{x.vegetationRows?.toLocaleString() ?? 'No count'}</td></>}</tr>)}</tbody></table></div>
    </details>
    <p className="lab__note">Hatched years ({FIRMS_SEALED.join(', ')}) are held back for the sealed test. An empty bar does not prove there was no burning.</p>
  </>
}
