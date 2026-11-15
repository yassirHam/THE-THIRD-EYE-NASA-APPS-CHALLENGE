import { useEffect, useMemo, useRef, useState, type KeyboardEvent, type PointerEvent as ReactPointerEvent } from 'react'
import type { AreaView } from './model'
import { OUTLINES as REGISTERED, boxOf, type Box } from './geo'

/** The access states the map and the list distinguish. Raw availability is not a calibration. */
export const ACCESS_TEXT = {
  evaluated: 'Evaluated comparison',
  blocked: 'Comparison blocked',
  raw_only: 'Raw observations only',
  unavailable: 'Unavailable',
  none: 'No data loaded',
} as const
type AccessKey = keyof typeof ACCESS_TEXT
const ROLE_TEXT = { primary_region: 'Primary region', backup_region: 'Backup region', predeclared_sub_area: 'Sub-area' } as const

const ASPECT = 0.6 // frame height / width
const WORLD: Box = { west: -20, south: -36, east: 55, north: 38 }
const accessOf = (area?: AreaView): AccessKey => (area ? area.access ?? 'none' : 'none')

function fitBox(box: Box | undefined) {
  const b = box ?? WORLD
  const pad = Math.max(b.east - b.west, (b.north - b.south) / ASPECT) * 0.35 + 1
  const w = Math.max(6, b.east - b.west + pad * 2, (b.north - b.south + pad * 2) / ASPECT)
  return { cx: (b.west + b.east) / 2, cy: (b.south + b.north) / 2, w }
}

/** Pan and zoom map of the registered areas on the NASA Blue Marble background.
 * The SVG works in degrees (x = longitude, y = -latitude). Panning and zooming change the view
 * only; the outlines are the registered ones and are coloured by what the artifacts allow. */
export default function AreaMap({ areas, selected, onSelect }: { areas: AreaView[]; selected?: string; onSelect: (id: string) => void }) {
  const byId = useMemo(() => new Map(areas.map((area) => [area.id, area])), [areas])
  // Only registered outlines that belong to a loaded area are drawn; an area without a supplied boundary is listed, not guessed.
  const OUTLINES = useMemo(() => REGISTERED.filter((o) => byId.has(o.id)), [byId])
  const home = useMemo(() => fitBox(boxOf(OUTLINES)), [OUTLINES])
  const [view, setView] = useState(home)
  useEffect(() => setView(home), [home])
  const [hover, setHover] = useState<string | undefined>()
  const frame = useRef<HTMLDivElement>(null)
  const drag = useRef<{ x: number; y: number; cx: number; cy: number; moved: boolean } | null>(null)
  const suppress = useRef(false)

  const h = view.w * ASPECT
  const box = { x: view.cx - view.w / 2, y: -view.cy - h / 2, w: view.w, h }
  const zoomBy = (factor: number, at?: { lon: number; lat: number }) => setView((v) => {
    const w = Math.min(360, Math.max(2, v.w / factor))
    if (!at) return { ...v, w }
    const k = w / v.w // keep the point under the cursor fixed
    return { cx: at.lon - (at.lon - v.cx) * k, cy: at.lat - (at.lat - v.cy) * k, w }
  })

  useEffect(() => {
    const el = frame.current
    if (!el) return
    const onWheel = (event: WheelEvent) => {
      event.preventDefault()
      const r = el.getBoundingClientRect()
      setView((v) => {
        const hh = v.w * ASPECT
        const lon = v.cx - v.w / 2 + ((event.clientX - r.left) / r.width) * v.w
        const lat = v.cy + hh / 2 - ((event.clientY - r.top) / r.height) * hh
        const w = Math.min(360, Math.max(2, v.w * (event.deltaY > 0 ? 1.15 : 1 / 1.15)))
        const k = w / v.w
        return { cx: lon - (lon - v.cx) * k, cy: lat - (lat - v.cy) * k, w }
      })
    }
    el.addEventListener('wheel', onWheel, { passive: false })
    return () => el.removeEventListener('wheel', onWheel)
  }, [])

  const down = (event: ReactPointerEvent) => { drag.current = { x: event.clientX, y: event.clientY, cx: view.cx, cy: view.cy, moved: false } }
  const move = (event: ReactPointerEvent) => {
    const d = drag.current
    const el = frame.current
    if (!d || !el) return
    const dx = event.clientX - d.x
    const dy = event.clientY - d.y
    if (!d.moved && Math.hypot(dx, dy) < 5) return
    if (!d.moved) { d.moved = true; el.setPointerCapture(event.pointerId) }
    const r = el.getBoundingClientRect()
    setView((v) => ({ ...v, cx: d.cx - (dx / r.width) * v.w, cy: d.cy + (dy / r.height) * v.w * ASPECT }))
  }
  const up = () => { suppress.current = drag.current?.moved ?? false; drag.current = null; window.setTimeout(() => { suppress.current = false }, 0) }
  const key = (event: KeyboardEvent) => {
    const step = view.w * 0.12
    if (event.key === '+' || event.key === '=') zoomBy(1.4)
    else if (event.key === '-') zoomBy(1 / 1.4)
    else if (event.key === 'ArrowLeft') setView((v) => ({ ...v, cx: v.cx - step }))
    else if (event.key === 'ArrowRight') setView((v) => ({ ...v, cx: v.cx + step }))
    else if (event.key === 'ArrowUp') setView((v) => ({ ...v, cy: v.cy + step }))
    else if (event.key === 'ArrowDown') setView((v) => ({ ...v, cy: v.cy - step }))
    else return
    event.preventDefault()
  }
  const focusOn = (id: string) => {
    onSelect(id)
    const outline = OUTLINES.find((o) => o.id === id)
    const b = outline ? boxOf([outline]) : undefined
    if (b) setView(fitBox(b))
  }

  const grid = box.w > 90 ? 20 : box.w > 40 ? 10 : box.w > 12 ? 5 : 1
  const ticks = (from: number, to: number) => { const out: number[] = []; for (let v = Math.ceil(from / grid) * grid; v <= to; v += grid) out.push(v); return out }
  const ring = (pts: Array<[number, number]>) => pts.map(([x, y]) => `${x},${-y}`).join(' ')
  const hovered = hover ? OUTLINES.find((o) => o.id === hover) : undefined
  const hoveredArea = hover ? byId.get(hover) : undefined
  const shown = areas.map((a) => ({ id: a.id, name: a.name, area: a }))

  if (!OUTLINES.length) return (
    <figure className="map wb__map">
      <ul className="wb__arealist" aria-label="Areas">{shown.map(({ id, name, area }) => <li key={id}><button type="button" aria-pressed={id === selected} onClick={() => onSelect(id)} data-access={accessOf(area)}><i aria-hidden="true" /><span><b>{name}</b><small>{area?.role ? ` · ` : ''}{ACCESS_TEXT[accessOf(area)]}</small></span></button></li>)}</ul>
      <figcaption className="map__caption">No boundary has been supplied for these areas yet, so none is drawn on the map.</figcaption>
    </figure>
  )

  return (
    <figure className="map wb__map">
      <div className="map__frame wb__mapframe" ref={frame} onPointerDown={down} onPointerMove={move} onPointerUp={up} onPointerCancel={up} onKeyDown={key} tabIndex={0}
        role="application" aria-label="Map of registered areas. Plus and minus zoom, arrow keys pan. The list below the map selects an area with a keyboard.">
        <svg className="map__svg" viewBox={`${box.x} ${box.y} ${box.w} ${box.h}`} aria-hidden="true">
          <image href={`${import.meta.env.BASE_URL}tex/earth_atmos_2048.webp`} x={-180} y={-90} width={360} height={180} preserveAspectRatio="none" className="map__earth" />
          <g className="map__grid">
            {ticks(box.x, box.x + box.w).map((x) => <line key={`x${x}`} x1={x} x2={x} y1={box.y} y2={box.y + box.h} />)}
            {ticks(box.y, box.y + box.h).map((y) => <line key={`y${y}`} x1={box.x} x2={box.x + box.w} y1={y} y2={y} />)}
          </g>
          {OUTLINES.map((o) => {
            const area = byId.get(o.id)
            const access = accessOf(area)
            return o.rings.map((r, i) => (
              <polygon key={`${o.id}-${i}`} points={ring(r)} data-access={access} data-role={area?.role}
                className={`map__area wb__area ${o.id === selected ? 'is-selected' : ''}`}
                onPointerEnter={() => setHover(o.id)} onPointerLeave={() => setHover(undefined)}
                onClick={() => { if (!suppress.current) focusOn(o.id) }} />
            ))
          })}
        </svg>
        <div className="map__tools" role="group" aria-label="Map view">
          <button type="button" className="chip chip--quiet" onClick={() => zoomBy(1.5)} aria-label="Zoom in">+</button>
          <button type="button" className="chip chip--quiet" onClick={() => zoomBy(1 / 1.5)} aria-label="Zoom out">&minus;</button>
          <button type="button" className="chip chip--quiet" onClick={() => setView(home)}>All areas</button>
        </div>
        <span className="map__scale" aria-hidden="true">{grid}&deg; grid</span>
        {hovered && <div className="wb__maptip" role="status"><b>{hoveredArea?.name ?? hovered.name}</b><span>{ACCESS_TEXT[accessOf(hoveredArea)]}</span></div>}
      </div>
      <ul className="wb__arealist" aria-label="Areas">
        {shown.map(({ id, name, area }) => {
          const access = accessOf(area)
          return <li key={id}><button type="button" aria-pressed={id === selected} disabled={!area} onClick={() => focusOn(id)} data-access={access}>
            <i aria-hidden="true" /><span><b>{name}</b><small>{area?.role ? `${ROLE_TEXT[area.role]} · ` : ''}{ACCESS_TEXT[access]}</small></span>
          </button></li>
        })}
      </ul>
      <ul className="wb__legend" aria-label="Map legend">
        {(['evaluated', 'blocked', 'raw_only', 'unavailable', 'none'] as const).map((k) => <li key={k}><i className="wb__swatch" data-access={k} aria-hidden="true" />{ACCESS_TEXT[k]}</li>)}
      </ul>
      <figcaption className="map__caption">Outlined areas are the registered areas; the rest of the map is background, not coverage. Raw availability is not an evaluated comparison. Background: NASA Blue Marble.</figcaption>
    </figure>
  )
}
