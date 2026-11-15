// Loads pages with the Google Translate page widget set to French, the same rewrite Chrome's
// "Translate this page" does, and saves screenshots so broken text can be spotted.
// Needs internet access. Usage: node scripts/translate.mjs [tag] [lang]
import { chromium } from 'playwright'
import { createServer } from 'vite'
import { mkdirSync } from 'node:fs'

const tag = process.argv[2] ? process.argv[2] + '-' : ''
const lang = process.argv[3] ?? 'fr'
const server = await createServer({ server: { port: 5185, strictPort: false }, logLevel: 'error' })
await server.listen()
const base = server.resolvedUrls.local[0].replace(/\/$/, '')
mkdirSync('shots', { recursive: true })
const browser = await chromium.launch({ channel: 'chromium', args: ['--use-angle=d3d11', '--enable-gpu', '--ignore-gpu-blocklist', '--enable-unsafe-swiftshader', '--autoplay-policy=no-user-gesture-required'] })
const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 } })
await ctx.addCookies([{ name: 'googtrans', value: `/en/${lang}`, domain: new URL(base).hostname, path: '/' }])
const errors = []
const page = await ctx.newPage()
page.on('pageerror', (e) => errors.push('pageerror: ' + e.message))
page.on('console', (m) => { if (m.type() === 'error') errors.push('console: ' + m.text().slice(0, 200)) })

const translate = async () => {
  await page.evaluate(() => {
    if (document.getElementById('gt-probe')) return
    const d = document.createElement('div'); d.id = 'gt-probe'; d.style.display = 'none'; document.body.appendChild(d)
    window.__gtInit = () => new window.google.translate.TranslateElement({ pageLanguage: 'en', autoDisplay: false }, 'gt-probe')
    const s = document.createElement('script'); s.src = 'https://translate.google.com/translate_a/element.js?cb=__gtInit'; document.head.appendChild(s)
  })
  await page.waitForFunction(() => /translated-/.test(document.documentElement.className), null, { timeout: 30000 }).catch(() => errors.push('translation did not start'))
  await page.waitForTimeout(3500)
}
const shot = async (name) => { await page.screenshot({ path: `shots/${tag}T-${name}.png` }) }
const state = async () => page.evaluate(() => ({ html: document.documentElement.className, lang: document.documentElement.lang }))

// landing gate
await page.goto(base + '/?arrival=0')
await page.waitForTimeout(9000)
await translate()
console.log('gate', JSON.stringify(await state()))
await shot('gate')
// story scroll page
await page.click('.mode--story')
await page.waitForTimeout(2500)
await shot('hero')
const ys = await page.evaluate(() => [...document.querySelectorAll('.chapter')].map((el) => el.offsetTop + el.offsetHeight / 2 - innerHeight / 2))
await page.evaluate((v) => window.scrollTo(0, v), Math.round(ys[0]))
await page.waitForTimeout(2500)
await shot('chapter1')
// intro: through the in-app link, so the translated page keeps running
await page.goto(base + '/story')
await page.waitForFunction(() => !!window.__introTl, null, { timeout: 60000 })
await translate()
for (const [l, o, name] of [['b1', 3, 'intro-park'], ['b2', 6, 'intro-modis'], ['b3', 6, 'intro-viirs'], ['b5', 7, 'intro-third']]) {
  await page.evaluate(([l, o]) => { const t = window.__introTl; t.pause(); t.seek(t.labels[l] + o) }, [l, o])
  await page.waitForTimeout(1500)
  await shot(name)
}
await page.evaluate(() => { const t = window.__introTl; t.pause(); t.progress(1) })
await page.waitForTimeout(1200)
await shot('intro-title')
console.log('intro texts:', JSON.stringify(await page.evaluate(() => [...document.querySelectorAll('.intro__line')].slice(4, 7).map((p) => p.innerText.replace(/\s+/g, ' ').slice(0, 90)))))
console.log('title text:', JSON.stringify(await page.evaluate(() => [...document.querySelectorAll('.gate__title, .hero__title, .intro__title, .topbar__mark span')].map((e) => e.textContent))))
// a story chapter
await page.goto(base + '/story/two-eyes')
await page.waitForTimeout(3000)
await translate()
await shot('chapter-two-eyes')
await browser.close()
await server.close()
console.log(errors.length ? [...new Set(errors)].join('\n') : 'no page errors')
