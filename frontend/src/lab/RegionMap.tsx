import { useEffect, useRef, useState, type KeyboardEvent, type PointerEvent as ReactPointerEvent } from 'react'

/** Pan and zoom map on NASA Blue Marble with one marker per region.
 * The evidence file gives no boundary for these regions, so a marker shows roughly where the region
 * is. It is not the analysed outline, and nothing is computed from its position. */
export type MapMarker = { id: string; name: string; lon: number; lat: number; status: string; placeholder?: boolean }
const ASPECT = 0.62

export default function RegionMap({ markers, selected, onSelect, home, compact }: { markers: MapMarker[]; selected?: string; onSelect?: (id: string) => void; home: { cx: number; cy: number; w: number }; compact?: boolean }) {
  const [view, setView] = useState(home)
  // Zoom to a region when the selection changes after the first render (map click, list or menu).
  const first = useRef(true)
  useEffect(() => {
    if (first.current) { first.current = false; return }
    const m = markers.find((x) => x.id === selected && !x.placeholder)
    if (m) setView({ cx: m.lon, cy: m.lat, w: 40 })
  }, [selected]) // eslint-disable-line react-hooks/exhaustive-deps
  const frame = useRef<HTMLDivElement>(null)
  const drag = useRef<{ x: number; y: number; cx: number; cy: number; moved: boolean } | null>(null)
  const [hover, setHover] = useState<string | undefined>()
  const h = view.w * ASPECT
  const box = { x: view.cx - view.w / 2, y: -view.cy - h / 2, w: view.w, h }
  const zoom = (k: number) => setView((v) => ({ ...v, w: Math.min(360, Math.max(3, v.w / k)) }))

  useEffect(() => {
    const el = frame.current
    if (!el) return
    const onWheel = (e: WheelEvent) => {
      e.preventDefault()
      const r = el.getBoundingClientRect()
      setView((v) => {
        const hh = v.w * ASPECT
        const lon = v.cx - v.w / 2 + ((e.clientX - r.left) / r.width) * v.w
        const lat = v.cy + hh / 2 - ((e.clientY - r.top) / r.height) * hh
        const w = Math.min(360, Math.max(3, v.w * (e.deltaY > 0 ? 1.15 : 1 / 1.15)))
        const k = w / v.w
        return { cx: lon - (lon - v.cx) * k, cy: lat - (lat - v.cy) * k, w }
      })
    }
    el.addEventListener('wheel', onWheel, { passive: false })
    return () => el.removeEventListener('wheel', onWheel)
  }, [])

  const down = (e: ReactPointerEvent) => { drag.current = { x: e.clientX, y: e.clientY, cx: view.cx, cy: view.cy, moved: false } }
  const move = (e: ReactPointerEvent) => {
    const d = drag.current, el = frame.current
    if (!d || !el) return
    const dx = e.clientX - d.x, dy = e.clientY - d.y
    if (!d.moved && Math.hypot(dx, dy) < 5) return
    if (!d.moved) { d.moved = true; el.setPointerCapture(e.pointerId) }
    const r = el.getBoundingClientRect()
    setView((v) => ({ ...v, cx: d.cx - (dx / r.width) * v.w, cy: d.cy + (dy / r.height) * v.w * ASPECT }))
  }
  const up = () => { const moved = drag.current?.moved; drag.current = null; return moved }
  const key = (e: KeyboardEvent) => {
    const s = view.w * 0.12
    if (e.key === '+' || e.key === '=') zoom(1.4)
    else if (e.key === '-') zoom(1 / 1.4)
    else if (e.key === 'ArrowLeft') setView((v) => ({ ...v, cx: v.cx - s }))
    else if (e.key === 'ArrowRight') setView((v) => ({ ...v, cx: v.cx + s }))
    else if (e.key === 'ArrowUp') setView((v) => ({ ...v, cy: v.cy + s }))
    else if (e.key === 'ArrowDown') setView((v) => ({ ...v, cy: v.cy - s }))
    else return
    e.preventDefault()
  }
  const grid = box.w > 90 ? 20 : box.w > 40 ? 10 : 5
  const ticks = (from: number, to: number) => { const o: number[] = []; for (let v = Math.ceil(from / grid) * grid; v <= to; v += grid) o.push(v); return o }
  const u = box.w / 100
  const hovered = markers.find((m) => m.id === hover)

  return (
    <figure className={`map wb__map ${compact ? 'map--compact' : ''}`}>
      <div className="map__frame wb__mapframe" ref={frame} tabIndex={0} role="application" aria-label="Map. Plus and minus zoom, arrow keys pan. The area list selects a region with a keyboard."
        onPointerDown={down} onPointerMove={move} onPointerUp={up} onPointerCancel={up} onKeyDown={key}>
        <svg className="map__svg" viewBox={`${box.x} ${box.y} ${box.w} ${box.h}`} aria-hidden="true">
          <image href={`${import.meta.env.BASE_URL}tex/earth_atmos_2048.webp`} x={-180} y={-90} width={360} height={180} preserveAspectRatio="none" className="map__earth" />
          <g className="map__grid">
            {ticks(box.x, box.x + box.w).map((x) => <line key={`x${x}`} x1={x} x2={x} y1={box.y} y2={box.y + box.h} />)}
            {ticks(box.y, box.y + box.h).map((y) => <line key={`y${y}`} x1={box.x} x2={box.x + box.w} y1={y} y2={y} />)}
          </g>
          {markers.map((m) => {
            const on = m.id === selected
            return <g key={m.id} className={`rm__marker ${on ? 'is-selected' : ''} ${m.placeholder ? 'is-placeholder' : ''}`} transform={`translate(${m.lon},${-m.lat})`}
              onPointerEnter={() => setHover(m.id)} onPointerLeave={() => setHover(undefined)} onClick={() => { if (!m.placeholder) onSelect?.(m.id) }}>
              <circle r={u * (on ? 4.2 : 3.2)} className="rm__halo" />
              <circle r={u * 1.4} className="rm__dot" />
              <text x={u * 4.5} y={u * 1.4} style={{ fontSize: u * 3.6 }} className="rm__label">{m.name}</text>
            </g>
          })}
        </svg>
        <div className="map__tools" role="group" aria-label="Map view">
          <button type="button" className="chip chip--quiet" onClick={() => zoom(1.5)} aria-label="Zoom in">+</button>
          <button type="button" className="chip chip--quiet" onClick={() => zoom(1 / 1.5)} aria-label="Zoom out">&minus;</button>
          <button type="button" className="chip chip--quiet" onClick={() => setView(home)}>Reset</button>
        </div>
        <span className="map__scale" aria-hidden="true">{grid}&deg; grid</span>
        {hovered && <div className="wb__maptip" role="status"><b>{hovered.name}</b><span>{hovered.status}</span></div>}
      </div>
      <figcaption className="map__caption">Markers show roughly where each region is; the evidence file supplies no boundary, so no outline is drawn and nothing is computed from the marker. Background: NASA Blue Marble.</figcaption>
    </figure>
  )
}
