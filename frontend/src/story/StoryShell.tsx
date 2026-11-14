import { useEffect, useMemo, useRef, useState, type ReactNode } from 'react'
import { Link, Navigate, useNavigate, useParams } from 'react-router-dom'
import gsap from 'gsap'
import { useGSAP } from '@gsap/react'

import Hud from '../components/Hud'
import Pips from '../components/Pips'
import Cursor from '../components/Cursor'
import ChapterScene from '../three/ChapterScene'
import SeamChart from './SeamChart'
import { CHAPTERS, VERDICTS, chapterIndex, skipTarget, type Art, type Choice } from './chapters'
import { grid, stat, type FieldView } from '../lib/field'
import { prefersReducedMotion } from '../lib/random'
import { playSfx } from '../lib/sfx'
import { Keep } from '../components/Keep'
import './story.css'

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

  const skip = () => { playSfx('skip'); go(skipTarget(current), 'Skipped') }

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
    },
    { scope: root, dependencies: [log] },
  )

  return (
    <div ref={root}>
      <Cursor />
      <Hud
        objective={{ title: chapter.title, hint: chapter.hint }}
        top={<ChapterBar idx={idx} />}
        bottom={
          <nav className="story__bottom" aria-label="Story controls">
            <Link className="chip chip--quiet" to="/story">Replay intro</Link>
            <span className="story__keys" aria-hidden="true">
              <kbd>1</kbd>{current.choices.length > 1 && <>–<kbd>{current.choices.length}</kbd></>} choose
            </span>
            <button type="button" className="chip" onClick={skip}>Skip step <kbd>S</kbd></button>
            <Link className="chip" to="/lab">Open Lab</Link>
            <Link className="chip chip--quiet" to="/">Exit <kbd>Esc</kbd></Link>
          </nav>
        }
      >
        <div className="story" data-kind={art.kind} data-universe={parallel ? 'parallel' : 'main'}>
          <section className="story__art" aria-label="Illustration">
            <div className="story__stage">
              <ChapterScene art={art} fieldView={fieldView} />
            </div>
            <ArtOverlay art={art} fieldView={fieldView} onField={setFieldOverride} caption={chapter.caption} parallel={parallel ? answer : undefined} />
          </section>

          <section className="story__text" aria-label="Narration">
            <div className="story__log" ref={logRef} aria-live="polite">
              {log.map((entry, i) => {
                const node = chapter.nodes.find((n) => n.id === entry.node)
                if (!node) return null
                const isLast = i === log.length - 1
                return (
                  <div key={`${i}-${entry.node}`} className={`story__entry ${isLast ? '' : 'is-past'} ${node.universe === 'parallel' ? 'is-parallel' : ''}`}>
                    {node.universe === 'parallel' && <p className="story__universe-tag">Parallel universe</p>}
                    {entry.returned && <p className="story__back-note">Back in the main universe. Try another answer.</p>}
                    {node.text.map((p, j) => <p key={j} className="story__para"><Keep text={p} /></p>)}
                    {node.question && (
                      <p className="story__question">
                        <span className="story__qmark" aria-hidden="true">?</span>
                        {node.question}
                      </p>
                    )}
                    {entry.said && <p className="story__said">{node.question ? 'Your answer: ' : 'You: '}{entry.said}</p>}
                    {isLast && node.question && (
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
              <Pips n={i + 1} size={26} />
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
    note = 'Real image: eastern Angola, 18 June 2024, VIIRS true colour (NASA GIBS). Fires and squares are illustrations.'
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
          {clouds && !zero && <span>Hazy squares are under cloud: not seen, not counted.</span>}
          {zero && <span className="readout--parallel">Cloudy squares counted as no fire.</span>}
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
      <b>{label}</b> {s.lit} squares with fire of {s.seen} seen{s.rate !== null && <> = {Math.round(s.rate)} per 1,000</>}
    </span>
  )
}
