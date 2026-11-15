/* Menu music for the landing page: the mode screen and the Story scroll page.
   Source: menu_sfx.mp3 at the repository root (192 kbps, 4 MB), re-encoded to 96 kbps
   (public/audio/menu_music.mp3, 1.9 MB) so the static site stays inside its size budget.
   Browsers block sound before the first click or key press, so the music starts on the first
   gesture on the page and never before it. It follows the same "Sound off" setting as the narrator
   and the interface effects (localStorage 'the-third-eye-sound' === 'off'). It is fetched only when
   it starts, so it does not compete with the Earth maps while the page loads.
   On the scroll page the volume swells a little while the reader scrolls and settles when they stop. */

const SRC = '/audio/menu_music.mp3'
const KEY = 'the-third-eye-sound'
const BASE = 0.3
const SWELL = 0.16

let audio: HTMLAudioElement | null = null
let wanted = false
let level = 0
let target = 0
let swell = 0
let raf = 0

export function soundOn() {
  return typeof localStorage === 'undefined' || localStorage.getItem(KEY) !== 'off'
}

function el() {
  if (!audio && typeof Audio !== 'undefined') {
    audio = new Audio(SRC)
    audio.loop = true
    audio.preload = 'auto'
    audio.volume = 0
  }
  return audio
}

/** Ease the volume toward its target; pause once fully faded out. */
function tick() {
  raf = 0
  const a = audio
  if (!a) return
  swell *= 0.94
  const goal = Math.min(1, target + swell)
  level += (goal - level) * 0.06
  if (Math.abs(goal - level) < 0.002) level = goal
  a.volume = Math.max(0, Math.min(1, level))
  if (target === 0 && level <= 0.002) { a.pause(); return }
  if (level !== goal || swell > 0.002) raf = requestAnimationFrame(tick)
}
function kick() { if (!raf && typeof requestAnimationFrame !== 'undefined') raf = requestAnimationFrame(tick) }

/** Start (or resume) the music with a fade in. Call from a user gesture. */
export function startMenuMusic() {
  wanted = true
  if (!soundOn()) return
  const a = el()
  if (!a) return
  target = BASE
  if (a.paused) void a.play().catch(() => { /* blocked until a real gesture; the next one retries */ })
  kick()
}

/** Fade the music out, for example when the reader leaves the landing page. */
export function stopMenuMusic() {
  wanted = false
  target = 0
  swell = 0
  kick()
}

/** Scrolling swells the music; speed is the scroll velocity in pixels per frame. */
export function menuMusicScroll(speed: number) {
  if (!wanted || !audio || audio.paused) return
  swell = Math.max(swell, Math.min(SWELL, Math.abs(speed) / 60 * SWELL))
  kick()
}

/** Follow the shared "Sound on/off" setting. */
export function setMenuSound(on: boolean) {
  localStorage.setItem(KEY, on ? 'on' : 'off')
  if (on) { if (wanted) startMenuMusic() } else { target = 0; swell = 0; kick() }
}

if (typeof document !== 'undefined') {
  // pause in a background tab, resume where it was when the reader comes back
  document.addEventListener('visibilitychange', () => {
    if (!audio) return
    if (document.hidden) audio.pause()
    else if (wanted && soundOn()) void audio.play().catch(() => {})
  })
}
