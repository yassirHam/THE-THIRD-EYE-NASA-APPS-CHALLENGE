import { chromium } from 'playwright'
import assert from 'node:assert/strict'
const out = process.env.TEMP + '/prof/'
const browser = await chromium.launch({ headless: true, channel: 'chrome', args: ['--autoplay-policy=user-gesture-required'] })
for (const width of [1440, 390, 360]) {
  const page = await browser.newPage({ viewport: { width, height: 900 } })
  await page.addInitScript(() => {
    window.__plays = []
    const play = HTMLMediaElement.prototype.play
    HTMLMediaElement.prototype.play = function () { window.__plays.push(this.src.split('/').pop()); return play.call(this) }
  })
  await page.goto('http://127.0.0.1:5173/', { waitUntil: 'domcontentloaded' })
  await page.getByRole('heading', { name: 'Choose your mode' }).waitFor()
  await page.waitForTimeout(2500)
  assert.equal((await page.evaluate(() => window.__plays)).includes('menu_music.mp3'), false, 'no music before a gesture')
  await page.screenshot({ path: out + 'landing-' + width + '.png' })
  await page.mouse.click(5, 450)
  await page.waitForTimeout(1500)
  const state = await page.evaluate(() => window.__plays)
  assert.ok(state.includes('menu_music.mp3'), 'music starts on first click')
  // story scroll page keeps it and scrolling should not throw
  await page.keyboard.press('1'); await page.waitForTimeout(1500)
  await page.mouse.wheel(0, 1200); await page.waitForTimeout(800)
  await page.getByRole('button', { name: /Sound on/ }).click()
  assert.ok(await page.getByRole('button', { name: /Sound off/ }).isVisible())
  await page.getByRole('button', { name: /Sound off/ }).click()
  await page.screenshot({ path: out + 'scroll-' + width + '.png' })
  console.log(width + 'px ok, plays:', state.join(','))
  await page.close()
}
await browser.close()
