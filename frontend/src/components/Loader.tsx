import { useEffect, useRef, useState } from 'react'
import { useProgress } from '@react-three/drei'
import gsap from 'gsap'
import { prefersReducedMotion } from '../lib/random'
import { blink } from '../lib/pointer'
import './loader.css'

/* An astrolabe-style year dial for the record, 2002 to 2026. The amber arc is MODIS,
   which covers the whole span; the teal arc is VIIRS, which joins at the 2012 seam.
   Both arcs, and the third eye in the centre, follow real loader progress. */
const R = 118
const SPAN = 24
const SEAM = (2012 - 2002) / SPAN
const LABELS = [2002, 2007, 2012, 2017, 2022]
const ang = (f: number) => f * Math.PI * 2 - Math.PI / 2
const at = (f: number, r: number) => [Math.cos(ang(f)) * r, Math.sin(ang(f)) * r] as const

/** Almond eye outline. h is the half-height of the opening: 0 closed, about 34 open. */
const almond = (h: number) => `M-58 0 Q0 ${-h * 2} 58 0 Q0 ${h * 2} -58 0 Z`

function arc(r: number, from: number, to: number) {
  if (to <= from) return ''
  const [x0, y0] = at(from, r)
  const [x1, y1] = at(Math.min(to, 0.9999), r)
  return `M${x0} ${y0} A${r} ${r} 0 ${to - from > 0.5 ? 1 : 0} 1 ${x1} ${y1}`
}

const TICKS = Array.from({ length: SPAN * 4 }, (_, i) => {
  const f = i / (SPAN * 4)
  const year = i % 4 === 0
  const five = year && (i / 4) % 5 === 0
  const len = five ? 12 : year ? 7 : 3
  const [x0, y0] = at(f, R + 4)
  const [x1, y1] = at(f, R + 4 + len)
  return { x0, y0, x1, y1, cls: five ? 'is-five' : year ? 'is-year' : '' }
})

export default function Loader({ onDone }: { onDone?: () => void }) {
  const { progress, active, loaded, total } = useProgress()
  const root = useRef<HTMLDivElement>(null)
  const [gone, setGone] = useState(false)
  // loaders may not report anything when textures are already cached, so arm after a beat
  const [armed, setArmed] = useState(false)
  const shown = active ? Math.round(progress) : armed ? 100 : Math.round(progress)
  const f = shown / 100
  const reduced = prefersReducedMotion()

  useEffect(() => {
    const id = window.setTimeout(() => setArmed(true), 500)
    return () => window.clearTimeout(id)
  }, [])

  useEffect(() => {
    const el = root.current
    if (active || !armed || !el) return
    const finish = () => { setGone(true); onDone?.() }
    if (reduced) {
      const id = window.setTimeout(finish, 250)
      return () => window.clearTimeout(id)
    }
    const lid = { h: 34 }
    const shapes = el.querySelectorAll<SVGPathElement>('.loader__almond')
    const tl = gsap.timeline({ delay: 0.35, onComplete: finish })
    tl.to(lid, { h: 46, duration: 0.5, ease: 'power2.out', onUpdate: () => shapes.forEach((p) => p.setAttribute('d', almond(lid.h))) }, 0)
      .to(el.querySelector('.loader__dial'), { rotate: 30, scale: 1.25, autoAlpha: 0, duration: 0.9, ease: 'power2.in', transformOrigin: '50% 50%' }, 0.25)
      .to(el.querySelectorAll('.loader__text, .loader__meta'), { autoAlpha: 0, y: 8, duration: 0.45, ease: 'power2.in' }, 0.25)
      .to(el.querySelector('.loader__lid--top'), { yPercent: -100, duration: 1.1, ease: 'expo.inOut' }, 0.75)
      .to(el.querySelector('.loader__lid--bot'), { yPercent: 100, duration: 1.1, ease: 'expo.inOut' }, 0.75)
    return () => { tl.kill() }
  }, [active, armed, onDone, reduced])

  if (gone) return null
  const h = 2 + f * 32
  const status = shown >= 100 ? 'Opening the third eye' : 'Loading Earth maps'
  return (
    <div className="loader" ref={root} role="status" aria-live="polite" aria-label={`Loading, ${shown} percent`}>
      <div className="loader__lid loader__lid--top" />
      <div className="loader__lid loader__lid--bot" />

      <div className="loader__meta" aria-hidden="true">
        <span className="loader__corner loader__corner--tl" />
        <span className="loader__corner loader__corner--tr" />
        <span className="loader__corner loader__corner--bl" />
        <span className="loader__corner loader__corner--br" />
        <p className="loader__meta-tl">NASA Space Apps 2026</p>
        <p className="loader__meta-tr">Harmonization of MODIS and VIIRS hot spots</p>
        <ul className="loader__legend">
          <li><i className="sw-a" /> MODIS on Aqua, 2002 onward</li>
          <li><i className="sw-t" /> <span>VIIRS on <span translate="no" className="notranslate">Suomi NPP</span>, 2012 to 2026</span></li>
        </ul>
        <p className="loader__meta-br">Earth maps: NASA Blue Marble and Black Marble</p>
      </div>

      <div className="loader__center">
        <svg className="loader__dial" viewBox="-170 -170 340 340" aria-hidden="true">
          <defs>
            <clipPath id="loader-eye"><path className="loader__almond" d={almond(h)} /></clipPath>
          </defs>
          <circle className="loader__ring" r={R} />
          <circle className="loader__ring loader__ring--inner" r={R - 14} />
          {TICKS.map((t, i) => <line key={i} className={`loader__tick ${t.cls}`} x1={t.x0} y1={t.y0} x2={t.x1} y2={t.y1} />)}
          {LABELS.map((y) => {
            const yf = (y - 2002) / SPAN
            const [x, yy] = at(yf, R + 32)
            return <text key={y} x={x} y={yy} className={`loader__year ${y === 2012 ? 'is-seam' : ''}`} textAnchor="middle" dominantBaseline="middle">{y}</text>
          })}
          {/* the seam: where the second eye joins */}
          <line className="loader__seam" x1={at(SEAM, R - 22)[0]} y1={at(SEAM, R - 22)[1]} x2={at(SEAM, R + 4)[0]} y2={at(SEAM, R + 4)[1]} />
          <path className="loader__arc loader__arc--modis" d={arc(R, 0, f)} />
          <path className="loader__arc loader__arc--viirs" d={arc(R - 7, SEAM, f)} />

          {/* two orbits, two eyes */}
          <ellipse className="loader__orbit" rx="88" ry="26" transform="rotate(-16)" />
          <ellipse className="loader__orbit" rx="88" ry="26" transform="rotate(16)" />
          <g transform="rotate(-16)">
            <rect className="loader__sat loader__sat--modis" x="-3" y="-3" width="6" height="6">
              {!reduced && <animateMotion dur="7s" repeatCount="indefinite" path="M88 0 A88 26 0 1 1 -88 0 A88 26 0 1 1 88 0" />}
            </rect>
          </g>
          <g transform="rotate(16)" style={{ opacity: f >= SEAM ? 1 : 0 }}>
            <rect className="loader__sat loader__sat--viirs" x="-2.5" y="-2.5" width="5" height="5">
              {!reduced && <animateMotion dur="5.2s" repeatCount="indefinite" path="M-88 0 A88 26 0 1 0 88 0 A88 26 0 1 0 -88 0" />}
            </rect>
          </g>

          {/* the third eye, opening with progress; click it to blink */}
          <g className="loader__eye blink-target" onPointerDown={(e) => blink(e.currentTarget)}>
            <path className="loader__almond loader__eye-fill" d={almond(h)} />
            <g clipPath="url(#loader-eye)">
              <circle className="loader__iris" r="22" />
              <circle className="loader__iris loader__iris--inner" r="14" />
              <circle className="loader__pupil" r="7" />
            </g>
            <path className="loader__almond loader__eye-line" d={almond(h)} />
            <rect x="-60" y="-40" width="120" height="80" fill="transparent" />
          </g>
        </svg>

        <div className="loader__text">
          <p className="loader__title notranslate" translate="no">The Third Eye</p>
          <div className="loader__meter"><span style={{ transform: `scaleX(${f})` }} /></div>
          <p className="loader__status">
            <span className="loader__num">{String(shown).padStart(3, '0')}</span>
            <span className="loader__pct">%</span>
            <span className="loader__msg">{status}</span>
            {total > 0 && <span className="loader__files">{loaded} of {total} files</span>}
          </p>
        </div>
      </div>
    </div>
  )
}
