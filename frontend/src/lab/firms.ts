import rawManifest from './data/firms_manifest.json?raw'

/** NASA FIRMS country yearly files, as listed in the repository's download manifest.
 * A separate view: FIRMS detection points never enter the calendar, its baselines, the
 * corrections or any conclusion. Counts are detection rows, not fires and not cell-days.
 * Years the manifest holds back for the sealed test are shown as held back, without a count. */
export type FirmsSensor = 'modis' | 'viirs-snpp'
export type FirmsYear = { year: number; sealed: boolean; rows: number | null; platformRows: number | null; vegetationRows: number | null; file: string; url: string }
export type FirmsCountry = { country: string; label: string; bySensor: Record<FirmsSensor, FirmsYear[]> }

type FileRow = { sensor?: string; year?: number; country?: string; status?: string; rows?: number; aqua_or_snpp_rows?: number; vegetation_rows?: number; file?: string; url?: string }
const manifest = JSON.parse(rawManifest) as { dataset?: string; source_page?: string; sealed_years_for_P5?: number[]; created_utc?: string; files?: FileRow[] }

export const FIRMS_DATASET = manifest.dataset ?? 'NASA FIRMS'
export const FIRMS_SOURCE = manifest.source_page ?? 'https://firms.modaps.eosdis.nasa.gov/country/'
export const FIRMS_RETRIEVED = manifest.created_utc ?? ''
export const FIRMS_SEALED = (manifest.sealed_years_for_P5 ?? []).filter((y) => Number.isFinite(y))
export const FIRMS_SENSOR_LABEL: Record<FirmsSensor, string> = { modis: 'MODIS (Aqua and Terra points)', 'viirs-snpp': 'VIIRS / Suomi NPP points' }
const COUNTRY_LABEL: Record<string, string> = { United_States: 'United States', Canada: 'Canada' }
const num = (v: unknown) => (typeof v === 'number' && Number.isFinite(v) ? v : null)

function build(): FirmsCountry[] {
  const files = (manifest.files ?? []).filter((f) => f.status === 'ok' && typeof f.country === 'string' && typeof f.year === 'number')
  const countries = [...new Set(files.map((f) => f.country as string))]
  return countries.map((country) => {
    const bySensor = { modis: [] as FirmsYear[], 'viirs-snpp': [] as FirmsYear[] }
    for (const sensor of ['modis', 'viirs-snpp'] as const) {
      const list = files.filter((f) => f.country === country && f.sensor === sensor)
      if (!list.length) continue
      const years = list.map((f) => f.year as number)
      const all = new Set([...years, ...FIRMS_SEALED.filter((y) => y >= Math.min(...years) && y <= Math.max(...years))])
      bySensor[sensor] = [...all].sort((a, b) => a - b).map((year) => {
        const f = list.find((x) => x.year === year)
        const sealed = FIRMS_SEALED.includes(year)
        return { year, sealed, rows: sealed ? null : num(f?.rows), platformRows: sealed ? null : num(f?.aqua_or_snpp_rows), vegetationRows: sealed ? null : num(f?.vegetation_rows), file: f?.file ?? '', url: f?.url ?? '' }
      })
    }
    return { country, label: COUNTRY_LABEL[country] ?? country.replace(/_/g, ' '), bySensor }
  })
}

export const FIRMS_COUNTRIES = build()
/** Country whose FIRMS file contains the region. Country-wide, never the region alone. */
export const REGION_COUNTRY: Record<string, string> = { '3218': 'United_States', '826': 'Canada' }
