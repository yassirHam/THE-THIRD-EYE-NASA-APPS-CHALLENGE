import { useEffect, useMemo, useRef } from 'react'
import { useFrame, useThree } from '@react-three/fiber'
import * as THREE from 'three'
import { mulberry32 } from '../lib/random'
import { cursorHint, overControl, pointer, trackPointer } from '../lib/pointer'

/* The third eye as a cast-bronze instrument: a vesica housing with bevelled walls, a recessed
   iris, and an astrolabe dial set behind it on separate planes. The shapes are lit geometry,
   so the eye reads without bloom; only the pupil is bright enough to glow. */

// Vesica geometry in "eye units". The opening is about 0.84 wide and 1.9 tall.
const R = 1.2845, C = 0.8645, B = Math.sqrt(R * R - C * C)

function vesica(sx: number, sy: number, n = 56): THREE.Vector2[] {
  const th = Math.atan2(B, C)
  const pts: THREE.Vector2[] = []
  for (let i = 0; i <= n; i++) {
    const a = -th + (2 * th * i) / n
    pts.push(new THREE.Vector2((-C + R * Math.cos(a)) * sx, R * Math.sin(a) * sy))
  }
  for (let i = 1; i < n; i++) {
    const a = Math.PI - th + (2 * th * i) / n
    pts.push(new THREE.Vector2((C + R * Math.cos(a)) * sx, R * Math.sin(a) * sy))
  }
  return pts
}

function frame(outer: THREE.Vector2[], inner: THREE.Vector2[], depth: number, bevel: number) {
  const s = new THREE.Shape(outer)
  s.holes.push(new THREE.Path(inner))
  const g = new THREE.ExtrudeGeometry(s, { depth, bevelEnabled: true, bevelThickness: bevel, bevelSize: bevel * 0.8, bevelSegments: 4, curveSegments: 64 })
  g.translate(0, 0, -depth)
  g.computeVertexNormals()
  return g
}

function annulus(r0: number, r1: number, depth: number, bevel: number) {
  const s = new THREE.Shape()
  s.absarc(0, 0, r1, 0, Math.PI * 2, false)
  const hole = new THREE.Path()
  hole.absarc(0, 0, r0, 0, Math.PI * 2, true)
  s.holes.push(hole)
  const g = new THREE.ExtrudeGeometry(s, { depth, bevelEnabled: true, bevelThickness: bevel, bevelSize: bevel * 0.7, bevelSegments: 3, curveSegments: 160 })
  g.translate(0, 0, -depth)
  return g
}

/** Worn bronze: blotchy colour with dark patina, fine scratches for the bump and roughness. */
function bronzeMaps() {
  const r = mulberry32(77)
  const size = 512
  const col = document.createElement('canvas'); col.width = col.height = size
  const bump = document.createElement('canvas'); bump.width = bump.height = size
  const c = col.getContext('2d')!, b = bump.getContext('2d')!
  c.fillStyle = '#9a7442'; c.fillRect(0, 0, size, size)
  b.fillStyle = '#808080'; b.fillRect(0, 0, size, size)
  for (let i = 0; i < 260; i++) {
    const x = r() * size, y = r() * size, rad = 8 + r() * 60
    const g = c.createRadialGradient(x, y, 0, x, y, rad)
    const dark = r() < 0.5
    g.addColorStop(0, dark ? 'rgba(52,38,22,0.35)' : 'rgba(196,150,88,0.22)')
    g.addColorStop(1, 'rgba(0,0,0,0)')
    c.fillStyle = g; c.fillRect(x - rad, y - rad, rad * 2, rad * 2)
  }
  for (let i = 0; i < 70; i++) {
    const x = r() * size, y = r() * size, rad = 4 + r() * 22
    const g = c.createRadialGradient(x, y, 0, x, y, rad)
    g.addColorStop(0, 'rgba(46,60,48,0.28)'); g.addColorStop(1, 'rgba(0,0,0,0)')
    c.fillStyle = g; c.fillRect(x - rad, y - rad, rad * 2, rad * 2)
  }
  for (let i = 0; i < 900; i++) {
    const x = r() * size, y = r() * size, len = 4 + r() * 38, a = r() * Math.PI
    const v = r() < 0.5 ? 60 : 200
    b.strokeStyle = `rgba(${v},${v},${v},0.5)`; b.lineWidth = 0.6 + r()
    b.beginPath(); b.moveTo(x, y); b.lineTo(x + Math.cos(a) * len, y + Math.sin(a) * len); b.stroke()
  }
  for (let i = 0; i < 2400; i++) {
    const v = Math.floor(100 + r() * 60)
    b.fillStyle = `rgba(${v},${v},${v},0.5)`
    b.fillRect(r() * size, r() * size, 1 + r() * 2, 1 + r() * 2)
  }
  const map = new THREE.CanvasTexture(col)
  map.colorSpace = THREE.SRGBColorSpace
  const bumpMap = new THREE.CanvasTexture(bump)
  for (const t of [map, bumpMap]) { t.wrapS = t.wrapT = THREE.RepeatWrapping; t.repeat.set(0.9, 0.9); t.anisotropy = 8 }
  return { map, bumpMap }
}

let shared: ReturnType<typeof makeShared> | null = null
function makeShared() {
  const { map, bumpMap } = bronzeMaps()
  const bronze = new THREE.MeshStandardMaterial({ color: '#c69a5c', map, bumpMap, bumpScale: 0.9, roughnessMap: bumpMap, metalness: 1, roughness: 0.42 })
  const bronzeDark = new THREE.MeshStandardMaterial({ color: '#7a5a34', map, bumpMap, bumpScale: 0.6, metalness: 1, roughness: 0.55 })
  const brass = new THREE.MeshStandardMaterial({ color: '#d2a865', map, metalness: 1, roughness: 0.3 })
  const housing = frame(vesica(1.62, 1.13), vesica(1, 1), 0.12, 0.05)
  const collar = frame(vesica(1.95, 1.24), vesica(1.66, 1.15), 0.05, 0.02)
  const dial = annulus(1.18, 1.31, 0.05, 0.015)
  const outerRing = annulus(1.47, 1.5, 0.02, 0.006)
  // the inner eye surface is cut to the opening, so no plane corners show past the rim
  const innerGeo = new THREE.ShapeGeometry(new THREE.Shape(vesica(1.04, 1.02)), 48)
  return { bronze, bronzeDark, brass, housing, collar, dial, outerRing, innerGeo }
}

const innerVert = /* glsl */ `
varying vec2 vP;
void main(){ vP = position.xy; gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0); }`

/* Inside the opening: bronze lids that close toward a crease, a dark recessed sclera, a
   muted iris with a brass rete, and a hot pupil. Only the pupil exceeds the bloom threshold. */
const innerFrag = /* glsl */ `
precision highp float;
uniform float uOpen; uniform float uTime; uniform vec2 uGaze;
varying vec2 vP;
#define PI 3.14159265
float sdVesica(vec2 p, float r, float d){ p = abs(p); float b = sqrt(r*r - d*d);
  return ((p.y - b) * d > p.x * b) ? length(p - vec2(0.0, b)) : length(p - vec2(-d, 0.0)) - r; }
float ln(float d, float w){ float f = fwidth(d); return 1.0 - smoothstep(w, w + f * 1.5, abs(d)); }
float hash(float n){ return fract(sin(n) * 43758.5453); }
float noise(vec2 x){ vec2 i = floor(x); vec2 f = fract(x); f = f*f*(3.0-2.0*f);
  float a = hash(i.x + i.y*57.0), b = hash(i.x+1.0 + i.y*57.0), c = hash(i.x + (i.y+1.0)*57.0), d = hash(i.x+1.0 + (i.y+1.0)*57.0);
  return mix(mix(a,b,f.x), mix(c,d,f.x), f.y); }
void main(){
  vec2 p = vP;
  float open = max(uOpen, 0.003);
  float dLens = sdVesica(vec2(p.x / mix(0.03, 1.0, open), p.y), ${R.toFixed(4)}, ${C.toFixed(4)});
  float aa = fwidth(dLens) * 1.5;
  float inside = 1.0 - smoothstep(-aa, aa, dLens);

  // lids: curved bronze, lit from above, with fine engraved lines and a dark crease
  vec3 bronze = vec3(0.30, 0.20, 0.10);
  float curve = 0.55 + 0.45 * smoothstep(-0.9, 0.9, p.y);
  float etch = 0.85 + 0.15 * sin(p.y * 140.0 + noise(p * 18.0) * 3.0);
  vec3 lidC = bronze * curve * etch * (0.75 + 0.5 * noise(p * 9.0));
  lidC *= 1.0 - 0.7 * exp(-abs(dLens) * 40.0);
  lidC += vec3(0.9, 0.5, 0.2) * exp(-abs(dLens) * 120.0) * 0.18 * (1.0 - inside);

  // sclera: a dark bowl, lighter toward its centre
  // the opening is narrow and tall, so the iris has more room to travel up and down
  vec2 q = p - uGaze * vec2(0.075, 0.3);
  float ir = length(q); float ia = atan(q.y, q.x);
  vec3 sclera = mix(vec3(0.05, 0.035, 0.022), vec3(0.012, 0.01, 0.009), smoothstep(0.0, 0.9, length(p * vec2(1.6, 0.6))));

  // iris with limbal ring and fibres
  float irisR = 0.355;
  float iris = 1.0 - smoothstep(irisR - 0.004, irisR + 0.004, ir);
  float fib = noise(vec2(ia * 16.0, ir * 8.0 - uTime * 0.06)) * 0.6 + noise(vec2(ia * 54.0, ir * 26.0)) * 0.4;
  vec3 ic = mix(vec3(0.20, 0.09, 0.03), vec3(0.42, 0.29, 0.13), smoothstep(0.12, 0.34, ir)) * (0.5 + 0.6 * fib);
  ic *= 1.0 - 0.6 * smoothstep(0.30, 0.355, ir);
  // brass rete: two rings and counter-rotating spokes with a bevel cue
  float rr = uTime * 0.18;
  float bevel = 0.75 + 0.35 * sign(q.y) * 0.5;
  vec3 brass = vec3(0.62, 0.46, 0.24) * bevel;
  ic = mix(ic, brass, ln(ir - 0.315, 0.006));
  ic = mix(ic, brass * 0.8, ln(ir - 0.255, 0.004));
  float spokes = step(fract((ia + rr) / (2.0*PI) * 24.0), 0.07) * step(0.255, ir) * step(ir, 0.315);
  ic = mix(ic, brass * 0.9, spokes);
  float notch = step(fract((ia - rr * 1.6) / (2.0*PI) * 8.0), 0.1) * step(0.18, ir) * step(ir, 0.225);
  ic = mix(ic, vec3(0.25, 0.42, 0.43), notch * 0.8);
  // pupil: the only hot surface
  float pupR = 0.105 + 0.012 * sin(uTime * 0.6);
  float pupil = 1.0 - smoothstep(pupR - 0.004, pupR + 0.004, ir);
  vec3 core = mix(vec3(1.0, 0.42, 0.10) * 2.4, vec3(1.0, 0.86, 0.6) * 4.0, exp(-ir * ir / (pupR * pupR * 0.18)));
  ic = mix(ic, core, pupil);
  ic += vec3(1.0, 0.5, 0.15) * exp(-max(ir - pupR, 0.0) * 28.0) * 0.35 * (1.0 - pupil);
  float glint = 1.0 - smoothstep(0.0, 0.025, length(q - vec2(-0.11, 0.12)));
  ic += vec3(0.95, 0.9, 0.8) * glint * 0.8;

  vec3 eye = mix(sclera, ic, iris);
  // the lids cast shadow into the bowl
  eye *= 1.0 - 0.8 * smoothstep(-0.22, 0.0, dLens);
  vec3 col = mix(lidC, eye, inside);
  gl_FragColor = vec4(col, 1.0);
  #include <colorspace_fragment>
}`

interface ThirdEyeProps {
  /** read every frame: { eyeOpen } on a state object, or a fixed number */
  source?: { eyeOpen: number }
  open?: number
  reveal?: number
  /** overall width of the instrument in world units */
  size?: number
  position?: [number, number, number]
  follow?: boolean
}

const TICKS = 120

export default function ThirdEye({ source, open = 1, reveal = 1, size = 3, position = [0, 0, 0], follow = true }: ThirdEyeProps) {
  const root = useRef<THREE.Group>(null)
  const dialRef = useRef<THREE.Group>(null)
  const dotsRef = useRef<THREE.Group>(null)
  const light = useRef<THREE.PointLight>(null)
  const k = size / 3.2

  const s = useMemo(() => (shared ??= makeShared()), [])
  const inner = useMemo(
    () => new THREE.ShaderMaterial({ vertexShader: innerVert, fragmentShader: innerFrag, uniforms: { uOpen: { value: 0 }, uTime: { value: 0 }, uGaze: { value: new THREE.Vector2() } } }),
    [],
  )
  const ticks = useMemo(() => {
    const m = new THREE.InstancedMesh(new THREE.BoxGeometry(0.008, 0.05, 0.02), s.brass, TICKS)
    const o = new THREE.Object3D()
    for (let i = 0; i < TICKS; i++) {
      const a = (i / TICKS) * Math.PI * 2
      const major = i % 10 === 0
      o.position.set(Math.cos(a) * 1.245, Math.sin(a) * 1.245, 0.012)
      o.rotation.set(0, 0, a + Math.PI / 2)
      o.scale.set(major ? 1.8 : 1, major ? 2.2 : i % 5 === 0 ? 1.5 : 1, 1)
      o.updateMatrix(); m.setMatrixAt(i, o.matrix)
    }
    return m
  }, [s])
  const blades = useMemo(() => {
    const g = new THREE.ConeGeometry(0.035, 0.34, 4, 1)
    g.scale(1, 1, 0.35)
    const m = new THREE.InstancedMesh(g, s.bronze, 12)
    const o = new THREE.Object3D()
    for (let i = 0; i < 12; i++) {
      const a = (i / 12) * Math.PI * 2 + Math.PI / 12
      o.position.set(Math.cos(a) * 1.47, Math.sin(a) * 1.47, -0.03)
      o.rotation.set(0, 0, a - Math.PI / 2)
      o.scale.setScalar(i % 3 === 0 ? 1.3 : 0.85)
      o.updateMatrix(); m.setMatrixAt(i, o.matrix)
    }
    return m
  }, [s])
  const dots = useMemo(() => {
    const m = new THREE.InstancedMesh(new THREE.SphereGeometry(0.012, 8, 6), s.brass, 48)
    const o = new THREE.Object3D()
    for (let i = 0; i < 48; i++) {
      const a = (i / 48) * Math.PI * 2
      o.position.set(Math.cos(a) * 1.58, Math.sin(a) * 1.58, 0)
      o.updateMatrix(); m.setMatrixAt(i, o.matrix)
    }
    return m
  }, [s])

  const rv = useRef(0)
  const opened = useRef(0)
  const blinkAt = useRef(-10)
  const hovering = useRef(false)
  const tilt = useRef(new THREE.Vector2())
  const { camera, gl } = useThree()

  // click the eye to make it blink; the hit area is the vesica opening, in screen pixels
  useEffect(() => {
    trackPointer()
    const c = new THREE.Vector3(), top = new THREE.Vector3(), side = new THREE.Vector3()
    const hit = (x: number, y: number) => {
      const g = root.current
      if (!g || !g.visible || opened.current < 0.15) return false
      let o: THREE.Object3D | null = g
      while (o) { if (!o.visible) return false; o = o.parent }
      const r = gl.domElement.getBoundingClientRect()
      if (x < r.left || x > r.right || y < r.top || y > r.bottom) return false
      const px = (v: THREE.Vector3) => { v.project(camera); return [r.left + (v.x + 1) / 2 * r.width, r.top + (1 - v.y) / 2 * r.height] }
      const [cx, cy] = px(g.localToWorld(c.set(0, 0, 0)))
      const [tx, ty] = px(g.localToWorld(top.set(0, 1.15 * k, 0)))
      const [sx, sy] = px(g.localToWorld(side.set(0.78 * k, 0, 0)))
      const ry = Math.hypot(tx - cx, ty - cy), rx = Math.hypot(sx - cx, sy - cy)
      return ((x - cx) / rx) ** 2 + ((y - cy) / ry) ** 2 <= 1
    }
    const down = (e: PointerEvent) => {
      if (e.button !== 0 || overControl(e.target)) return
      if (hit(e.clientX, e.clientY)) {
        blinkAt.current = performance.now() / 1000
        if (import.meta.env.DEV) { const w = window as unknown as { __eyeBlinks?: number }; w.__eyeBlinks = (w.__eyeBlinks ?? 0) + 1 }
      }
    }
    const move = (e: PointerEvent) => {
      const on = !overControl(e.target) && hit(e.clientX, e.clientY)
      if (on) cursorHint('Blink')
      else if (hovering.current) cursorHint('')
      if (on !== hovering.current) document.documentElement.classList.toggle('is-eye-hover', on)
      hovering.current = on
    }
    window.addEventListener('pointerdown', down)
    window.addEventListener('pointermove', move, { passive: true })
    return () => {
      window.removeEventListener('pointerdown', down)
      window.removeEventListener('pointermove', move)
      if (hovering.current) { cursorHint(''); document.documentElement.classList.remove('is-eye-hover') }
    }
  }, [camera, gl, k])

  const here = useMemo(() => new THREE.Vector3(), [])
  useFrame((st, dt) => {
    const u = inner.uniforms
    u.uTime.value += dt
    const targetOpen = source ? source.eyeOpen : open
    opened.current = THREE.MathUtils.damp(opened.current, targetOpen, 5, dt)
    // a blink closes the lids fully and opens them again in about a third of a second
    const b = THREE.MathUtils.clamp((performance.now() / 1000 - blinkAt.current) / 0.32, 0, 1)
    const shut = b < 1 ? Math.sin(Math.PI * b) ** 0.6 : 0
    u.uOpen.value = opened.current * (1 - shut)
    rv.current = THREE.MathUtils.damp(rv.current, source ? Math.min(1, source.eyeOpen * 1.2) : reveal, 2, dt)
    // gaze: from the eye's place on screen toward the cursor
    let gx = 0, gy = 0
    if (follow && pointer.seen && root.current) {
      const r = st.gl.domElement.getBoundingClientRect()
      root.current.getWorldPosition(here).project(st.camera)
      const ex = r.left + (here.x + 1) / 2 * r.width, ey = r.top + (1 - here.y) / 2 * r.height
      const reach = Math.max(260, Math.min(r.width, r.height) * 0.45)
      gx = THREE.MathUtils.clamp((pointer.x - ex) / reach, -1, 1)
      gy = THREE.MathUtils.clamp(-(pointer.y - ey) / reach, -1, 1)
    }
    const g = u.uGaze.value as THREE.Vector2
    g.x = THREE.MathUtils.damp(g.x, gx, 4, dt)
    g.y = THREE.MathUtils.damp(g.y, gy, 4, dt)
    tilt.current.x = THREE.MathUtils.damp(tilt.current.x, gx, 2.5, dt)
    tilt.current.y = THREE.MathUtils.damp(tilt.current.y, gy, 2.5, dt)
    const t = u.uTime.value
    if (dialRef.current) {
      const sc = 0.72 + 0.28 * rv.current
      dialRef.current.scale.setScalar(sc)
      dialRef.current.visible = rv.current > 0.02
      dialRef.current.rotation.z = t * 0.04 + (1 - rv.current) * 0.6
    }
    if (dotsRef.current) dotsRef.current.rotation.z = -t * 0.06
    if (light.current) light.current.intensity = 0.25 + 0.9 * u.uOpen.value
    if (root.current) {
      root.current.lookAt(st.camera.position)
      // the whole instrument turns a little toward the cursor, like a head following a sound
      if (follow) root.current.rotateY(tilt.current.x * 0.22).rotateX(-tilt.current.y * 0.16)
    }
  })

  return (
    <group ref={root} position={position}>
      <group scale={k}>
        {/* the instrument behind the eye, on three planes for depth */}
        <group ref={dialRef}>
          <mesh geometry={s.dial} material={s.bronzeDark} position={[0, 0, -0.18]} />
          <primitive object={ticks} position={[0, 0, -0.18]} />
          <primitive object={blades} position={[0, 0, -0.2]} />
          <mesh geometry={s.outerRing} material={s.brass} position={[0, 0, -0.3]} />
          <group ref={dotsRef} position={[0, 0, -0.34]}>
            <primitive object={dots} />
          </group>
        </group>
        {/* housing: an outer collar and the bevelled vesica rim */}
        <mesh geometry={s.collar} material={s.bronzeDark} position={[0, 0, -0.07]} />
        <mesh geometry={s.housing} material={s.bronze} />
        {/* the recessed eye inside the rim */}
        <mesh geometry={s.innerGeo} material={inner} position={[0, 0, -0.1]} />
        {/* a raking key from upper left, so the bevels and engraving read without bloom */}
        <pointLight color="#ffd9a8" intensity={2.2} distance={9 * k} decay={2} position={[-1.4, 1.9, 2.4]} />
        <pointLight ref={light} color="#ff9a44" intensity={0.6} distance={2.2 * k} decay={2} position={[0, 0, 0.35]} />
      </group>
    </group>
  )
}
