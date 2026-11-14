import { STATUS_LABELS, describePracticalChange, type AreaView, type ComparisonView } from './model'

/** Last-resort wording when an artifact carries neither a status label nor a category. */
const applicabilityLabels = { applicable: 'Applicable', failed: 'Failed Applicability', missing: 'Missing Required Support', 'out-of-domain': 'Out of Domain' } as const

/** The artifact's own label first, then the Contract 1.1.0 category label, so compound
 * results such as a failed check with missing evidence are never shortened. */
function statusText(comparison: ComparisonView): string {
  if (comparison.statusLabel) return comparison.statusLabel
  if (comparison.outputCategory) return STATUS_LABELS[comparison.outputCategory]
  return applicabilityLabels[comparison.applicability]
}

export default function Comparison({ area }: { area: AreaView | undefined }) {
  const comparison = area?.rawOnly ? undefined : area?.comparison
  return <section className="lab__comparison" aria-labelledby="comparison-title">
    <div className="lab__sectionhead"><div><p className="lab__eyebrow">Evidence review</p><h3 id="comparison-title">Compare perspectives</h3></div><span className={`lab__status ${comparison ? `lab__status--${comparison.applicability}` : ''}`}>{comparison ? statusText(comparison) : area?.rawOnly ? 'Raw observations only' : 'Unavailable'}</span></div>
    {comparison ? <><p>{comparison.applicabilityDetail}</p><dl className="lab__checks"><div><dt>Calibration sensitivity</dt><dd>{comparison.sensitivity}</dd></div><div><dt>Inference</dt><dd>{comparison.inference}</dd></div><div><dt>Practical change</dt><dd>{describePracticalChange(comparison.practicalChange)}</dd></div></dl><a className="chip" href={comparison.evidenceUrl}>Inspect comparison evidence</a></> : <p>{area?.rawOnly ? 'This area has raw observations only. A comparison requires its own evaluation.' : 'A comparison will appear when its evidence and applicability checks are available.'}</p>}
  </section>
}
