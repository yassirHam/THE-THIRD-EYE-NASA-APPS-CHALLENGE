/* Shared clock for the first-visit opening film. The overlay (components/Arrival) reads it
   for captions and the hand-off; the shader (three/ArrivalScene) advances it every frame. */

/** Seconds. The film waits at HOLD until the site has loaded, then hands off at END. */
export const HOLD = 9.4
export const END = 9.7
/** Near-black stretch between the warp and space: a hitch here is invisible. */
export const DARK = 5.6

export const arrival = {
  /** film time in seconds */
  t: 0,
  /** distance travelled during the warp, integrated from speed */
  dist: 0,
  /** set once the landing page's assets have finished loading */
  loaded: false,
  /** dev only: the film stops advancing at this time, so screenshots land on exact frames */
  stopAt: Infinity,
}

// dev hook so the screenshot script can follow the film
if (import.meta.env.DEV && typeof window !== 'undefined') (window as unknown as { __arrival: typeof arrival }).__arrival = arrival

const sat = (x: number) => Math.min(1, Math.max(0, x))
const ss = (a: number, b: number, x: number) => {
  const t = sat((x - a) / (b - a))
  return t * t * (3 - 2 * t)
}
const mix = (a: number, b: number, t: number) => a + (b - a) * t

/** Every animated value of the film as a function of film time. */
export function curves(t: number) {
  const fade = ss(0, 1.1, t)
  // a thin vertical slit of light, which then opens into the third eye
  const eyeLine = ss(0.9, 1.5, t) * (1 - ss(3.45, 3.85, t))
  const eye = ss(1.4, 2.6, t)
  const dive = sat((t - 2.75) / 0.95)
  const warp = ss(3.15, 3.9, t) * (1 - ss(4.9, 5.9, t))
  const neb = fade * (1 - ss(5.1, 5.95, t))
  const space = ss(5.75, 6.9, t)
  const approach = ss(6.0, HOLD, t)
  const earthR = 0.01 * Math.pow(0.62 / 0.01, approach)
  return {
    fade,
    eyeLine,
    eye,
    dive,
    eyeScale: 1 + Math.pow(dive, 3) * 70,
    warp,
    neb,
    space,
    approach,
    earthR,
    earthY: mix(0.02, -0.36, approach),
    sunY: mix(0.11, 0.86, approach),
    sunS: mix(0.006, 0.05, approach),
    rays: mix(0.25, 1, approach) + ss(8.9, END, t) * 0.5,
  }
}
