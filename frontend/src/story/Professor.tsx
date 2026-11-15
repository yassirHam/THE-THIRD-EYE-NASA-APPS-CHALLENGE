import { Canvas, useFrame, useThree } from '@react-three/fiber'
import { useGLTF } from '@react-three/drei'
import { Suspense, useEffect, useMemo, useRef, useState, type ReactNode } from 'react'
import * as THREE from 'three'
import { prefersReducedMotion } from '../lib/random'

/* Professor Orez, built from celestar-character-2026-11-14T14-10-07.json (a minefun avatar export,
   shown in the celestar-character-*.png turnaround shots at the repo root).
   The six cosmetics in that file are the original GLBs, copied into public/professor/ so the static
   site never calls the minefun CDN: long blonde hair, brown eyes, a gold monocle on a chain, a gold
   watch on the right wrist, and two boot models worn together (black sneakers under winged gold
   "God shoes"). The skin uses minefun's own rounded-body UV layout, which needs their base mesh, so
   the body is a set of boxes painted pixel by pixel in the skin's palette
   (frontend/source-models/skin_suit.png): black suit jacket over a gold waistcoat, white shirt and
   black tie, black trousers, dark fingerless gloves with a pink cuff band.
   The rig is in the export's units: about 2.26 tall, feet at y = 0, facing -z. */

export type ProfessorMood = 'thinking' | 'explaining' | 'wrong' | 'correct' | 'reveal'

/** Colours sampled from the avatar skin. They belong to the character, not to the interface palette. */
const C = {
  skin: '#fec1a2', cheek: '#fea79d', mouth: '#ee8899', mouthLight: '#f6d3cf',
  suit: '#201f22', suitDark: '#171618', suitLight: '#2b2928', suitEdge: '#393635',
  shirt: '#cfd6d7', shirtShade: '#b1b9bb', tie: '#0d0d0e',
  gold: '#fbc500', goldMid: '#f5a300', goldDark: '#ef8e00', goldDeep: '#d87800',
  glove: '#393635', gloveDark: '#2b2928', band: '#ee8899', bandDark: '#d76f80',
}

const FILES = {
  hair: '/professor/long_blonde.glb',
  eyes: '/professor/brown_eyes.glb',
  monocle: '/professor/monocle.glb',
  watch: '/professor/watches.glb',
  boots: '/professor/blacky.glb',
  wings: '/professor/god_shoes.glb',
}

/* ---------- pixel textures ---------- */

type Painter = (px: (x: number, y: number, w: number, h: number, c: string) => void) => void

function texture(w: number, h: number, draw: Painter) {
  const cv = document.createElement('canvas')
  cv.width = w
  cv.height = h
  const ctx = cv.getContext('2d')!
  draw((x, y, ww, hh, c) => { ctx.fillStyle = c; ctx.fillRect(x, y, ww, hh) })
  const t = new THREE.CanvasTexture(cv)
  t.magFilter = THREE.NearestFilter
  t.minFilter = THREE.NearestFilter
  t.generateMipmaps = false
  t.colorSpace = THREE.SRGBColorSpace
  return t
}

const mat = (t: THREE.Texture) => new THREE.MeshLambertMaterial({ map: t })
/** BoxGeometry face order: +x, -x, +y, -y, +z (back), -z (front). */
const faces = (side: THREE.Texture, top: THREE.Texture, bottom: THREE.Texture, back: THREE.Texture, front: THREE.Texture, side2 = side) =>
  [mat(side), mat(side2), mat(top), mat(bottom), mat(back), mat(front)]

function useMaterials() {
  return useMemo(() => {
    const flat = (c: string) => texture(2, 2, (p) => p(0, 0, 2, 2, c))

    // head: 10 x 10, bare face with blush and a small smile; the eyes are their own model
    const face = texture(10, 10, (p) => {
      p(0, 0, 10, 10, C.skin)
      p(1, 6, 2, 1, C.cheek); p(7, 6, 2, 1, C.cheek)
      p(4, 7, 2, 1, C.mouthLight); p(4, 8, 2, 1, C.mouth)
    })
    const headSkin = flat(C.skin)

    // torso: 16 x 24, open black jacket over a gold waistcoat, white shirt collar and black tie
    const chest = texture(16, 24, (p) => {
      p(0, 0, 16, 24, C.suit)
      p(0, 0, 1, 24, C.suitLight); p(15, 0, 1, 24, C.suitDark)
      p(4, 0, 8, 22, C.shirt) // shirt
      p(5, 0, 6, 3, C.shirtShade)
      p(4, 3, 8, 18, C.gold) // waistcoat, darker toward the bottom
      p(4, 11, 8, 10, C.goldMid)
      p(4, 17, 8, 4, C.goldDark)
      p(6, 3, 4, 3, C.shirt) // V neck shows the shirt
      p(7, 0, 2, 8, C.tie); p(6, 0, 4, 1, C.tie) // tie knot and tail
      for (let y = 9; y < 21; y += 3) p(7, y, 2, 1, C.suitLight) // buttons
      p(4, 3, 1, 18, C.goldDeep); p(11, 3, 1, 18, C.goldDeep)
      p(3, 0, 1, 24, C.suitEdge); p(12, 0, 1, 24, C.suitEdge) // lapel edges
      p(4, 21, 8, 1, C.shirtShade) // shirt below the waistcoat
    })
    const suitBack = texture(16, 24, (p) => {
      p(0, 0, 16, 24, C.suit)
      p(0, 0, 16, 2, C.suitLight)
      p(0, 18, 16, 6, C.suitDark)
    })
    const suitSide = texture(8, 24, (p) => { p(0, 0, 8, 24, C.suit); p(0, 0, 8, 2, C.suitEdge) })
    const suitTop = flat(C.suit)
    const collarTop = texture(16, 8, (p) => { p(0, 0, 16, 8, C.suit); p(5, 2, 6, 4, C.shirt); p(7, 2, 2, 3, C.tie) })

    // sleeves: black jacket to the wrist, a pink cuff band, a dark fingerless glove and bare fingers
    const sleeve = texture(8, 24, (p) => {
      p(0, 0, 8, 24, C.suit)
      p(0, 0, 8, 4, C.suitLight)
      p(0, 0, 1, 24, C.suitLight); p(7, 0, 1, 24, C.suitDark)
      p(0, 15, 8, 1, C.band); p(0, 16, 8, 1, C.bandDark)
      p(0, 17, 8, 5, C.glove)
      p(2, 18, 2, 2, C.tie)
      p(0, 22, 8, 2, C.skin)
    })
    const hand = flat(C.skin)

    // trousers: black with a knee crease
    const trouser = texture(8, 28, (p) => {
      p(0, 0, 8, 28, C.suit)
      p(0, 0, 1, 28, C.suitLight)
      p(1, 13, 6, 1, C.suitDark); p(1, 14, 6, 3, C.suitDark)
    })
    const trouserBack = texture(8, 28, (p) => { p(0, 0, 8, 28, C.suitDark); p(0, 12, 8, 2, C.tie) })
    const trouserTop = flat(C.suit)

    return {
      head: faces(headSkin, headSkin, headSkin, headSkin, face),
      torso: faces(suitSide, collarTop, suitTop, suitBack, chest),
      arm: faces(sleeve, suitTop, hand, sleeve, sleeve),
      leg: faces(trouser, trouserTop, trouserTop, trouserBack, trouser),
    }
  }, [])
}

/* ---------- cosmetics from the avatar export ---------- */

function useCosmetic(url: string, keep?: string) {
  const { scene } = useGLTF(url)
  return useMemo(() => {
    const s = scene.clone(true)
    s.traverse((o) => {
      const m = o as THREE.Mesh
      if (!m.isMesh) return
      const src = m.material as THREE.MeshStandardMaterial
      if (src.map) { src.map.magFilter = THREE.NearestFilter; src.map.minFilter = THREE.NearestFilter; src.map.generateMipmaps = false; src.map.needsUpdate = true }
      m.material = new THREE.MeshLambertMaterial({ map: src.map ?? null, transparent: src.transparent, alphaTest: 0.5, side: THREE.DoubleSide })
    })
    if (keep) {
      // each boot file holds both boots; each leg wears only its own
      for (const name of ['LeftBoot', 'RightBoot']) { const n = s.getObjectByName(name); if (n) n.visible = name === keep }
    }
    return s
  }, [scene, keep])
}

/* ---------- rig ---------- */

const NECK = 1.62
const HIP = 0.88
const SHOULDER = 1.58
const EYE = new THREE.Vector3(0, 1.91, -0.25)

interface Pose {
  lift: number; lean: number; yaw: number
  headX: number; headY: number; headZ: number
  leadX: number; leadZ: number; offX: number; offZ: number
  legL: number; legR: number
}

const REST: Pose = { lift: 0, lean: 0, yaw: 0, headX: 0, headY: 0, headZ: 0, leadX: 0, leadZ: 0.08, offX: 0, offZ: -0.08, legL: 0, legR: 0 }

/** Target pose for a mood at time t, s seconds after the mood began (and w seconds into a wave). */
function pose(mood: ProfessorMood, t: number, s: number, w: number | null): Pose {
  const p = { ...REST }
  const breathe = Math.sin(t * 1.6) * 0.012
  p.lift = breathe
  const settle = Math.exp(-s * 1.8)
  switch (mood) {
    case 'explaining':
      // the lead hand talks, the other rests on the hip
      p.leadX = 0.95 + Math.sin(t * 1.9) * 0.18
      p.leadZ = 0.45 + Math.sin(t * 2.7) * 0.12
      p.offZ = -0.22; p.offX = 0.15
      p.headY = -0.18 + Math.sin(t * 0.8) * 0.12
      p.headZ = Math.sin(t * 1.1) * 0.04
      p.yaw = -0.18
      break
    case 'thinking':
      // points at the question, head turned toward it
      p.leadZ = 0.95; p.leadX = 1.3 + Math.sin(t * 2.2) * 0.04
      p.offZ = -0.2; p.offX = 0.2
      p.headY = -0.42; p.headZ = 0.12 + Math.sin(t * 1.3) * 0.03
      p.yaw = -0.32
      p.lean = -0.04
      p.legL = 0.12
      break
    case 'wrong':
      // a small shrug, shaking his head
      p.leadZ = 0.38; p.leadX = 0.55; p.offZ = -0.38; p.offX = 0.55
      p.headY = Math.sin(s * 11) * 0.38 * Math.max(settle, 0.12)
      p.headX = -0.14
      p.lean = 0.05
      break
    case 'correct': {
      // a hop with both arms up, then a raised fist
      const hop = Math.abs(Math.sin(s * 7)) * 0.16 * settle
      p.lift += hop
      p.leadZ = 2.4 * (0.35 + 0.65 * settle) + 0.4; p.leadX = 0.6 * (1 - settle)
      p.offZ = -2.4 * settle - 0.3
      p.headX = 0.18 * settle
      p.legL = -0.25 * settle; p.legR = 0.25 * settle
      p.yaw = -0.15
      break
    }
    case 'reveal':
      // startled: leans back, hands up
      p.lean = 0.14; p.headX = 0.24
      p.leadZ = 2.0; p.leadX = 0.4; p.offZ = -2.0; p.offX = 0.4
      p.lift += Math.abs(Math.sin(s * 14)) * 0.05 * settle
      break
  }
  if (w !== null) {
    // clicked: he waves back
    const k = Math.min(1, w * 6) * Math.min(1, Math.max(0, (1.4 - w) * 4))
    p.leadZ = p.leadZ + (2.75 - p.leadZ) * k
    p.leadX = p.leadX * (1 - k) + Math.sin(w * 14) * 0.35 * k
    p.headY *= 1 - k
  }
  return p
}

function Figure({ mood, reduced, still }: { mood: ProfessorMood; reduced: boolean; still: boolean }) {
  const m = useMaterials()
  const hair = useCosmetic(FILES.hair)
  const eyes = useCosmetic(FILES.eyes)
  const monocle = useCosmetic(FILES.monocle)
  const watch = useCosmetic(FILES.watch)
  const bootL = useCosmetic(FILES.boots, 'LeftBoot')
  const bootR = useCosmetic(FILES.boots, 'RightBoot')
  const wingL = useCosmetic(FILES.wings, 'LeftBoot')
  const wingR = useCosmetic(FILES.wings, 'RightBoot')

  const root = useRef<THREE.Group>(null)
  const body = useRef<THREE.Group>(null)
  const head = useRef<THREE.Group>(null)
  const eyeLid = useRef<THREE.Group>(null)
  const lead = useRef<THREE.Group>(null)
  const off = useRef<THREE.Group>(null)
  const legL = useRef<THREE.Group>(null)
  const legR = useRef<THREE.Group>(null)

  const cur = useRef<Pose>({ ...REST })
  const moodAt = useRef(0)
  const waveAt = useRef<number | null>(null)
  const nextBlink = useRef(2)
  const blinkAt = useRef(-1)
  const entered = useRef(reduced || still ? 1 : 0)
  const { invalidate, clock } = useThree()

  useEffect(() => { moodAt.current = clock.elapsedTime; invalidate() }, [mood, clock, invalidate])
  useEffect(() => {
    const onWave = () => { waveAt.current = clock.elapsedTime; blinkAt.current = clock.elapsedTime; invalidate() }
    window.addEventListener('professor-wave', onWave)
    return () => window.removeEventListener('professor-wave', onWave)
  }, [clock, invalidate])

  useFrame((_, dt) => {
    const t = still ? 0 : clock.elapsedTime
    const s = still ? 10 : t - moodAt.current
    const wv = waveAt.current === null || still ? null : t - waveAt.current
    if (wv !== null && wv > 1.6) waveAt.current = null
    const target = pose(mood, t, s, wv)
    const c = cur.current
    const k = still ? 1 : 1 - Math.exp(-dt * 9)
    for (const key of Object.keys(target) as (keyof Pose)[]) c[key] += (target[key] - c[key]) * k

    // walks in from the right on first appearance
    entered.current = still ? 1 : Math.min(1, entered.current + dt * 1.4)
    const e = 1 - Math.pow(1 - entered.current, 3)

    if (root.current) {
      root.current.position.x = (1 - e) * 1.6
      root.current.position.y = c.lift
      root.current.rotation.y = Math.PI + c.yaw
    }
    if (body.current) body.current.rotation.x = c.lean
    if (head.current) head.current.rotation.set(c.headX, c.headY, c.headZ)
    if (lead.current) lead.current.rotation.set(c.leadX, 0, c.leadZ)
    if (off.current) off.current.rotation.set(c.offX, 0, c.offZ)
    // a stride while walking in, otherwise the pose's own stance
    const stride = (1 - e) * Math.sin(t * 12) * 0.5
    if (legL.current) legL.current.rotation.x = c.legL + stride
    if (legR.current) legR.current.rotation.x = c.legR - stride

    // blinks every few seconds, and when clicked
    if (!still && t > nextBlink.current) { blinkAt.current = t; nextBlink.current = t + 2.4 + Math.random() * 3 }
    const b = t - blinkAt.current
    const lid = still || b < 0 || b > 0.16 ? 1 : Math.abs(b - 0.08) / 0.08
    if (eyeLid.current) eyeLid.current.scale.y = Math.max(0.08, lid)
  })

  const box = (size: [number, number, number], pos: [number, number, number], mats: THREE.Material[]) => (
    <mesh position={pos} material={mats}><boxGeometry args={size} /></mesh>
  )

  return (
    <group ref={root} rotation-y={Math.PI}>
      {/* legs pivot at the hip; the boots keep the export's own placement */}
      {[{ r: legL, x: -0.125, boot: bootL, wing: wingL }, { r: legR, x: 0.125, boot: bootR, wing: wingR }].map(({ r, x, boot, wing }) => (
        <group key={x} ref={r} position={[0, HIP, 0]}>
          {box([0.245, HIP - 0.06, 0.25], [x, -(HIP + 0.06) / 2, 0], m.leg)}
          <primitive object={boot} position={[0, -HIP, 0]} />
          <primitive object={wing} position={[0, -HIP, 0]} />
        </group>
      ))}

      <group ref={body} position={[0, HIP, 0]}>
        <group position={[0, -HIP, 0]}>
          {box([0.5, NECK - HIP, 0.26], [0, (NECK + HIP) / 2, 0], m.torso)}
          {/* the lead arm is on +x, which faces screen left after the half turn: it points at the text */}
          <group ref={lead} position={[0.37, SHOULDER, 0]} rotation-order="ZYX">
            {box([0.24, 0.74, 0.25], [0, -0.33, 0], m.arm)}
            {/* the watch is on the right wrist in the export, which is this arm */}
            <primitive object={watch} position={[-0.37, -SHOULDER, 0]} />
          </group>
          <group ref={off} position={[-0.37, SHOULDER, 0]} rotation-order="ZYX">{box([0.24, 0.74, 0.25], [0, -0.33, 0], m.arm)}</group>

          <group ref={head} position={[0, NECK, 0]}>
            <group position={[0, -NECK, 0]}>
              {box([0.5, 0.52, 0.5], [0, NECK + 0.27, 0.01], m.head)}
              <group ref={eyeLid} position={EYE.toArray()}>
                <primitive object={eyes} position={EYE.clone().negate().toArray()} />
              </group>
              <primitive object={monocle} />
              <primitive object={hair} />
            </group>
          </group>
        </group>
      </group>
    </group>
  )
}

function Rig({ children }: { children: ReactNode }) {
  const { camera, size, invalidate } = useThree()
  useEffect(() => {
    // frame the whole figure, with room on the left for the pointing arm
    const cam = camera as THREE.PerspectiveCamera
    const aspect = size.width / Math.max(1, size.height)
    const tall = 2.62
    const fit = Math.max(tall, 1.7 / aspect)
    // feet near the bottom edge, so he stands on the name plate rather than floating above it
    const y = fit / 2 - 0.12
    cam.position.set(-0.12, y, fit / (2 * Math.tan(THREE.MathUtils.degToRad(cam.fov / 2))))
    cam.lookAt(-0.12, y, 0)
    cam.updateProjectionMatrix()
    invalidate()
  }, [camera, size, invalidate])
  return <>{children}</>
}

export default function Professor({ mood, paused }: { mood: ProfessorMood; paused: boolean }) {
  const [reduced] = useState(prefersReducedMotion)
  const still = paused || reduced
  const [hello, setHello] = useState(0)
  const wave = () => { setHello((n) => n + 1); window.dispatchEvent(new Event('professor-wave')) }
  return (
    <div className={`professor professor--${mood}`} data-wave={hello}>
      <button type="button" className="professor__hit" onClick={wave} data-cursor="Wave" aria-label="Professor Orez, your guide. Wave hello." />
      <div className="professor__stage" aria-hidden="true">
        <Canvas
          frameloop={still ? 'demand' : 'always'}
          dpr={[1, 1.75]}
          camera={{ fov: 24, near: 0.1, far: 40 }}
          gl={{ alpha: true, antialias: false, powerPreference: 'high-performance' }}
        >
          <ambientLight intensity={1.15} />
          <directionalLight position={[-3, 5, 4]} intensity={1.7} color="#ffcf8f" />
          <directionalLight position={[3, -1, -3]} intensity={0.55} color="#7fb6b8" />
          {/* cool light from the side so the black suit keeps its outline on the dark page */}
          <directionalLight position={[4, 2, 1]} intensity={1.1} color="#a9d3d5" />
          <Suspense fallback={null}>
            <Rig><Figure mood={mood} reduced={reduced} still={still} /></Rig>
          </Suspense>
        </Canvas>
      </div>
      {mood === 'thinking' && <QuestionMarks />}
      <p className="professor__name"><span>Professor</span> Orez</p>
    </div>
  )
}

/** Pixel question marks that pop in once when he asks something. */
function QuestionMarks() {
  const glyph = ['.###.', '#...#', '....#', '...#.', '..#..', '.....', '..#..']
  const cells = glyph.flatMap((row, y) => [...row].map((ch, x) => (ch === '#' ? <rect key={`${x}-${y}`} x={x} y={y} width="1" height="1" /> : null)))
  return (
    <div className="professor__qs" aria-hidden="true">
      {[0, 1, 2].map((i) => <svg key={i} className={`professor__q professor__q--${i}`} viewBox="0 0 5 7" shapeRendering="crispEdges">{cells}</svg>)}
    </div>
  )
}

for (const url of Object.values(FILES)) useGLTF.preload(url)
