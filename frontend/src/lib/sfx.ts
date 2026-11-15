/* Short interface sound effects for clicks that change state: a wrong quiz answer, choosing or
   switching a mode, and skipping a step. One pooled HTMLAudioElement per effect, replayed from the
   start on each trigger. Silenced by the same "Sound off" toggle as the narrator
   (localStorage 'the-third-eye-sound' === 'off'). These fire on a click or key press, so the browser
   lets them play without the autoplay block the narrator has to work around.
   The files are MP3 encodes (about 40 KB each) of the WAV masters in frontend/source-audio/;
   the WAVs were 916 KB together and were downloaded on every first visit. */

const FILES = {
  wrong: '/audio/wrong_answers.mp3',
  mode: '/audio/mode_transition.mp3',
  skip: '/audio/skip_button.mp3',
} as const

export type Sfx = keyof typeof FILES

const KEY = 'the-third-eye-sound'
const LEVEL: Record<Sfx, number> = { wrong: 0.6, mode: 0.5, skip: 0.5 }

const pool = new Map<Sfx, HTMLAudioElement>()

function element(name: Sfx): HTMLAudioElement | null {
  let a = pool.get(name)
  if (!a && typeof Audio !== 'undefined') {
    a = new Audio(FILES[name])
    a.preload = 'auto'
    a.volume = LEVEL[name]
    pool.set(name, a)
  }
  return a ?? null
}

function muted(): boolean {
  return typeof localStorage !== 'undefined' && localStorage.getItem(KEY) === 'off'
}

/** Fetch the effects ahead of time so the first play has no lag. Safe to call more than once. */
export function preloadSfx() {
  for (const name of Object.keys(FILES) as Sfx[]) element(name)
}

/** Play a one-shot interface sound, unless sound is turned off. */
export function playSfx(name: Sfx) {
  if (muted()) return
  const a = element(name)
  if (!a) return
  try { a.currentTime = 0 } catch { /* not seekable until it has loaded; play from wherever it is */ }
  void a.play().catch(() => {}) // a click that lands as the page unloads can reject; nothing to do
}
