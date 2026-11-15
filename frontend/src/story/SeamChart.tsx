import { useLayoutEffect, useMemo, useRef, useState } from 'react'
import gsap from 'gsap'
import { useGSAP } from '@gsap/react'
import { SEAM, type SeamView } from '../lib/field'
import { prefersReducedMotion } from '../lib/random'

/* The seam chapter's chart, drawn in SVG at the real pixel size of its box so text stays crisp
   and legible at any width. Lines are labelled where they end instead of in a legend. */

const Y_MAX = 100
const TICKS = [0, 25, 50, 75, 100]

interface Props {
  view: SeamView
  /** parallel universe: the jump reported as real news */
  headline?: string
}

export default function SeamChart({ view, headline }: Props) {
  const box = useRef<HTMLDivElement>(null)
  const svg = useRef<SVGSVGElement>(null)
  const [size, setSize] = useState({ w: 0, h: 0 })
  const reduced = useMemo(() => prefersReducedMotion(), [])

  useLayoutEffect(() => {
    const el = box.current
    if (!el) return
    const ro = new ResizeObserver(([e]) => setSize({ w: Math.round(e.contentRect.width), h: Math.round(e.contentRect.height) }))
    ro.observe(el)
    return () => ro.disconnect()
  }, [])

  const narrow = size.w < 520
  const m = { l: narrow ? 34 : 52, r: narrow ? 76 : 132, t: 34, b: 40 }
  const iw = Math.max(size.w - m.l - m.r, 10)
  const ih = Math.max(size.h - m.t - m.b, 10)
  const y0 = SEAM.years[0], y1 = SEAM.years[SEAM.years.length - 1]
  const X = (yr: number) => m.l + ((yr - y0) / (y1 - y0)) * iw
  const Y = (v: number) => m.t + ih - (v / Y_MAX) * ih
  const iS = SEAM.years.indexOf(SEAM.start)
  const seamX = (X(SEAM.start - 1) + X(SEAM.start)) / 2

  const path = (pts: [number, number][]) => pts.map(([yr, v], i) => `${i ? 'L' : 'M'}${X(yr).toFixed(1)},${Y(v).toFixed(1)}`).join(' ')
  const coarseAll = SEAM.years.map((yr, i) => [yr, SEAM.coarse[i]] as [number, number])
  const fineRaw = SEAM.years.slice(iS).map((yr, k) => [yr, SEAM.fine[iS + k]] as [number, number])
  const fineFixed = SEAM.years.slice(iS).map((yr, k) => [yr, SEAM.fine[iS + k] * SEAM.factor] as [number, number])
  const stitched = [...coarseAll.slice(0, iS), ...fineRaw]
  const d = {
    coarse: path(coarseAll),
    stitched: path(stitched),
    stitchedArea: `${path(stitched)} L${X(y1).toFixed(1)},${Y(0).toFixed(1)} L${X(y0).toFixed(1)},${Y(0).toFixed(1)} Z`,
    fine: path(fineRaw),
    fixed: path(fineFixed),
  }
  const jump = SEAM.fine[iS] / SEAM.coarse[iS - 1]
  const last = SEAM.years.length - 1

  const show = {
    stitched: view === 'stitched' ? 1 : 0.16,
    coarse: view === 'stitched' ? 0 : 1,
    teal: view === 'stitched' ? 0 : 1,
    ghost: view === 'corrected' ? 0.35 : 0,
  }
  const tealD = view === 'corrected' ? d.fixed : d.fine

  // fade layers to their state; draw lines that appear; morph the teal line when it is rescaled
  useGSAP(
    () => {
      if (!size.w) return
      const dur = reduced ? 0 : 0.9
      gsap.to('[data-l="stitched"]', { opacity: show.stitched, duration: dur, ease: 'power2.out' })
      gsap.to('[data-l="coarse"]', { opacity: show.coarse, duration: dur, ease: 'power2.out' })
      gsap.to('[data-l="ghost"]', { opacity: show.ghost, duration: dur, ease: 'power2.out' })
      gsap.to('[data-l="teal"]', { opacity: show.teal, duration: dur, ease: 'power2.out' })
      gsap.to('.seam__teal-line', { attr: { d: tealD }, duration: reduced ? 0 : 1.4, ease: 'power3.inOut' })
      if (!reduced) {
        const draw = view === 'stitched' ? '.seam__line--stitched' : view === 'both-eyes' ? '.seam__line--modis, .seam__teal-line' : null
        if (draw) svg.current?.querySelectorAll<SVGPathElement>(draw).forEach((p) => {
          const len = p.getTotalLength()
          gsap.fromTo(p, { strokeDasharray: len, strokeDashoffset: len }, { strokeDashoffset: 0, duration: 1.6, ease: 'power2.inOut', clearProps: 'strokeDasharray,strokeDashoffset' })
        })
      }
    },
    { scope: svg, dependencies: [view, size.w, size.h] },
  )

  const label = (() => {
    if (view === 'stitched') return 'Made-up yearly fire record drawn as one line. It jumps by about 1.9 times in 2012, the year the fine eye takes over.'
    if (view === 'both-eyes') return 'Each eye drawn separately. The coarse eye continues after 2012 with no jump; the fine eye starts higher.'
    return 'The fine eye rescaled to the coarse eye using the years both watched. The two lines now nearly overlap.'
  })()

  return (
    <div className="seam" ref={box}>
      {size.w > 0 && (
        <svg ref={svg} width={size.w} height={size.h} role="img" aria-label={label}>
          {/* eras */}
          <rect x={seamX} y={m.t} width={X(y1) - seamX + 8} height={ih} className="seam__era" />
          <text x={m.l} y={m.t - 12} className="seam__era-label">Coarse eye only</text>
          <text x={seamX + 10} y={m.t - 12} className="seam__era-label">Both eyes watching</text>

          {/* value grid */}
          {TICKS.map((v) => (
            <g key={v}>
              <line x1={m.l} x2={X(y1)} y1={Y(v)} y2={Y(v)} className={v === 0 ? 'seam__base' : 'seam__grid'} />
              <text x={m.l - 10} y={Y(v) + 4} className="seam__tick" textAnchor="end">{v}</text>
            </g>
          ))}
          {!narrow && (
            <text className="seam__axis" transform={`translate(${m.l - 40}, ${m.t + ih / 2}) rotate(-90)`} textAnchor="middle">
              detected fire-cell-days per 1,000 usable land-cell-days
            </text>
          )}
          {SEAM.years.filter((yr) => (yr - y0) % (narrow ? 6 : 3) === 0 || yr === SEAM.start).map((yr) => (
            <text key={yr} x={X(yr)} y={Y(0) + 24} className={`seam__tick ${yr === SEAM.start ? 'is-seam' : ''}`} textAnchor="middle">{yr}</text>
          ))}

          {/* the seam */}
          <line x1={seamX} x2={seamX} y1={m.t} y2={Y(0)} className="seam__seam" />

          {/* one stitched line, with its jump marked */}
          <g data-l="stitched" opacity={show.stitched}>
            <path d={d.stitchedArea} className="seam__area" />
            <path d={d.stitched} className="seam__line seam__line--stitched" />
            {stitched.map(([yr, v]) => <circle key={yr} cx={X(yr)} cy={Y(v)} r={2.6} className="seam__dot seam__dot--stitched" />)}
            {view === 'stitched' && (
              <g className="seam__jump">
                <line x1={seamX + 6} x2={seamX + 6} y1={Y(SEAM.coarse[iS - 1])} y2={Y(SEAM.fine[iS])} />
                <line x1={seamX + 2} x2={seamX + 10} y1={Y(SEAM.coarse[iS - 1])} y2={Y(SEAM.coarse[iS - 1])} />
                <line x1={seamX + 2} x2={seamX + 10} y1={Y(SEAM.fine[iS])} y2={Y(SEAM.fine[iS])} />
                <text x={seamX + 16} y={(Y(SEAM.coarse[iS - 1]) + Y(SEAM.fine[iS])) / 2 + 5}>×{jump.toFixed(1)} in one year</text>
              </g>
            )}
            {view === 'stitched' && <text x={X(y1) + 8} y={Y(SEAM.fine[last]) + 4} className="seam__end seam__end--stitched">One line</text>}
          </g>

          {/* each eye on its own */}
          <g data-l="coarse" opacity={show.coarse}>
            <path d={d.coarse} className="seam__line seam__line--modis" />
            {coarseAll.map(([yr, v]) => <circle key={yr} cx={X(yr)} cy={Y(v)} r={2.6} className="seam__dot seam__dot--modis" />)}
            <text x={X(y1) + 8} y={Y(SEAM.coarse[last]) + (view === 'corrected' ? 14 : 4)} className="seam__end seam__end--modis">Coarse eye</text>
          </g>
          <g data-l="ghost" opacity={show.ghost}>
            <path d={d.fine} className="seam__line seam__line--ghost" />
            <text x={X(y1) + 8} y={Y(SEAM.fine[last]) + 4} className="seam__end seam__end--ghost">Fine eye, raw</text>
          </g>
          <g data-l="teal" opacity={show.teal}>
            <path d={d.fine} className="seam__line seam__line--viirs seam__teal-line" />
            <text x={X(y1) + 8} y={(view === 'corrected' ? Y(SEAM.fine[last] * SEAM.factor) - 6 : Y(SEAM.fine[last])) + 4} className="seam__end seam__end--viirs">
              {view === 'corrected' ? 'Fine eye, rescaled' : 'Fine eye'}
            </text>
          </g>
        </svg>
      )}
      {headline && (
        <p className="seam__headline">
          <span>The Parallel Times</span>
          {headline}
        </p>
      )}
    </div>
  )
}
