/* Window-level pointer state. The WebGL canvases sit under HTML layers that catch pointer
   events, so the 3D scenes cannot rely on their own pointer; they read this instead. */

export const pointer = { x: -1, y: -1, seen: false }

let started = false
export function trackPointer() {
  if (started || typeof window === 'undefined') return
  started = true
  window.addEventListener('pointermove', (e) => { pointer.x = e.clientX; pointer.y = e.clientY; pointer.seen = true }, { passive: true })
}

/** True when a click or hover is meant for a control, so eyes behind it should not react. */
export function overControl(target: EventTarget | null) {
  return target instanceof Element && !!target.closest('a, button, input, select, textarea, label, [role="button"], [data-no-eye]')
}

/** Ask the custom cursor to show a label while over something that is not an HTML control. */
export function cursorHint(label: string) {
  window.dispatchEvent(new CustomEvent('cursor-hint', { detail: label }))
}

/** Restart a CSS blink animation on an element (the class runs it once, then is removed). */
export function blink(el: Element | null) {
  if (!el) return
  el.classList.remove('is-blinking')
  void (el as HTMLElement).getBoundingClientRect()
  el.classList.add('is-blinking')
  el.addEventListener('animationend', () => el.classList.remove('is-blinking'), { once: true })
}
