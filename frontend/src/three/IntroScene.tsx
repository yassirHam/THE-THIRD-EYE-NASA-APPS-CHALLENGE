import { Suspense, useMemo, useRef } from 'react'
import { Canvas, useFrame } from '@react-three/fiber'
import * as THREE from 'three'
import Globe from './Globe'
import ThirdEye from './ThirdEye'
import Park, { PARK_FOG, SKY_HORIZON } from './Park'
import Kid, { KID_EYE, KID_TIP, KID_TIP_WORLD } from './Kid'
import Satellite from './Satellite'
import SensorGrid from './SensorGrid'
import { Stars } from './Atmosphere'
import Effects, { type FocusState } from './Effects'
import Lights from './Lights'
import { intro } from './state'
import { prefersReducedMotion } from '../lib/random'

const KID_AT = new THREE.Vector3(0, 0, 4.2)
const KID_CHEST = new THREE.Vector3()
const KID_AT_ARR = KID_AT.toArray() as [number, number, number]
const GLOBE_R = 2.3
/** half the distance between the eyes, scaled up so the jump of the finger is easy to see */
const EYE_HALF = 0.034

// third person: behind the child's right shoulder, looking past the hand to the sundial and trees
const THIRD_POS = new THREE.Vector3(1.55, 1.3, 6.7)
const THIRD_LOOK = new THREE.Vector3(-0.55, 0.78, 1.4)
const FIRST_POS = KID_AT.clone().add(KID_EYE)
// portrait screens are narrow: stand further back and look at the child, not past them
const THIRD_POS_TALL = new THREE.Vector3(1.05, 1.5, 7.9)
const THIRD_LOOK_TALL = new THREE.Vector3(0.05, 0.8, 2.4)
// first person: level with the eyes and aimed through the finger tip, so it sits mid-frame on the tree line
const FIRST_LOOK = (() => {
  const eye = KID_AT.clone().add(KID_EYE), tip = KID_AT.clone().add(KID_TIP)
  const d = tip.sub(eye)
  const k = (eye.z + 20) / -d.z
  return new THREE.Vector3(eye.x + d.x * k, KID_EYE.y - 0.4, -20)
})()
const SPACE_BG = new THREE.Color('#030405')
const SPACE_FOG = new THREE.Color('#120a06')

function Orbiters() {
  const modis = useRef<THREE.Group>(null)
  const viirs = useRef<THREE.Group>(null)
  const mPos = useMemo(() => new THREE.Vector3(1.5, 1.75, 1.2), [])
  const vPos = useMemo(() => new THREE.Vector3(-1.5, 1.75, 1.2), [])
  useFrame(({ clock }) => {
    const t = clock.elapsedTime
    const set = (g: THREE.Group | null, w: number, base: THREE.Vector3, ph: number) => {
      if (!g) return
      g.visible = w > 0.04
      g.scale.setScalar(0.72 * THREE.MathUtils.smoothstep(w, 0, 1))
      g.position.set(base.x, base.y + Math.sin(t * 0.7 + ph) * 0.04, base.z)
      g.rotation.set(0.35, -0.5 + Math.sin(t * 0.3 + ph) * 0.05, 0.1)
    }
    set(modis.current, intro.tintR, mPos, 0)
    set(viirs.current, intro.tintL, vPos, 2)
  })
  return (
    <>
      <Satellite ref={modis} tone="modis" />
      <Satellite ref={viirs} tone="viirs" />
    </>
  )
}

function Worlds({ focus }: { focus: FocusState }) {
  const stones = useRef<THREE.Group>(null)
  const space = useRef<THREE.Group>(null)
  const earth = useRef<THREE.Group>(null)
  const eyeGroup = useRef<THREE.Group>(null)
  const fires = useRef({ modis: 1, viirs: 1 })
  const eye = useRef({ eyeOpen: 0 })
  const v = useMemo(() => ({ pos: new THREE.Vector3(), dirA: new THREE.Vector3(), dirB: new THREE.Vector3(), lookB: new THREE.Vector3(), look: new THREE.Vector3() }), [])
  const reduced = useMemo(prefersReducedMotion, [])

  useFrame((st) => {
    const inEarth = intro.world > 0.5
    if (stones.current) stones.current.visible = !inEarth
    if (space.current) space.current.visible = inEarth
    // daylight haze in the park, the old dark fog in space
    const fog = st.scene.fog as THREE.Fog | null
    if (fog) {
      fog.color.copy(inEarth ? SPACE_FOG : SKY_HORIZON)
      fog.near = inEarth ? 9 : PARK_FOG.near
      fog.far = inEarth ? 40 : PARK_FOG.far
    }
    if (st.scene.background instanceof THREE.Color) st.scene.background.copy(inEarth ? SPACE_BG : SKY_HORIZON)
    if (earth.current) {
      earth.current.visible = inEarth
      // portrait screens stack the narration above or below the globe, so the globe moves
      // vertically instead of sideways and shrinks to fit the narrow frame
      const portrait = st.size.width / st.size.height < 0.8
      const side = Math.sign(intro.globeX) * Math.min(1, Math.abs(intro.globeX) / 2.25)
      earth.current.position.x = portrait ? side * 0.55 : intro.globeX
      earth.current.position.y = THREE.MathUtils.lerp(portrait ? -side * 1.7 : 0.55, -5.3, intro.rise)
      earth.current.scale.setScalar(THREE.MathUtils.lerp(portrait ? 0.62 : 1, 1.55, intro.rise))
    }
    fires.current.modis = intro.fireModis
    fires.current.viirs = intro.fireViirs
    eye.current.eyeOpen = intro.eyeOpen
    if (eyeGroup.current) {
      eyeGroup.current.visible = inEarth && intro.rise > 0.01
      eyeGroup.current.position.y = THREE.MathUtils.lerp(-0.6, 1.55, intro.rise)
      eyeGroup.current.scale.setScalar(THREE.MathUtils.lerp(0.6, 0.86, intro.rise))
    }
    const cam = st.camera
    if (!inEarth) {
      // the camera moves from behind the child into their eyes; then each eye is a small hop,
      // which makes the near finger jump while the far trees stay put
      const p = intro.pov
      const t = st.clock.elapsedTime
      const drift = (1 - p) * 0.12
      const tall = st.size.width / st.size.height < 0.8
      v.pos.copy(tall ? THIRD_POS_TALL : THIRD_POS).add(new THREE.Vector3(Math.sin(t * 0.21) * drift, Math.sin(t * 0.17) * drift * 0.4, 0))
      v.dirA.subVectors(tall ? THIRD_LOOK_TALL : THIRD_LOOK, v.pos).normalize()
      const fp = FIRST_POS.clone()
      // a smaller hop on narrow screens keeps the jumping finger inside the frame
      fp.x += intro.camX * EYE_HALF * (tall ? 0.6 : 1)
      // a seated person's head is never still: breathing lifts it, and it drifts a few
      // millimetres while they hold a pose. None of this moves the eyes apart.
      const h = reduced ? 0 : p
      fp.x += (Math.sin(t * 0.37) * 0.6 + Math.sin(t * 0.83 + 1.3) * 0.4) * 0.0035 * h
      fp.y += Math.sin(t * 1.55 + 0.6) * 0.0028 * h + Math.sin(t * 0.29) * 0.002 * h
      v.dirB.subVectors(FIRST_LOOK, fp).normalize()
      v.lookB.set((Math.sin(t * 0.41 + 0.5) * 0.6 + Math.sin(t * 0.97) * 0.4) * 0.006 * h, Math.sin(t * 0.53 + 2) * 0.004 * h, 0)
      v.dirB.add(v.lookB).normalize()
      v.pos.lerp(fp, p)
      // on the way in the camera rises over the shoulder instead of sliding through it
      v.pos.y += Math.sin(Math.PI * p) * 0.09
      // the gaze turns a beat ahead of the body, as a person looks first and then moves
      v.dirA.lerp(v.dirB, THREE.MathUtils.smoothstep(p, 0, 0.82)).normalize()
      cam.position.copy(v.pos)
      v.look.copy(v.pos).add(v.dirA)
      // focus: on the child from behind, on the finger tip through their eyes
      const f = THREE.MathUtils.smoothstep(p, 0.35, 0.95)
      KID_CHEST.set(KID_AT.x, KID_AT.y + 0.8, KID_AT.z)
      focus.target.lerpVectors(KID_CHEST, KID_TIP_WORLD.lengthSq() > 0 ? KID_TIP_WORLD : FIRST_POS, f)
      focus.range = THREE.MathUtils.lerp(3.2, 0.5, f)
      focus.bokeh = THREE.MathUtils.lerp(1.1, 2.4, f)
    } else {
      cam.position.set(0, THREE.MathUtils.lerp(0.2, 0.4, intro.rise), THREE.MathUtils.lerp(8.6, 12.5, intro.rise))
      v.look.set(0, THREE.MathUtils.lerp(0.1, 0.2, intro.rise), 0)
      focus.bokeh = 0
    }
    cam.lookAt(v.look)
  })

  return (
    <>
      <group ref={stones}>
        <Park kidAt={KID_AT_ARR} />
        <Kid position={KID_AT_ARR} />
      </group>
      <group ref={space} visible={false}>
        <Stars count={1800} />
      </group>
      <group ref={earth} visible={false}>
        <Globe radius={GLOBE_R} fires={fires.current} spin={0.03} />
        <SensorGrid radius={GLOBE_R} state={intro} />
        <Orbiters />
      </group>
      <group ref={eyeGroup} visible={false}>
        <ThirdEye source={eye.current} size={4.4} follow={false} />
      </group>
    </>
  )
}

export default function IntroScene() {
  const focus = useMemo<FocusState>(() => ({ target: new THREE.Vector3(0, 0.8, 4.2), range: 3, bokeh: 0 }), [])
  return (
    <Canvas
      className="webgl"
      shadows
      dpr={[1, 1.75]}
      camera={{ fov: 40, near: 0.05, far: 200, position: THIRD_POS.toArray() as [number, number, number] }}
      gl={{ antialias: false, toneMapping: THREE.ACESFilmicToneMapping }}
    >
      <color attach="background" args={['#030405']} />
      <fog attach="fog" args={['#120a06', 9, 40]} />
      <Suspense fallback={null}>
        <Lights />
        <Worlds focus={focus} />
        <Effects bloom={1.0} eyes={intro} focus={focus} />
      </Suspense>
    </Canvas>
  )
}
