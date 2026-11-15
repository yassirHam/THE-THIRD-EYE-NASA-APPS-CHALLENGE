import type { CalendarEntry } from './model'

/** A single sensor and unit only. Gaps stay gaps and data remain in the table. */
export default function Chart({ entries }: { entries: CalendarEntry[] }) {
  const values = entries.filter((entry) => entry.availability === 'available' && entry.value !== null && Number.isFinite(entry.value))
  const units = new Set(values.map((entry) => entry.unit))
  if (!values.length || units.size !== 1 || values.some((entry) => entry.value! < 0)) return null
  const max = Math.max(...values.map((entry) => entry.value!), 0)
  return <figure className={`lab__chart lab__chart--${values[0].sensor.toLowerCase()}`}><figcaption>Observed values <span>({values[0].unit})</span></figcaption><div className="lab__bars" aria-hidden="true">{entries.map((entry) => {
    const valid = entry.availability === 'available' && entry.value !== null && Number.isFinite(entry.value) && entry.value >= 0 && entry.unit === values[0].unit
    const sealed = entry.availability === 'sealed'
    return <div className="lab__bar-slot" key={entry.period} title={`${entry.label}: ${valid ? `${entry.value} ${entry.unit}` : sealed ? 'sealed evaluation period, not missing data' : 'Unavailable'}`}><span className={valid ? 'lab__bar' : sealed ? 'lab__bar lab__bar--sealed' : 'lab__bar lab__bar--missing'} style={valid ? { height: `${max ? Math.max(2, entry.value! / max * 100) : 2}%` } : undefined} /></div>
  })}</div><p>Exact values, missing periods and the sealed evaluation period are listed in the table below.</p></figure>
}
