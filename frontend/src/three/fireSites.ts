import { mulberry32 } from '../lib/random'

/** Decorative fire glints in regions that burn every year (savannas, croplands, boreal).
 *  Positions are illustrative, not NASA detections. Kind 0 = large fire (both eyes see it),
 *  kind 1 = small fire (only the finer eye sees it). */
const REGIONS: [lat: number, lon: number, dLat: number, dLon: number, n: number][] = [
  [9, 12, 5, 26, 240], // Sahel and Sudanian savanna
  [-11, 25, 6, 12, 260], // southern African miombo
  [-10, -55, 5, 12, 170], // Cerrado and southern Amazon
  [18, 100, 4, 7, 110], // mainland Southeast Asia
  [-15, 133, 3, 12, 110], // northern Australia
  [29, 76, 2, 4, 50], // Punjab cropland
  [60, 115, 5, 20, 70], // Siberian boreal
  [40, -120, 4, 4, 30], // western North America
  [-2, 113, 2, 4, 50], // Borneo and Sumatra
  [52, 40, 3, 12, 50], // European Russia cropland
]

export function fireSites(radius: number, seed = 2026) {
  const r = mulberry32(seed)
  const total = REGIONS.reduce((s, x) => s + x[4], 0)
  const positions = new Float32Array(total * 3)
  const kinds = new Float32Array(total)
  const seeds = new Float32Array(total)
  let k = 0
  for (const [lat0, lon0, dLat, dLon, n] of REGIONS) {
    for (let i = 0; i < n; i++) {
      const g = () => (r() + r() + r()) / 1.5 - 1
      const lat = lat0 + g() * dLat
      const lon = lon0 + g() * dLon
      const [x, y, z] = latLonToXYZ(lat, lon, radius)
      positions.set([x, y, z], k * 3)
      kinds[k] = r() < 0.34 ? 0 : 1
      seeds[k] = r()
      k++
    }
  }
  return { positions, kinds, seeds }
}

/** Matches THREE.SphereGeometry UV layout so points sit on the right texels. */
export function latLonToXYZ(lat: number, lon: number, radius: number): [number, number, number] {
  const u = (lon + 180) / 360
  const phi = u * Math.PI * 2
  const theta = ((90 - lat) / 180) * Math.PI
  return [-radius * Math.cos(phi) * Math.sin(theta), radius * Math.cos(theta), radius * Math.sin(phi) * Math.sin(theta)]
}
