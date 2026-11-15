// Finds content that is cut off at common laptop viewports (CSS pixels after Windows scaling).
// For every page and size it reports visible text or controls that end outside the viewport or
// outside a clipping ancestor that cannot be scrolled to reveal them.
import { chromium } from 'playwright'

const BASE = process.env.BASE_URL ?? 'http://127.0.0.1:5173'
const SIZES = [
  [1280, 720], // 1920x1080 at 150%, or 1280x720 panels
  [1366, 768], // common budget laptop
  [1280, 800],
  [1536, 864], // 1920x1080 at 125%
  [1440, 900],
  [1024, 768],
]
const PAGES = [
  ['landing', '/', async () => {}],
  ['story-scroll', '/?mode=story', async () => {}],
  ['story-ch1', '/story/third-eye', async () => {}],
  ['story-quiz', '/story/third-eye', async (p) => { for (let i = 0; i < 8 && !(await p.locator('.quiz').count()); i++) { await p.keyboard.press('s'); await p.waitForTimeout(350) } }],
  ['story-ch2', '/story/two-eyes', async () => {}],
  ['story-ch3', '/story/clouds', async () => {}],
  ['story-ch4', '/story/seam', async () => {}],
  ['story-ch5', '/story/verdict', async () => {}],
  ['intro', '/story', async () => {}],
  ['lab', '/lab', async () => {}],
  ['mission', '/mission', async () => {}],
]
const only = process.env.ONLY?.split(',')

const browser = await chromium.launch({ headless: true, channel: 'chrome', args: ['--use-angle=swiftshader', '--enable-unsafe-swiftshader'] })
let problems = 0
for (const [name, path, prep] of PAGES) {
  if (only && !only.includes(name)) continue
  for (const [w, h] of SIZES) {
    const ctx = await browser.newContext({ viewport: { width: w, height: h }, reducedMotion: 'reduce' })
    await ctx.addInitScript(() => { localStorage.setItem('the-third-eye-menu-seen', 'yes'); localStorage.setItem('the-third-eye-intro-seen', 'yes') })
    const page = await ctx.newPage()
    await page.goto(BASE + path, { waitUntil: 'domcontentloaded' })
    await page.waitForFunction(() => !document.querySelector('.loader'), null, { timeout: 20000 }).catch(() => {})
    await page.waitForTimeout(1800)
    await prep(page)
    await page.waitForTimeout(600)
    const cut = await page.evaluate(() => {
      const vw = innerWidth, vh = innerHeight
      const docScrolls = document.scrollingElement.scrollHeight > vh + 2 && getComputedStyle(document.body).overflowY !== 'hidden' && getComputedStyle(document.documentElement).overflowY !== 'hidden'
      const out = []
      const els = [...document.querySelectorAll('h1,h2,h3,h4,p,li,button,a,label,select,figcaption,dt,dd,th,td,kbd,span.mode__state,.gate__headline')]
      for (const el of els) {
        const cs = getComputedStyle(el)
        if (cs.visibility === 'hidden' || cs.display === 'none' || Number(cs.opacity) === 0) continue
        if (el.closest('[aria-hidden="true"], .sr-only, .loader, canvas')) continue
        const r = el.getBoundingClientRect()
        if (r.width < 2 || r.height < 2) continue
        if (!(el.textContent || '').trim() && !['SELECT', 'BUTTON'].includes(el.tagName)) continue
        // walk clipping ancestors; a scrollable one can reveal its content, so it is not a cut
        let clipped = null
        let inScroller = false
        let fixedChain = cs.position === 'fixed'
        for (let a = el.parentElement; a && a !== document.body; a = a.parentElement) {
          const s = getComputedStyle(a)
          if (s.position === 'fixed') fixedChain = true
          const ox = s.overflowX, oy = s.overflowY
          const scrollY = (oy === 'auto' || oy === 'scroll') && a.scrollHeight > a.clientHeight + 1
          const scrollX = (ox === 'auto' || ox === 'scroll') && a.scrollWidth > a.clientWidth + 1
          if (ox === 'visible' && oy === 'visible') continue
          const ar = a.getBoundingClientRect()
          const outY = r.bottom > ar.bottom + 1 || r.top < ar.top - 1
          const outX = r.right > ar.right + 1 || r.left < ar.left - 1
          if ((outY && !scrollY && oy !== 'visible') || (outX && !scrollX && ox !== 'visible')) { clipped = `${a.className || a.tagName}`.toString().slice(0, 40); break }
          if (scrollY || scrollX) { inScroller = true; break }
        }
        const offScreen = (r.right > vw + 1 || r.left < -1) || ((r.bottom > vh + 1) && !inScroller && (fixedChain || !docScrolls))
        if (clipped || offScreen) out.push({ text: (el.getAttribute('aria-label') || el.textContent).trim().replace(/\s+/g, ' ').slice(0, 50), tag: el.tagName, box: [Math.round(r.left), Math.round(r.top), Math.round(r.right), Math.round(r.bottom)], by: clipped ?? 'viewport' })
      }
      // keep only outermost reports
      return out.filter((o, i) => !out.slice(0, i).some((p) => p.text.includes(o.text) && p.by === o.by && p.box[1] <= o.box[1] && p.box[3] >= o.box[3]))
    })
    if (cut.length) {
      problems += cut.length
      console.log(`CUT ${name} ${w}x${h}: ${cut.length}`)
      for (const c of cut.slice(0, 6)) console.log(`    ${c.tag} "${c.text}" ${c.box.join(',')} by ${c.by}`)
      await page.screenshot({ path: `${process.env.TEMP}/fit/${name}-${w}x${h}.png` })
    } else console.log(`ok  ${name} ${w}x${h}`)
    await ctx.close()
  }
}
await browser.close()
console.log(problems ? `${problems} cut elements` : 'nothing cut')
process.exitCode = problems ? 1 : 0
