import { counterexampleView } from './adapter'
import Counterexamples from './Counterexamples'
import { STATUS_LABELS, describePracticalChange, type AreaView, type ComparisonView, type CounterexampleView } from './model'

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
  // An evaluated area can still be blocked (ineligible conclusion or uncertified footprint):
  // say so first, so a passing status label is never read as a conclusion.
  const blocked = area?.access === 'blocked'
  return <section className="lab__comparison" aria-labelledby="comparison-title">
    <div className="lab__sectionhead"><div><p className="lab__eyebrow">Evidence review</p><h3 id="comparison-title">Compare perspectives</h3></div><span className={`lab__status ${comparison ? `lab__status--${comparison.applicability}` : ''}`}>{comparison ? (blocked ? `Comparison blocked: ${statusText(comparison)}` : statusText(comparison)) : area?.rawOnly ? 'Raw observations only' : blocked ? 'Comparison blocked' : 'Unavailable'}</span></div>
    {blocked && <p className="lab__note">No conclusion is shown for this area. {area?.limitation}</p>}
    {comparison ? <><p>{comparison.applicabilityDetail}</p><dl className="lab__checks"><div><dt>Calibration sensitivity</dt><dd>{comparison.sensitivity}</dd></div><div><dt>Inference</dt><dd>{comparison.inference}</dd></div><div><dt>Practical change</dt><dd>{describePracticalChange(comparison.practicalChange)}</dd></div></dl><a className="chip" href={comparison.evidenceUrl}>Inspect comparison evidence</a><Counterexamples items={(comparison.counterexampleInterpretations ?? []).map((item, i) => counterexampleView(item, i)).filter((x): x is CounterexampleView => x !== null)} /></> : <p>{area?.rawOnly ? 'This area has raw observations only. A comparison requires its own evaluation.' : 'A comparison will appear when its evidence and applicability checks are available.'}</p>}
  </section>
}
