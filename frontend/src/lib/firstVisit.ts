import { prefersReducedMotion } from './random'

/* The opening film plays on a visitor's first visit of the day. ?arrival=1 forces it,
   ?arrival=0 turns it off, and reduced motion always gets the short loader instead. */
const KEY = 'the-third-eye.arrival'
const today = () => new Date().toLocaleDateString('en-CA')

export function wantsArrival(search: URLSearchParams): boolean {
  const force = search.get('arrival')
  if (force === '1') return true
  if (force === '0' || prefersReducedMotion()) return false
  try {
    return localStorage.getItem(KEY) !== today()
  } catch {
    return true
  }
}

export function markArrived() {
  try {
    localStorage.setItem(KEY, today())
  } catch {
    /* private mode: the film may play again next time */
  }
}
