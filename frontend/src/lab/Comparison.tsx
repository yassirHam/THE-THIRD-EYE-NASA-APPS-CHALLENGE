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

/** Geographic composition counterexample panel (plan Section 4B).
 * Values are shown as given from the artifact; never recomputed or zero-filled. */
function CounterexamplePanel({ items }: { items: Array<Record<string, unknown>> }) {
  if (!items.length) return null
  return (
    <details className="lab__counterexample">
      <summary>Geographic composition counterexamples ({items.length})</summary>
      {items.map((item, i) => {
        const id = typeof item['counterexample_id'] === 'string' ? item['counterexample_id'] : `counterexample-${i}`
        const label = typeof item['label'] === 'string' ? item['label'] : undefined
        const description = typeof item['description'] === 'string' ? item['description'] : undefined
        const p1 = item['period_1'] as Record<string, unknown> | undefined
        const p2 = item['period_2'] as Record<string, unknown> | undefined
        const apparentChange = typeof item['apparent_change_percent'] === 'number' ? item['apparent_change_percent'] : undefined
        const trueChange = typeof item['true_block_rate_change_percent'] === 'number' ? item['true_block_rate_change_percent'] : undefined
        const stdInfo = item['fixed_weight_standardization'] as Record<string, unknown> | undefined
        const r1 = p1 && typeof p1['regional_index_R'] === 'number' ? p1['regional_index_R'] : undefined
        const r2 = p2 && typeof p2['regional_index_R'] === 'number' ? p2['regional_index_R'] : undefined
        const rStd1 = stdInfo && typeof stdInfo['R_std_period_1'] === 'number' ? stdInfo['R_std_period_1'] : undefined
        const rStd2 = stdInfo && typeof stdInfo['R_std_period_2'] === 'number' ? stdInfo['R_std_period_2'] : undefined
        return (
          <div key={id} className="lab__counterexample-item">
            {label && <p className="lab__counterexample-label">{label}</p>}
            {description && <p className="lab__counterexample-desc">{description}</p>}
            {(r1 !== undefined || r2 !== undefined) && (
              <dl className="lab__checks">
                {r1 !== undefined && <div><dt>Observed index period 1 (R₁)</dt><dd>{r1}</dd></div>}
                {r2 !== undefined && <div><dt>Observed index period 2 (R₂)</dt><dd>{r2}</dd></div>}
                {apparentChange !== undefined && <div><dt>Apparent change</dt><dd>{apparentChange.toFixed(2)}%</dd></div>}
                {trueChange !== undefined && <div><dt>True block-rate change</dt><dd>{trueChange.toFixed(2)}%</dd></div>}
                {rStd1 !== undefined && <div><dt>Standardised index period 1 (R_std)</dt><dd>{rStd1}</dd></div>}
                {rStd2 !== undefined && <div><dt>Standardised index period 2 (R_std)</dt><dd>{rStd2}</dd></div>}
              </dl>
            )}
            {stdInfo && typeof stdInfo['note'] === 'string' && <p className="lab__note">{stdInfo['note']}</p>}
          </div>
        )
      })}
    </details>
  )
}

export default function Comparison({ area }: { area: AreaView | undefined }) {
  const comparison = area?.rawOnly ? undefined : area?.comparison
  // An evaluated area can still be blocked (ineligible conclusion or uncertified footprint):
  // say so first, so a passing status label is never read as a conclusion.
  const blocked = area?.access === 'blocked'
  return <section className="lab__comparison" aria-labelledby="comparison-title">
    <div className="lab__sectionhead"><div><p className="lab__eyebrow">Evidence review</p><h3 id="comparison-title">Compare perspectives</h3></div><span className={`lab__status ${comparison ? `lab__status--${comparison.applicability}` : ''}`}>{comparison ? (blocked ? `Comparison blocked: ${statusText(comparison)}` : statusText(comparison)) : area?.rawOnly ? 'Raw observations only' : blocked ? 'Comparison blocked' : 'Unavailable'}</span></div>
    {blocked && <p className="lab__note">No conclusion is shown for this area. {area?.limitation}</p>}
    {comparison ? <><p>{comparison.applicabilityDetail}</p><dl className="lab__checks"><div><dt>Calibration sensitivity</dt><dd>{comparison.sensitivity}</dd></div><div><dt>Inference</dt><dd>{comparison.inference}</dd></div><div><dt>Practical change</dt><dd>{describePracticalChange(comparison.practicalChange)}</dd></div></dl><a className="chip" href={comparison.evidenceUrl}>Inspect comparison evidence</a>{comparison.counterexampleInterpretations && comparison.counterexampleInterpretations.length > 0 && <CounterexamplePanel items={comparison.counterexampleInterpretations} />}</> : <p>{area?.rawOnly ? 'This area has raw observations only. A comparison requires its own evaluation.' : 'A comparison will appear when its evidence and applicability checks are available.'}</p>}
  </section>
}
