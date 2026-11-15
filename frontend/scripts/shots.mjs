// Visual check of the WebGL site. Starts its own Vite server, renders with the GPU
// (falls back to SwiftShader), and saves screenshots to ./shots.
// Usage: node scripts/shots.mjs [landing|intro|story|mobile|all] [tag]
import { chromium } from 'playwright'
import { createServer } from 'vite'
import { mkdirSync } from 'node:fs'

const which = process.argv[2] ?? 'all'
const server = await createServer({ server: { port: 5179, strictPort: false }, logLevel: 'error' })
await server.listen()
const base = server.resolvedUrls.local[0].replace(/\/$/, '')
const out = 'shots'
const tag = process.argv[3] ? process.argv[3] + '-' : ''
mkdirSync(out, { recursive: true })

const browser = await chromium.launch({ args: ['--use-angle=d3d11', '--enable-gpu', '--ignore-gpu-blocklist', '--enable-unsafe-swiftshader'] })
const errors = []
const page = async (viewport) => {
  const p = await browser.newPage({ viewport })
  p.on('pageerror', (e) => errors.push(`pageerror: ${e.message}`))
  p.on('console', (m) => { if (m.type() === 'error' || m.type() === 'warning') errors.push(`${m.type()}: ${m.text().slice(0, 300)}`) })
  return p
}
const desk = await page({ width: 1600, height: 900 })
// warm-up: Vite optimizes dependencies on first visit and may reload
await desk.goto(base + '/')
await desk.waitForTimeout(6000)

if (which === 'previews') {
  // clean frames for the Story Mode card on the first screen: interface hidden, small JPEGs.
  // These are the masters; the site ships WebP encodes of them (quality 0.82) in public/previews/.
  mkdirSync('source-textures/previews', { recursive: true })
  const pv = await page({ width: 960, height: 540 })
  const hideUi = () => pv.addStyleTag({ content: '.intro__panel, .intro__controls, .intro__eyes, .cursor-ring, .cursor-dot, .story__overlay, .objective { display: none !important; }' })
  await pv.goto(base + '/story')
  await pv.waitForFunction(() => !!window.__introTl, null, { timeout: 60000, polling: 500 })
  await hideUi()
  for (const [l, o, name] of [['b1', 2.4, 'story-1-park'], ['b2', -1.0, 'story-2-finger'], ['b5', 6, 'story-4-third-eye']]) {
    await pv.evaluate(([l, o]) => { const t = window.__introTl; t.pause(); t.seek(t.labels[l] + o) }, [l, o])
    await pv.waitForTimeout(2200)
    await pv.screenshot({ path: `source-textures/previews/${name}.jpg`, type: 'jpeg', quality: 78 })
  }
  await pv.setViewportSize({ width: 1500, height: 760 })
  await pv.goto(base + '/story/two-eyes')
  await pv.waitForTimeout(3000)
  await hideUi()
  await pv.keyboard.press('1')
  await pv.waitForTimeout(2600)
  const box = await pv.locator('.story__art').boundingBox()
  const w = Math.min(box.width, box.height * 16 / 9), h = w * 9 / 16
  await pv.screenshot({ path: 'source-textures/previews/story-3-two-eyes.jpg', type: 'jpeg', quality: 78, clip: { x: box.x + (box.width - w) / 2, y: box.y + (box.height - h) / 2, width: w, height: h } })
  await pv.close()
}

if (which === 'all' || which === 'landing' || which === 'loader') {
  // loader: delay only the textures, so the page runs but progress stays visible
  const lp = await page({ width: 1600, height: 900 })
  await lp.route(/\.(jpe?g|png|webp|ktx2|hdr)(\?.*)?$/, async (r) => { await new Promise((ok) => setTimeout(ok, 900 + Math.random() * 2600)); await r.continue() })
  lp.goto(base + '/').catch(() => {})
  for (const [wait, name] of [[1200, 'P0-loader-a'], [1300, 'P1-loader-b'], [2200, 'P2-loader-c'], [1400, 'P3-loader-open']]) {
    await lp.waitForTimeout(wait)
    await lp.screenshot({ path: `${out}/${tag}${name}.png` })
  }
  await lp.close()
}

if (which === 'all' || which === 'landing') {
  await desk.goto(base + '/')
  await desk.waitForTimeout(5000)
  await desk.screenshot({ path: `${out}/${tag}L0-gate.png` })
  // the eye follows the cursor: look toward the lower left, then the upper right
  await desk.mouse.move(120, 860, { steps: 8 })
  await desk.waitForTimeout(1500)
  await desk.screenshot({ path: `${out}/${tag}L0d-gaze-low-left.png`, clip: { x: 900, y: 40, width: 480, height: 440 } })
  await desk.mouse.move(1560, 60, { steps: 8 })
  await desk.waitForTimeout(1500)
  await desk.screenshot({ path: `${out}/${tag}L0e-gaze-up-right.png`, clip: { x: 900, y: 40, width: 480, height: 440 } })
  await desk.hover('.mode--story')
  await desk.waitForTimeout(900)
  await desk.screenshot({ path: `${out}/${tag}L0b-gate-hover.png` })
  await desk.click('.mode--story')
  await desk.waitForTimeout(3500)
  await desk.screenshot({ path: `${out}/${tag}L0c-hero.png` })
  const h = await desk.evaluate(() => document.documentElement.scrollHeight - innerHeight)
  // centre each chapter in the viewport, then the bottom for the closing section
  const ys = await desk.evaluate(() => [...document.querySelectorAll('.chapter')].map((el) => el.offsetTop + el.offsetHeight / 2 - innerHeight / 2))
  for (const [y, name] of [[ys[0], 'L1-eyes'], [ys[1], 'L2-seam'], [ys[2], 'L3-third'], [h, 'L4-finale']]) {
    await desk.evaluate((v) => window.scrollTo(0, v), Math.round(y))
    await desk.waitForTimeout(3500)
    await desk.screenshot({ path: `${out}/${tag}${name}.png` })
  }
}

if (which === 'all' || which === 'intro') {
  await desk.goto(base + '/story')
  await desk.waitForFunction(() => !!window.__introTl, null, { timeout: 60000, polling: 500 })
  await desk.waitForTimeout(1500)
  for (const [label, off, name] of [['b1', -2.2, 'I0-phones'], ['b1', 1.4, 'I1-kid'], ['b1', 4, 'I1b-raised'], ['pov', 1.6, 'I1c-move'], ['pov', 3.4, 'I1d-pov'], ['hops', 0.62, 'I2a-left'], ['hops', 1.04, 'I2b-squint'], ['hops', 1.3, 'I2c-right'], ['b2', 5, 'I3-left'], ['b3', 5, 'I4-right'], ['b4', 6, 'I5-both'], ['b5', 6, 'I6-third'], [null, 0, 'I7-title']]) {
    await desk.evaluate(([l, o]) => {
      const t = window.__introTl
      t.pause()
      t.seek(l === null ? t.duration() : t.labels[l] + o)
    }, [label, off])
    await desk.waitForTimeout(1800)
    await desk.screenshot({ path: `${out}/${tag}${name}.png` })
  }
}

if (which === 'all' || which === 'story') {
  // [chapter, keys pressed in order, file name]; answers that lead into parallel universes are included
  const runs = [
    ['third-eye', '', 'third-eye'], ['two-eyes', '', 'two-eyes-ground'], ['two-eyes', '1', 'two-eyes-modis'],
    ['two-eyes', '11', 'two-eyes-question'], ['two-eyes', '111', 'two-eyes-u-modis'], ['two-eyes', '113', 'two-eyes-both'],
    ['clouds', '', 'clouds-question'], ['clouds', '1', 'clouds-u-zero'], ['clouds', '11', 'clouds-returned'],
    ['seam', '', 'seam-stitched'], ['seam', '1', 'seam-u-double'], ['seam', '2', 'seam-eyes'], ['seam', '21', 'seam-fixed'],
    ['verdict', '', 'verdict'],
  ]
  for (const [ch, keys, name] of runs) {
    await desk.goto(`${base}/story/${ch}`)
    await desk.waitForTimeout(3500)
    for (const k of keys) { await desk.keyboard.press(k); await desk.waitForTimeout(1600) }
    await desk.waitForTimeout(800)
    await desk.screenshot({ path: `${out}/${tag}S-${name}.png` })
  }
}
if (which === 'all' || which === 'mobile') {
  for (const w of [390, 360]) {
    const mob = await page({ width: w, height: w === 390 ? 844 : 780, isMobile: true, hasTouch: true, deviceScaleFactor: 2 })
    const pre = `${out}/${tag}M${w}-`
    await mob.goto(base + '/')
    await mob.waitForTimeout(6000)
    await mob.screenshot({ path: pre + 'gate.png' })
    await mob.evaluate(() => { const g = document.querySelector('.gate'); if (g) g.scrollTop = g.scrollHeight })
    await mob.waitForTimeout(600)
    await mob.screenshot({ path: pre + 'gate-end.png' })
    await mob.goto(base + '/?mode=story')
    await mob.waitForTimeout(4000)
    await mob.screenshot({ path: pre + 'hero.png' })
    await mob.evaluate(() => window.scrollTo(0, document.documentElement.scrollHeight))
    await mob.waitForTimeout(3500)
    await mob.screenshot({ path: pre + 'finale.png' })
    await mob.goto(base + '/story')
    await mob.waitForFunction(() => !!window.__introTl, null, { timeout: 60000, polling: 500 })
    for (const [l, o, name] of [['b1', -2.2, 'intro-phones'], ['b1', 4, 'intro-kid'], ['pov', 3.4, 'intro-pov'], ['b2', 5, 'intro-left'], ['b3', 5, 'intro-right'], [null, 0, 'intro-title']]) {
      await mob.evaluate(([l, o]) => { const t = window.__introTl; t.pause(); t.seek(l === null ? t.duration() : t.labels[l] + o) }, [l, o])
      await mob.waitForTimeout(1800)
      await mob.screenshot({ path: pre + name + '.png' })
    }
    for (const ch of ['third-eye', 'two-eyes', 'clouds', 'verdict']) {
      await mob.goto(`${base}/story/${ch}`)
      await mob.waitForTimeout(4000)
      await mob.screenshot({ path: pre + ch + '.png', fullPage: true })
    }
    await mob.close()
  }
}
await browser.close()
await server.close()
console.log(errors.length ? [...new Set(errors)].join('\n') : 'no page errors')
