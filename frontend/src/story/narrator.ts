import narration from './narration.json'
import music from './music.json'

/* The intro's sound: one short MP3 per subtitle line, made offline by scripts/narrate.py with
   a local synthetic voice, over a music loop synthesized by scripts/compose.py. The timeline
   asks for a line when its subtitle starts typing; pause, resume and skip follow the timeline.

   Both go through one Web Audio graph so they can be placed in space:
     voice lines -> voicePan -> master -> speakers
     music loop  -> musicGain -> musicPan -> master
   Match the eye NAMED by the narration, not the eye that remains open:
   "close your left eye" / MODIS -> left ear; "close your right eye" / VIIRS -> right ear.
   Both-eyes and other lines are centered. Music leans the same way, by half. */

export const LINE_SECONDS: Record<string, number> = narration.lines
const KEY = 'the-third-eye-sound'

const MUSIC_LEVEL = 0.34
const MUSIC_DUCKED = 0.17 // under the voice
const MUSIC_LEAN = 0.5 // share of the voice's pan the music follows

/** Voice follows the spoken eye instruction, independently of the visual panel position. */
export function panFor(k: string): number {
  if (/^l\d$/.test(k)) return -1
  if (/^r\d$/.test(k)) return 1
  return 0
}

type Listener = (s: { muted: boolean; blocked: boolean }) => void
type Ctx = typeof AudioContext

class Narrator {
  private audio = new Map<string, HTMLAudioElement>()
  private current: HTMLAudioElement | null = null
  private listeners = new Set<Listener>()
  private ctx: AudioContext | null = null
  private master: GainNode | null = null
  private voicePan: StereoPannerNode | null = null
  private musicGain: GainNode | null = null
  private musicPan: StereoPannerNode | null = null
  private musicBuffer: AudioBuffer | null = null
  private musicSource: AudioBufferSourceNode | null = null
  private wantMusic = false
  muted = typeof localStorage !== 'undefined' && localStorage.getItem(KEY) === 'off'
  /** true when the browser refused to play sound before the visitor interacted with the page */
  blocked = false
  /** where the voice is placed now, -1 left to 1 right (read by the behaviour checks) */
  pan = 0

  preload() {
    if (this.audio.size || typeof Audio === 'undefined') return
    this.graph()
    for (const k of Object.keys(LINE_SECONDS)) {
      const a = new Audio(`/audio/intro/${k}.mp3`)
      a.preload = 'auto'
      a.addEventListener('ended', () => { if (a === this.current) this.duck(false) })
      if (this.ctx && this.voicePan) this.ctx.createMediaElementSource(a).connect(this.voicePan)
      this.audio.set(k, a)
    }
    if (this.ctx) {
      fetch(music.file)
        .then((r) => r.arrayBuffer())
        .then((b) => this.ctx!.decodeAudioData(b))
        .then((buf) => { this.musicBuffer = buf; if (this.wantMusic) this.startMusic() })
        .catch(() => {}) // music is optional; the voice still works without it
    }
  }

  /** Build the Web Audio graph. Without Web Audio the lines play straight from their elements. */
  private graph() {
    const AC: Ctx | undefined = window.AudioContext ?? (window as unknown as { webkitAudioContext?: Ctx }).webkitAudioContext
    if (!AC || this.ctx) return
    const ctx = new AC()
    this.ctx = ctx
    this.master = ctx.createGain()
    this.master.gain.value = this.muted ? 0 : 1
    this.master.connect(ctx.destination)
    this.voicePan = ctx.createStereoPanner()
    this.voicePan.connect(this.master)
    this.musicPan = ctx.createStereoPanner()
    this.musicPan.connect(this.master)
    this.musicGain = ctx.createGain()
    this.musicGain.gain.value = 0
    this.musicGain.connect(this.musicPan)
  }

  private glide(p: AudioParam | undefined, to: number, seconds: number) {
    if (!p || !this.ctx) return
    const now = this.ctx.currentTime
    p.cancelScheduledValues(now)
    p.setValueAtTime(p.value, now)
    p.linearRampToValueAtTime(to, now + seconds)
  }

  private duck(on: boolean) {
    if (!this.musicSource) return
    this.glide(this.musicGain?.gain, on ? MUSIC_DUCKED : MUSIC_LEVEL, on ? 0.35 : 1.4)
  }

  /** Try to start sound. Resolves to false if the browser still holds it back. */
  private unlock(a: HTMLAudioElement | null) {
    const ctx = this.ctx
    const resumed = ctx && ctx.state !== 'running'
      ? Promise.race([ctx.resume(), new Promise((r) => setTimeout(r, 600))])
      : Promise.resolve()
    // only a refusal counts as blocked; a play() cut short by Next or Pause is not
    const played = a ? a.play().then(() => true, (e: DOMException) => e?.name !== 'NotAllowedError') : Promise.resolve(true)
    return Promise.all([played, resumed])
      .then(([ok]) => ok && (!ctx || ctx.state === 'running'))
      .then((ok) => { this.set({ blocked: !ok }); return ok })
  }

  say(k: string) {
    this.stop()
    const a = this.audio.get(k)
    if (!a) return
    this.current = a
    this.pan = panFor(k)
    // The previous clip has stopped. Route before play(), so even the first
    // syllable is in the correct ear (and both-eyes speech starts centered).
    if (this.voicePan && this.ctx) {
      const now = this.ctx.currentTime
      this.voicePan.pan.cancelScheduledValues(now)
      this.voicePan.pan.setValueAtTime(this.pan, now)
    }
    this.glide(this.musicPan?.pan, this.pan * MUSIC_LEAN, 0.9)
    if (this.muted) return
    a.currentTime = 0
    this.duck(true)
    void this.unlock(a)
  }

  /** The music loop starts with the intro and runs until the intro is left. */
  startMusic() {
    this.wantMusic = true
    const ctx = this.ctx
    if (!ctx || !this.musicBuffer || !this.musicGain || this.musicSource) return
    const src = ctx.createBufferSource()
    src.buffer = this.musicBuffer
    src.loop = true
    // some decoders keep the encoder's lead-in silence; loop the exact composed length after it
    const data = this.musicBuffer.getChannelData(0)
    let lead = 0
    while (lead < data.length && Math.abs(data[lead]) < 1e-4) lead++
    const start = lead / this.musicBuffer.sampleRate
    src.loopStart = start
    src.loopEnd = Math.min(this.musicBuffer.duration, start + music.loopSeconds)
    src.connect(this.musicGain)
    src.start(0, start)
    this.musicSource = src
    // a slow fade in, so the music arrives with the dark screen rather than on top of it
    const g = this.musicGain.gain
    const now = ctx.currentTime
    g.cancelScheduledValues(now)
    g.setValueAtTime(0, now)
    g.linearRampToValueAtTime(this.current && !this.current.paused ? MUSIC_DUCKED : MUSIC_LEVEL, now + 4)
    if (!this.muted) void this.unlock(null)
  }

  stopMusic() {
    this.wantMusic = false
    const src = this.musicSource
    if (!src || !this.ctx) return
    this.musicSource = null
    this.glide(this.musicGain?.gain, 0, 0.5)
    src.stop(this.ctx.currentTime + 0.55)
  }

  get musicPlaying() { return !!this.musicSource && this.ctx?.state === 'running' }

  pause() {
    this.current?.pause()
    void this.ctx?.suspend()
  }

  resume() {
    if (this.muted) return
    const a = this.current
    void this.unlock(a && a.currentTime > 0 && !a.ended ? a : null)
  }

  /** Play the current line from its start, e.g. after sound was turned on mid-line. */
  replay() {
    const a = this.current
    if (this.muted) return
    if (a) { a.currentTime = 0; this.duck(true) }
    void this.unlock(a)
  }

  stop() {
    this.duck(false)
    if (!this.current) return
    this.current.pause()
    this.current.currentTime = 0
    this.current = null
  }

  setMuted(m: boolean) {
    localStorage.setItem(KEY, m ? 'off' : 'on')
    this.set({ muted: m, blocked: false })
    this.glide(this.master?.gain, m ? 0 : 1, 0.2)
    if (m) this.current?.pause()
  }

  subscribe(fn: Listener) {
    this.listeners.add(fn)
    return () => { this.listeners.delete(fn) }
  }

  private set(s: Partial<{ muted: boolean; blocked: boolean }>) {
    Object.assign(this, s)
    this.listeners.forEach((fn) => fn({ muted: this.muted, blocked: this.blocked }))
  }
}

export const narrator = new Narrator()
if (import.meta.env.DEV) (window as unknown as { __narrator: Narrator }).__narrator = narrator
