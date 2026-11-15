import { useId, useState, type KeyboardEvent } from 'react'
import type { CalendarEntry } from './model'
import { MONTH_SHORT, cellState, entryText, formatValue, hasValue } from './view'

const W = 960
const H = 280
const M = { l: 52, r: 12, t: 14, b: 30 }

/** A display ceiling for the value axis (1, 2, 2.5, 5 or 10 times a power of ten). Axis only. */
function niceMax(max: number): number {
  if (!(max > 0)) return 1
  const p = 10 ** Math.floor(Math.log10(max))
  for (const m of [1, 2, 2.5, 5, 10]) if (max <= m * p) return m * p
  return 10 * p
}

/** One sensor, one unit, one resolution. A period without an observation is a gap or a labelled
 * state (sealed, partial, unavailable); it is never drawn as a zero-height bar. */
export default function Chart({ entries, selected, onPick }: { entries: CalendarEntry[]; selected?: string; onPick?: (period: string) => void }) {
  const patternId = useId().replace(/:/g, '')
  const [hover, setHover] = useState<string | undefined>()
  const ordered = [...entries].sort((a, b) => (a.period < b.period ? -1 : 1))
  const sensors = new Set(ordered.map((entry) => entry.sensor))
  const values = ordered.filter(hasValue)
  const units = new Set(values.map((entry) => entry.unit))
  if (sensors.size > 1 || units.size > 1) return <p className="lab__note">This chart shows one satellite and one unit at a time. Choose a single satellite.</p>
  if (!ordered.length) return null
  if (!values.length) return <div className="lab__empty"><h4>No observed values to draw</h4><p>Every period in this selection is sealed, partial or unavailable. They are listed in the calendar and table. Nothing is drawn as zero.</p></div>

  const sensor = ordered[0].sensor
  const isWeek = ordered[0].resolution === 'week'
  const top = niceMax(Math.max(...values.map((entry) => entry.value)))
  const innerW = W - M.l - M.r
  const innerH = H - M.t - M.b
  const slot = innerW / ordered.length
  const barW = Math.max(1.5, slot * 0.72)
  const x = (i: number) => M.l + i * slot + (slot - barW) / 2
  const y = (v: number) => M.t + innerH - (v / top) * innerH
  const ticks = [0, 0.25, 0.5, 0.75, 1].map((f) => f * top)
  const active = hover ?? selected
  const activeIndex = ordered.findIndex((entry) => entry.period === active)
  const activeEntry = activeIndex >= 0 ? ordered[activeIndex] : undefined

  const move = (delta: number) => {
    const from = ordered.findIndex((entry) => entry.period === selected)
    const next = Math.min(ordered.length - 1, Math.max(0, (from < 0 ? (delta > 0 ? -1 : ordered.length) : from) + delta))
    onPick?.(ordered[next].period)
  }
  const onKey = (event: KeyboardEvent) => {
    if (event.key === 'ArrowRight') { event.preventDefault(); move(1) }
    else if (event.key === 'ArrowLeft') { event.preventDefault(); move(-1) }
    else if (event.key === 'Home') { event.preventDefault(); onPick?.(ordered[0].period) }
    else if (event.key === 'End') { event.preventDefault(); onPick?.(ordered[ordered.length - 1].period) }
  }
  const slotAt = (clientX: number, el: SVGSVGElement) => {
    const box = el.getBoundingClientRect()
    const vx = ((clientX - box.left) / box.width) * W
    const i = Math.floor((vx - M.l) / slot)
    return i >= 0 && i < ordered.length ? ordered[i].period : undefined
  }

  return (
    <figure className={`lab__chart wb__chart wb__chart--${sensor.toLowerCase()}`}>
      <figcaption>Observed values by {isWeek ? 'week' : 'month'} <span>({values[0].unit})</span></figcaption>
      <svg viewBox={`0 0 ${W} ${H}`} role="group" tabIndex={0} aria-label={`Chart of observed values by ${isWeek ? 'week' : 'month'}. Use the left and right arrow keys to move between periods.`}
        onKeyDown={onKey}
        onPointerMove={(event) => setHover(slotAt(event.clientX, event.currentTarget))}
        onPointerLeave={() => setHover(undefined)}
        onClick={(event) => { const p = slotAt(event.clientX, event.currentTarget); if (p) onPick?.(p) }}>
        <defs>
          <pattern id={`${patternId}-sealed`} width="6" height="6" patternUnits="userSpaceOnUse" patternTransform="rotate(45)"><rect width="6" height="6" className="wb__sealed-bg" /><line x1="0" y1="0" x2="0" y2="6" className="wb__sealed-line" /></pattern>
        </defs>
        {ticks.map((t) => <g key={t} className="wb__tick"><line x1={M.l} x2={W - M.r} y1={y(t)} y2={y(t)} /><text x={M.l - 8} y={y(t) + 4} textAnchor="end">{formatValue(t)}</text></g>)}
        {ordered.map((entry, i) => {
          const state = cellState(entry)
          const cx = M.l + i * slot
          const on = entry.period === active
          if (state === 'sealed') return <g key={entry.period}><rect x={cx} y={M.t} width={slot} height={innerH} fill={`url(#${patternId}-sealed)`} className="wb__sealed" /></g>
          if (state === 'value') {
            const v = entry.value as number
            return <g key={entry.period}>
              {on && <rect x={cx} y={M.t} width={slot} height={innerH} className="wb__focus" />}
              <rect x={x(i)} y={y(v)} width={barW} height={Math.max(1, M.t + innerH - y(v))} className={`wb__bar ${entry.coverage === 'partial' ? 'is-partial' : ''} ${selected === entry.period ? 'is-selected' : ''}`} />
              {entry.unusualLabel === 'Unusual' && <path d={`M${x(i) + barW / 2 - 3},${y(v) - 9} h6 l-3,6 z`} className="wb__unusual" />}
            </g>
          }
          return <g key={entry.period}>
            {on && <rect x={cx} y={M.t} width={slot} height={innerH} className="wb__focus" />}
            <rect x={x(i)} y={M.t + innerH - 7} width={barW} height={7} className={`wb__gap wb__gap--${state}`} />
          </g>
        })}
        <line x1={M.l} x2={W - M.r} y1={M.t + innerH} y2={M.t + innerH} className="wb__axis" />
        {ordered.map((entry, i) => {
          const first = isWeek ? entry.period.endsWith('W01') : entry.period.endsWith('-01')
          const label = isWeek ? entry.period.slice(0, 4) : `${MONTH_SHORT[0]} ${entry.period.slice(0, 4)}`
          return first ? <text key={entry.period} x={M.l + i * slot} y={H - 8} className="wb__xlabel">{label}</text> : null
        })}
        {activeEntry && <line x1={M.l + activeIndex * slot + slot / 2} x2={M.l + activeIndex * slot + slot / 2} y1={M.t} y2={M.t + innerH} className="wb__cursor" />}
      </svg>
      <p className="wb__readout" aria-live="polite">{activeEntry ? entryText(activeEntry) : 'Hover or select a period to read its value. Gaps are periods without an observation, not zero.'}</p>
      <ul className="wb__legend" aria-label="Chart legend">
        <li><i className="wb__key wb__key--bar" aria-hidden="true" />Observed</li>
        <li><i className="wb__key wb__key--partial" aria-hidden="true" />Part of the period only</li>
        <li><i className="wb__key wb__key--gap" aria-hidden="true" />Unavailable, not zero</li>
        <li><i className="wb__key wb__key--sealed" aria-hidden="true" />Sealed evaluation period</li>
        <li><i className="wb__key wb__key--unusual" aria-hidden="true" />Unusual</li>
      </ul>
    </figure>
  )
}
