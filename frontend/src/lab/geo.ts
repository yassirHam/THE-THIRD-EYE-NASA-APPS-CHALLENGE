import rawRegions from '../../../data/manifests/canonical_regions.geojson?raw'

/** Outlines of the registered areas, read from the repository's canonical region manifest.
 * An outline is only a place to draw and click. Which area has data, and what may be concluded
 * for it, comes from the artifacts and never from this file. */
export type LonLat = [number, number]
export type Outline = { id: string; name: string; rings: LonLat[][] }
export type Box = { west: number; south: number; east: number; north: number }

type Feature = { id?: string; properties?: { name?: string }; geometry?: { type: string; coordinates: unknown } }

function ringsOf(geometry: Feature['geometry']): LonLat[][] {
  if (!geometry) return []
  if (geometry.type === 'Polygon') return (geometry.coordinates as number[][][]).map((ring) => ring.map(([lon, lat]) => [lon, lat] as LonLat))
  if (geometry.type === 'MultiPolygon') return (geometry.coordinates as number[][][][]).flatMap((poly) => poly.map((ring) => ring.map(([lon, lat]) => [lon, lat] as LonLat)))
  return []
}

const regions = JSON.parse(rawRegions) as { features?: Feature[] }

export const OUTLINES: Outline[] = (regions.features ?? [])
  .filter((feature) => typeof feature.id === 'string')
  .map((feature) => ({ id: feature.id as string, name: feature.properties?.name ?? (feature.id as string), rings: ringsOf(feature.geometry) }))
  .filter((outline) => outline.rings.length > 0)

export const outlineById = (id: string): Outline | undefined => OUTLINES.find((outline) => outline.id === id)

export function boxOf(outlines: Outline[]): Box | undefined {
  const points = outlines.flatMap((outline) => outline.rings.flat())
  if (!points.length) return undefined
  const lons = points.map((p) => p[0])
  const lats = points.map((p) => p[1])
  return { west: Math.min(...lons), east: Math.max(...lons), south: Math.min(...lats), north: Math.max(...lats) }
}
