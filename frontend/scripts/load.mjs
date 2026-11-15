// First-visit load cost on a slow link, like an ngrok tunnel or a phone on 4G.
// Serves either the dev server or the production build, throttles the browser, and reports
// requests, bytes and the time until the mode cards are usable.
// Usage: node scripts/load.mjs [prod|dev] [mbps=8] [rttMs=120] [path=/?arrival=0]
import { chromium } from 'playwright'
import { createServer, preview } from 'vite'

const [mode = 'prod', mbps = '8', rtt = '120', path = '/?arrival=0'] = process.argv.slice(2)
const server = mode === 'dev'
  ? await createServer({ server: { port: 5191, strictPort: false }, logLevel: 'error' })
  : await preview({ preview: { port: 5192, strictPort: false }, logLevel: 'error' })
if (mode === 'dev') await server.listen()
const base = server.resolvedUrls.local[0].replace(/\/$/, '')

const browser = await chromium.launch({ channel: 'chromium', args: ['--use-angle=d3d11', '--enable-gpu', '--ignore-gpu-blocklist', '--enable-unsafe-swiftshader'] })
// warm the dev server's dependency optimiser so the measured run is not its first compile
if (mode === 'dev') { const w = await browser.newPage(); await w.goto(base + path); await w.waitForTimeout(8000); await w.close() }

const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 } })
const page = await ctx.newPage()
const cdp = await ctx.newCDPSession(page)
await cdp.send('Network.enable')
await cdp.send('Network.setCacheDisabled', { cacheDisabled: true })
await cdp.send('Network.emulateNetworkConditions', { offline: false, latency: Number(rtt), downloadThroughput: Number(mbps) * 125000, uploadThroughput: 2 * 125000 })
const reqs = new Map()
cdp.on('Network.requestWillBeSent', (e) => reqs.set(e.requestId, { url: e.request.url, t0: e.timestamp }))
cdp.on('Network.loadingFinished', (e) => { const r = reqs.get(e.requestId); if (r) { r.bytes = e.encodedDataLength; r.t1 = e.timestamp } })
cdp.on('Network.responseReceived', (e) => { const r = reqs.get(e.requestId); if (r) r.enc = e.response.headers['content-encoding'] || e.response.headers['Content-Encoding'] || '' })

const t0 = Date.now()
await page.goto(base + path, { waitUntil: 'commit' })
await page.waitForSelector('.loader, .arrival', { timeout: 120000 })
const firstPaint = Date.now() - t0
// usable: the loader/film has gone and the first mode card is clickable
await page.waitForFunction(() => !document.querySelector('.loader') && !document.querySelector('.arrival') && !!document.querySelector('.mode--story'), null, { timeout: 300000, polling: 100 })
const ready = Date.now() - t0
await page.waitForTimeout(4000) // anything fetched shortly after the cards appear

const list = [...reqs.values()].filter((r) => r.bytes)
const kind = (u) => /\.(js|mjs|tsx?|jsx)(\?|$)|\/@|node_modules/.test(u) ? 'script' : /\.css/.test(u) ? 'css' : /\.(woff2?|ttf)/.test(u) ? 'font' : /\.(jpe?g|png|webp|avif|ktx2)/.test(u) ? 'image' : /\.(mp3|wav|ogg|m4a)/.test(u) ? 'audio' : 'other'
const by = {}
for (const r of list) { const k = kind(r.url); by[k] ??= { n: 0, kb: 0 }; by[k].n++; by[k].kb += r.bytes / 1024 }
const total = list.reduce((s, r) => s + r.bytes, 0) / 1024
console.log(`${mode} @ ${mbps} Mbps, ${rtt} ms  path ${path}`)
console.log(`  loader visible after ${(firstPaint / 1000).toFixed(1)} s, cards usable after ${(ready / 1000).toFixed(1)} s`)
console.log(`  ${list.length} requests, ${Math.round(total)} KB transferred`)
for (const [k, v] of Object.entries(by).sort((a, b) => b[1].kb - a[1].kb)) console.log(`    ${k.padEnd(7)} ${String(v.n).padStart(4)} req  ${String(Math.round(v.kb)).padStart(6)} KB`)
console.log('  largest:')
for (const r of list.sort((a, b) => b.bytes - a.bytes).slice(0, 10)) console.log(`    ${String(Math.round(r.bytes / 1024)).padStart(6)} KB ${r.enc ? '(' + r.enc + ') ' : ''}${r.url.replace(base, '')}`)
await browser.close()
await (server.close?.() ?? server.httpServer?.close())
process.exit(0)
