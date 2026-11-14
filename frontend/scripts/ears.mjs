// Measures the real left and right loudness of the intro's sound while it plays from beat 2
// (MODIS) through beat 4 (both eyes). Prints one row per line: which line, left level, right level.
// Usage: node scripts/ears.mjs
import { chromium } from 'playwright'
import { createServer } from 'vite'

const server = await createServer({ server: { port: 5183, strictPort: false }, logLevel: 'error' })
await server.listen()
const base = server.resolvedUrls.local[0].replace(/\/$/, '')
const browser = await chromium.launch({ channel: 'chromium', args: ['--use-angle=d3d11', '--enable-gpu', '--ignore-gpu-blocklist', '--enable-unsafe-swiftshader', '--autoplay-policy=no-user-gesture-required'] })
const page = await browser.newPage({ viewport: { width: 1400, height: 860 } })
page.on('pageerror', (e) => console.log('pageerror', e.message))
await page.goto(base + '/story')
await page.waitForFunction(() => !!window.__introTl, null, { timeout: 60000 })
await page.mouse.click(700, 400) // a user gesture, so audio may start
await page.waitForTimeout(1500)

// tap the master output with a channel splitter and one analyser per ear
await page.evaluate(() => {
  const n = window.__narrator
  const ctx = n.ctx
  const split = ctx.createChannelSplitter(2)
  const L = ctx.createAnalyser(), R = ctx.createAnalyser()
  L.fftSize = R.fftSize = 2048
  n.master.connect(split)
  split.connect(L, 0); split.connect(R, 1)
  const rms = (a) => { const b = new Float32Array(a.fftSize); a.getFloatTimeDomainData(b); let s = 0; for (const v of b) s += v * v; return Math.sqrt(s / b.length) }
  window.__ears = { rms: () => [rms(L), rms(R)] }
})

// optionally mute music so only the voice is measured
const voiceOnly = process.argv.includes('--voice')
if (voiceOnly) await page.evaluate(() => { const n = window.__narrator; n.musicGain.gain.cancelScheduledValues(0); n.musicGain.gain.value = 0; n.musicGain.disconnect() })

await page.evaluate(() => { window.__introTl.seek(window.__introTl.labels.b2).play() })
const rows = new Map()
const t0 = Date.now()
while (Date.now() - t0 < 42000) {
  const s = await page.evaluate(() => {
    const n = window.__narrator
    const k = n.current && !n.current.paused ? n.current.src.split('/').pop().replace('.mp3', '') : '-'
    const [l, r] = window.__ears.rms()
    return { k, l, r, ctx: n.ctx.state, pan: n.voicePan.pan.value }
  })
  if (s.k === 'b3' && rows.has('b3') && rows.get('b3').n > 8) break
  const row = rows.get(s.k) ?? { l: 0, r: 0, n: 0, pan: s.pan, ctx: s.ctx }
  row.l += s.l; row.r += s.r; row.n++; row.pan = s.pan; row.ctx = s.ctx
  rows.set(s.k, row)
  await page.waitForTimeout(120)
}
console.log(voiceOnly ? 'voice only' : 'voice + music')
console.log('line   left    right   share-left  panner  ctx')
for (const [k, r] of rows) {
  const l = r.l / r.n, rr = r.r / r.n
  console.log(`${k.padEnd(6)} ${l.toFixed(4)}  ${rr.toFixed(4)}  ${(l / (l + rr || 1) * 100).toFixed(0).padStart(5)}%     ${r.pan.toFixed(2).padStart(5)}  ${r.ctx}`)
}
await browser.close()
await server.close()
