// Screenshots of the first screen (the mode gate) only, at a few viewport sizes.
// Usage: node scripts/gate.mjs [tag]
import { chromium } from 'playwright'
import { createServer } from 'vite'
import { mkdirSync } from 'node:fs'

const tag = process.argv[2] ? process.argv[2] + '-' : ''
const server = await createServer({ server: { port: 5181, strictPort: false }, logLevel: 'error' })
await server.listen()
const base = server.resolvedUrls.local[0].replace(/\/$/, '')
mkdirSync('shots', { recursive: true })

// channel 'chromium' runs the full browser in headless mode; the separate headless shell fails to start on this machine
const browser = await chromium.launch({ channel: 'chromium', args: ['--use-angle=d3d11', '--enable-gpu', '--ignore-gpu-blocklist', '--enable-unsafe-swiftshader'] })
const errors = []
const sizes = [
  [1600, 900, 'desk'],
  [1366, 768, 'laptop'],
  [1920, 1080, 'fhd'],
  [1024, 768, 'tablet'],
  [390, 844, 'mobile'],
]
let warmed = false
for (const [width, height, name] of sizes) {
  const mobile = width < 600
  const p = await browser.newPage({ viewport: { width, height }, isMobile: mobile, hasTouch: mobile, deviceScaleFactor: mobile ? 2 : 1 })
  p.on('pageerror', (e) => errors.push(`pageerror: ${e.message}`))
  p.on('console', (m) => { if (m.type() === 'error') errors.push(`${m.type()}: ${m.text().slice(0, 300)}`) })
  await p.goto(base + '/?arrival=0')
  await p.waitForTimeout(warmed ? 5000 : 14000)
  warmed = true
  await p.screenshot({ path: `shots/${tag}G-${name}.png` })
  if (name === 'desk') {
    await p.hover('.mode--story')
    await p.waitForTimeout(900)
    await p.screenshot({ path: `shots/${tag}G-${name}-hover.png` })
    await p.mouse.move(800, 20)
    await p.waitForTimeout(400)
    // a second frame of the prompt to check its idle motion
    await p.waitForTimeout(1300)
    await p.screenshot({ path: `shots/${tag}G-${name}-b.png`, clip: { x: 400, y: 200, width: 800, height: 300 } })
  }
  if (mobile) {
    await p.evaluate(() => { const g = document.querySelector('.gate'); if (g) g.scrollTop = g.scrollHeight })
    await p.waitForTimeout(600)
    await p.screenshot({ path: `shots/${tag}G-${name}-end.png` })
  }
  await p.close()
}
await browser.close()
await server.close()
console.log(errors.length ? [...new Set(errors)].join('\n') : 'no page errors')
