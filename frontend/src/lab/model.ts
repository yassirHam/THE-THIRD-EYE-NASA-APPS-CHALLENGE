/** Presentation model only. P4's published artifact contract must be adapted here;
 * these types are not a scientific schema or an approval of any result. */
export type Sensor = 'MODIS' | 'VIIRS'
export type Resolution = 'month' | 'week'
export type Availability = 'available' | 'missing' | 'failed' | 'out-of-domain'
export type CalendarEntry = {
  period: string
  label: string
  sensor: Sensor
  resolution: Resolution
  value: number | null
  unit: string
  availability: Availability
  detail?: string
}
export type AreaView = {
  id: string
  name: string
  rawOnly: boolean
  entries: CalendarEntry[]
  finding?: { text: string; evidenceUrl: string }
  limitation: string
  comparison?: ComparisonView
  normalSeason?: { text: string; evidenceUrl: string }
  artifactUrl?: string
}
export type ComparisonView = {
  applicability: 'applicable' | 'failed' | 'missing' | 'out-of-domain'
  applicabilityDetail: string
  sensitivity: string
  inference: string
  practicalChange: string
  evidenceUrl: string
}
export type LabView = { areas: AreaView[]; headline?: { text: string; denominator: string; evidenceUrl: string } }

// Replace this provider with a P4-approved artifact adapter when its contract exists.
// Keep it empty until real, approved artifacts are available.
export const labView: LabView = { areas: [] }
