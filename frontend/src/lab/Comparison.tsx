import type { AreaView } from './model'

const labels = { applicable: 'Applicable', failed: 'Failed Applicability', missing: 'Missing Required Support', 'out-of-domain': 'Out of Domain' } as const

export default function Comparison({ area }: { area: AreaView | undefined }) {
  const comparison = area?.rawOnly ? undefined : area?.comparison
  return <section className="lab__comparison" aria-labelledby="comparison-title">
    <div className="lab__sectionhead"><div><p className="lab__eyebrow">Evidence review</p><h3 id="comparison-title">Compare perspectives</h3></div><span className={`lab__status ${comparison ? `lab__status--${comparison.applicability}` : ''}`}>{comparison ? labels[comparison.applicability] : area?.rawOnly ? 'Raw observations only' : 'Unavailable'}</span></div>
    {comparison ? <><p>{comparison.applicabilityDetail}</p><dl className="lab__checks"><div><dt>Calibration sensitivity</dt><dd>{comparison.sensitivity}</dd></div><div><dt>Inference</dt><dd>{comparison.inference}</dd></div><div><dt>Practical change</dt><dd>{comparison.practicalChange}</dd></div></dl><a className="chip" href={comparison.evidenceUrl}>Inspect comparison evidence</a></> : <p>{area?.rawOnly ? 'This area has raw observations only. A comparison requires its own evaluation.' : 'A comparison will appear when its evidence and applicability checks are available.'}</p>}
  </section>
}
