import { chromium } from 'playwright'
import assert from 'node:assert/strict'

const browser = await chromium.launch({ headless: true, channel: 'chrome' })
try {
  for (const width of [1440, 390]) {
    const page = await browser.newPage({ viewport: { width, height: 900 }, reducedMotion: 'reduce' })
    await page.goto('http://127.0.0.1:5174/story/third-eye', { waitUntil: 'domcontentloaded' })
    await page.getByText("Hello, I'm Professor Orez.", { exact: false }).waitFor()
    assert.deepEqual(await page.locator('.chapterbar__slot > span[aria-hidden]').allTextContents(), ['I', 'II', 'III', 'IV', 'V'])
    await page.getByRole('button', { name: 'Story options' }).click()
    assert.equal(await page.getByText('Restart chapter').isVisible(), true)
    await page.keyboard.press('Escape')
    assert.equal(await page.getByText('Restart chapter').count(), 0)
    await page.getByRole('button', { name: 'Pause animation' }).click()
    assert.equal(await page.getByRole('button', { name: 'Resume animation' }).isVisible(), true)
    await page.locator('.chapterbar__slot').nth(2).click()
    await page.getByText('How should the cloudy chunks count?').waitFor()
    assert.equal(await page.getByRole('button', { name: /Next/ }).isDisabled(), true)
    await page.getByRole('button', { name: 'Leave the cloudy chunks out.' }).click()
    await page.getByText(/classified as unobserved or unusable/).waitFor()
    await page.getByRole('button', { name: 'Previous story step' }).click()
    await page.getByText('How should the cloudy chunks count?').waitFor()
    await page.goto('http://127.0.0.1:5174/lab', { waitUntil: 'domcontentloaded' })
    await page.getByRole('heading', { name: 'Fire calendar' }).waitFor()
    await page.close()
    console.log(`Story controls and Lab smoke test passed at ${width}px`)
  }
} finally { await browser.close() }
