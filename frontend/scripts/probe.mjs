// Debug helper: open the intro and report whether the dev timeline handle exists.
import { chromium } from 'playwright'
import { createServer } from 'vite'

const server = await createServer({ server: { port: 5181 }, logLevel: 'error' })
await server.listen()
const base = server.resolvedUrls.local[0].replace(/\/$/, '')
const browser = await chromium.launch({ args: ['--use-angle=d3d11', '--enable-gpu', '--ignore-gpu-blocklist'] })
const p = await browser.newPage({ viewport: { width: 1600, height: 900 } })
p.on('console', (m) => console.log('console', m.type(), m.text().slice(0, 200)))
p.on('pageerror', (e) => console.log('pageerror', e.message))
await p.goto(base + '/story')
for (let i = 0; i < 4; i++) {
  await p.waitForTimeout(5000)
  console.log(i, await p.evaluate(() => ({ tl: typeof window.__introTl, loader: !!document.querySelector('.loader'), url: location.href })))
}
await browser.close()
await server.close()
