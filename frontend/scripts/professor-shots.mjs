import { chromium } from 'playwright'
const out = process.env.TEMP + '/prof/'
const browser = await chromium.launch({ headless: true, channel: 'chrome', args: ['--use-angle=swiftshader','--enable-unsafe-swiftshader'] })
const errors = []
for (const width of [1440, 390]) {
  const page = await browser.newPage({ viewport: { width, height: 900 } })
  page.on('console', (m) => { if (m.type() === 'error' || m.type() === 'warning') errors.push(width + ' ' + m.text()) })
  page.on('pageerror', (e) => errors.push(width + ' PAGEERR ' + e.message))
  await page.goto('http://127.0.0.1:5173/story/third-eye', { waitUntil: 'domcontentloaded' })
  await page.getByText("Hello, I'm Professor Orez.", { exact: false }).waitFor()
  await page.waitForTimeout(3500)
  await page.screenshot({ path: out + 'explain-' + width + '.png' })
  await page.locator('.professor').screenshot({ path: out + 'prof-explain-' + width + '.png' })
  // walk to the first question
  for (let i = 0; i < 8 && !(await page.locator('.quiz').count()); i++) { await page.keyboard.press('s'); await page.waitForTimeout(400) }
  await page.waitForTimeout(2500)
  await page.screenshot({ path: out + 'quiz-' + width + '.png' })
  await page.locator('.professor').screenshot({ path: out + 'prof-think-' + width + '.png' })
  await page.keyboard.press('1'); await page.waitForTimeout(1500)
  await page.locator('.professor').screenshot({ path: out + 'prof-wrong-' + width + '.png' })
  await page.getByRole('button', { name: 'Previous story step' }).click(); await page.waitForTimeout(800)
  await page.keyboard.press('3'); await page.waitForTimeout(350)
  await page.locator('.professor').screenshot({ path: out + 'prof-correct-' + width + '.png' })
  await page.close()
}
console.log(errors.slice(0, 15).join('\n') || 'no console errors')
await browser.close()
