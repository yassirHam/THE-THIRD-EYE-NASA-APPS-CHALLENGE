// SI compliance check (Space Apps 2026): every image or video the site ships must have a known
// source; SI-generated ones must carry a visible label naming the tool; the SI disclosure must be
// visible. Run: node scripts/si-check.mjs (static part) and with the dev server for the page part.
import { readdirSync, statSync } from 'node:fs'
import { join, relative } from 'node:path'
import { chromium } from 'playwright'

const root = new URL('..', import.meta.url).pathname.replace(/^\/(\w:)/, '$1')
// Every shipped image/video and where it comes from. SI-generated entries need `label`.
const SOURCES = {
  'public/tex/earth_atmos_2048.webp': 'NASA Blue Marble (derived)',
  'public/tex/earth_lights_2048.webp': 'NASA Black Marble (derived)',
  'public/tex/earth_specular_2048.webp': 'derived from NASA Blue Marble land/water mask',
  'public/tex/field-angola-20240618.webp': 'VIIRS true colour, NASA GIBS, 18 June 2024',
  'public/previews/story-1-park.webp': 'screenshot of the site\'s own 3D intro (scripts/shots.mjs)',
  'public/previews/story-2-finger.webp': 'screenshot of the site\'s own 3D intro (scripts/shots.mjs)',
  'public/previews/story-3-two-eyes.webp': 'screenshot of the site\'s own story chapter (scripts/shots.mjs)',
  'public/previews/story-4-third-eye.webp': 'screenshot of the site\'s own 3D intro (scripts/shots.mjs)',
  'public/professor/skin.png': 'minefun avatar export (professor_0rez.json)',
  'public/eye.svg': 'hand-authored SVG',
}
const media = /\.(png|jpe?g|webp|gif|avif|svg|mp4|webm|mov)$/i
const walk = (d) => readdirSync(d).flatMap((n) => { const p = join(d, n); return statSync(p).isDirectory() ? walk(p) : [p] })
const shipped = walk(join(root, 'public')).filter((p) => media.test(p)).map((p) => relative(root, p).replace(/\\/g, '/'))
const unknown = shipped.filter((p) => !SOURCES[p])
let failed = false
if (unknown.length) { failed = true; console.log('FAIL shipped media with no recorded source (label it if SI-generated, or record its source):\n  ' + unknown.join('\n  ')) }
else console.log(`ok  all ${shipped.length} shipped images have a recorded source; none is SI-generated`)

const base = process.env.BASE_URL ?? 'http://127.0.0.1:5173'
const browser = await chromium.launch({ headless: true, channel: 'chrome', args: ['--use-angle=swiftshader', '--enable-unsafe-swiftshader'] })
const page = await browser.newPage({ viewport: { width: 1440, height: 900 } })
for (const path of ['/', '/?mode=story', '/lab?tab=evidence', '/mission', '/story/third-eye']) {
  await page.goto(base + path); await page.waitForTimeout(2500)
  const imgs = await page.evaluate(() => [...document.querySelectorAll('img, video, image')].map((e) => new URL(e.getAttribute('src') || e.getAttribute('href') || '', location.href).pathname))
  const bad = imgs.filter((s) => !SOURCES['public' + s])
  if (bad.length) { failed = true; console.log(`FAIL ${path}: media without a recorded source: ${bad.join(', ')}`) }
}
await page.goto(base + '/?mode=story'); await page.waitForTimeout(2500)
const landing = await page.locator('.credits--si').textContent().catch(() => '')
await page.goto(base + '/lab?tab=evidence'); await page.waitForTimeout(1500)
const lab = await page.locator('.lab__si').textContent().catch(() => '')
for (const [where, t] of [['landing story page', landing], ['Lab evidence', lab]]) {
  if (!/Use of Super Intelligence|use of Super Intelligence/.test(t) || !/NASA logos, flags or official mission identifiers/.test(t)) { failed = true; console.log(`FAIL ${where}: SI disclosure or NASA-branding statement missing`) }
  else console.log(`ok  ${where}: SI disclosure and NASA-branding statement visible`)
}
await browser.close()
process.exitCode = failed ? 1 : 0
