// Measure real decoded MP3 output per channel, including pause and mute recovery.
// No GPU scene needed. Run: node scripts/audio-routing.mjs
import assert from 'node:assert/strict'
import { chromium } from 'playwright'
import { createServer } from 'vite'

const server = await createServer({ server: { port: 5196, strictPort: false }, logLevel: 'error' })
await server.listen()
const browser = await chromium.launch({ channel: 'chromium' })
try {
  const page = await browser.newPage()
  const errors = []
  page.on('pageerror', e => errors.push(e.message))
  const base = server.resolvedUrls.local[0]
  await page.route(base + 'audio-test', route => route.fulfill({ contentType: 'text/html', body: '<button>Enable audio</button>' }))
  await page.goto(base + 'audio-test')
  await page.evaluate(async () => {
    const { narrator: n } = await import('/src/story/narrator.ts')
    n.preload()
    document.querySelector('button').onclick = () => { n.setMuted(false); n.say('p1') }
    const split = n.ctx.createChannelSplitter(2)
    const left = n.ctx.createAnalyser(), right = n.ctx.createAnalyser()
    left.fftSize = right.fftSize = 2048
    n.master.connect(split); split.connect(left, 0); split.connect(right, 1)
    const rms = node => {
      const buffer = new Float32Array(node.fftSize)
      node.getFloatTimeDomainData(buffer)
      return Math.sqrt(buffer.reduce((sum, v) => sum + v * v, 0) / buffer.length)
    }
    window.readEars = () => [rms(left), rms(right)]
  })
  await page.getByRole('button').click()
  await page.waitForFunction(() => window.__narrator.ctx.state === 'running')
  await page.waitForFunction(() => window.__narrator.current?.currentTime > .15)
  const measure = async (key, action = 'say') => {
    const result = await page.evaluate(async ({ key, action }) => {
      const n = window.__narrator
      n.say(key)
      await new Promise(resolve => setTimeout(resolve, 200))
      if (action === 'pause') { n.pause(); await new Promise(resolve => setTimeout(resolve, 80)); n.resume() }
      if (action === 'mute') { n.setMuted(true); await new Promise(resolve => setTimeout(resolve, 250)); n.setMuted(false); n.replay() }
      let l = 0, r = 0, count = 0
      for (let i = 0; i < 30; i++) {
        await new Promise(resolve => setTimeout(resolve, 20))
        const [a, b] = window.readEars()
        if (a + b > .002) { l += a; r += b; count++ }
      }
      return { l, r, count, pan: n.voicePan.pan.value, state: n.ctx.state, time: n.current?.currentTime, ready: n.current?.readyState, muted: n.muted, blocked: n.blocked, gain: n.master.gain.value }
    }, { key, action })
    assert.ok(result.count > 3, `${key}: must actually produce audible samples ${JSON.stringify(result)}`)
    const share = result.l / (result.l + result.r)
    const expected = key.startsWith('l') ? 1 : key.startsWith('r') ? 0 : .5
    assert.ok(Math.abs(share - expected) < .02, `${key}/${action}: wrong output ${Math.round(share * 100)}% left`)
    console.log(`PASS ${key}/${action}: ${(share * 100).toFixed(1)}% left, ${((1 - share) * 100).toFixed(1)}% right`)
  }
  for (const key of ['l1', 'l2', 'l3', 'r1', 'r2', 'r3', 'b1', 'b2', 'b3', 'p1', 't1', 'title']) await measure(key)
  await measure('l2', 'pause')
  await measure('r2', 'mute')
  await measure('b1')
  assert.deepEqual(errors, [])
} finally { await browser.close(); await server.close() }
