import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import Hud from '../components/Hud'
import { Name } from '../components/Keep'
import AreaMap from '../lab/AreaMap'
import BurnCalendar from '../lab/BurnCalendar'
import Calendar from '../lab/Calendar'
import Chart from '../lab/Chart'
import Comparison from '../lab/Comparison'
import EvidencePanel from '../lab/EvidencePanel'
import PeriodDetail from '../lab/PeriodDetail'
import { findingVisible } from '../lab/adapter'
import { loadBundle } from '../lab/loader'
import { SENSOR_LABEL, labView as placeholderView, type LabView, type Sensor } from '../lab/model'
import { formatValue, highest, tally, yearOf, yearsOf } from '../lab/view'
import './lab.css'
import './workbench.css'
import './evidence.css'

export default function Lab() {
  const [view, setView] = useState<'month' | 'week'>('month')
  const [areaId, setAreaId] = useState(placeholderView.areas[0]?.id ?? '')
  const [sensor, setSensor] = useState<Sensor>('MODIS')
  const [display, setDisplay] = useState<'chart' | 'table'>('chart')
  const [year, setYear] = useState<'all' | number>('all')
  const [period, setPeriod] = useState<string | undefined>()
  const [liveView, setLiveView] = useState<LabView>(placeholderView)
  const [loaded, setLoaded] = useState(false)
  const area = liveView.areas.find((item) => item.id === areaId)
  const series = useMemo(() => area?.entries.filter((entry) => entry.sensor === sensor && entry.resolution === view) ?? [], [area, sensor, view])
  const years = useMemo(() => yearsOf(series), [series])
  const entries = useMemo(() => (year === 'all' ? series : series.filter((entry) => yearOf(entry) === year)), [series, year])
  const counts = useMemo(() => tally(entries), [entries])
  const top = useMemo(() => highest(entries), [entries])
  const selected = entries.find((entry) => entry.period === period)

  // Wire static artifact bundle if present in public/artifacts/; falls back to placeholder silently.
  useEffect(() => {
    const base = `${import.meta.env.BASE_URL}artifacts/`
    loadBundle(base).then((loaded) => {
      if (loaded.areas.length > 0 || (loaded.evidence?.length ?? 0) > 0) {
        setLiveView(loaded)
        setAreaId(loaded.areas[0]?.id ?? '')
      }
    }).catch(() => { /* bundle absent or fetch error: stay on placeholder */ }).finally(() => setLoaded(true))
  }, [])

  useEffect(() => { document.title = 'Research Lab - THE THIRD EYE' }, [])
  // A selection or filter change must never leave a period selected that is no longer shown.
  const pickArea = (id: string) => { setAreaId(id); setPeriod(undefined); setYear('all') }

  return (
    <Hud className="lab" objective={{ title: 'Research Lab', hint: 'Explore the record, with its limits in view.' }}
      top={<span className="lab__top">THE THIRD EYE / RESEARCH LAB</span>}
      bottom={<Link className="chip" to="/">Back to start</Link>}>
      <div className="lab__scroll">
        <div className="lab__intro">
          <div><p className="lab__eyebrow">Historical fire calendar</p><h2>Read the record.<br />Keep the uncertainty.</h2></div>
          <p>Explore observations from two satellite perspectives. A comparison is only shown when its evidence is available.</p>
        </div>

        {liveView.evidence?.map((item) => <EvidencePanel key={item.id} evidence={item} />)}

        {liveView.areas.length === 0 ? <section className="lab__empty wb__none" aria-live="polite"><h4>{loaded ? 'No area calendars in this bundle yet' : 'Loading the artifact bundle'}</h4><p>{loaded ? 'Monthly and weekly calendars appear here once they are published for an area. Nothing is drawn in the meantime, and no period is shown as zero.' : 'Reading the published artifacts.'}</p></section> : <div className="wb">
          <div className="wb__toolbar lab__controls" role="group" aria-label="Selection">
            <label>Area <select disabled={!liveView.areas.length} value={areaId} onChange={(event) => pickArea(event.target.value)} aria-label="Area">{liveView.areas.length ? liveView.areas.map((item) => <option key={item.id} value={item.id}>{item.name}</option>) : <option value="">{loaded ? 'No area data yet' : 'Loading area data'}</option>}</select></label>
            <label>Satellite <select value={sensor} onChange={(event) => { setSensor(event.target.value as Sensor); setPeriod(undefined) }}>{(Object.keys(SENSOR_LABEL) as Sensor[]).map((s) => <option key={s} value={s}>{SENSOR_LABEL[s]}</option>)}</select></label>
            <label>Years <select value={String(year)} disabled={!years.length} onChange={(event) => { setYear(event.target.value === 'all' ? 'all' : Number(event.target.value)); setPeriod(undefined) }}><option value="all">All years</option>{years.map((y) => <option key={y} value={y}>{y}</option>)}</select></label>
            <div className="lab__switch" role="group" aria-label="Calendar view"><button className="chip" aria-pressed={view === 'month'} onClick={() => { setView('month'); setPeriod(undefined) }}>Monthly</button><button className="chip" aria-pressed={view === 'week'} onClick={() => { setView('week'); setPeriod(undefined) }}>Weekly</button></div>
          </div>

          <div className="wb__body">
            <aside className="wb__side" aria-label="Map and areas">
              <AreaMap areas={liveView.areas} selected={areaId} onSelect={pickArea} />
              {!liveView.areas.length && <p className="lab__note wb__awaiting">{loaded ? 'No artifact bundle is published yet, so no area has data. The outlines show where areas are registered, not coverage.' : 'Loading the artifact bundle.'}</p>}
              {area?.rawOnly && <p className="lab__status">Raw observations only</p>}
            </aside>

            <section className="wb__main" aria-labelledby="calendar-title">
              <div className="lab__sectionhead"><div><p className="lab__eyebrow">{area ? area.name : 'Observation record'}</p><h3 id="calendar-title">Fire calendar</h3></div><span className="lab__status">{counts.observed > 0 ? 'Observations available' : 'Data unavailable'}</span></div>
              <dl className="wb__kpis" aria-label="Periods in this selection">
                <div><dt>Periods shown</dt><dd>{counts.periods}</dd></div>
                <div><dt>With an observation</dt><dd>{counts.observed}</dd></div>
                <div><dt>Unavailable</dt><dd>{counts.unavailable}</dd></div>
                <div><dt>Part of the period only</dt><dd>{counts.partial}</dd></div>
                <div><dt>Sealed evaluation</dt><dd>{counts.sealed}</dd></div>
                <div><dt>Highest observed</dt><dd>{top ? <>{formatValue(top.value as number)}<small>{top.label}</small></> : 'None'}</dd></div>
              </dl>
              {entries.length > 0 && <div className="lab__display" role="group" aria-label="Observation display"><button className="chip" aria-pressed={display === 'chart'} onClick={() => setDisplay('chart')}>Charts and table</button><button className="chip" aria-pressed={display === 'table'} onClick={() => setDisplay('table')}>Table only</button></div>}
              {display === 'chart' && <>
                <Chart entries={entries} selected={period} onPick={setPeriod} />
                <BurnCalendar entries={entries} selected={period} onPick={setPeriod} />
              </>}
              {entries.length > 0 && <PeriodDetail entry={selected} />}
              <Calendar entries={entries} />
              <p className="lab__note">Each calendar uses one sensor at a time. <Name>Suomi NPP</Name> data ended 2 November 2026; NOAA-20 is a separate platform.</p>
            </section>
          </div>
        </div>}

        <div className="wb__lower">
          <aside className="lab__aside wb__findings" aria-label="Finding and limitations">
            <section><p className="lab__eyebrow">Finding</p>{area?.finding && findingVisible(area) ? <><h3>{area.finding.text}</h3><a href={area.finding.evidenceUrl}>Inspect evidence</a></> : <><h3>No finding available yet.</h3><p>An evidence-backed finding will appear when the selected area and comparison have been evaluated.</p></>}</section>
            <section><p className="lab__eyebrow">Limit</p><p>{area?.limitation ?? 'Satellite observations do not count individual fires. Missing observations and failed checks must remain visible.'}</p></section>
            <section><p className="lab__eyebrow">Normal season</p>{area?.normalSeason ? <><p>{area.normalSeason.text}</p><a href={area.normalSeason.evidenceUrl}>Inspect seasonal evidence</a></> : <p>Unavailable until enough eligible observations are present.</p>}</section>
            <section><p className="lab__eyebrow">Sensor-switch test</p>{liveView.headline ? <><strong>{liveView.headline.text}</strong><p>{liveView.headline.denominator}</p><a href={liveView.headline.evidenceUrl}>Inspect evidence</a></> : <><strong>Unavailable</strong><p>Result and number of evaluated cases are not available yet.</p></>}</section>
          </aside>
          <Comparison area={area} />
        </div>
        <section className="lab__comparison"><div className="lab__sectionhead"><div><p className="lab__eyebrow">Trace the record</p><h3>Source and evidence</h3></div><span className="lab__status">{area?.artifactUrl ? 'Available' : 'Unavailable'}</span></div><p>{area?.artifactUrl ? 'Open the artifact for the selected area and its accompanying evidence.' : 'The source artifact will be linked here when it is available for the selected area.'}</p>{area?.artifactUrl && <a className="chip" href={area.artifactUrl}>Open area artifact</a>}</section>
        <section className="lab__firms"><div><p className="lab__eyebrow">Another perspective</p><h3>Reported hotspots</h3></div><div><p>1-km grids come from the same active-fire detection algorithms as FIRMS points and add a usable-observation denominator; point hotspots never enter D, O, baselines, calibration factors, or verdicts.</p><p>Choose the area and dates manually in FIRMS until a supported selection is available here.</p><a className="chip" href="https://firms.modaps.eosdis.nasa.gov/map/" target="_blank" rel="noreferrer">Open NASA FIRMS</a></div></section>
      </div>
    </Hud>
  )
}
