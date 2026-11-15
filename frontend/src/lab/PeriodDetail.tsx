import type { CalendarEntry } from './model'
import { formatValue, hasValue, stateText, cellState } from './view'

/** Everything the artifact says about one period, as given. Nothing is recomputed. */
export default function PeriodDetail({ entry }: { entry: CalendarEntry | undefined }) {
  if (!entry) return <section className="wb__detail" aria-label="Selected period"><p className="lab__eyebrow">Selected period</p><p className="lab__note">Choose a period in the chart or calendar to read its value, coverage and labels.</p></section>
  const state = cellState(entry)
  return (
    <section className="wb__detail" aria-label="Selected period" data-state={state}>
      <p className="lab__eyebrow">Selected period</p>
      <h3>{entry.label}</h3>
      <p className="wb__bignum">{hasValue(entry) ? <>{formatValue(entry.value)} <small>{entry.unit}</small></> : <span className="wb__nodata">{state === 'sealed' ? 'Sealed' : 'No value'}</span>}</p>
      <p className="wb__statetext">{stateText(entry)}</p>
      {entry.detail && <p className="lab__note">{entry.detail}</p>}
      <dl className="lab__checks">
        <div><dt>Seasonal label</dt><dd>{entry.unusualLabel ?? 'No label'}</dd></div>
        {entry.criticalLabel && <div><dt>Week label</dt><dd>{entry.criticalLabel}</dd></div>}
        <div><dt>Used in comparisons</dt><dd>{entry.comparisonEligible === true ? 'Yes' : entry.comparisonEligible === false ? 'No, shown for reading only' : 'Not stated'}</dd></div>
      </dl>
    </section>
  )
}
