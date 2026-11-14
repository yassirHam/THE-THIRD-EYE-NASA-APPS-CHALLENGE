// Intro playback controls: Space, M, Previous, Next, and the phone layout. Usage: node scripts/controls.mjs
import { chromium } from 'playwright'
import { createServer } from 'vite'
const server = await createServer({ server: { port: 5186, strictPort: false }, logLevel: 'error' })
await server.listen()
const base = server.resolvedUrls.local[0].replace(/\/$/, '')
const b = await chromium.launch({ channel: 'chromium', args: ['--use-angle=d3d11', '--enable-gpu', '--ignore-gpu-blocklist', '--enable-unsafe-swiftshader', '--autoplay-policy=no-user-gesture-required'] })
const p = await b.newPage({ viewport: { width: 1440, height: 900 } })
const errors = []
p.on('pageerror', (e) => errors.push(e.message))
let ok = true
const check = (name, pass, extra = '') => { ok &&= pass; console.log(`${pass ? 'PASS' : 'FAIL'}  ${name}${extra ? '  ' + extra : ''}`) }
const T = () => p.evaluate(() => window.__introTl.time())
const L = (l) => p.evaluate((l) => window.__introTl.labels[l], l)
const paused = () => p.evaluate(() => window.__introTl.paused())

await p.goto(base + '/story')
await p.waitForFunction(() => !!window.__introTl, null, { timeout: 60000 })
await p.evaluate(() => localStorage.removeItem('the-third-eye-sound'))
await p.mouse.click(700, 300)
await p.waitForTimeout(1500)

// Space toggles pause and play
await p.keyboard.press('Space'); await p.waitForTimeout(200)
const t1 = await T(); await p.waitForTimeout(600); const t2 = await T()
check('Space pauses', (await paused()) && t1 === t2 && (await p.textContent('.intro__controls button:nth-child(2)')) === 'Play')
await p.keyboard.press('Space'); await p.waitForTimeout(600)
check('Space plays again', !(await paused()) && (await T()) > t2)

// Space while a control has focus toggles play, and does not press that control
await p.evaluate((t) => { window.__introTl.seek(t) }, await L('b2'))
await p.getByRole('button', { name: 'Next', exact: true }).focus()
const before = await T()
await p.keyboard.press('Space'); await p.waitForTimeout(300)
check('Space on a focused button pauses instead of pressing it', (await paused()) && (await T()) < (await L('b3')), `t ${before.toFixed(1)} -> ${(await T()).toFixed(1)}, b3 at ${(await L('b3')).toFixed(1)}`)
await p.keyboard.press('Space'); await p.waitForTimeout(200)

// M mutes and unmutes
await p.keyboard.press('m'); await p.waitForTimeout(250)
check('M turns sound off', await p.evaluate(() => window.__narrator.muted) && (await p.textContent('.intro__sound')).includes('Sound off'))
await p.keyboard.press('M'); await p.waitForTimeout(250)
check('M turns sound on again', !(await p.evaluate(() => window.__narrator.muted)) && (await p.textContent('.intro__sound')).includes('Sound on'))
check('Sound setting is saved', (await p.evaluate(() => localStorage.getItem('the-third-eye-sound'))) === 'on')

// Previous: deep in a beat goes to its start; right at the start goes to the beat before
const prev = () => p.getByRole('button', { name: 'Previous', exact: true }).click()
await p.evaluate((t) => { window.__introTl.seek(t) }, (await L('b3')) + 4)
await prev(); await p.waitForTimeout(150)
check('Previous goes to the start of this step', Math.abs((await T()) - (await L('b3'))) < 0.4, `${(await T()).toFixed(2)} vs b3 ${(await L('b3')).toFixed(2)}`)
await prev(); await p.waitForTimeout(150)
check('Previous again goes to the step before', Math.abs((await T()) - (await L('b2'))) < 0.4, `${(await T()).toFixed(2)} vs b2 ${(await L('b2')).toFixed(2)}`)
await p.waitForFunction(() => window.__narrator.current?.src.endsWith('/l1.mp3'), null, { timeout: 8000 }).catch(() => {})
check('Narration restarts with that step', await p.evaluate(() => window.__narrator.current?.src.endsWith('/l1.mp3')))
check('Earlier lines are untyped again after going back', await p.evaluate(() => getComputedStyle(document.querySelector('.intro__line[data-k="r2"] .ch')).opacity === '0'))
await p.evaluate((t) => { window.__introTl.seek(t) }, (await L('b1')) + 0.5)
await prev(); await p.waitForTimeout(150)
check('Previous from the first step goes to the very start', (await T()) < 0.4, (await T()).toFixed(2))
// Next still works
await p.getByRole('button', { name: 'Next', exact: true }).click(); await p.waitForTimeout(150)
check('Next goes to the next step', Math.abs((await T()) - (await L('b1'))) < 0.4)

// at the end: Previous brings back the controls and plays the last step again
await p.evaluate(() => { window.__introTl.progress(1) })
await p.waitForTimeout(500)
check('End screen hides Skip intro', !(await p.getByRole('button', { name: /Skip intro/ }).isVisible().catch(() => false)))
await prev(); await p.waitForTimeout(600)
check('Previous at the end returns to the last step and plays', Math.abs((await T()) - (await L('b5'))) < 1.2 && !(await paused()) && (await p.getByRole('button', { name: /Skip intro/ }).isVisible()), (await T()).toFixed(2))

// Space on "Begin the story" at the end still begins it
await p.evaluate(() => { window.__introTl.progress(1) })
await p.waitForTimeout(600)
await p.focus('.intro__begin')
await p.keyboard.press('Space')
await p.waitForURL('**/story/third-eye', { timeout: 4000 }).catch(() => {})
check('Space on Begin the story opens the story', p.url().endsWith('/story/third-eye'))

// mobile: the extra button still fits on one row, on common phone widths
for (const w of [390, 360]) {
await p.setViewportSize({ width: w, height: 800 })
await p.goto(base + '/story')
await p.waitForFunction(() => !!window.__introTl, null, { timeout: 60000 })
await p.waitForTimeout(800)
const bar = await p.evaluate(() => { const r = document.querySelector('.intro__controls').getBoundingClientRect(); const bs = [...document.querySelectorAll('.intro__controls button')].map((b) => b.getBoundingClientRect()); return { l: r.left, r: r.right, rows: new Set(bs.map((b) => Math.round((b.top + b.height / 2) / 8))).size, h: Math.round(Math.max(...bs.map((b) => b.height))) } })
check(`Phone controls fit on one line at ${w}px`, bar.rows === 1 && bar.h < 40 && bar.l >= 0 && bar.r <= w, JSON.stringify(bar))
await p.screenshot({ path: `shots/controls-mobile-${w}.png` })
}
await b.close(); await server.close()
console.log(errors.length ? errors.join('\n') : 'no page errors')
process.exit(ok ? 0 : 1)
