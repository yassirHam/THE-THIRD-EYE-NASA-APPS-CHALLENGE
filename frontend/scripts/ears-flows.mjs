// Real left/right loudness of the intro voice along the paths a visitor takes, with the browser's
// normal autoplay policy. Taps the narrator's master output; music is silenced so only the voice
// is measured. Usage: node scripts/ears-flows.mjs
import { chromium } from 'playwright'
import { createServer } from 'vite'

const server = await createServer({ server: { port: 5190, strictPort: false }, logLevel: 'error' })
await server.listen()
const base = server.resolvedUrls.local[0].replace(/\/$/, '')
const browser = await chromium.launch({ channel: 'chromium', args: ['--use-angle=d3d11', '--enable-gpu', '--ignore-gpu-blocklist', '--enable-unsafe-swiftshader'] })

const tap = (p) => p.evaluate(() => {
  const n = window.__narrator
  if (!n?.ctx || window.__ears) return !!window.__ears
  const ctx = n.ctx, split = ctx.createChannelSplitter(2), L = ctx.createAnalyser(), R = ctx.createAnalyser()
  L.fftSize = R.fftSize = 2048
  n.master.connect(split); split.connect(L, 0); split.connect(R, 1)
  n.musicGain.disconnect()
  const rms = (a) => { const b = new Float32Array(a.fftSize); a.getFloatTimeDomainData(b); let s = 0; for (const v of b) s += v * v; return Math.sqrt(s / b.length) }
  window.__ears = () => [rms(L), rms(R)]
  return true
})

/** Listen until `until` line has played a while; return per-line left share. */
async function listen(p, until, ms = 70000) {
  const rows = new Map(), t0 = Date.now()
  while (Date.now() - t0 < ms) {
    await tap(p)
    const s = await p.evaluate(() => {
      const n = window.__narrator, a = n?.current
      const k = a && !a.paused ? a.src.split('/').pop().replace('.mp3', '') : '-'
      const [l, r] = window.__ears ? window.__ears() : [0, 0]
      return { k, l, r, ctx: n?.ctx?.state, pan: n?.voicePan?.pan.value }
    })
    if (s.k !== '-' && s.l + s.r > 0.004) {
      const row = rows.get(s.k) ?? { l: 0, r: 0, n: 0, ctx: s.ctx, pan: s.pan }
      row.l += s.l; row.r += s.r; row.n++; row.ctx = s.ctx; row.pan = s.pan
      rows.set(s.k, row)
    }
    if (rows.get(until)?.n > 6) break
    await p.waitForTimeout(120)
  }
  return [...rows].map(([k, r]) => `${k}:${Math.round(r.l / (r.l + r.r) * 100)}%L(pan ${r.pan?.toFixed(2)})`).join('  ')
}
const verdict = (s) => {
  const share = Object.fromEntries(s.split('  ').map((x) => [x.split(':')[0], parseInt(x.split(':')[1])]))
  // Match the named eye; missing required speech is a failure, not a vacuous pass.
  const lOk = ['l1', 'l2', 'l3'].every((k) => k in share && share[k] >= 95)
  const rOk = ['r1', 'r2'].every((k) => k in share && share[k] <= 5)
  return lOk && rOk ? 'OK' : 'MONO/WRONG'
}

const flows = {
  // landing -> Story Mode card -> Watch the introduction, then let it play with no seeking
  async landing(p) {
    await p.goto(base + '/?arrival=0'); await p.waitForTimeout(7000)
    await p.click('.mode--story'); await p.waitForTimeout(2500)
    await p.click('.dock__play')
    await p.waitForFunction(() => !!window.__introTl, null, { timeout: 60000 })
    await p.evaluate(() => { window.__introTl.timeScale(3) }) // play the park faster, still in order
    await p.waitForFunction(() => window.__introTl.time() > window.__introTl.labels.b2 - 1, null, { timeout: 90000 })
    await p.evaluate(() => { window.__introTl.timeScale(1) })
    return listen(p, 'r2')
  },
  // straight to /story: sound is blocked until "Turn sound on" is clicked
  async direct(p) {
    await p.goto(base + '/story')
    await p.waitForFunction(() => !!window.__introTl, null, { timeout: 60000 })
    await p.waitForTimeout(3000)
    const blocked = await p.evaluate(() => window.__narrator.blocked)
    if (blocked) { await p.click('.intro__sound'); await p.waitForTimeout(500) } else await p.mouse.click(700, 300)
    await p.evaluate(() => { const t = window.__introTl; t.seek(t.labels.b2) })
    return `(blocked first: ${blocked}) ` + await listen(p, 'r2')
  },
  // pause, previous, next, M twice: the controls must not knock the voice back to the centre
  async controls(p) {
    await p.goto(base + '/story')
    await p.waitForFunction(() => !!window.__introTl, null, { timeout: 60000 })
    await p.mouse.click(700, 300); await p.waitForTimeout(800)
    await p.evaluate(() => { const t = window.__introTl; t.seek(t.labels.b2 + 4) })
    await p.waitForTimeout(1500)
    await p.keyboard.press('Space'); await p.waitForTimeout(600)
    await p.keyboard.press('Space'); await p.waitForTimeout(600)
    await p.keyboard.press('m'); await p.waitForTimeout(400)
    await p.keyboard.press('m'); await p.waitForTimeout(400)
    await p.getByRole('button', { name: 'Previous', exact: true }).click()
    await p.waitForTimeout(300)
    await p.getByRole('button', { name: 'Next', exact: true }).click() // to b3, VIIRS
    await p.waitForTimeout(300)
    await p.getByRole('button', { name: 'Previous', exact: true }).click() // back to b2, MODIS
    return listen(p, 'r2')
  },
  // leave the intro for a chapter, then "Replay intro" back into it
  async replay(p) {
    await p.goto(base + '/story')
    await p.waitForFunction(() => !!window.__introTl, null, { timeout: 60000 })
    await p.mouse.click(700, 300); await p.waitForTimeout(800)
    await p.keyboard.press('Escape')
    await p.waitForURL('**/story/third-eye'); await p.waitForTimeout(2500)
    await p.getByRole('link', { name: /replay intro/i }).first().click().catch(async () => { await p.getByRole('button', { name: /replay intro/i }).first().click() })
    await p.waitForFunction(() => !!window.__introTl && location.pathname === '/story', null, { timeout: 60000 })
    await p.waitForTimeout(1500)
    await p.evaluate(() => { const t = window.__introTl; t.seek(t.labels.b2) })
    return listen(p, 'r2')
  },
}

const only = process.argv[2]
for (const [name, run] of Object.entries(flows)) {
  if (only && name !== only) continue
  const p = await browser.newPage({ viewport: { width: 1440, height: 900 } })
  p.on('pageerror', (e) => console.log(`  [${name}] pageerror ${e.message}`))
  const out = await run(p).catch((e) => 'ERROR ' + e.message.split('\n')[0])
  console.log(`${name.padEnd(9)} ${out.startsWith('ERROR') ? out : verdict(out.replace(/^\(.*?\) /, '')) + '  ' + out}`)
  await p.close()
}
await browser.close()
await server.close()
