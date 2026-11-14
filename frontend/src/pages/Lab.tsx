import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import Hud from '../components/Hud'
import { Name } from '../components/Keep'
import Calendar from '../lab/Calendar'
import Chart from '../lab/Chart'
import Comparison from '../lab/Comparison'
import { labView, type Sensor } from '../lab/model'
import './lab.css'

export default function Lab() {
  const [view, setView] = useState<'month' | 'week'>('month')
  const [areaId, setAreaId] = useState(labView.areas[0]?.id ?? '')
  const [sensor, setSensor] = useState<Sensor>('MODIS')
  const [display, setDisplay] = useState<'chart' | 'table'>('chart')
  const area = labView.areas.find((item) => item.id === areaId)
  const entries = area?.entries.filter((entry) => entry.sensor === sensor && entry.resolution === view) ?? []
  useEffect(() => { document.title = 'Research Lab - THE THIRD EYE' }, [])

  return (
    <Hud className="lab" objective={{ title: 'Research Lab', hint: 'Explore the record, with its limits in view.' }}
      top={<span className="lab__top">THE THIRD EYE / RESEARCH LAB</span>}
      bottom={<Link className="chip" to="/">Back to start</Link>}>
      <div className="lab__scroll">
        <div className="lab__intro">
          <div><p className="lab__eyebrow">Historical fire calendar</p><h2>Read the record.<br />Keep the uncertainty.</h2></div>
          <p>Explore observations from two satellite perspectives. A comparison is only shown when its evidence is available.</p>
        </div>
        <figure className="lab__art"><img src={`${import.meta.env.BASE_URL}tex/concept-landscape.png`} alt="" /><figcaption className="illustration-note">SI GENERATED IMAGE — conceptual illustration, not satellite imagery.</figcaption></figure>
        <div className="lab__grid">
          <section className="lab__calendar" aria-labelledby="calendar-title">
            <div className="lab__sectionhead"><div><p className="lab__eyebrow">Observation record</p><h3 id="calendar-title">Fire calendar</h3></div><span className="lab__status">{entries.some((entry) => entry.availability === 'available' && entry.value !== null && Number.isFinite(entry.value)) ? 'Observations available' : 'Data unavailable'}</span></div>
            <div className="lab__controls">
              <label>Area <select disabled={!labView.areas.length} value={areaId} onChange={(event) => setAreaId(event.target.value)} aria-label="Area">{labView.areas.length ? labView.areas.map((item) => <option key={item.id} value={item.id}>{item.name}</option>) : <option value="">Awaiting area data</option>}</select></label>
              <label>Satellite <select value={sensor} onChange={(event) => setSensor(event.target.value as Sensor)}><option value="MODIS">MODIS / Aqua</option><option value="VIIRS">VIIRS / Suomi NPP</option></select></label>
              <div className="lab__switch" role="group" aria-label="Calendar view"><button className="chip" aria-pressed={view === 'month'} onClick={() => setView('month')}>Monthly</button><button className="chip" aria-pressed={view === 'week'} onClick={() => setView('week')}>Weekly</button></div>
            </div>
            {area?.rawOnly && <p className="lab__status">Raw observations only</p>}
            {entries.length > 0 && <div className="lab__display" role="group" aria-label="Observation display"><button className="chip" aria-pressed={display === 'chart'} onClick={() => setDisplay('chart')}>Chart and table</button><button className="chip" aria-pressed={display === 'table'} onClick={() => setDisplay('table')}>Table only</button></div>}
            {display === 'chart' && <Chart entries={entries} />}
            <Calendar entries={entries} />
            <p className="lab__note">Each calendar uses one sensor at a time. <Name>Suomi NPP</Name> data ended 2 November 2026; NOAA-20 is a separate platform.</p>
          </section>
          <aside className="lab__aside" aria-label="Finding and limitations">
            <section><p className="lab__eyebrow">Finding</p>{area?.finding && !area.rawOnly ? <><h3>{area.finding.text}</h3><a href={area.finding.evidenceUrl}>Inspect evidence</a></> : <><h3>No finding available yet.</h3><p>An evidence-backed finding will appear when the selected area and comparison have been evaluated.</p></>}</section>
            <section><p className="lab__eyebrow">Limit</p><p>{area?.limitation ?? 'Satellite observations do not count individual fires. Missing observations and failed checks must remain visible.'}</p></section>
            <section><p className="lab__eyebrow">Normal season</p>{area?.normalSeason ? <><p>{area.normalSeason.text}</p><a href={area.normalSeason.evidenceUrl}>Inspect seasonal evidence</a></> : <p>Unavailable until enough eligible observations are present.</p>}</section>
            <section><p className="lab__eyebrow">Sensor-switch test</p>{labView.headline ? <><strong>{labView.headline.text}</strong><p>{labView.headline.denominator}</p><a href={labView.headline.evidenceUrl}>Inspect evidence</a></> : <><strong>Unavailable</strong><p>Result and number of evaluated cases are not available yet.</p></>}</section>
          </aside>
        </div>
        <Comparison area={area} />
        <section className="lab__comparison"><div className="lab__sectionhead"><div><p className="lab__eyebrow">Trace the record</p><h3>Source and evidence</h3></div><span className="lab__status">{area?.artifactUrl ? 'Available' : 'Unavailable'}</span></div><p>{area?.artifactUrl ? 'Open the artifact for the selected area and its accompanying evidence.' : 'The source artifact will be linked here when it is available for the selected area.'}</p>{area?.artifactUrl && <a className="chip" href={area.artifactUrl}>Open area artifact</a>}</section>
        <section className="lab__firms"><div><p className="lab__eyebrow">Another perspective</p><h3>Reported hotspots</h3></div><div><p>1-km grids come from the same active-fire detection algorithms as FIRMS points and add a usable-observation denominator; point hotspots never enter D, O, baselines, calibration factors, or verdicts.</p><p>Choose the area and dates manually in FIRMS until a supported selection is available here.</p><a className="chip" href="https://firms.modaps.eosdis.nasa.gov/map/" target="_blank" rel="noreferrer">Open NASA FIRMS</a></div></section>
      </div>
    </Hud>
  )
}
