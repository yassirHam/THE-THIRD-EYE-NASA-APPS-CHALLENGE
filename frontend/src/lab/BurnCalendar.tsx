import { useState } from 'react'
import type { CalendarEntry } from './model'
import { MONTH_LONG, MONTH_SHORT, cellState, entryText, formatValue, hasValue, ramp, yearGrid } from './view'

/** Fire calendar heat map: years down, months (or weeks) across, one sensor.
 * Colour is one hue from dark to bright, so it also reads in greyscale. Every state also has a
 * shape: hatched = unavailable, split = part of the period only, striped with S = sealed.
 * Cells carry the artifact's own value and label in their accessible name. */
export default function BurnCalendar({ entries, selected, onPick }: { entries: CalendarEntry[]; selected?: string; onPick?: (period: string) => void }) {
  const [numbers, setNumbers] = useState(false)
  if (!entries.length) return <div className="lab__empty"><h4>Calendar unavailable</h4><p>No observations for this satellite and selection. Missing periods are not shown as zero.</p></div>
  const weekly = entries[0].resolution === 'week'
  const columns = weekly ? 53 : 12
  const { years, rows } = yearGrid(entries, columns)
  const { edges, bin } = ramp(entries.filter(hasValue).map((entry) => entry.value))
  const sensor = entries[0].sensor === 'MODIS' ? 'modis' : 'viirs'
  return (
    <figure className={`burn burn--${sensor} ${weekly ? 'burn--weekly' : ''}`}>
      <figcaption className="burn__head">
        <span>{weekly ? 'Weekly' : 'Monthly'} fire calendar</span>
        <span className="burn__unit">{entries[0].unit}</span>
        {!weekly && <button type="button" className="chip chip--quiet" aria-pressed={numbers} onClick={() => setNumbers(!numbers)}>{numbers ? 'Hide numbers' : 'Show numbers'}</button>}
      </figcaption>
      <div className="burn__scroll">
        <table className="burn__grid">
          <caption className="sr-only">Fire calendar by year and {weekly ? 'week' : 'month'}. Choose a period to inspect it.</caption>
          <thead><tr><th scope="col"><span className="sr-only">Year</span></th>{Array.from({ length: columns }, (_, c) => (
            <th key={c} scope="col">{weekly ? (c % 4 === 0 ? c + 1 : '') : <abbr title={MONTH_LONG[c]}>{MONTH_SHORT[c]}</abbr>}</th>))}</tr></thead>
          <tbody>{rows.map((row, r) => (
            <tr key={years[r]}><th scope="row">{years[r]}</th>{row.map((entry, c) => {
              const key = `${years[r]}-${c}`
              if (!entry) return <td key={key} className="burn__cell burn__cell--none" title={`${weekly ? `Week ${c + 1}` : MONTH_LONG[c]} ${years[r]}: outside the record`}><span role="img" aria-label={`${weekly ? `Week ${c + 1}` : MONTH_LONG[c]} ${years[r]}: outside the record`} /></td>
              const state = cellState(entry)
              const cls = state === 'value' ? `b${bin(entry.value as number)}` : state === 'unavailable' ? 'gap' : state
              const name = entryText(entry)
              const body = state === 'sealed' ? 'S' : numbers && state === 'value' ? formatValue(entry.value as number) : ''
              return <td key={key} className={`burn__cell burn__cell--${cls} ${entry.unusualLabel === 'Unusual' ? 'is-unusual' : ''} ${selected === entry.period ? 'is-selected' : ''}`} title={name}>
                {onPick ? <button type="button" aria-label={name} aria-pressed={selected === entry.period} onClick={() => onPick(entry.period)}>{body}</button> : <span role="img" aria-label={name}>{body}</span>}
              </td>
            })}</tr>
          ))}</tbody>
        </table>
      </div>
      <ul className="burn__legend" aria-label="Legend">
        {[1, 2, 3, 4, 5].filter((b) => edges[b] > edges[b - 1] || b === 5).map((b) => <li key={b}><i className={`burn__key burn__cell--b${b}`} aria-hidden="true" />{formatValue(edges[b - 1])} to {formatValue(edges[b])}</li>)}
        <li><i className="burn__key burn__cell--gap" aria-hidden="true" />Unavailable, not zero</li>
        <li><i className="burn__key burn__cell--partial" aria-hidden="true" />Part of the period only</li>
        <li><i className="burn__key burn__cell--sealed" aria-hidden="true" />Sealed evaluation period</li>
        <li><i className="burn__key burn__key--unusual" aria-hidden="true" />Unusual</li>
      </ul>
    </figure>
  )
}
