import { mulberry32 } from './random'

export type FieldView = 'ground' | 'modis' | 'viirs' | 'both'
export type SeamView = 'stitched' | 'both-eyes' | 'corrected'

/** A 240 x 160 unit field laid over a real satellite image of eastern Angola (VIIRS true colour,
 *  18 June 2024, via NASA GIBS). The fires are made up and placed near smoke plumes in the image.
 *  Teaching illustration only: cell sizes and detection thresholds show the idea, they do not
 *  model either sensor. */
export const FIELD_W = 240
export const FIELD_H = 160

export interface Fire { x: number; y: number; k: number }
export interface Cell { x: number; y: number; size: number; lit: boolean; seen: boolean }

export const FIRES: Fire[] = (() => {
  const r = mulberry32(42)
  const out: Fire[] = []
  // cluster centres sit near the smoke plumes visible in the image (field units, y = image top down)
  const centers = [[38, 78], [76, 95], [134, 26], [112, 47], [202, 53], [170, 118]]
  for (const [cx, cy] of centers) {
    const n = 6 + Math.floor(r() * 6)
    for (let i = 0; i < n; i++) out.push({ x: cx + (r() - 0.5) * 40, y: cy + (r() - 0.5) * 28, k: r() })
  }
  for (let i = 0; i < 16; i++) out.push({ x: r() * FIELD_W, y: r() * FIELD_H, k: r() * 0.5 })
  return out.filter((f) => f.x > 1 && f.x < FIELD_W - 1 && f.y > 1 && f.y < FIELD_H - 1)
})()

export function isCloudy(x: number, y: number) {
  const a = ((x - 150) / 62) ** 2 + ((y - 52) / 34) ** 2
  const b = ((x - 60) / 30) ** 2 + ((y - 128) / 20) ** 2
  return a < 1 || b < 1
}

export const EYES = {
  modis: { cell: 20, threshold: 0.62 },
  viirs: { cell: 10, threshold: 0.22 },
} as const

/** countCloudy is the parallel-universe mistake: squares under cloud count as seen, with no fire. */
export function grid(eye: keyof typeof EYES, clouds: boolean, countCloudy = false): Cell[] {
  const { cell, threshold } = EYES[eye]
  const cells: Cell[] = []
  for (let j = 0; j < FIELD_H / cell; j++) {
    for (let i = 0; i < FIELD_W / cell; i++) {
      const x = i * cell, y = j * cell
      const cloudy = clouds && isCloudy(x + cell / 2, y + cell / 2)
      const seen = !cloudy || countCloudy
      const lit = !cloudy && FIRES.some((f) => f.k >= threshold && f.x >= x && f.x < x + cell && f.y >= y && f.y < y + cell)
      cells.push({ x, y, size: cell, lit, seen })
    }
  }
  return cells
}

export function stat(cells: Cell[]) {
  const seen = cells.filter((c) => c.seen).length
  const lit = cells.filter((c) => c.lit).length
  return { seen, lit, rate: seen ? (1000 * lit) / seen : null }
}

/** Made-up yearly indicator for the seam chapter. */
export const SEAM = (() => {
  const r = mulberry32(11)
  const years = Array.from({ length: 22 }, (_, i) => 2003 + i)
  const coarse = years.map((y, i) => 40 + 6 * Math.sin(i / 2.3) - (y - 2003) * 0.35 + (r() - 0.5) * 6)
  const fine = coarse.map((b) => b * 1.9 + (r() - 0.5) * 4)
  return { years, coarse, fine, start: 2012, factor: 1 / 1.9 }
})()
