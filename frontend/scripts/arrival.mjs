// Visual check of the first-visit opening film. A fresh browser context has nothing in
// localStorage, like a first visit. Textures are delayed to imitate a cold cache.
// Usage: node scripts/arrival.mjs [tag] [width] [height] [delayMs]
import { chromium } from 'playwright'
import { createServer } from 'vite'
import { mkdirSync } from 'node:fs'

const tag = process.argv[2] ?? 'arr'
const width = Number(process.argv[3] ?? 1600)
const height = Number(process.argv[4] ?? 900)
const delay = Number(process.argv[5] ?? 4000)
const server = await createServer({ server: { port: 5183, strictPort: false }, logLevel: 'error' })
await server.listen()
const base = server.resolvedUrls.local[0].replace(/\/$/, '')
mkdirSync('shots', { recursive: true })

const browser = await chromium.launch({ args: ['--use-angle=d3d11', '--enable-gpu', '--ignore-gpu-blocklist', '--enable-unsafe-swiftshader'] })
const errors = []
// warm-up so Vite's dependency optimisation does not reload the page mid-film
const warm = await browser.newPage()
await warm.goto(base + '/?arrival=0')
await warm.waitForTimeout(5000)
await warm.close()

const ctx = await browser.newContext({ viewport: { width, height }, deviceScaleFactor: width < 600 ? 2 : 1 })
const p = await ctx.newPage()
p.on('pageerror', (e) => errors.push(`pageerror: ${e.message}`))
p.on('console', (m) => { if (m.type() === 'error' || m.type() === 'warning') errors.push(`${m.type()}: ${m.text().slice(0, 300)}`) })
await p.route(/\/tex\/.*\.(jpe?g|png)$/, async (r) => { await new Promise((ok) => setTimeout(ok, delay)); await r.continue() })
await p.goto(base + '/')
await p.waitForFunction(() => !!window.__arrival, null, { timeout: 30000 })
const marks = [0.6, 1.3, 2.0, 2.7, 3.1, 3.5, 4.2, 5.0, 5.6, 6.3, 7.2, 8.2, 9.2]
const timing = []
for (const m of marks) {
  await p.evaluate((v) => { window.__arrival.stopAt = v }, m)
  await p.waitForFunction((v) => window.__arrival.t >= v - 0.05, m, { timeout: 60000, polling: 16 })
  await p.waitForTimeout(250)
  const t = await p.evaluate(() => window.__arrival.t.toFixed(2))
  await p.screenshot({ path: `shots/${tag}-${String(m).replace('.', '_')}s.png` })
  timing.push(`${m}:${t}`)
}
console.log('frames', timing.join(' '))
await p.evaluate(() => { window.__arrival.stopAt = Infinity })
await p.waitForTimeout(700)
const hold = await p.evaluate(() => ({ t: window.__arrival.t.toFixed(2), loaded: window.__arrival.loaded, skip: document.querySelector('.arrival__skip')?.textContent }))
console.log('after last mark', JSON.stringify(hold))
await p.screenshot({ path: `shots/${tag}-hold.png` })
// hand-off and the page underneath
await p.waitForTimeout(800)
await p.screenshot({ path: `shots/${tag}-handoff.png` })
await p.waitForFunction(() => !document.querySelector('.arrival'), null, { timeout: 30000 })
await p.waitForTimeout(2500)
await p.screenshot({ path: `shots/${tag}-after.png` })
const stored = await p.evaluate(() => localStorage.getItem('the-third-eye.arrival'))
await p.reload()
await p.waitForTimeout(1500)
const again = await p.evaluate(() => ({ film: !!document.querySelector('.arrival'), loader: !!document.querySelector('.loader') }))
console.log('stored', stored, 'second visit', JSON.stringify(again))
await browser.close()
await server.close()
console.log(errors.length ? [...new Set(errors)].join('\n') : 'no page errors')
