import type { CalendarEntry } from './model'

/** Display helpers only. Nothing here recomputes a rate, baseline, label or conclusion:
 * values are passed through as given and only counted or binned for drawing. */

export const MONTH_SHORT = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
export const MONTH_LONG = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December']

/** True only for a real, finite observation. null, missing and sealed periods are never values. */
export const hasValue = (entry: CalendarEntry): entry is CalendarEntry & { value: number } =>
  entry.availability === 'available' && !entry.sealedPeriod && typeof entry.value === 'number' && Number.isFinite(entry.value)

export const yearOf = (entry: CalendarEntry): number => Number(entry.period.slice(0, 4))

export function formatValue(value: number): string {
  return value.toLocaleString(undefined, { maximumSignificantDigits: 4 })
}

/** The state a period is drawn in. Sealed is its own state: withheld from public evaluation,
 * which is different from missing data and different from zero fire. */
export type CellState = 'value' | 'sealed' | 'partial' | 'unavailable'
export function cellState(entry: CalendarEntry): CellState {
  if (entry.sealedPeriod) return 'sealed'
  if (hasValue(entry)) return 'value'
  if (entry.coverage === 'partial') return 'partial'
  return 'unavailable'
}

/** Plain-language one-line status for tooltips and accessible names. */
export function stateText(entry: CalendarEntry): string {
  switch (cellState(entry)) {
    case 'sealed': return 'Sealed evaluation period, withheld from public evaluation'
    case 'value': return entry.coverage === 'partial' ? 'Observed, part of the period only' : 'Observed'
    case 'partial': return 'Part of the period only, no value'
    case 'unavailable': return 'Unavailable, not a zero-fire result'
  }
}

export function entryText(entry: CalendarEntry): string {
  const base = hasValue(entry) ? `${entry.label}: ${formatValue(entry.value)}` : `${entry.label}: ${stateText(entry)}`
  return hasValue(entry) ? `${base}. ${stateText(entry)}` : base
}

export function yearsOf(entries: CalendarEntry[]): number[] {
  return [...new Set(entries.map(yearOf))].sort((a, b) => a - b)
}

/** Five equal-count bins over the observed values, for colour only. The numbers shown to the
 * reader are always the artifact's own values, not the bin edges' rounding. */
export function ramp(values: number[]): { edges: number[]; bin: (value: number) => number } {
  const sorted = [...values].sort((a, b) => a - b)
  if (!sorted.length) return { edges: [0, 0, 0, 0, 0, 0], bin: () => 1 }
  const at = (q: number) => sorted[Math.min(sorted.length - 1, Math.floor(q * (sorted.length - 1)))]
  const edges = [sorted[0], at(0.2), at(0.4), at(0.6), at(0.8), sorted[sorted.length - 1]]
  const bin = (value: number) => {
    for (let b = 1; b <= 4; b += 1) if (value <= edges[b]) return b
    return 5
  }
  return { edges, bin }
}

export type Tally = { periods: number; observed: number; sealed: number; partial: number; unavailable: number }
/** Counts of periods per state. A count of periods, never a count of fires. */
export function tally(entries: CalendarEntry[]): Tally {
  const out: Tally = { periods: entries.length, observed: 0, sealed: 0, partial: 0, unavailable: 0 }
  for (const entry of entries) {
    const state = cellState(entry)
    if (state === 'value') out.observed += 1
    else if (state === 'sealed') out.sealed += 1
    else if (state === 'partial') out.partial += 1
    else out.unavailable += 1
  }
  return out
}

/** The observed entry with the largest value, as selected from the artifact (not computed). */
export function highest(entries: CalendarEntry[]): CalendarEntry | undefined {
  let best: CalendarEntry | undefined
  for (const entry of entries) if (hasValue(entry) && (!best || entry.value > best.value!)) best = entry
  return best
}

/** Rows of years, columns of months (1-12) or weeks (1-53). A missing period stays undefined. */
export function yearGrid(entries: CalendarEntry[], columns: number): { years: number[]; rows: Array<Array<CalendarEntry | undefined>> } {
  const years = yearsOf(entries)
  const rows = years.map(() => new Array<CalendarEntry | undefined>(columns).fill(undefined))
  for (const entry of entries) {
    const row = years.indexOf(yearOf(entry))
    const column = Number(entry.period.slice(entry.period.includes('W') ? 6 : 5)) - 1
    if (row >= 0 && column >= 0 && column < columns) rows[row][column] = entry
  }
  return { years, rows }
}
