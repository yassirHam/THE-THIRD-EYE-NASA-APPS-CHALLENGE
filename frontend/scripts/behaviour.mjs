// Behaviour checks for the intro and Story Mode: skip, next, replay, keyboard choices,
// question answers and reduced motion. Prints one line per check and exits 1 on failure.
import { chromium } from 'playwright'
import { createServer } from 'vite'

const server = await createServer({ server: { port: 5181, strictPort: false }, logLevel: 'error' })
await server.listen()
const base = server.resolvedUrls.local[0].replace(/\/$/, '')
// channel 'chromium' runs the full browser headless; the separate headless shell fails to start on some machines
const browser = await chromium.launch({ channel: 'chromium', args: ['--use-angle=d3d11', '--enable-gpu', '--ignore-gpu-blocklist', '--enable-unsafe-swiftshader'] })
const results = []
const check = (name, ok, extra = '') => { results.push(ok); console.log(`${ok ? 'PASS' : 'FAIL'}  ${name}${extra ? '  ' + extra : ''}`) }
const errors = []

const ctx = await browser.newContext({ viewport: { width: 1400, height: 860 } })
const page = await ctx.newPage()
page.on('pageerror', (e) => errors.push(e.message))
// ?arrival=0 skips the once-a-day opening film, which would otherwise cover the first screen here
await page.goto(base + '/?arrival=0')
await page.waitForTimeout(5000)

// first screen: three tall mode cards under a "Choose your mode" prompt, before any scrolling
await page.goto(base + '/?arrival=0')
await page.waitForSelector('.loader', { state: 'detached', timeout: 30000 })
await page.waitForTimeout(2600)
const cards = await page.$$eval('.mode', (els) => els.map((e) => ({ name: e.querySelector('.mode__name')?.textContent, what: !!e.querySelector('.mode__what')?.textContent, go: !!e.querySelector('.mode__go')?.textContent, font: getComputedStyle(e.querySelector('.mode__what')).fontFamily, top: e.getBoundingClientRect().top, bottom: e.getBoundingClientRect().bottom, h: e.getBoundingClientRect().height })))
check('First screen shows three mode cards', cards.length === 3 && cards.map((c) => c.name).join('|') === 'Story Mode|Research Lab|Quick Mission', cards.map((c) => c.name).join(', '))
check('Each card says in one line what it does, with one action', cards.every((c) => c.what && c.go))
check('The cards take most of the screen height', cards.every((c) => c.h >= 860 * 0.5), cards.map((c) => Math.round(c.h)).join(','))
check('The gate prompt says Choose your mode', (await page.textContent('.gate__choose'))?.trim() === 'Choose your mode')
check('Card sentences use the sans font', cards.every((c) => c.font.includes('IBM Plex Sans')), cards[0]?.font)
check('Story card shows real frames', (await page.$$('.preview--story img')).length === 4)
check('Unbuilt modes are labelled as planned', (await page.$$eval('.preview--plan .preview__tag', (els) => els.map((e) => e.textContent))).every((t) => t === 'Planned layout'))
check('All three cards fit the first screen', cards.every((c) => c.top >= 0 && c.bottom <= 860), cards.map((c) => Math.round(c.bottom)).join(','))
// the 3D third eye sits centred above the title, its pupil about 12% down; click it to blink
await page.mouse.move(700, 104)
await page.waitForTimeout(400)
const hintShown = await page.evaluate(() => document.documentElement.classList.contains('is-eye-hover'))
await page.mouse.down(); await page.mouse.up()
await page.waitForTimeout(100)
check('Clicking the landing eye makes it blink', hintShown && (await page.evaluate(() => window.__eyeBlinks ?? 0)) >= 1)
await page.mouse.move(200, 120); await page.mouse.down(); await page.mouse.up()
check('Clicking elsewhere does not', (await page.evaluate(() => window.__eyeBlinks ?? 0)) === 1)
// common laptop and desktop sizes: the cards must be fully visible without scrolling
const fit = await browser.newPage()
for (const [w, h] of [[1920, 1080], [1536, 864], [1440, 900], [1366, 768], [1280, 720], [1024, 768]]) {
  await fit.setViewportSize({ width: w, height: h })
  await fit.goto(base + '/')
  await fit.waitForSelector('.loader', { state: 'detached', timeout: 30000 })
  await fit.waitForTimeout(2600)
  const b = await fit.$$eval('.mode', (els) => Math.max(...els.map((e) => e.getBoundingClientRect().bottom)))
  check(`Cards fit at ${w}x${h}`, b <= h, `bottom ${Math.round(b)}`)
}
await fit.close()
check('Loader has left', (await page.$('.loader')) === null)
check('No scroll page before a mode is chosen', (await page.$('.landing__track')) === null)
await page.click('.mode--story')
await page.waitForURL('**/?mode=story', { timeout: 4000 }).catch(() => {})
await page.waitForTimeout(1200)
check('Story card opens the scroll page', page.url().includes('mode=story') && (await page.$('.landing__track')) !== null)
check('Watch the introduction button appears', await page.isVisible('.dock__play'))
await page.click('.dock__back')
await page.waitForTimeout(800)
check('All modes returns to the cards', (await page.$$('.mode')).length === 3 && !page.url().includes('mode='))
await page.keyboard.press('2')
await page.waitForURL('**/lab', { timeout: 4000 }).catch(() => {})
check('Key 2 opens the Research Lab', page.url().endsWith('/lab'))
await page.goto(base + '/?mode=story')
await page.waitForTimeout(1500)
await page.click('.dock__play')
await page.waitForURL('**/story', { timeout: 4000 }).catch(() => {})
check('Watch the introduction opens the intro', page.url().endsWith('/story'))
// narration: the click above counts as the visitor's go-ahead for sound
await page.waitForFunction(() => !!window.__introTl, null, { timeout: 60000 })
const phones = await page.waitForSelector('.intro__phones', { state: 'visible', timeout: 6000 }).then(() => true, () => false)
check('Headphones note shows at the start', phones && (await page.textContent('.intro__phones'))?.includes('headphones'))
await page.waitForFunction(() => window.__narrator?.current?.currentTime > 0.3, null, { timeout: 15000 }).catch(() => {})
const voice = await page.evaluate(() => { const a = window.__narrator?.current; return { src: a?.src ?? '', playing: !!a && !a.paused, t: a?.currentTime ?? 0 } })
check('Narrator reads the first line', voice.src.endsWith('/audio/intro/p1.mp3') && voice.t > 0.3, `${voice.src.split('/').pop()} at ${voice.t.toFixed(2)}s`)
check('Synthetic voice is labelled', await page.isVisible('.intro__voice') && (await page.textContent('.intro__sound'))?.includes('Sound'))
check('Sound button has an accessible name', !!(await page.getAttribute('.intro__sound', 'aria-label')))
check('Background music plays', await page.evaluate(() => window.__narrator.musicPlaying))
check('Headphones note has gone once the scene starts', !(await page.isVisible('.intro__phones')))
await page.getByRole('button', { name: 'Pause' }).click()
await page.waitForTimeout(300)
check('Pause also pauses the voice', await page.evaluate(() => window.__narrator.current?.paused !== false))
await page.getByRole('button', { name: 'Play' }).click()
await page.click('.intro__sound')
await page.waitForTimeout(200)
check('Sound button mutes the voice', await page.evaluate(() => window.__narrator.muted && window.__narrator.current?.paused !== false))
await page.click('.intro__sound')
await page.evaluate(() => localStorage.removeItem('the-third-eye-sound'))
// each eye speaks in its own ear: MODIS (right eye open) on the right, VIIRS on the left
const panAt = async (label, key) => {
  await page.evaluate((l) => { window.__introTl.seek(window.__introTl.labels[l]).play() }, label)
  await page.waitForFunction((k) => window.__narrator.current?.src.endsWith(`/${k}.mp3`), key, { timeout: 8000 }).catch(() => {})
  await page.waitForTimeout(400)
  return page.evaluate(() => ({ pan: window.__narrator.pan, param: window.__narrator.voicePan?.pan.value ?? NaN, music: window.__narrator.musicPan?.pan.value ?? NaN }))
}
const pl = await panAt('b2', 'l1')
check('Left-eye / MODIS lines play in the left ear', pl.pan === -1 && pl.param < -0.95, `voice ${pl.param.toFixed(2)} music ${pl.music.toFixed(2)}`)
const pr = await panAt('b3', 'r1')
check('Right-eye / VIIRS lines play in the right ear', pr.pan === 1 && pr.param > 0.95, `voice ${pr.param.toFixed(2)} music ${pr.music.toFixed(2)}`)
const pb = await panAt('b4', 'b1')
check('Both-eyes lines are centred again', pb.pan === 0 && Math.abs(pb.param) < 0.05, `voice ${pb.param.toFixed(2)}`)
// the two small eyes in the intro blink when clicked (they show once the view is through the child's eyes)
await page.evaluate(() => window.__introTl.seek(window.__introTl.labels.b2 - 1.0).pause())
await page.waitForTimeout(900)
await page.click('.intro__eye--l', { timeout: 5000 }).catch(() => {})
await page.waitForTimeout(60)
check('Clicking an intro eye makes it blink', await page.evaluate(() => !!document.querySelector('.intro__eye--l .eye__blink.is-blinking')))
// intro: Escape skips to the first chapter
await page.goto(base + '/story')
await page.waitForFunction(() => !!window.__introTl, null, { timeout: 60000 })
await page.keyboard.press('Escape')
await page.waitForURL('**/story/third-eye', { timeout: 5000 }).catch(() => {})
check('Esc skips the intro', page.url().endsWith('/story/third-eye'))

// intro: Next walks the beats, then leaves
await page.goto(base + '/story')
await page.waitForFunction(() => !!window.__introTl, null, { timeout: 60000 })
const times = []
for (let i = 0; i < 5; i++) {
  await page.getByRole('button', { name: 'Next' }).click()
  await page.waitForTimeout(250)
  times.push(await page.evaluate(() => window.__introTl?.time() ?? -1))
}
check('Next advances through beats', times.slice(0, 4).every((t, i) => i === 0 || t > times[i - 1]), times.map((t) => t.toFixed(1)).join(' '))
await page.waitForTimeout(500)
check('Next past the last beat enters the story', page.url().endsWith('/story/third-eye'))

// intro: pause toggles
await page.goto(base + '/story')
await page.waitForFunction(() => !!window.__introTl, null, { timeout: 60000 })
await page.getByRole('button', { name: 'Pause' }).click()
const pausedAt = await page.evaluate(() => window.__introTl.time())
await page.waitForTimeout(600)
check('Pause holds the timeline', Math.abs((await page.evaluate(() => window.__introTl.time())) - pausedAt) < 0.01)

// chapter: number keys choose; questions render answers under the question
await page.goto(base + '/story/two-eyes')
await page.waitForTimeout(2500)
for (let i = 0; i < 2; i++) { await page.keyboard.press('1'); await page.waitForTimeout(700) }
const q = page.locator('.story__entry:last-child .story__question')
check('Question node shows its question', (await q.count()) === 1 && (await q.innerText()).includes('So which eye is right?'))
check('Question has three answer buttons', (await page.locator('.story__answers button').count()) === 3)
check('No plain choice list while asking', (await page.locator('.story__choices').count()) === 0)
const universe = () => page.locator('.story').getAttribute('data-universe')

// a wrong answer opens a parallel universe; going back re-asks the question
await page.keyboard.press('1')
await page.waitForTimeout(1400)
check('Wrong answer enters a parallel universe', (await universe()) === 'parallel')
check('Parallel universe is labelled', (await page.locator('.story__entry:last-child .story__universe-tag').count()) === 1)
check('Universe offers the way back', (await page.locator('.story__choices button.is-back').count()) === 1)
await page.keyboard.press('1')
await page.waitForTimeout(1400)
check('Going back returns to the main universe', (await universe()) === 'main')
check('Back note is shown', (await page.locator('.story__back-note').count()) === 1)
check('Question is asked again', (await page.locator('.story__answers button').count()) === 3)
check('Tried answer is marked', (await page.locator('.story__answers button').first().getAttribute('class'))?.includes('is-tried') === true)

await page.keyboard.press('3')
await page.waitForTimeout(700)
check('Answer by key 3 is recorded', (await page.locator('.story__said').last().innerText()).includes('Your answer: Neither, on its own.'))
check('Correct answer stays in the main universe', (await universe()) === 'main')
check('After answering, choices return', (await page.locator('.story__choices button').count()) === 1)

// skip: S and the button move on, and never into a parallel universe
await page.goto(base + '/story/two-eyes')
await page.waitForTimeout(2500)
await page.keyboard.press('s')
await page.waitForTimeout(700)
check('S skips a step', (await page.locator('.story__said').last().innerText()).includes('Skipped') && (await page.locator('.story__entry').count()) === 2)
await page.keyboard.press('s')
await page.keyboard.press('s')
await page.waitForTimeout(900)
const lastText = await page.locator('.story__entry:last-child .story__para').first().innerText()
check('Skipping a question takes the right answer', lastText.startsWith('Neither is right on its own') && (await universe()) === 'main', lastText.slice(0, 40))
await page.goto(base + '/story/clouds')
await page.waitForTimeout(2500)
await page.getByRole('button', { name: /Skip step/ }).click()
await page.waitForTimeout(900)
check('Skip button skips the question', (await page.locator('.story__entry:last-child .story__para').first().innerText()).startsWith('Right.') && (await universe()) === 'main')

// the first choice is not highlighted on its own
await page.goto(base + '/story/third-eye')
await page.waitForTimeout(2500)
await page.mouse.move(5, 5)
const looks = await page.locator('.story__choices button').evaluateAll((els) => els.map((e) => { const s = getComputedStyle(e); return `${s.color}|${s.backgroundColor}|${s.borderColor}` }))
check('First choice looks like the others', looks.length >= 2 && looks.every((l) => l === looks[0]), looks.join(' / '))

// clouds: wrong answer path and Tab focus reaches an answer
await page.goto(base + '/story/clouds')
await page.waitForTimeout(2500)
let reached = false
for (let i = 0; i < 25 && !reached; i++) {
  await page.keyboard.press('Tab')
  reached = await page.evaluate(() => !!document.activeElement?.closest('.story__answers'))
}
check('Tab reaches the answers', reached)
await page.keyboard.press('Enter')
await page.waitForTimeout(700)
check('Enter answers the focused option', (await page.locator('.story__said').last().innerText()).startsWith('Your answer:'))
await page.waitForTimeout(800)
check('First clouds answer opens its universe', (await universe()) === 'parallel')

// footer: replay intro, and Esc exits to the landing page
await page.goto(base + '/story/seam')
await page.waitForTimeout(1500)
await page.getByRole('link', { name: 'Replay intro' }).click()
await page.waitForURL('**/story', { timeout: 5000 }).catch(() => {})
check('Replay intro opens the intro', new URL(page.url()).pathname === '/story')
await page.goto(base + '/story/seam')
await page.waitForTimeout(1500)
await page.keyboard.press('Escape')
await page.waitForTimeout(800)
check('Esc in a chapter returns home', new URL(page.url()).pathname === '/')

// reduced motion: the intro is shown at its end with Begin ready
const rctx = await browser.newContext({ viewport: { width: 1400, height: 860 }, reducedMotion: 'reduce' })
const rp = await rctx.newPage()
rp.on('pageerror', (e) => errors.push(e.message))
await rp.goto(base + '/story')
await rp.waitForFunction(() => !!window.__introTl, null, { timeout: 60000 })
await rp.waitForTimeout(800)
const prog = await rp.evaluate(() => window.__introTl.progress())
check('Reduced motion jumps the intro to its end', prog === 1, `progress ${prog}`)
check('Reduced motion shows Begin', await rp.locator('.intro__begin').isVisible())

check('No page errors', errors.length === 0, errors.join(' | '))
await browser.close()
await server.close()
process.exit(results.every(Boolean) ? 0 : 1)
