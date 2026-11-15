/** Mutable scene state. GSAP and scroll write here; useFrame reads it.
 *  Kept outside React so animation never triggers re-renders. */
export type PortalKey = '' | 'story' | 'lab' | 'mission'

export const landing = {
  progress: 0,
  hover: '' as PortalKey,
  pointer: { x: 0, y: 0 },
  eyeOpen: 0,
  /** 1 while the mode screen is showing: the camera shifts so the eye sits beside the title */
  gate: 0,
}

export const intro = {
  /** 0 = stone field (parallax), 1 = Earth */
  world: 0,
  /** 0 = watching the child from behind, 1 = looking through their eyes */
  pov: 0,
  /** 0 = right hand resting in the lap, 1 = index finger held up in front of the face */
  raise: 1,
  /** both eyes narrowed a little, as when someone switches which eye is open */
  squint: 0,
  /** horizontal camera offset: -1 left eye, +1 right eye */
  camX: 0,
  /** per-half eyelids, 0 open, 1 closed */
  lidL: 0,
  lidR: 0,
  /** per-half sensor weight: colour cast and footprint grid, 0..1 */
  tintL: 0,
  tintR: 0,
  seam: 0,
  globeX: 0,
  eyeOpen: 0,
  rise: 0,
  fireModis: 1,
  fireViirs: 1,
}

export const live = { modis: 1, viirs: 1 }
