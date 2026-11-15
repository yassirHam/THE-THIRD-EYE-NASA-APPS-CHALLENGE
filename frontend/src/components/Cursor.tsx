import { useEffect, useRef, useState } from 'react'
import gsap from 'gsap'
import { prefersReducedMotion } from '../lib/random'
import './cursor.css'

/** A small sighting reticle that follows the pointer and widens over anything clickable.
 *  Hidden on touch devices; the native cursor stays for keyboard and accessibility tools. */
export default function Cursor() {
  const ring = useRef<HTMLDivElement>(null)
  const dot = useRef<HTMLDivElement>(null)
  const [label, setLabel] = useState('')
  const hinted = useRef('')
  const [enabled] = useState(() => typeof window !== 'undefined' && window.matchMedia('(pointer: fine)').matches && !prefersReducedMotion())

  useEffect(() => {
    if (!enabled || !ring.current || !dot.current) return
    const rx = gsap.quickTo(ring.current, 'x', { duration: 0.45, ease: 'power3' })
    const ry = gsap.quickTo(ring.current, 'y', { duration: 0.45, ease: 'power3' })
    const dx = gsap.quickTo(dot.current, 'x', { duration: 0.08 })
    const dy = gsap.quickTo(dot.current, 'y', { duration: 0.08 })
    const move = (e: PointerEvent) => {
      // refs detach before this effect is cleaned up on route changes, so guard them
      ring.current?.classList.add('is-live'); dot.current?.classList.add('is-live')
      rx(e.clientX); ry(e.clientY); dx(e.clientX); dy(e.clientY)
    }
    const over = (e: PointerEvent) => {
      const t = (e.target as HTMLElement).closest<HTMLElement>('a, button, [data-cursor]')
      hinted.current = ''
      ring.current?.classList.toggle('is-active', !!t)
      setLabel(t?.dataset.cursor ?? '')
    }
    // 3D objects (the eyes) are not HTML elements, so they announce themselves with an event
    const hint = (e: Event) => {
      const l = (e as CustomEvent<string>).detail
      if (l === hinted.current) return
      hinted.current = l
      ring.current?.classList.toggle('is-active', !!l)
      setLabel(l)
    }
    window.addEventListener('pointermove', move)
    window.addEventListener('pointerover', over)
    window.addEventListener('cursor-hint', hint)
    document.documentElement.classList.add('has-cursor')
    return () => {
      window.removeEventListener('pointermove', move)
      window.removeEventListener('pointerover', over)
      window.removeEventListener('cursor-hint', hint)
      document.documentElement.classList.remove('has-cursor')
    }
  }, [enabled])

  if (!enabled) return null
  return (
    <>
      <div className="cursor-ring" ref={ring} aria-hidden="true">
        <svg viewBox="0 0 40 40"><circle cx="20" cy="20" r="18" /><path d="M20 0v6M20 34v6M0 20h6M34 20h6" /></svg>
        {label && <span>{label}</span>}
      </div>
      <div className="cursor-dot" ref={dot} aria-hidden="true" />
    </>
  )
}
