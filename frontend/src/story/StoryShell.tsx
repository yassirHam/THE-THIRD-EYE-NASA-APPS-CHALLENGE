import { lazy, Suspense, useEffect, useMemo, useRef, useState, type ReactNode } from 'react'
import { Link, Navigate, useNavigate, useParams } from 'react-router-dom'
import gsap from 'gsap'
import { useGSAP } from '@gsap/react'

import Hud from '../components/Hud'
import Cursor from '../components/Cursor'
import ChapterScene from '../three/ChapterScene'
import SeamChart from './SeamChart'
import { CHAPTERS, VERDICTS, chapterIndex, skipTarget, type Art, type Choice } from './chapters'
import { grid, stat, type FieldView } from '../lib/field'
import { prefersReducedMotion } from '../lib/random'
import { playSfx } from '../lib/sfx'
import { Keep } from '../components/Keep'
import './story.css'

const Professor = lazy(() => import('./Professor'))

interface LogEntry {
  node: string
  said?: string
  /** set when the reader came back here from a parallel universe */
  returned?: boolean
  /** answers already tried at this question; each led to a parallel universe */
  tried?: string[]
}

export default function StoryShell() {
  const { chapter: chapterId = '' } = useParams()
  const idx = chapterIndex(chapterId)
  if (idx < 0) return <Navigate to="/story/third-eye" replace />
  return <ChapterView key={chapterId} idx={idx} />
}

function ChapterView({ idx }: { idx: number }) {
  const chapter = CHAPTERS[idx]
  const navigate = useNavigate()
  const root = useRef<HTMLDivElement>(null)
  const logRef = useRef<HTMLDivElement>(null)
  const [log, setLog] = useState<LogEntry[]>([{ node: 'start' }])
  const [fieldOverride, setFieldOverride] = useState<FieldView | null>(null)
  const [menu, setMenu] = useState(false)
  // first visit to Story Mode: open the menu briefly so the reader learns where the controls are
  const [preview, setPreview] = useState(() => localStorage.getItem('the-third-eye-menu-seen') !== 'yes')
  const [paused, setPaused] = useState(false)
  const [sound, setSound] = useState(() => localStorage.getItem('the-third-eye-sound') !== 'off')
  const [eyeReaction, setEyeReaction] = useState(false)
  const menuRef = useRef<HTMLDivElement>(null)
  const clicks = useRef<number[]>([])
  const cooldown = useRef(0)
  const busy = useRef(false)

  const current = chapter.nodes.find((n) => n.id === log[log.length - 1].node) ?? chapter.nodes[0]
  const art: Art = current.art ?? chapter.art
  const parallel = current.universe === 'parallel'
  const answer = log.length > 1 ? log[log.length - 2].said : undefined
  const reduced = useMemo(prefersReducedMotion, [])
  const fieldView = art.kind === 'field' ? fieldOverride ?? art.view : null

  useEffect(() => {
    document.title = `${chapter.title} - THE THIRD EYE Story`
  }, [chapter.title])

  const go = (to: string, said: string) => {
    if (to.startsWith('/')) return navigate(to)
    if (to.startsWith('#')) return navigate(`/story/${to.slice(1)}`)
    setFieldOverride(null)
    setLog((l) => {
      const copy = l.slice()
      copy[copy.length - 1] = { ...copy[copy.length - 1], said }
      return [...copy, { node: to }]
    })
  }

  const choose = (c: Choice) => {
    if (busy.current) return
    busy.current = true
    window.setTimeout(() => { busy.current = false }, 250)
    // a quiz answer that is neither correct nor a return leads into a parallel universe: wrong
    if (current.question && !c.correct && !c.back) playSfx('wrong')
    if (!c.back) return go(c.to, c.label)
    // leave the parallel universe: drop that branch and ask the question again
    setFieldOverride(null)
    setLog((l) => {
      const at = l.map((e) => e.node).lastIndexOf(c.to)
      if (at < 0) return l
      const left = l[at]
      const tried = [...(left.tried ?? []), ...(left.said ? [left.said] : [])]
      return [...l.slice(0, at), { node: c.to, returned: true, tried }]
    })
  }

  const skip = () => { if (current.question) return; playSfx('skip'); go(skipTarget(current), 'Continued') }
  const back = () => {
    if (log.length > 1) { setFieldOverride(null); setLog((items) => items.slice(0, -1).map((item, i, all) => i === all.length - 1 ? { ...item, said: undefined } : item)); return }
    navigate(idx > 0 ? `/story/${CHAPTERS[idx - 1].id}` : '/?mode=story')
  }

  useEffect(() => {
    const onEye = () => {
      const now = Date.now()
      if (now < cooldown.current) return
      clicks.current = [...clicks.current.filter((time) => now - time < 2200), now]
      if (clicks.current.length >= 6) { clicks.current = []; cooldown.current = now + 4000; setEyeReaction(true); window.setTimeout(() => setEyeReaction(false), 1800) }
    }
    window.addEventListener('third-eye-blink', onEye)
    return () => window.removeEventListener('third-eye-blink', onEye)
  }, [])
  useEffect(() => {
    if (!preview) return
    localStorage.setItem('the-third-eye-menu-seen', 'yes')
    const open = window.setTimeout(() => setMenu(true), 1100)
    const close = window.setTimeout(() => { setMenu(false); setPreview(false) }, 4300)
    return () => { window.clearTimeout(open); window.clearTimeout(close) }
  }, [preview])
  useEffect(() => {
    if (!menu) return
    const close = (event: PointerEvent) => { if (!menuRef.current?.contains(event.target as Node)) setMenu(false) }
    const escape = (event: KeyboardEvent) => { if (event.key === 'Escape') { event.stopPropagation(); setMenu(false) } }
    document.addEventListener('pointerdown', close)
    document.addEventListener('keydown', escape, true)
    return () => { document.removeEventListener('pointerdown', close); document.removeEventListener('keydown', escape, true) }
  }, [menu])

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.metaKey || e.ctrlKey || e.altKey) return
      if (e.key === 'Escape') navigate('/')
      if (e.key === 's' || e.key === 'S') skip()
      const n = Number(e.key)
      if (n >= 1 && n <= current.choices.length) choose(current.choices[n - 1])
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  })

  useGSAP(
    () => {
      if (reduced) return
      const tl = gsap.timeline({ defaults: { ease: 'expo.out' } })
      tl.from('.story__art', { clipPath: 'inset(0 100% 0 0)', duration: 1.4 })
        .from('.story__overlay', { opacity: 0, y: 10, duration: 0.8 }, '-=0.9')
    },
    { scope: root },
  )

  // crossing into or out of a parallel universe: the illustration opens like a portal
  const first = useRef(true)
  useGSAP(
    () => {
      if (first.current) { first.current = false; return }
      if (reduced) return
      gsap.fromTo('.story__art', { clipPath: 'circle(0% at 50% 50%)' }, { clipPath: 'circle(75% at 50% 50%)', duration: 1.1, ease: 'expo.inOut', clearProps: 'clipPath' })
    },
    { scope: root, dependencies: [parallel] },
  )

  useGSAP(
    () => {
      const el = logRef.current
      if (!el) return
      el.scrollTo({ top: el.scrollHeight, behavior: reduced ? 'auto' : 'smooth' })
      if (reduced) return
      gsap.from('.story__entry:last-child .story__para, .story__entry:last-child .story__question, .story__entry:last-child .story__back-note, .story__choices li, .story__answers li', { opacity: 0, y: 14, filter: 'blur(6px)', duration: 0.7, stagger: 0.1, ease: 'power3.out' })
      if (root.current?.querySelector('.story__entry:last-child .quiz')) gsap.from('.story__entry:last-child .quiz', { clipPath: 'inset(0 0 0 100%)', duration: 0.8, delay: 0.15, ease: 'expo.out', clearProps: 'clipPath' })
    },
    { scope: root, dependencies: [log] },
  )

  return (
    <div ref={root}>
      <Cursor />
      <Hud
        objective={{ title: chapter.title, hint: chapter.hint }}
        top={<>
          <button className="story__back" onClick={back} aria-label="Previous story step">←</button>
          <ChapterBar idx={idx} />
          <div className={`story__menu ${preview ? 'is-preview' : ''}`} ref={menuRef}>
            <button className="story__menu-trigger" aria-expanded={menu} aria-controls="story-options" onClick={() => { setPreview(false); setMenu(!menu) }}>
              <span className="story__menu-label">Menu</span>
              <span className="story__menu-dots" aria-hidden="true">⋯</span>
            </button>
            {menu && (
              <div id="story-options" className="story__menu-panel">
                {preview && <p className="story__menu-hint">Story controls live here.</p>}
                <button onClick={() => { back(); setMenu(false) }}>Previous step</button>
                <button onClick={() => { skip(); setMenu(false) }} disabled={!!current.question} title={current.question ? 'Answer the question to go on' : undefined}>Next step <kbd>S</kbd></button>
                <button aria-pressed={paused} onClick={() => setPaused(!paused)}>{paused ? 'Resume animation' : 'Pause animation'}</button>
                <button onClick={() => { const next = !sound; setSound(next); localStorage.setItem('the-third-eye-sound', next ? 'on' : 'off') }}>Sound {sound ? 'on' : 'off'}</button>
                <span className="story__menu-rule" aria-hidden="true" />
                <button onClick={() => { setLog([{ node: 'start' }]); setFieldOverride(null); setMenu(false) }}>Restart chapter</button>
                <Link to="/story/third-eye">Restart Story Mode</Link>
                <Link to="/story">Replay introduction</Link>
                <Link to="/lab">Open Research Lab</Link>
                <a href="https://earthdata.nasa.gov/data/instruments/modis">Data sources</a>
              </div>
            )}
          </div>
        </>}
      >
        <div className={`story ${eyeReaction && !reduced ? 'story--reaction' : ''}`} data-kind={art.kind} data-universe={parallel ? 'parallel' : 'main'}>
          <p className="story__eye-message" role="status">{eyeReaction ? 'Stop making me blink!' : ''}</p>
          <section className="story__art" aria-label="Illustration">
            <div className="story__stage">
              <ChapterScene art={art} fieldView={fieldView} paused={paused || reduced} />
            </div>
            <ArtOverlay art={art} fieldView={fieldView} onField={setFieldOverride} caption={chapter.caption} parallel={parallel ? answer : undefined} />
          </section>

          <section className="story__text" aria-label="Narration">
            <Suspense fallback={<span className="professor-fallback">Professor Orez</span>}><Professor paused={paused || reduced} mood={eyeReaction ? 'reveal' : parallel ? 'wrong' : current.question ? 'thinking' : answer && log.length > 1 && chapter.nodes.find((n) => n.id === log[log.length - 2].node)?.question ? 'correct' : 'explaining'} /></Suspense>
            <div className="story__log" ref={logRef} aria-live="polite">
              {log.map((entry, i) => {
                const node = chapter.nodes.find((n) => n.id === entry.node)
                if (!node) return null
                const isLast = i === log.length - 1
                return (
                  <div key={`${i}-${entry.node}`} className={`story__entry ${isLast ? '' : 'is-past'} ${node.universe === 'parallel' ? 'is-parallel' : ''}`}>
                    {node.universe === 'parallel' && <p className="story__universe-tag">Parallel universe</p>}
                    {entry.returned && <p className="story__back-note">Back in the main universe. Try another answer.</p>}
                    {isLast ? (
                      <div className="speech">
                        <p className="speech__who">
                          Professor Orez
                          <span className="speech__talk" aria-hidden="true"><i /><i /><i /></span>
                        </p>
                        {node.text.map((p, j) => <p key={j} className="story__para"><Keep text={p} /></p>)}
                        <span className="speech__tail" aria-hidden="true" />
                      </div>
                    ) : node.text.map((p, j) => <p key={j} className="story__para"><Keep text={p} /></p>)}
                    {node.question && !isLast && (
                      <p className="story__question">
                        <span className="story__qmark" aria-hidden="true">?</span>
                        {node.question}
                      </p>
                    )}
                    {entry.said && <p className="story__said">{node.question ? 'Your answer: ' : 'You: '}{entry.said}</p>}
                    {isLast && node.question && (
                      <div className="quiz">
                        <p className="story__question quiz__head">
                          <span className="story__qmark" aria-hidden="true">?</span>
                          {node.question}
                          <span className="quiz__pointer" aria-hidden="true" />
                        </p>
                        <ol className="story__answers" aria-label={node.question}>
                          {node.choices.map((c, k) => (
                            <li key={c.label}>
                              <button type="button" className={entry.tried?.includes(c.label) ? 'is-tried' : ''} onClick={() => choose(c)} data-cursor="Answer">
                                <kbd aria-hidden="true">{k + 1}</kbd>
                                <span>{c.label}</span>
                                {entry.tried?.includes(c.label) && <small className="story__tried">Visited</small>}
                              </button>
                            </li>
                          ))}
                        </ol>
                      </div>
                    )}
                  </div>
                )
              })}
            </div>
            {!current.question && (
              <ol className="story__choices">
                {current.choices.map((c, i) => (
                  <li key={c.label}>
                    <button type="button" className={c.back ? 'is-back' : ''} onClick={() => choose(c)} data-cursor={c.back ? 'Return' : 'Choose'}>
                      <span className="story__arrow" aria-hidden="true" />
                      <span>{c.label}</span>
                      <kbd aria-hidden="true">{i + 1}</kbd>
                    </button>
                  </li>
                ))}
              </ol>
            )}
          </section>
        </div>
      </Hud>
    </div>
  )
}

function ChapterBar({ idx }: { idx: number }) {
  return (
    <nav className="chapterbar" aria-label="Chapters">
      <span className="chapterbar__label">Story</span>
      <ol className="chapterbar__slots">
        {CHAPTERS.map((c, i) => (
          <li key={c.id}>
            <Link
              to={`/story/${c.id}`}
              className={`chapterbar__slot ${i === idx ? 'is-current' : i < idx ? 'is-done' : ''}`}
              aria-current={i === idx ? 'step' : undefined}
              title={c.title}
            >
              <span aria-hidden="true">{['I', 'II', 'III', 'IV', 'V'][i]}</span>
              <span className="sr-only">Chapter {i + 1}: {c.title}</span>
            </Link>
          </li>
        ))}
      </ol>
      <div className="chapterbar__progress" aria-hidden="true">
        <span style={{ width: `${((idx + 1) / CHAPTERS.length) * 100}%` }} />
      </div>
    </nav>
  )
}

interface OverlayProps {
  art: Art
  fieldView: FieldView | null
  onField: (v: FieldView) => void
  caption: string
  /** the answer that led into a parallel universe, when in one */
  parallel?: string
}

/** HTML layer over the 3D illustration. Rows, top to bottom: controls, open space (or the chart),
 *  live readouts, then the caption with its provenance note. Readouts and caption never share a row. */
function ArtOverlay({ art, fieldView, onField, caption, parallel }: OverlayProps) {
  let controls: ReactNode = null
  let body: ReactNode = null
  let readouts: ReactNode = null
  let note = art.kind === 'third' ? 'Illustration: made-up fires' : 'Illustration'
  if (art.kind === 'field' && fieldView) {
    const clouds = !!art.clouds
    const zero = !!art.cloudsAsZero
    const m = stat(grid('modis', clouds, zero))
    const v = stat(grid('viirs', clouds, zero))
    const showM = fieldView === 'modis' || fieldView === 'both'
    const showV = fieldView === 'viirs' || fieldView === 'both'
    note = 'Real image: eastern Angola, 18 June 2024, VIIRS true colour (NASA GIBS). Fires and chunks are illustrations.'
    if (art.toggles) {
      controls = (
        <div className="art__toggles" role="group" aria-label="Choose an eye">
          {(['ground', 'modis', 'viirs', 'both'] as FieldView[]).map((k) => (
            <button key={k} type="button" className="chip" aria-pressed={fieldView === k} onClick={() => onField(k)}>
              {k === 'ground' ? 'Ground' : k === 'modis' ? 'MODIS' : k === 'viirs' ? 'VIIRS' : 'Both'}
            </button>
          ))}
        </div>
      )
    }
    if (showM || showV || clouds) {
      readouts = (
        <div className="readouts">
          {showM && <Readout tone="modis" label="Coarse eye" s={m} />}
          {showV && <Readout tone="viirs" label="Fine eye" s={v} />}
          {clouds && !zero && <span>Hazy chunks are under cloud: not seen, not counted.</span>}
          {zero && <span className="readout--parallel">Cloudy chunks counted as no fire.</span>}
        </div>
      )
    }
  } else if (art.kind === 'seam') {
    note = 'Illustration: made-up numbers'
    body = <SeamChart view={art.view} headline={art.headline} />
  } else if (art.kind === 'verdict') {
    note = ''
    controls = (
      <ul className="verdicts">
        {VERDICTS.map((v) => (
          <li key={v.label} className={`verdict verdict--${v.tone}`}>
            <span className="verdict__mark" aria-hidden="true" />
            <div><b>{v.label}</b><span>{v.meaning}</span></div>
          </li>
        ))}
      </ul>
    )
  }
  return (
    <div className={`story__overlay story__overlay--${art.kind}`}>
      <div className="story__controls">
        {parallel !== undefined && (
          <p className="story__universe">
            <b>Parallel universe</b>
            <span>Where the answer “{parallel}” leads</span>
          </p>
        )}
        {controls}
      </div>
      {body && <div className="story__body">{body}</div>}
      {readouts}
      <p className="story__caption">
        <span>{caption}</span>
        {note && <span className="story__note">{note}</span>}
      </p>
    </div>
  )
}

function Readout({ tone, label, s }: { tone: 'modis' | 'viirs'; label: string; s: { seen: number; lit: number; rate: number | null } }) {
  return (
    <span className={`readout readout--${tone}`}>
      <b>{label}</b> {s.lit} chunks with detected fire of {s.seen} seen{s.rate !== null && <> = {Math.round(s.rate)} per 1,000 seen chunks in this illustration</>}
    </span>
  )
}
