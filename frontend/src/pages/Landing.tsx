import { useCallback, useEffect, useRef, useState } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import gsap from 'gsap'
import { ScrollTrigger } from 'gsap/ScrollTrigger'
import { SplitText } from 'gsap/SplitText'
import { useGSAP } from '@gsap/react'
import Lenis from 'lenis'

import LandingScene from '../three/LandingScene'
import Loader from '../components/Loader'
import Arrival from '../components/Arrival'
import Cursor from '../components/Cursor'
import { landing, type PortalKey } from '../three/state'
import { prefersReducedMotion } from '../lib/random'
import { playSfx, preloadSfx } from '../lib/sfx'
import { menuMusicScroll, setMenuSound, soundOn, startMenuMusic, stopMenuMusic } from '../lib/menuMusic'
import { prefetchRoutes } from '../routes'
import { blink } from '../lib/pointer'
import { LabPreview, MissionPreview, StoryPreview } from '../components/ModePreviews'
import { Animated, Name } from '../components/Keep'
import { HEADLINE_UNAVAILABLE, labView } from '../lab/model'
import { DATA_CREDITS, NASA_BRANDING_RULE, SI_USE } from '../lib/credits'
import './landing.css'

gsap.registerPlugin(ScrollTrigger, SplitText)

interface Mode {
  key: Exclude<PortalKey, ''>
  to: string
  /** keyboard shortcut on the first screen */
  hotkey: string
  name: string
  what: string
  action: string
  state?: string
}

/** The three ways in. Shown first so nobody has to scroll to find them. */
const MODES: Mode[] = [
  {
    key: 'story', to: '/?mode=story', hotkey: '1', name: 'Story Mode',
    what: 'A short narrated film, then a guided story.', action: 'Start Story Mode',
  },
  {
    key: 'lab', to: '/lab', hotkey: '2', name: 'Research Lab',
    what: 'Read the fire calendar of a supported area.', action: 'Preview the Lab', state: 'Being built',
  },
  {
    key: 'mission', to: '/mission', hotkey: '3', name: 'Quick Mission',
    what: 'One real case, start to finish, in about 90 seconds.', action: 'Preview the mission', state: 'Being built',
  },
]

const PREVIEW = { story: StoryPreview, lab: LabPreview, mission: MissionPreview }

/** The frozen sensor-switch result and its denominator, or its unavailable status. Same source
 *  and wording as the Research Lab, so the two pages cannot disagree. */
function HeadlineStatus({ className }: { className: string }) {
  const h = labView.headline
  return (
    <p className={className}>
      <b>{HEADLINE_UNAVAILABLE.title}:</b>{' '}
      {h ? <>{h.text} <span>{h.denominator}</span></> : <><span className="status-chip">{HEADLINE_UNAVAILABLE.status}</span> {HEADLINE_UNAVAILABLE.text}</>}
    </p>
  )
}

export default function Landing() {
  const root = useRef<HTMLDivElement>(null)
  const [ready, setReady] = useState(false)
  const [params, setParams] = useSearchParams()
  const navigate = useNavigate()
  const chosen = params.get('mode') === 'story'
  const leaving = useRef(false)
  // first visit of the day: the opening film plays instead of the short loader
  const [film] = useState(false)
  const [paused, setPaused] = useState(film)
  const filmDone = useRef(false)
  const [sound, setSound] = useState(soundOn)
  const warm = useCallback(() => {
    // render the hidden page for a moment so its shaders compile while the film is dark
    setPaused(false)
    window.setTimeout(() => { if (!filmDone.current) setPaused(true) }, 500)
  }, [])
  const endFilm = useCallback(() => {
    filmDone.current = true
    setPaused(false)
    setReady(true)
  }, [])

  useEffect(() => {
    document.title = chosen ? 'Story Mode - THE THIRD EYE' : 'THE THIRD EYE'
  }, [chosen])

  // The mode screen is a fixed page; only the Story scroll page scrolls the body.
  useEffect(() => {
    window.scrollTo(0, 0)
    landing.progress = 0
    landing.hover = ''
    landing.gate = chosen ? 0 : 1
    leaving.current = false
    if (!chosen) return
    document.body.classList.add('is-scroll')
    return () => document.body.classList.remove('is-scroll')
  }, [chosen])

  // Smooth scroll drives a single progress value that the 3D camera follows.
  useEffect(() => {
    if (!chosen) return
    const reduced = prefersReducedMotion()
    const lenis = reduced ? null : new Lenis({ lerp: 0.085, wheelMultiplier: 0.9 })
    const raf = (t: number) => { lenis?.raf(t * 1000) }
    if (lenis) { lenis.on('scroll', ScrollTrigger.update); lenis.on('scroll', (l: Lenis) => menuMusicScroll(l.velocity)); gsap.ticker.add(raf); gsap.ticker.lagSmoothing(0) }
    // without smooth scrolling, read the scroll speed from the native position
    let lastY = window.scrollY
    const onScroll = () => { menuMusicScroll(window.scrollY - lastY); lastY = window.scrollY }
    if (!lenis) window.addEventListener('scroll', onScroll, { passive: true })
    const st = ScrollTrigger.create({
      trigger: '.landing__track',
      start: 'top top',
      end: 'bottom bottom',
      onUpdate: (s) => { landing.progress = s.progress },
    })
    ScrollTrigger.refresh()
    return () => { st.kill(); window.removeEventListener('scroll', onScroll); if (lenis) { gsap.ticker.remove(raf); lenis.destroy() } }
  }, [chosen])

  const { contextSafe } = useGSAP(
    () => {
      // the fixed dock steps aside where the closing section shows the same buttons
      if (chosen) {
        ScrollTrigger.create({
          trigger: '.finale',
          start: 'top 55%',
          onToggle: (s) => root.current?.querySelector('.dock')?.classList.toggle('is-hidden', s.isActive),
        })
      }
      if (!ready || prefersReducedMotion()) return
      if (!chosen) {
        gsap.timeline({ defaults: { ease: 'expo.out' } })
          .from('.gate__head > *', { y: 26, opacity: 0, duration: 1.2, stagger: 0.08 })
          .from('.gate__choose', { scale: 0.6, opacity: 0, duration: 0.9, ease: 'back.out(2.2)' }, '-=0.8')
          .from('.mode', { y: 48, opacity: 0, duration: 1.1, stagger: 0.1 }, '-=0.7')
          .from('.preview', { clipPath: 'inset(0 0 100% 0)', duration: 1.1, stagger: 0.1, ease: 'expo.inOut', clearProps: 'clipPath' }, '-=1')
          .from('.chrome, .topbar', { opacity: 0, duration: 0.8 }, '-=1')
        return
      }
      const title = SplitText.create('.hero__title', { type: 'chars', charsClass: 'hero__char' })
      gsap.timeline({ defaults: { ease: 'expo.out' } })
        .from(title.chars, { yPercent: 110, rotate: 6, filter: 'blur(12px)', opacity: 0, duration: 1.6, stagger: 0.055 })
        .from('.hero__kicker, .hero__sub, .hero__cue, .chrome', { opacity: 0, y: 12, duration: 1, stagger: 0.12 }, '-=1.1')
        .from('.dock', { y: 30, opacity: 0, duration: 0.9 }, '-=1.2')

      gsap.utils.toArray<HTMLElement>('.chapter').forEach((el) => {
        const head = el.querySelector('.chapter__head .tx-anim')
        if (!head) return
        const split = SplitText.create(head, { type: 'lines', mask: 'lines', linesClass: 'chapter__line' })
        gsap.timeline({ scrollTrigger: { trigger: el, start: 'top 65%', end: 'bottom 35%', toggleActions: 'play reverse play reverse' } })
          .from(split.lines, { yPercent: 105, duration: 1.1, stagger: 0.09, ease: 'expo.out' })
          .from(el.querySelectorAll('.chapter__body, .chapter__meta'), { opacity: 0, y: 18, duration: 0.8, stagger: 0.1, ease: 'power3.out' }, '-=0.7')
      })

      gsap.from('.finale > *', { scrollTrigger: { trigger: '.finale', start: 'top 60%' }, y: 40, opacity: 0, duration: 1.1, stagger: 0.1, ease: 'expo.out' })
      gsap.to('.hero', { scrollTrigger: { trigger: '.hero', start: 'top top', end: 'bottom top', scrub: true }, yPercent: -30, opacity: 0 })
      gsap.to('.chrome__bar span', { scrollTrigger: { trigger: '.landing__track', start: 'top top', end: 'bottom bottom', scrub: true }, scaleX: 1, ease: 'none' })
    },
    { scope: root, dependencies: [ready, chosen], revertOnUpdate: true },
  )

  // Story stays on this page: the gate folds away and the scroll page takes its place.
  const chooseStory = contextSafe(() => {
    if (leaving.current) return
    leaving.current = true
    playSfx('mode')
    const go = () => setParams({ mode: 'story' })
    if (prefersReducedMotion()) { go(); return }
    gsap.timeline({ onComplete: go, defaults: { ease: 'power3.in' } })
      .to('.mode:not(.mode--story)', { y: 40, opacity: 0, duration: 0.45, stagger: 0.06 }, 0)
      .to('.gate__head > *, .gate__choose', { y: -20, opacity: 0, duration: 0.45, stagger: 0.04 }, 0)
      .to('.mode--story', { y: -16, opacity: 0, duration: 0.5 }, 0.2)
  })

  const backToModes = () => { playSfx('mode'); setParams({}) }

  // 1, 2, 3 pick a mode from the first screen.
  useEffect(() => {
    if (chosen) return
    const onKey = (e: KeyboardEvent) => {
      if (e.metaKey || e.ctrlKey || e.altKey) return
      if (e.key === '1') chooseStory()
      else if (e.key === '2') { playSfx('mode'); navigate('/lab') }
      else if (e.key === '3') { playSfx('mode'); navigate('/mission') }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [chosen, chooseStory, navigate])

  // Fetch the interface sounds and the other pages once this page is showing, so they do not
  // compete with the Earth maps for bandwidth, and are still ready before the first click.
  useEffect(() => { if (ready) { preloadSfx(); prefetchRoutes() } }, [ready])

  // Menu music: starts on the first click, tap or key press on this page (browsers block sound
  // before that), carries on into the Story scroll page, and fades out when the reader leaves.
  useEffect(() => {
    const go = () => startMenuMusic()
    const events = ['pointerdown', 'keydown', 'touchstart'] as const
    for (const ev of events) window.addEventListener(ev, go, { capture: true, passive: true })
    return () => {
      for (const ev of events) window.removeEventListener(ev, go, { capture: true })
      stopMenuMusic()
    }
  }, [])
  const toggleSound = () => { const next = !sound; setSound(next); setMenuSound(next) }

  const hover = (key: PortalKey) => ({
    onPointerEnter: () => { landing.hover = key },
    onPointerLeave: () => { landing.hover = '' },
    onFocus: () => { landing.hover = key },
    onBlur: () => { landing.hover = '' },
  })

  return (
    <div className={`landing ${chosen ? 'is-story' : 'is-gate'}`} ref={root}>
      <LandingScene paused={paused} />
      {film ? <Arrival onWarm={warm} onDone={endFilm} /> : <Loader onDone={() => setReady(true)} />}
      <Cursor />

      <div className="chrome" aria-hidden="true">
        <span className="chrome__corner chrome__corner--tl" />
        <span className="chrome__corner chrome__corner--tr" />
        <span className="chrome__corner chrome__corner--bl" />
        <span className="chrome__corner chrome__corner--br" />
        {chosen && <div className="chrome__bar"><span /></div>}
      </div>

      <header className="topbar">
        <Link to="/" className="topbar__mark" data-cursor="Modes" onClick={(e) => blink(e.currentTarget.querySelector('.topbar__eye'))}>
          <svg viewBox="-60 -90 120 180" aria-hidden="true"><g className="topbar__eye blink-target blink-x"><path d="M0 -84 Q46 0 0 84 Q-46 0 0 -84 Z" /><circle r="16" /></g></svg>
          <span translate="no" className="notranslate">The Third Eye</span>
        </Link>
        <nav className="topbar__nav" aria-label="Modes">
          <Link to="/?mode=story" aria-current={chosen ? 'page' : undefined} data-cursor="Story" onClick={() => playSfx('mode')}>Story</Link>
          <Link to="/lab" data-cursor="Soon" onClick={() => playSfx('mode')}>Lab</Link>
          <Link to="/mission" data-cursor="Soon" onClick={() => playSfx('mode')}>Mission</Link>
          <button type="button" className="topbar__sound" aria-pressed={sound} onClick={toggleSound} data-cursor={sound ? 'Mute' : 'Unmute'}>
            <span className="topbar__bars" aria-hidden="true"><i /><i /><i /></span>
            Sound {sound ? 'on' : 'off'}
          </button>
        </nav>
      </header>

      {!chosen && (
        <main className="gate" aria-labelledby="gate-title">
          <div className="gate__head">
            <h1 className="gate__title notranslate" id="gate-title" translate="no">The Third Eye</h1>
            <p className="gate__sub">A fire calendar with a third eye.</p>
          </div>

          <section className="gate__modes" aria-labelledby="gate-choose">
            {/* the idle wobble lives on the inner span so the entrance tween can move the heading itself */}
            <h2 className="gate__choose" id="gate-choose">
              <span className="gate__prompt">
                <i className="gate__pip" aria-hidden="true" />
                Choose your mode
                <i className="gate__pip" aria-hidden="true" />
              </span>
            </h2>
            <ul className="modes">
              {MODES.map((m) => {
                const Preview = PREVIEW[m.key]
                const body = (
                  <>
                    <Preview />
                    <span className="mode__body">
                      <span className="mode__head">
                        <kbd className="mode__key" aria-hidden="true">{m.hotkey}</kbd>
                        <span className="mode__name">{m.name}</span>
                        {m.state && <span className="mode__state">{m.state}</span>}
                      </span>
                      <span className="mode__what">{m.what}</span>
                      <span className="mode__go">{m.action} <span aria-hidden="true">→</span></span>
                    </span>
                  </>
                )
                return (
                  <li key={m.key}>
                    {m.key === 'story' ? (
                      <button type="button" className="mode mode--story" onClick={chooseStory} data-cursor="Choose" {...hover(m.key)}>{body}</button>
                    ) : (
                      <Link to={m.to} className="mode mode--soon" data-cursor="Preview" onClick={() => playSfx('mode')} {...hover(m.key)}>{body}</Link>
                    )}
                  </li>
                )
              })}
            </ul>
          </section>
        </main>
      )}

      {chosen && (
        <>
          <div className="dock" role="group" aria-label="Story Mode">
            <button type="button" className="dock__back" onClick={backToModes} data-cursor="Modes"><span aria-hidden="true">←</span> All modes</button>
            <Link to="/story" className="dock__play" data-cursor="Watch">
              <span className="dock__tri" aria-hidden="true" />
              Watch the introduction
            </Link>
          </div>

          <main className="landing__track">
            <section className="hero" aria-label="Introduction">
              <p className="hero__kicker">Story Mode. NASA Space Apps 2026.</p>
              <h1 className="hero__title notranslate" translate="no">The Third Eye</h1>
              <p className="hero__sub">A fire calendar with a third eye.</p>
              <p className="hero__cue"><span /> Scroll to read, or watch the introduction now</p>
            </section>

            <section className="chapter chapter--left">
              <p className="chapter__meta"><i className="sw sw--modis" /> MODIS on Aqua, since 2002 <i className="sw sw--viirs" /> <span>VIIRS on <Name>Suomi NPP</Name>, 2012 to 2026</span></p>
              <h2 className="chapter__head"><Animated text="For twenty years, two satellite eyes have watched the Earth burn." /></h2>
              <p className="chapter__body">The older eye sees the ground in coarse kilometre squares. The younger one, from 2012, catches smaller fires the first one misses.</p>
            </section>

            <section className="chapter chapter--right">
              <p className="chapter__meta">The seam, 2012</p>
              <h2 className="chapter__head"><Animated text="In 2012 the record jumps. Not all of that jump is fire." /></h2>
              <p className="chapter__body">Join the two records end to end and a change of eye looks like a change in burning. Most fire charts never tell you which is which.</p>
            </section>

            <section className="chapter chapter--left chapter--eye">
              <p className="chapter__meta">The third eye</p>
              <h2 className="chapter__head"><Animated text="The third eye looks at the seam itself." /></h2>
              <p className="chapter__body">It tests every comparison against the change of satellite, counts only what was actually seen, and tells you when it cannot tell.</p>
            </section>

            <section className="finale" aria-label="Start the story">
              <p className="finale__meta">Story Mode</p>
              <h2 className="finale__head">Now see it for yourself.</h2>
              <div className="finale__actions">
                <Link to="/story" className="finale__play" data-cursor="Watch">
                  <span className="dock__tri" aria-hidden="true" />
                  Watch the introduction
                </Link>
                <Link to="/story/third-eye" className="finale__skip" data-cursor="Skip" onClick={() => playSfx('skip')}>Skip to the story</Link>
              </div>
              <p className="finale__others">
                Other modes: <Link to="/lab" onClick={() => playSfx('mode')}>Research Lab</Link> (preliminary real data for California and British Columbia) and <Link to="/mission" onClick={() => playSfx('mode')}>Quick Mission</Link> (being built). <button type="button" onClick={backToModes}>See all modes</button>
              </p>
              <aside className="headline">
                <span className="headline__mark" aria-hidden="true" />
                <HeadlineStatus className="headline__text" />
              </aside>
              <p className="credits">{DATA_CREDITS}</p>
              <section className="credits credits--si" aria-labelledby="si-title">
                <h3 id="si-title">Use of Super Intelligence (SI)</h3>
                <ul>{SI_USE.map((u) => <li key={u.what}><b>{u.what}:</b> {u.how}</li>)}</ul>
                <p>{NASA_BRANDING_RULE}</p>
              </section>
            </section>
          </main>
        </>
      )}
    </div>
  )
}
