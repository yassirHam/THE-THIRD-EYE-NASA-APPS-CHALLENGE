import { useLayoutEffect, useMemo, useRef, type RefObject } from 'react'
import { useFrame } from '@react-three/fiber'
import * as THREE from 'three'
import { RoundedBoxGeometry } from 'three/examples/jsm/geometries/RoundedBoxGeometry.js'
import { prefersReducedMotion } from '../lib/random'
import { intro } from './state'

/* A child sitting on a park bench, swinging their feet, a toy satellite in the left hand and the
   right index finger held up at arm's length. The intro first sees them from behind the
   shoulder, then the camera moves into their eyes. The body fades as the camera arrives, so the
   view never passes through the head; the right arm and hand stay. */

/** Seat height of the bench the child sits on. */
export const SEAT_Y = 0.43
/** Eye height and the finger tip, in the kid's local space (the kid faces -z). */
export const KID_EYE = new THREE.Vector3(0, 0.99, -0.07)
export const KID_TIP = new THREE.Vector3(0.022, 0.975, -0.44)
/** Where the finger tip actually is this frame, in world space, after the arm has moved. */
export const KID_TIP_WORLD = new THREE.Vector3()

const Y = new THREE.Vector3(0, 1, 0)
const v = (x: number, y: number, z: number) => new THREE.Vector3(x, y, z)

function limb(a: THREE.Vector3, b: THREE.Vector3, r: number, radial = 14) {
  const d = new THREE.Vector3().subVectors(b, a)
  const len = d.length()
  const g = new THREE.CapsuleGeometry(r, Math.max(len - r * 2, 0.001), 6, radial)
  g.applyQuaternion(new THREE.Quaternion().setFromUnitVectors(Y, d.normalize()))
  g.translate((a.x + b.x) / 2, (a.y + b.y) / 2, (a.z + b.z) / 2)
  return g
}

function ball(r: number, at: THREE.Vector3, s: [number, number, number] = [1, 1, 1], w = 24, h = 18) {
  const g = new THREE.SphereGeometry(r, w, h)
  g.scale(...s)
  g.translate(at.x, at.y, at.z)
  return g
}

const TIP_LOCAL = v(-0.017, 0.133, -0.006)

/** A finger as one smooth tube through its joints, thinning toward the tip, with rounded ends. */
function digit(pts: THREE.Vector3[], r: number, tipR: number) {
  const curve = new THREE.CatmullRomCurve3(pts, false, 'centripetal')
  const seg = 18, radial = 12
  const g = new THREE.TubeGeometry(curve, seg, r, radial, false)
  const pos = g.attributes.position as THREE.BufferAttribute
  const p = new THREE.Vector3(), c = new THREE.Vector3()
  for (let i = 0; i <= seg; i++) {
    curve.getPointAt(i / seg, c)
    const k = THREE.MathUtils.lerp(1, tipR / r, i / seg)
    for (let j = 0; j <= radial; j++) {
      const n = i * (radial + 1) + j
      p.fromBufferAttribute(pos, n).sub(c).multiplyScalar(k).add(c)
      pos.setXYZ(n, p.x, p.y, p.z)
    }
  }
  g.computeVertexNormals()
  return [g, ball(r, pts[0], [1, 1, 1], 14, 10), ball(tipR, pts[pts.length - 1], [1, 1, 1], 14, 10)]
}

/* The right hand, in its own frame: the wrist at the origin, the hand standing up (+y), the back
   of the hand toward the viewer (+z), the palm away (-z). For a right hand held like this the
   thumb is on the left (-x), the index finger next to it. */
function makeHand() {
  const W = 0.058, H = 0.066
  const palm = new RoundedBoxGeometry(W, H, 0.026, 3, 0.011)
  {
    // narrower at the wrist, a little domed across the back
    const pos = palm.attributes.position as THREE.BufferAttribute
    for (let i = 0; i < pos.count; i++) {
      const x = pos.getX(i), y = pos.getY(i), z = pos.getZ(i)
      const t = (y + H / 2) / H
      pos.setX(i, x * (0.84 + 0.16 * t))
      if (z > 0) pos.setZ(i, z + 0.004 * (1 - (2 * x / W) ** 2))
    }
    palm.computeVertexNormals()
  }
  palm.translate(0, H / 2, -0.002)
  // index finger: up from the knuckle, bending very slightly forward
  const index = digit([v(-0.018, 0.058, 0), v(-0.018, 0.093, -0.003), v(-0.0175, 0.115, -0.0055), TIP_LOCAL], 0.0093, 0.0079)
  // middle, ring and little finger curl forward and down into the palm
  const curled = [
    { x: -0.003, y: 0.062, r: 0.0093 },
    { x: 0.0115, y: 0.06, r: 0.009 },
    { x: 0.0245, y: 0.054, r: 0.008 },
  ].flatMap(({ x, y, r }) => digit([v(x, y, 0), v(x, y + 0.01, -0.02), v(x, y - 0.006, -0.036), v(x, y - 0.024, -0.03)], r, r * 0.85))
  // thumb: from the heel of the palm, out, then across the front of the curled fingers
  const thumb = digit([v(-0.022, 0.014, -0.004), v(-0.035, 0.034, -0.016), v(-0.026, 0.047, -0.032), v(-0.008, 0.05, -0.038)], 0.0108, 0.0088)
  // knuckles show as low bumps on the back of the fist
  const knuckles = [-0.018, -0.003, 0.0115, 0.0245].map((x, i) => ball(0.0078, v(x, i === 3 ? 0.054 : 0.06, 0.006), [1.15, 0.8, 0.7], 12, 10))
  const nail = ball(0.0048, v(TIP_LOCAL.x, TIP_LOCAL.y - 0.0075, TIP_LOCAL.z + 0.0066), [0.9, 1.25, 0.22], 12, 10)
  return { skin: [palm, ...index, ...curled, ...thumb, ...knuckles], nail }
}
function makeParts() {
  const s = SEAT_Y
  // shirt: a lathe from the waist to the collar, flattened front to back
  const shirt = new THREE.LatheGeometry(
    [[0.0, s + 0.05], [0.128, s + 0.05], [0.134, s + 0.1], [0.13, s + 0.2], [0.137, s + 0.3], [0.13, s + 0.37], [0.1, s + 0.405], [0.05, s + 0.425], [0.0, s + 0.43]].map(([r, y]) => new THREE.Vector2(r, y)),
    30,
  )
  shirt.scale(1, 1, 0.74)
  const hem = new THREE.TorusGeometry(0.13, 0.012, 8, 32)
  hem.rotateX(Math.PI / 2); hem.scale(1, 1, 0.74); hem.translate(0, s + 0.06, 0)
  const collar = new THREE.TorusGeometry(0.052, 0.01, 8, 24)
  collar.rotateX(Math.PI / 2 + 0.12); collar.translate(0, s + 0.425, -0.004)
  // shorts: hips and thighs, resting on the bench and reaching forward to the knees
  const shorts = [
    ball(0.13, v(0, s + 0.06, 0.02), [1, 0.55, 0.85]),
    limb(v(-0.068, s + 0.06, 0.02), v(-0.08, s + 0.058, -0.2), 0.058),
    limb(v(0.068, s + 0.06, 0.02), v(0.08, s + 0.058, -0.2), 0.058),
  ]
  const thighs = [limb(v(-0.08, s + 0.058, -0.16), v(-0.082, s + 0.055, -0.27), 0.047), limb(v(0.08, s + 0.058, -0.16), v(0.082, s + 0.055, -0.27), 0.047)]
  // shins hang from the knee; each lives in its own frame so it can swing
  const shin = limb(v(0, 0, 0), v(0, -0.27, 0.02), 0.037)
  const sock = limb(v(0, -0.25, 0.018), v(0, -0.3, 0.022), 0.034)
  const shoe = ball(0.05, v(0, -0.32, -0.025), [0.85, 0.65, 1.6])
  const sole = ball(0.051, v(0, -0.338, -0.025), [0.88, 0.25, 1.62])
  const neck = limb(v(0, s + 0.4, -0.005), v(0, s + 0.5, -0.01), 0.038)
  // head: a cranium, a softer jaw, small nose and ears
  const head = [
    ball(0.106, v(0, 0.995, -0.005), [0.93, 1.0, 1.0], 36, 28),
    ball(0.074, v(0, 0.945, -0.035), [1.0, 0.82, 1.0]),
    ball(0.014, v(0, 0.982, -0.11), [0.8, 1, 0.9], 12, 10),
    ball(0.022, v(-0.097, 0.985, 0.0), [0.45, 1, 0.8], 12, 10),
    ball(0.022, v(0.097, 0.985, 0.0), [0.45, 1, 0.8], 12, 10),
  ]
  // hair: a cap over the top and back, with a few tufts so the outline is not a perfect dome
  const cap = new THREE.SphereGeometry(0.113, 36, 18, 0, Math.PI * 2, 0, Math.PI * 0.56)
  cap.rotateX(0.42)
  cap.scale(0.95, 1.02, 1.03)
  cap.translate(0, 1.0, 0.004)
  const tufts = [
    [0.0, 1.095, 0.0, 0.05], [0.045, 1.085, 0.03, 0.045], [-0.05, 1.08, 0.025, 0.045], [0.02, 1.06, 0.075, 0.048],
    [-0.03, 1.04, 0.085, 0.045], [0.06, 1.03, 0.06, 0.04], [-0.065, 1.035, 0.05, 0.04], [0.0, 1.075, -0.06, 0.04],
    [0.04, 1.068, -0.07, 0.032], [-0.04, 1.066, -0.068, 0.032],
  ].map(([x, y, z, r]) => ball(r, v(x, y, z), [1, 0.8, 1], 14, 10))
  // left arm rests on the lap, holding the toy
  const lShoulder = v(-0.125, s + 0.37, 0.0), lElbow = v(-0.16, s + 0.2, -0.06), lWrist = v(-0.07, s + 0.15, -0.21)
  const leftSleeve = limb(lShoulder, lShoulder.clone().lerp(lElbow, 0.45), 0.047)
  const leftArm = [limb(lShoulder, lElbow, 0.033), limb(lElbow, lWrist, 0.029), ball(0.03, lWrist.clone().add(v(0.008, 0.008, -0.026)), [0.9, 0.75, 1.2])]
  // right arm reaches forward so the hand stands in front of the eyes
  const hand = makeHand()
  const rot = new THREE.Euler(0.06, -0.18, 0.02)
  const q = new THREE.Quaternion().setFromEuler(rot)
  const wrist = KID_TIP.clone().sub(TIP_LOCAL.clone().applyQuaternion(q))
  const handMatrix = new THREE.Matrix4().compose(wrist, q, new THREE.Vector3(1, 1, 1))
  for (const g of [...hand.skin, hand.nail]) g.applyMatrix4(handMatrix)
  const rShoulder = v(0.125, s + 0.37, 0.0), rElbow = v(0.118, s + 0.35, -0.23)
  const rightSleeve = limb(rShoulder, rShoulder.clone().lerp(rElbow, 0.45), 0.047)
  const rightArm = [limb(rShoulder, rElbow, 0.033), limb(rElbow, wrist.clone().add(v(0, 0.012, 0.004)), 0.028), ball(0.026, wrist.clone().add(v(0, 0.012, 0)))]
  const belt = new THREE.TorusGeometry(0.131, 0.009, 8, 32)
  belt.rotateX(Math.PI / 2); belt.scale(1, 1, 0.75); belt.translate(0, s + 0.085, 0)
  return { shirt, hem, collar, shorts, thighs, shin, sock, shoe, sole, neck, head, hair: [cap, ...tufts], leftSleeve, leftArm, rightSleeve, rightArm, hand, belt, lWrist, rShoulder }
}

/** A palm-sized satellite: a brass body, two teal solar wings and a dish. */
function ToySatellite() {
  const ref = useRef<THREE.Group>(null)
  const reduced = useMemo(prefersReducedMotion, [])
  useFrame(({ clock }) => {
    if (!ref.current || reduced) return
    const t = clock.elapsedTime
    ref.current.rotation.set(0.25 + Math.sin(t * 0.9) * 0.15, t * 0.6, Math.sin(t * 0.7) * 0.2)
  })
  return (
    <group ref={ref}>
      <mesh castShadow>
        <boxGeometry args={[0.045, 0.04, 0.045]} />
        <meshStandardMaterial color="#c8964f" metalness={0.85} roughness={0.32} />
      </mesh>
      {[-1, 1].map((d) => (
        <group key={d} position={[d * 0.068, 0, 0]}>
          <mesh castShadow>
            <boxGeometry args={[0.075, 0.004, 0.036]} />
            <meshStandardMaterial color="#2f6f78" metalness={0.3} roughness={0.45} />
          </mesh>
          <mesh position={[-d * 0.04, 0, 0]}>
            <cylinderGeometry args={[0.003, 0.003, 0.012, 6]} />
            <meshStandardMaterial color="#c8964f" metalness={0.85} roughness={0.32} />
          </mesh>
        </group>
      ))}
      <mesh position={[0, 0.032, 0]} rotation={[Math.PI, 0, 0]}>
        <coneGeometry args={[0.018, 0.014, 16, 1, true]} />
        <meshStandardMaterial color="#e2d6bc" roughness={0.5} side={THREE.DoubleSide} />
      </mesh>
    </group>
  )
}

interface KidProps {
  position?: [number, number, number]
}

export default function Kid({ position = [0, 0, 0] }: KidProps) {
  const parts = useMemo(makeParts, [])
  const reduced = useMemo(prefersReducedMotion, [])
  const mats = useMemo(() => {
    const arm = new THREE.MeshStandardMaterial({ color: '#a86f4c', roughness: 0.62 })
    const nail = new THREE.MeshStandardMaterial({ color: '#b98263', roughness: 0.4 })
    const skin = new THREE.MeshStandardMaterial({ color: '#a86f4c', roughness: 0.62, transparent: true })
    const shirt = new THREE.MeshStandardMaterial({ color: '#b04a2a', roughness: 0.9, transparent: true })
    const shirtDark = new THREE.MeshStandardMaterial({ color: '#8c3820', roughness: 0.9, transparent: true })
    const shorts = new THREE.MeshStandardMaterial({ color: '#2d4a50', roughness: 0.88, transparent: true })
    const sock = new THREE.MeshStandardMaterial({ color: '#e6dccb', roughness: 0.9, transparent: true })
    const shoe = new THREE.MeshStandardMaterial({ color: '#3b2a20', roughness: 0.6, transparent: true })
    const sole = new THREE.MeshStandardMaterial({ color: '#e6dccb', roughness: 0.8, transparent: true })
    const hair = new THREE.MeshStandardMaterial({ color: '#24170f', roughness: 0.75, transparent: true })
    const brass = new THREE.MeshStandardMaterial({ color: '#c8964f', metalness: 0.9, roughness: 0.35, transparent: true })
    return { arm, nail, skin, shirt, shirtDark, shorts, sock, shoe, sole, hair, brass, fading: [skin, shirt, shirtDark, shorts, sock, shoe, sole, hair, brass] }
  }, [])
  const root = useRef<THREE.Group>(null)
  const body = useRef<THREE.Group>(null)
  const shinL = useRef<THREE.Group>(null)
  const shinR = useRef<THREE.Group>(null)
  const armPivot = useRef<THREE.Group>(null)
  const armInner = useRef<THREE.Group>(null)
  const head = useMemo(() => new THREE.Vector3(), [])

  useLayoutEffect(() => {
    root.current?.traverse((o) => { if ((o as THREE.Mesh).isMesh) o.castShadow = true })
  }, [])

  useFrame(({ camera, clock }) => {
    if (!root.current) return
    head.copy(KID_EYE)
    root.current.localToWorld(head)
    // fade the body out over the last metre of the approach
    const d = camera.position.distanceTo(head)
    const a = THREE.MathUtils.smoothstep(d, 0.25, 0.9)
    for (const m of mats.fading) {
      m.opacity = a
      m.depthWrite = a > 0.98
    }
    if (body.current) body.current.visible = a > 0.01
    // feet swing under the bench, out of step with each other
    const t = reduced ? 0 : clock.elapsedTime
    if (shinL.current) shinL.current.rotation.x = 0.12 + Math.sin(t * 1.7) * 0.32
    if (shinR.current) shinR.current.rotation.x = 0.12 + Math.sin(t * 1.7 + 2.4) * 0.32
    // the right arm turns at the shoulder: it starts in the lap and comes up when the
    // narrator asks for a finger. Once up, it never holds perfectly still: a slow drift from
    // the shoulder, a slower one from breathing, and a faint unsteadiness at the wrist.
    if (armPivot.current) {
      const down = 1 - intro.raise
      const h = reduced ? 0 : 1
      const drift = (Math.sin(t * 0.61) * 0.6 + Math.sin(t * 1.13 + 1.7) * 0.3 + Math.sin(t * 2.3 + 0.4) * 0.1) * h
      const sway = (Math.sin(t * 0.47 + 2.1) * 0.6 + Math.sin(t * 1.29 + 0.3) * 0.3 + Math.sin(t * 2.7 + 1.1) * 0.1) * h
      const breath = Math.sin(t * 1.55) * h
      armPivot.current.rotation.set(-down * 1.05 + drift * 0.011 + breath * 0.004, down * 0.25 + sway * 0.014, -down * 0.3 + sway * 0.006)
    }
    if (armInner.current) armInner.current.localToWorld(KID_TIP_WORLD.copy(KID_TIP))
  })

  const knee = (x: number): [number, number, number] => [x, SEAT_Y + 0.055, -0.27]
  const lower = (ref: RefObject<THREE.Group | null>, x: number) => (
    <group ref={ref} position={knee(x)}>
      <mesh geometry={parts.shin} material={mats.skin} />
      <mesh geometry={parts.sock} material={mats.sock} />
      <mesh geometry={parts.shoe} material={mats.shoe} />
      <mesh geometry={parts.sole} material={mats.sole} />
    </group>
  )

  return (
    <group ref={root} position={position}>
      <group ref={body}>
        <mesh geometry={parts.shirt} material={mats.shirt} />
        <mesh geometry={parts.hem} material={mats.shirtDark} />
        <mesh geometry={parts.collar} material={mats.shirtDark} />
        <mesh geometry={parts.belt} material={mats.brass} />
        {parts.shorts.map((g, i) => <mesh key={i} geometry={g} material={mats.shorts} />)}
        {parts.thighs.map((g, i) => <mesh key={i} geometry={g} material={mats.shorts} />)}
        {lower(shinL, -0.082)}
        {lower(shinR, 0.082)}
        <mesh geometry={parts.neck} material={mats.skin} />
        {parts.head.map((g, i) => <mesh key={i} geometry={g} material={mats.skin} />)}
        {parts.hair.map((g, i) => <mesh key={i} geometry={g} material={mats.hair} />)}
        <mesh geometry={parts.leftSleeve} material={mats.shirt} />
        {parts.leftArm.map((g, i) => <mesh key={i} geometry={g} material={mats.skin} />)}
        <group position={parts.lWrist.clone().add(new THREE.Vector3(0.03, 0.06, -0.06)).toArray() as [number, number, number]}>
          <ToySatellite />
        </group>
      </group>
      {/* the raised arm, turning at the shoulder; the sleeve fades with the body */}
      <group ref={armPivot} position={parts.rShoulder.toArray() as [number, number, number]}>
        <group ref={armInner} position={parts.rShoulder.clone().negate().toArray() as [number, number, number]}>
          <mesh geometry={parts.rightSleeve} material={mats.shirt} />
          {parts.rightArm.map((g, i) => <mesh key={i} geometry={g} material={mats.arm} />)}
          {parts.hand.skin.map((g, i) => <mesh key={i} geometry={g} material={mats.arm} />)}
          <mesh geometry={parts.hand.nail} material={mats.nail} />
        </group>
      </group>
    </group>
  )
}
