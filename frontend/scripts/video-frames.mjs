// Dev helper: grab evenly spaced frames from a local video so a reference clip can be studied.
// Usage: node scripts/video-frames.mjs <video> <outDir> [count]
import { chromium } from 'playwright'
import { readFileSync, mkdirSync } from 'node:fs'
import { resolve } from 'node:path'

const [src, outDir = 'shots/ref', countArg = '24'] = process.argv.slice(2)
const count = Number(countArg)
mkdirSync(outDir, { recursive: true })
const b64 = readFileSync(resolve(src)).toString('base64')

const browser = await chromium.launch({ channel: 'msedge' })
const page = await browser.newPage({ viewport: { width: 540, height: 960 } })
await page.setContent('<body style="margin:0;background:#000"><video id="v" muted playsinline style="width:100vw;height:100vh;object-fit:contain"></video></body>')
const info = await page.evaluate(async (data) => {
  const v = document.getElementById('v')
  const blob = await (await fetch('data:video/mp4;base64,' + data)).blob()
  v.src = URL.createObjectURL(blob)
  await new Promise((r, j) => { v.onloadedmetadata = r; v.onerror = () => j(new Error('decode failed')) })
  return { duration: v.duration, w: v.videoWidth, h: v.videoHeight }
}, b64)
console.log(JSON.stringify(info))
for (let i = 0; i < count; i++) {
  const t = (info.duration * i) / (count - 1) - (i === count - 1 ? 0.05 : 0)
  await page.evaluate((time) => new Promise((r) => {
    const v = document.getElementById('v')
    v.onseeked = () => requestAnimationFrame(() => requestAnimationFrame(r))
    v.currentTime = Math.max(0, time)
  }), t)
  const name = `${outDir}/f${String(i).padStart(2, '0')}-${t.toFixed(2)}s.png`
  await page.screenshot({ path: name })
  console.log(name)
}
await browser.close()
