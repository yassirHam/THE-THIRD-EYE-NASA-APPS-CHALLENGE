import type { CalendarEntry } from './model'

const label = { available: 'Available', missing: 'Missing', failed: 'Failed check', 'out-of-domain': 'Out of domain' } as const

export default function Calendar({ entries }: { entries: CalendarEntry[] }) {
  if (!entries.length) return <div className="lab__empty"><h4>Observations unavailable</h4><p>No observations are available for this selection. Missing observations are not shown as zero.</p></div>
  return <div className="lab__table-wrap"><table className="lab__table"><caption>Observation values by period</caption><thead><tr><th scope="col">Period</th><th scope="col">Observation</th><th scope="col">Status</th><th scope="col">Label</th></tr></thead><tbody>{entries.map((entry) => { const valid = entry.value !== null && Number.isFinite(entry.value); return <tr key={`${entry.sensor}-${entry.resolution}-${entry.period}`}><th scope="row">{entry.label}</th><td>{entry.availability === 'available' && valid ? `${entry.value!.toLocaleString()} ${entry.unit}` : 'Unavailable'}</td><td>{entry.availability === 'available' && !valid ? 'Missing value' : label[entry.availability]}{entry.detail ? ` — ${entry.detail}` : ''}</td><td>{[entry.unusualLabel, entry.criticalLabel].filter(Boolean).join('; ') || 'No label'}</td></tr> })}</tbody></table></div>
}
