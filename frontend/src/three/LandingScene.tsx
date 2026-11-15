import { Suspense, useRef } from 'react'
import { Canvas, useFrame } from '@react-three/fiber'
import * as THREE from 'three'
import Globe from './Globe'
import ThirdEye from './ThirdEye'
import Armillary from './Armillary'
import { Embers, Stars } from './Atmosphere'
import Effects from './Effects'
import Lights from './Lights'
import { landing } from './state'

type V3 = [number, number, number]
interface Key { p: number; cam: V3; look: V3; eye: number; modis: number; viirs: number; seam: number; years: number; sats: number }

/** Camera and scene keyframes along the landing scroll. One per text section. */
const KEYS: Key[] = [
  { p: 0.0, cam: [0, 0.9, 12.5], look: [0, 1.6, 0], eye: 0.32, modis: 0.0, viirs: 0.0, seam: 0, years: 0, sats: 0 },
  { p: 0.25, cam: [2.4, 0.4, 7.8], look: [-2.3, -0.9, 0], eye: 0.32, modis: 1.0, viirs: 0.0, seam: 0, years: 0, sats: 1 },
  { p: 0.5, cam: [-2.6, -0.6, 7.4], look: [3.0, -1.0, 0], eye: 0.45, modis: 1.0, viirs: 1.0, seam: 1, years: 1, sats: 1 },
  // third eye framed on the right, text on the left
  { p: 0.75, cam: [-1.2, 3.1, 8.6], look: [-2.4, 2.8, 0], eye: 1.0, modis: 1.0, viirs: 1.0, seam: 1, years: 1, sats: 1 },
  // portals: eye up and to the right, clear of the heading
  { p: 1.0, cam: [-1.0, 0.6, 14.5], look: [-3.4, 1.0, 0], eye: 1.0, modis: 1.0, viirs: 1.0, seam: 0.4, years: 0.6, sats: 1 },
]

const ease = (t: number) => t * t * (3 - 2 * t)

function sample(p: number) {
  let i = 0
  while (i < KEYS.length - 2 && p > KEYS[i + 1].p) i++
  const a = KEYS[i], b = KEYS[i + 1]
  const t = ease(THREE.MathUtils.clamp((p - a.p) / (b.p - a.p), 0, 1))
  const lerp = (x: number, y: number) => x + (y - x) * t
  const lv = (x: V3, y: V3): V3 => [lerp(x[0], y[0]), lerp(x[1], y[1]), lerp(x[2], y[2])]
  return { cam: lv(a.cam, b.cam), look: lv(a.look, b.look), eye: lerp(a.eye, b.eye), modis: lerp(a.modis, b.modis), viirs: lerp(a.viirs, b.viirs), seam: lerp(a.seam, b.seam), years: lerp(a.years, b.years), sats: lerp(a.sats, b.sats) }
}

function Rig() {
  const look = useRef(new THREE.Vector3(0, 1.1, 0))
  const cam = useRef(new THREE.Vector3(0, 0.9, 12.5))
  const smooth = useRef(0)
  const refs = useRef({ seam: { current: 0 }, modis: { current: 0 }, viirs: { current: 0 }, years: { current: 0 }, fires: { modis: 0, viirs: 0 }, eye: { eyeOpen: 0 } })
  const intro = useRef(0)
  const gate = useRef(landing.gate)

  useFrame((st, dt) => {
    intro.current = Math.min(1, intro.current + dt * 0.45)
    smooth.current = THREE.MathUtils.damp(smooth.current, landing.progress, 3.2, dt)
    gate.current = THREE.MathUtils.damp(gate.current, landing.gate, 2.4, dt)
    const s = sample(smooth.current)
    // The mode screen centres its title under the eye. Lowering the camera lifts the eye's pupil
    // to about 11% from the top, clear of the title and tagline; the globe rises behind the cards.
    const lift = gate.current * 1.5
    s.cam[1] -= lift
    s.look[1] -= lift
    const hover = landing.hover ? 1 : 0
    const r = refs.current
    r.seam.current = s.seam
    r.modis.current = s.sats
    r.viirs.current = s.sats * Math.max(s.viirs, 0.0001)
    r.years.current = s.years
    r.fires.modis = s.modis
    r.fires.viirs = s.viirs
    r.eye.eyeOpen = Math.min(s.eye * ease(intro.current), 1) + hover * 0.2
    landing.eyeOpen = r.eye.eyeOpen

    // drift with the pointer for depth; never moves data
    cam.current.set(s.cam[0] + st.pointer.x * 0.5, s.cam[1] + st.pointer.y * 0.3, s.cam[2])
    st.camera.position.lerp(cam.current, 1 - Math.exp(-dt * 4))
    look.current.lerp(new THREE.Vector3(...s.look), 1 - Math.exp(-dt * 4))
    st.camera.lookAt(look.current)
  })

  const r = refs.current
  return (
    <>
      <group position={[0, -1.2, 0]}>
        <Globe radius={2} fires={r.fires} />
        <Armillary seam={r.seam} modis={r.modis} viirs={r.viirs} years={r.years} />
      </group>
      <ThirdEye source={r.eye} size={4.6} position={[0, 3.6, -0.5]} />
    </>
  )
}

export default function LandingScene({ paused = false }: { paused?: boolean }) {
  return (
    <Canvas
      className="webgl"
      frameloop={paused ? 'never' : 'always'}
      dpr={[1, 1.75]}
      camera={{ fov: 38, near: 0.1, far: 200, position: [0, 0.9, 12.5] }}
      gl={{ antialias: false, powerPreference: 'high-performance', toneMapping: THREE.ACESFilmicToneMapping }}
    >
      <color attach="background" args={['#050708']} />
      <fog attach="fog" args={['#050708', 18, 60]} />
      <Suspense fallback={null}>
        <Lights />
        <Stars />
        <Embers count={360} y={-6} height={12} />
        <Rig />
        <Effects bloom={1.15} />
      </Suspense>
    </Canvas>
  )
}
