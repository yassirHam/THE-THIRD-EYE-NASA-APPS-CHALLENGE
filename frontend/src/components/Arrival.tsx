import { useCallback, useEffect, useRef, useState } from 'react'
import { useProgress } from '@react-three/drei'
import ArrivalScene from '../three/ArrivalScene'
import { arrival, DARK, END, HOLD } from '../three/arrival'
import { markArrived } from '../lib/firstVisit'
import { playSfx } from '../lib/sfx'
import './arrival.css'

/** Captions by film time, in seconds. */
const CAPTIONS = [
  { from: 1.9, to: 3.3, text: 'Look closer.' },
  { from: 6.7, to: END + 0.4, text: 'For more than twenty years, satellites have watched the Earth burn.' },
]

interface Props {
  /** the film is near black: a good moment for the page underneath to compile its shaders */
  onWarm?: () => void
  /** the film is handing over; the page underneath should start its own entrance */
  onDone?: () => void
}

/**
 * First-visit opening film. Plays over the landing page while its Earth maps download,
 * waits on the Earth if they are still loading, then fades into the page.
 */
export default function Arrival({ onWarm, onDone }: Props) {
  const { progress, active } = useProgress()
  const [caption, setCaption] = useState(-1)
  const [leaving, setLeaving] = useState(false)
  const [gone, setGone] = useState(false)
  const [waiting, setWaiting] = useState(false)
  const [armed, setArmed] = useState(false)
  const warmed = useRef(false)
  const left = useRef(false)
  const cb = useRef({ onWarm, onDone })
  useEffect(() => { cb.current = { onWarm, onDone } }, [onWarm, onDone])

  // nothing may report progress when the files come from cache, so trust "idle" after a beat
  const loaded = !active && (progress >= 100 || armed)

  useEffect(() => {
    arrival.t = 0
    arrival.dist = 0
    arrival.loaded = false
    const id = window.setTimeout(() => setArmed(true), 1200)
    return () => window.clearTimeout(id)
  }, [])

  useEffect(() => { arrival.loaded = loaded }, [loaded])

  const leave = useCallback(() => {
    if (left.current) return
    left.current = true
    markArrived()
    if (!warmed.current) { warmed.current = true; cb.current.onWarm?.() }
    setLeaving(true)
    cb.current.onDone?.()
    window.setTimeout(() => setGone(true), 1300)
  }, [])

  const skip = useCallback(() => {
    playSfx('skip')
    if (arrival.loaded) leave()
    else arrival.t = Math.max(arrival.t, HOLD - 0.6)
  }, [leave])

  useEffect(() => {
    let raf = 0
    const tick = () => {
      const t = arrival.t
      setCaption(CAPTIONS.findIndex((c) => t >= c.from && t < c.to))
      setWaiting(t >= HOLD && !arrival.loaded)
      if (!warmed.current && arrival.loaded && t >= DARK) { warmed.current = true; cb.current.onWarm?.() }
      if (t >= END && arrival.loaded) leave()
      if (!left.current) raf = requestAnimationFrame(tick)
    }
    raf = requestAnimationFrame(tick)
    return () => cancelAnimationFrame(raf)
  }, [leave])

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape') skip() }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [skip])

  if (gone) return null
  const pct = loaded ? 100 : Math.round(progress)
  return (
    <div className={`arrival ${leaving ? 'is-leaving' : ''}`} aria-label="Opening film" role="region">
      <ArrivalScene />

      <div className="arrival__hud">
        <span className="arrival__corner arrival__corner--tl" aria-hidden="true" />
        <span className="arrival__corner arrival__corner--tr" aria-hidden="true" />
        <span className="arrival__corner arrival__corner--bl" aria-hidden="true" />
        <span className="arrival__corner arrival__corner--br" aria-hidden="true" />
        <p className="arrival__kicker"><span translate="no" className="notranslate">The Third Eye</span>. NASA Space Apps 2026.</p>
        <button type="button" className="arrival__skip" onClick={skip} data-cursor="Skip">
          {waiting ? 'Loading' : 'Skip'} <span aria-hidden="true">→</span>
        </button>

        <div className="arrival__captions" aria-live="polite">
          {CAPTIONS.map((c, i) => (
            <p key={c.text} className={`arrival__caption ${i === caption ? 'is-on' : ''}`} aria-hidden={i !== caption}>{c.text}</p>
          ))}
        </div>

        <div className="arrival__load" role="status" aria-label={`Loading, ${pct} percent`}>
          <div className="arrival__meter"><span style={{ transform: `scaleX(${pct / 100})` }} /></div>
          <p><span className="arrival__num">{String(pct).padStart(3, '0')}</span>% {loaded ? 'Ready' : 'Loading Earth maps'}</p>
        </div>
        <p className="arrival__credit">Illustration. Earth maps: NASA Blue Marble and Black Marble.</p>
      </div>
    </div>
  )
}
