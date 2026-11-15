import { useEffect, useMemo, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import gsap from 'gsap'
import { useGSAP } from '@gsap/react'

import IntroScene from '../three/IntroScene'
import Loader from '../components/Loader'
import Cursor from '../components/Cursor'
import Eye from '../art/Eye'
import { intro } from '../three/state'
import { prefersReducedMotion } from '../lib/random'
import { playSfx } from '../lib/sfx'
import { LINE_SECONDS, narrator } from './narrator'
import { Animated } from '../components/Keep'
import './intro.css'

/** Speaker glyph, drawn with the same 1.5px stroke as the other controls. */
function SoundIcon({ on }: { on: boolean }) {
  return (
    <svg width="14" height="14" viewBox="0 0 14 14" aria-hidden="true" fill="none" stroke="currentColor" strokeWidth="1.5">
      <path d="M1.5 5h2.5l3-2.5v9L4 9H1.5z" fill="currentColor" stroke="none" />
      {on ? <path d="M9.5 4.5a3.5 3.5 0 0 1 0 5M11 2.5a6 6 0 0 1 0 9" /> : <path d="M9.5 5l3.5 4M13 5l-3.5 4" />}
    </svg>
  )
}

const FIRST_CHAPTER = '/story/third-eye'
const BEATS = ['b1', 'b2', 'b3', 'b4', 'b5'] as const

const INITIAL = { world: 0, pov: 0, raise: 0, squint: 0, camX: 0, lidL: 1, lidR: 1, tintL: 0, tintR: 0, seam: 0, globeX: 0, eyeOpen: 0, rise: 0, fireModis: 1, fireViirs: 1 }

/** Typed line. The animated copy is one span per letter; translators and screen readers get the
    whole sentence instead (see components/Keep.tsx). */
function Line({ k, text, className }: { k: string; text: string; className?: string }) {
  return (
    <p className={`intro__line ${className ?? ''}`} data-k={k}>
      <Animated text={text}>
        {text.split(' ').map((word, w) => (
          <span key={w}>
            {w > 0 && ' '}
            <span className="word">
              {Array.from(word).map((ch, i) => <span key={i} className="ch">{ch}</span>)}
            </span>
          </span>
        ))}
      </Animated>
    </p>
  )
}

export default function Intro() {
  const root = useRef<HTMLDivElement>(null)
  const tl = useRef<gsap.core.Timeline | null>(null)
  const navigate = useNavigate()
  const reduced = useMemo(prefersReducedMotion, [])
  const [ready, setReady] = useState(false)
  const [playing, setPlaying] = useState(true)
  const [done, setDone] = useState(false)
  const [sound, setSound] = useState({ muted: narrator.muted, blocked: false })

  const skip = () => { playSfx('skip'); navigate(FIRST_CHAPTER) }

  useEffect(() => {
    narrator.preload()
    const off = narrator.subscribe(setSound)
    return () => { off(); narrator.stop(); narrator.stopMusic() }
  }, [])

  useEffect(() => {
    document.title = 'THE THIRD EYE - Story'
    Object.assign(intro, INITIAL)
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape') skip() }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  useGSAP(
    (_, contextSafe) => {
      if (!ready) return
      const t = gsap.timeline({
        defaults: { ease: 'power3.inOut' },
        onComplete: contextSafe!(() => {
          setDone(true)
          root.current?.querySelector<HTMLButtonElement>('.intro__begin')?.focus()
        }),
      })
      tl.current = t
      const type = (k: string, pos?: gsap.Position, speed = 0.026) => {
        t.to(`.intro__line[data-k="${k}"] .ch`, { opacity: 1, duration: 0.01, stagger: speed, ease: 'none' }, pos)
        // a translated page shows the whole sentence instead of the letters; it fades in on cue
        t.fromTo(`.intro__line[data-k="${k}"] .tx-whole`, { opacity: 0 }, { opacity: 1, duration: 0.5, ease: 'none' }, '<')
        // park lines take their place only when they start, so the card grows with the text
        if (k.startsWith('p')) t.set(`.intro__line[data-k="${k}"]`, { display: 'block' }, '<')
        // the narrator reads the line as it types; the timeline waits until the voice is done
        t.call(() => narrator.say(k), undefined, '<')
        t.to({}, { duration: LINE_SECONDS[k] ?? 0 }, '<')
      }
      const show = (sel: string, pos?: gsap.Position) => t.to(sel, { autoAlpha: 1, duration: 0.6 }, pos)
      const hide = (sel: string, pos?: gsap.Position) => t.to(sel, { autoAlpha: 0, duration: 0.6 }, pos)

      t.set('.ch', { opacity: 0 })
      t.set('.intro__panel--p1 .intro__line', { display: 'none' })
      t.set('.intro__panel, .intro__title .ch, .intro__begin, .intro__eyes, .intro__phones', { autoAlpha: 0 })
      t.set('.intro__seam-path', { strokeDashoffset: 900 })
      t.set(intro, INITIAL)

      // ---- Before the eyes open: the music fades in and a short note suggests headphones ----
      // the two ear cups light one after the other, left then right, the way the two eyes speak
      t.call(() => narrator.startMusic(), undefined, 0.05)
      t.to('.intro__phones', { autoAlpha: 1, duration: 0.5, ease: 'power2.out' }, 0.1)
      t.fromTo('.intro__cup--l', { opacity: 0.3 }, { opacity: 1, duration: 0.2, repeat: 1, yoyo: true, ease: 'sine.inOut' }, '+=0.25')
      t.fromTo('.intro__cup--r', { opacity: 0.3 }, { opacity: 1, duration: 0.2, repeat: 1, yoyo: true, ease: 'sine.inOut' }, '+=0.12')
      t.to('.intro__phones', { autoAlpha: 0, duration: 0.5, ease: 'power2.in' }, '+=1.4')

      // ---- Beat 1: a child on a park bench holds up a finger; then we look through their eyes ----
      t.addLabel('b1')
      t.to(intro, { lidL: 0, lidR: 0, duration: 1.6, ease: 'expo.out' })
      show('.intro__panel--p1', '<0.4')
      type('p1', '<0.3')
      // the child raises the finger as the narrator asks for it; the arm overshoots a touch and settles
      t.to(intro, { raise: 1, duration: 1.5, ease: 'back.out(1.25)' }, '<0.35')
      t.to(intro, { pov: 1, duration: 3.2, ease: 'power2.inOut' }, '+=0.7')
      t.addLabel('pov', '<')
      show('.intro__eyes', '-=0.6')
      type('p2', '<')
      // switching eyes, as a person does it: an uneven rhythm, a quick squint as one eye
      // closes, and the view settling a moment after the switch
      const hop = (dir: number, gap: number, dur: number) => {
        t.to(intro, { squint: 0.4, duration: dur * 0.45, ease: 'sine.in' }, `+=${gap}`)
        t.to(intro, { camX: dir, duration: dur, ease: 'sine.inOut' }, '<')
        t.to(intro, { squint: 0, duration: dur * 1.4, ease: 'sine.out' }, `<${dur * 0.45}`)
        t.set('.intro__eyes', { attr: { 'data-open': dir < 0 ? 'left' : 'right' } }, '<')
      }
      t.addLabel('hops', '+=0.01')
      ;[[-1, 0.5, 0.2], [1, 0.42, 0.17], [-1, 0.7, 0.22], [1, 0.36, 0.16], [-1, 0.58, 0.19], [1, 0.48, 0.18]]
        .forEach(([dir, gap, dur]) => hop(dir, gap, dur))
      t.to(intro, { camX: 0, duration: 0.55, ease: 'sine.inOut' }, '+=0.5')
      t.set('.intro__eyes', { attr: { 'data-open': 'both' } }, '<')
      type('p3', '+=0.2')
      type('p4', '+=0.5', 0.05)

      // blink: the world changes while both eyes are shut
      t.to(intro, { lidL: 1, lidR: 1, duration: 0.7, ease: 'power3.in' }, '+=1.1')
      hide('.intro__panel--p1, .intro__eyes', '<')
      t.set(intro, { world: 1, globeX: 2.25, tintR: 1, fireModis: 1, fireViirs: 0 })

      // ---- Beat 2: close your left eye; the right half shows MODIS ----
      t.addLabel('b2')
      show('.intro__panel--l', '+=0.2')
      type('l1', '<')
      t.to(intro, { lidR: 0, duration: 1.4, ease: 'expo.out' }, '+=0.2')
      type('l2', '<0.4', 0.02)
      type('l3', '+=0.4', 0.02)

      // ---- Beat 3: swap eyes; the left half shows VIIRS ----
      t.to(intro, { lidR: 1, duration: 0.8, ease: 'power3.in' }, '+=1.1')
      hide('.intro__panel--l', '<')
      t.set(intro, { globeX: -2.25, tintR: 0, tintL: 1, fireModis: 0, fireViirs: 1 })
      t.addLabel('b3')
      show('.intro__panel--r', '+=0.1')
      type('r1', '<')
      t.to(intro, { lidL: 0, duration: 1.4, ease: 'expo.out' }, '+=0.2')
      type('r2', '<0.4', 0.02)
      type('r3', '+=0.4', 0.02)

      // ---- Beat 4: both eyes open on one Earth; the seam ----
      t.to(intro, { lidL: 0.0, duration: 0.1 }, '+=1.1')
      hide('.intro__panel--r', '<')
      t.addLabel('b4')
      t.to(intro, { globeX: 0, lidR: 0, tintR: 1, fireModis: 1, duration: 1.6, ease: 'expo.inOut' })
      t.to(intro, { seam: 1, duration: 0.8 }, '-=0.6')
      show('.intro__panel--b', '<')
      type('b1', '<0.2')
      t.to('.intro__seam-path', { strokeDashoffset: 0, duration: 2.2, ease: 'power2.inOut' }, '+=0.2')
      type('b2', '-=0.8')
      type('b3', '+=0.4', 0.022)

      // ---- Beat 5: a third place to look from ----
      t.to(intro, { tintL: 0, tintR: 0, seam: 0, duration: 1.6, ease: 'power2.inOut' }, '+=1.1')
      hide('.intro__panel--b', '<')
      t.addLabel('b5', '<')
      show('.intro__panel--t', '<0.4')
      type('t1', '<')
      t.to(intro, { rise: 1, duration: 2.4, ease: 'expo.inOut' }, '<')
      t.to(intro, { eyeOpen: 1, duration: 2.2, ease: 'expo.out' }, '-=0.8')
      type('t2', '-=1.2', 0.02)
      type('t3', '+=0.4', 0.028)
      // the explanation gives way to the name, in the same place under the eye
      t.to('.intro__t-copy', { autoAlpha: 0, y: -16, duration: 0.8, ease: 'power2.in' }, '+=1.1')
      t.to('.intro__title .ch', { autoAlpha: 1, duration: 0.9, stagger: 0.06, ease: 'power2.out' }, '-=0.1')
      t.call(() => narrator.say('title'), undefined, '<0.3')
      t.fromTo('.intro__title .ch', { filter: 'blur(14px)', yPercent: 40 }, { filter: 'blur(0px)', yPercent: 0, duration: 1.2, stagger: 0.06, ease: 'expo.out' }, '<-0.3')
      t.to('.intro__begin', { autoAlpha: 1, duration: 0.6 }, '-=0.4')

      if (import.meta.env.DEV) (window as unknown as { __introTl: gsap.core.Timeline }).__introTl = t
      // reduced motion jumps to the end without firing the narration on the way
      if (reduced) t.progress(1, true)
    },
    { scope: root, dependencies: [ready] },
  )

  const togglePlay = () => {
    const t = tl.current
    if (!t) return
    if (t.paused()) { t.play(); narrator.resume(); setPlaying(true) } else { t.pause(); narrator.pause(); setPlaying(false) }
  }

  const next = () => {
    const t = tl.current
    if (!t) return
    const now = t.time()
    const target = BEATS.map((b) => t.labels[b]).find((time) => time > now + 0.05)
    narrator.stop()
    if (target === undefined) return skip()
    t.seek(target)
  }

  /** Back to the start of this beat, or to the beat before if this one has only just begun,
      the way a music player's back button works. Before the first beat, back to the very start. */
  const previous = () => {
    const t = tl.current
    if (!t) return
    const now = t.time()
    const starts = [0, ...BEATS.map((b) => t.labels[b])]
    const here = starts.filter((time) => time <= now + 0.05)
    const current = here[here.length - 1] ?? 0
    const target = now - current > 1.5 ? current : (here[here.length - 2] ?? 0)
    narrator.stop()
    t.seek(target)
    // stepping back from the end screen brings the playback controls back
    if (done) { setDone(false); if (!t.paused()) t.play() }
  }

  const toggleSound = () => {
    const turnOn = sound.muted || sound.blocked
    narrator.setMuted(!turnOn)
    if (turnOn && playing) narrator.replay()
  }

  // Space pauses and plays, M turns the sound off and on. Space would also press whichever
  // control has focus, so the shortcut takes it over, except on "Begin the story" at the end.
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.metaKey || e.ctrlKey || e.altKey || e.repeat) return
      const el = e.target as HTMLElement | null
      if (el?.closest('input, textarea, select, [contenteditable="true"]')) return
      if (e.code === 'Space' || e.key === ' ') {
        // at the end there is nothing left to play; Space presses the focused button as usual
        if (done || el?.closest('.intro__begin')) return
        e.preventDefault()
        togglePlay()
      } else if (e.key === 'm' || e.key === 'M') {
        toggleSound()
      }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  })

  return (
    <div className="intro" ref={root}>
      <IntroScene />
      <Loader onDone={() => setReady(true)} />
      <Cursor />

      <div className="intro__eyes" data-open="both" aria-hidden="true">
        <Eye tone="third" size={58} className="intro__eye intro__eye--l" />
        <Eye tone="third" size={58} className="intro__eye intro__eye--r" />
      </div>

      <div className="intro__phones" role="note">
        <svg width="46" height="46" viewBox="0 0 46 46" aria-hidden="true" fill="none" stroke="currentColor" strokeWidth="1.5">
          <path d="M8 27v-5a15 15 0 0 1 30 0v5" />
          <rect className="intro__cup--l" x="5" y="25" width="8" height="14" rx="1" fill="var(--teal)" stroke="none" />
          <rect className="intro__cup--r" x="33" y="25" width="8" height="14" rx="1" fill="var(--amber)" stroke="none" />
        </svg>
        <p className="intro__phones-title">Best with headphones</p>
        <p className="intro__phones-text">Each eye speaks in its own ear.</p>
      </div>
      <section className="intro__panel intro__panel--p1" aria-label="Parallax">
        <Line k="p1" text="Hold a finger in front of your face." />
        <Line k="p2" text="Close one eye, then the other." />
        <Line k="p3" text="It jumps. Nothing moved. Only the place you looked from." />
        <Line k="p4" text="That shift is parallax." className="intro__line--big" />
      </section>

      <section className="intro__panel intro__panel--l" aria-label="MODIS">
        <Line k="l1" text="Close your left eye." className="intro__line--big" />
        <Line k="l2" text="This is MODIS, on NASA's Aqua satellite. It has watched Earth since 2002." />
        <Line k="l3" text="It sees in squares about a kilometre wide. Small fires can slip through." />
        <p className="intro__tag intro__tag--modis">Coarse eye <span>Grid drawn larger than real</span></p>
      </section>

      <section className="intro__panel intro__panel--r" aria-label="VIIRS">
        <Line k="r1" text="Now close your right eye." className="intro__line--big" />
        <Line k="r2" text="This is VIIRS, on Suomi NPP. It watched from 2012 until November 2026." />
        <Line k="r3" text="Its squares are about 375 metres wide. It often catches small fires the first eye missed." />
        <p className="intro__tag intro__tag--viirs">Fine eye <span>Grid enlarged by the same factor</span></p>
      </section>

      <section className="intro__panel intro__panel--b" aria-label="The seam">
        <Line k="b1" text="Open both eyes and join their records." className="intro__line--big" />
        <svg className="intro__seam" viewBox="0 0 600 120" aria-hidden="true">
          <line x1="300" y1="4" x2="300" y2="116" stroke="var(--ivory)" strokeDasharray="2 5" opacity="0.6" />
          <path className="intro__seam-path" d="M10 92 L60 86 L110 94 L160 84 L210 90 L260 87 L300 89 L300 34 L350 40 L400 30 L450 38 L500 32 L550 39 L590 34" fill="none" stroke="var(--amber)" strokeWidth="2.4" strokeDasharray="900" />
          <text x="306" y="16" fill="var(--ivory)" fontSize="13" fontFamily="Chakra Petch">2012</text>
        </svg>
        <Line k="b2" text="The fire history jumps in 2012." />
        <Line k="b3" text="Part of that jump is not fire. It is the change of eye." />
      </section>

      <section className="intro__panel intro__panel--t" aria-label="The third eye">
        <Line k="t1" text="Now look from a third place." className="intro__line--big" />
        <div className="intro__t-bottom">
          <div className="intro__t-copy">
            <Line k="t2" text="From here you can tell which differences belong to the fire, and which belong to the eye." />
            <Line k="t3" text="And when you cannot tell, it says so." />
          </div>
          <div className="intro__t-end">
            <h1 className="intro__title notranslate" aria-label="THE THIRD EYE" translate="no">
              {Array.from('THE THIRD EYE').map((c, i) => <span key={i} className="ch" aria-hidden="true">{c}</span>)}
            </h1>
            <button type="button" className="intro__begin" onClick={skip} data-cursor="Begin">Begin the story</button>
          </div>
        </div>
      </section>

      <div className="intro__controls">
        <button type="button" onClick={previous} title="Back to the start of this step, or the step before">Previous</button>
        <button type="button" onClick={togglePlay} aria-pressed={!playing} aria-keyshortcuts="Space" title="Space">{playing ? 'Pause' : 'Play'}</button>
        <button type="button" onClick={next}>Next</button>
        <button
          type="button"
          className={`intro__sound ${sound.blocked ? 'is-blocked' : ''}`}
          onClick={toggleSound}
          aria-pressed={!sound.muted && !sound.blocked}
          aria-label={sound.blocked ? 'Turn sound on' : 'Sound: voice and music'}
          aria-keyshortcuts="M"
          title="Synthetic voice and generated music. Press M to turn off or on"
        >
          <SoundIcon on={!sound.muted && !sound.blocked} />
          <span className="intro__sound-text">{sound.blocked ? 'Turn sound on' : sound.muted ? 'Sound off' : 'Sound on'}</span>
        </button>
        {!done && <button type="button" className="is-strong" onClick={skip} aria-label="Skip intro" aria-keyshortcuts="Escape">Skip<span className="intro__skip-more"> intro</span> <kbd>Esc</kbd></button>}
        <span className="intro__voice">Synthetic voice and music</span>
      </div>
    </div>
  )
}
