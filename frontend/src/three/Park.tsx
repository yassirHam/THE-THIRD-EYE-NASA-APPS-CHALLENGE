import { useLayoutEffect, useMemo, useRef } from 'react'
import { useFrame } from '@react-three/fiber'
import * as THREE from 'three'
import { mulberry32, prefersReducedMotion } from '../lib/random'
import { SEAT_Y } from './Kid'

/* A park on a clear day: grass, a gravel path, trees near and far, hills in the haze, a few
   clouds and a kite. An old bronze sundial stands a few metres ahead of the bench, so the
   raised finger has near and far things to jump against. Everything is built from primitives. */

export const SKY_TOP = new THREE.Color('#3f7fcf')
export const SKY_HORIZON = new THREE.Color('#b4cfe6')
export const PARK_FOG = { near: 14, far: 125 }

const skyVert = /* glsl */ `
varying vec3 vDir;
void main(){ vDir = normalize(position); gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0); }`
const skyFrag = /* glsl */ `
uniform vec3 uTop; uniform vec3 uHor;
varying vec3 vDir;
void main(){
  float h = clamp(vDir.y, 0.0, 1.0);
  vec3 c = mix(uHor, uTop, pow(smoothstep(0.0, 0.55, h), 0.75));
  gl_FragColor = vec4(c, 1.0);
  #include <colorspace_fragment>
}`

function Sky() {
  const mat = useMemo(
    () => new THREE.ShaderMaterial({ vertexShader: skyVert, fragmentShader: skyFrag, side: THREE.BackSide, depthWrite: false, fog: false, uniforms: { uTop: { value: SKY_TOP }, uHor: { value: SKY_HORIZON } } }),
    [],
  )
  return (
    <mesh material={mat} renderOrder={-1} frustumCulled={false}>
      <sphereGeometry args={[150, 32, 16]} />
    </mesh>
  )
}

function canvasTexture(size: number, paint: (g: CanvasRenderingContext2D, r: () => number) => void, seed: number) {
  const c = document.createElement('canvas')
  c.width = c.height = size
  const g = c.getContext('2d')!
  paint(g, mulberry32(seed))
  const t = new THREE.CanvasTexture(c)
  t.colorSpace = THREE.SRGBColorSpace
  t.wrapS = t.wrapT = THREE.RepeatWrapping
  t.anisotropy = 8
  return t
}

/** Grass: a short-blade texture, with slow patches of lighter and darker green across the lawn. */
function Ground() {
  const mat = useMemo(() => {
    const map = canvasTexture(256, (g, r) => {
      g.fillStyle = '#4e7a32'
      g.fillRect(0, 0, 256, 256)
      const tones = ['#3f6a27', '#5c8b3c', '#6a9845', '#46722d', '#7aa552']
      for (let i = 0; i < 5200; i++) {
        const x = r() * 256, y = r() * 256, l = 2 + r() * 5
        g.strokeStyle = tones[Math.floor(r() * tones.length)]
        g.lineWidth = 0.8 + r() * 0.8
        g.beginPath(); g.moveTo(x, y); g.lineTo(x + (r() - 0.5) * 2, y - l); g.stroke()
      }
    }, 5)
    map.repeat.set(64, 64)
    const m = new THREE.MeshStandardMaterial({ map, roughness: 0.95 })
    m.onBeforeCompile = (sh) => {
      sh.vertexShader = sh.vertexShader
        .replace('#include <common>', '#include <common>\nvarying vec2 vGW;')
        .replace('#include <worldpos_vertex>', '#include <worldpos_vertex>\nvGW = (modelMatrix * vec4(transformed, 1.0)).xz;')
      sh.fragmentShader = sh.fragmentShader
        .replace('#include <common>', `#include <common>
varying vec2 vGW;
float vn(vec2 p){ vec2 i = floor(p), f = fract(p); f = f * f * (3.0 - 2.0 * f);
  float a = fract(sin(dot(i, vec2(127.1, 311.7))) * 43758.5); float b = fract(sin(dot(i + vec2(1, 0), vec2(127.1, 311.7))) * 43758.5);
  float c = fract(sin(dot(i + vec2(0, 1), vec2(127.1, 311.7))) * 43758.5); float d = fract(sin(dot(i + vec2(1, 1), vec2(127.1, 311.7))) * 43758.5);
  return mix(mix(a, b, f.x), mix(c, d, f.x), f.y); }`)
        .replace('#include <map_fragment>', `#include <map_fragment>
float lawn = vn(vGW * 0.11) * 0.6 + vn(vGW * 0.37) * 0.4;
diffuseColor.rgb *= 0.82 + lawn * 0.36;`)
    }
    return m
  }, [])
  return (
    <mesh rotation={[-Math.PI / 2, 0, 0]} material={mat} receiveShadow>
      <planeGeometry args={[300, 300]} />
    </mesh>
  )
}

/** A gravel path that crosses the lawn between the bench and the sundial. */
function Path() {
  const mat = useMemo(() => {
    const map = canvasTexture(256, (g, r) => {
      g.fillStyle = '#b9a47c'
      g.fillRect(0, 0, 256, 256)
      for (let i = 0; i < 4000; i++) {
        const t = r()
        g.fillStyle = t < 0.4 ? '#a48e66' : t < 0.75 ? '#cdb991' : '#8f7b58'
        g.fillRect(r() * 256, r() * 256, 1 + r() * 2, 1 + r() * 2)
      }
      // soft grass edges along both sides
      for (const [y0, dir] of [[0, 1], [256, -1]] as const) {
        for (let i = 0; i < 900; i++) {
          const x = r() * 256, d = Math.pow(r(), 2) * 34
          g.fillStyle = r() < 0.5 ? '#4e7a32' : '#5c8b3c'
          g.fillRect(x, y0 + dir * d - 1, 2, 3)
        }
      }
    }, 8)
    map.repeat.set(12, 1)
    return new THREE.MeshStandardMaterial({ map, roughness: 1 })
  }, [])
  return (
    <mesh rotation={[-Math.PI / 2, 0, 0.32]} position={[0, 0.006, 1.6]} material={mat} receiveShadow>
      <planeGeometry args={[70, 1.7]} />
    </mesh>
  )
}

type Tree = { x: number; z: number; h: number; kind: 'round' | 'cone' }

function placeTrees(): Tree[] {
  const r = mulberry32(42)
  const out: Tree[] = []
  const free = (x: number, z: number) => out.every((t) => Math.hypot(t.x - x, t.z - z) > 3.2)
  // a loose belt of trees ahead and to the sides, with the view down the lawn kept open
  for (let i = 0; i < 400 && out.length < 70; i++) {
    const x = (r() - 0.5) * 110
    const z = 8 - r() * 70
    const ahead = z < 0
    if (Math.abs(x) < 3.5 + Math.max(0, -z) * 0.05 && z > -26) continue // open lane behind the sundial
    if (Math.hypot(x, z - 4.2) < 7) continue // clearing around the bench
    if (!ahead && Math.abs(x) < 9) continue // nothing between the camera and the child
    if (!free(x, z)) continue
    out.push({ x, z, h: 3.4 + r() * 3.6, kind: r() < 0.3 ? 'cone' : 'round' })
  }
  return out
}

function Trees() {
  const { trunks, crowns, cones } = useMemo(() => {
    const trees = placeTrees()
    const r = mulberry32(77)
    const trunkG = new THREE.CylinderGeometry(0.6, 1, 1, 7)
    trunkG.translate(0, 0.5, 0)
    const crownG = new THREE.IcosahedronGeometry(1, 1)
    const coneG = new THREE.ConeGeometry(1, 1, 8)
    coneG.translate(0, 0.5, 0)
    const bark = new THREE.MeshStandardMaterial({ color: '#5a4030', roughness: 0.95 })
    const leaf = new THREE.MeshStandardMaterial({ roughness: 0.85, flatShading: true })
    const nTrunk = trees.length
    const round = trees.filter((t) => t.kind === 'round')
    const pointy = trees.filter((t) => t.kind === 'cone')
    const blobs = round.length * 5
    const trunks = new THREE.InstancedMesh(trunkG, bark, nTrunk)
    const crowns = new THREE.InstancedMesh(crownG, leaf, blobs)
    const cones = new THREE.InstancedMesh(coneG, leaf.clone(), pointy.length * 2)
    const m = new THREE.Matrix4(), q = new THREE.Quaternion(), p = new THREE.Vector3(), s = new THREE.Vector3(), c = new THREE.Color()
    const greens = ['#3f6b2c', '#4d7a33', '#5a8a3a', '#36602a', '#6a9440']
    trees.forEach((t, i) => {
      const trunkH = t.kind === 'round' ? t.h * 0.5 : t.h * 0.18
      m.compose(p.set(t.x, 0, t.z), q.identity(), s.set(t.h * 0.035, trunkH, t.h * 0.035))
      trunks.setMatrixAt(i, m)
    })
    let k = 0
    for (const t of round) {
      for (let j = 0; j < 5; j++) {
        const a = (j / 5) * Math.PI * 2 + r()
        const rad = t.h * (j === 0 ? 0.32 : 0.22 + r() * 0.07)
        const off = j === 0 ? 0 : t.h * 0.2
        p.set(t.x + Math.cos(a) * off, t.h * (j === 0 ? 0.68 : 0.56 + r() * 0.16), t.z + Math.sin(a) * off)
        q.setFromEuler(new THREE.Euler(r() * 3, r() * 3, r() * 3))
        m.compose(p, q, s.set(rad, rad * (0.85 + r() * 0.2), rad))
        crowns.setMatrixAt(k, m)
        crowns.setColorAt(k, c.set(greens[Math.floor(r() * greens.length)]))
        k++
      }
    }
    pointy.forEach((t, i) => {
      for (let j = 0; j < 2; j++) {
        const w = t.h * (j === 0 ? 0.26 : 0.19)
        m.compose(p.set(t.x, t.h * (0.14 + j * 0.3), t.z), q.setFromEuler(new THREE.Euler(0, r() * 3, 0)), s.set(w, t.h * (j === 0 ? 0.62 : 0.55), w))
        cones.setMatrixAt(i * 2 + j, m)
        cones.setColorAt(i * 2 + j, c.set(j === 0 ? '#2f5a2a' : '#3a6a30'))
      }
    })
    for (const im of [trunks, crowns, cones]) {
      im.castShadow = true
      im.instanceMatrix.needsUpdate = true
      if (im.instanceColor) im.instanceColor.needsUpdate = true
    }
    return { trunks, crowns, cones }
  }, [])
  return (
    <>
      <primitive object={trunks} />
      <primitive object={crowns} />
      <primitive object={cones} />
    </>
  )
}

/** Low hills far off, softened by the haze. */
function Hills() {
  const hills = useMemo(() => {
    const r = mulberry32(13)
    return Array.from({ length: 9 }, (_, i) => ({
      p: [-110 + i * 27 + (r() - 0.5) * 12, -2, -88 - r() * 22] as [number, number, number],
      s: [22 + r() * 18, 7 + r() * 8, 14] as [number, number, number],
    }))
  }, [])
  return (
    <>
      {hills.map((h, i) => (
        <mesh key={i} position={h.p} scale={h.s}>
          <sphereGeometry args={[1, 24, 12, 0, Math.PI * 2, 0, Math.PI / 2]} />
          <meshStandardMaterial color={i % 2 ? '#56804a' : '#4b7442'} roughness={1} />
        </mesh>
      ))}
    </>
  )
}

/** A few soft cumulus clouds, kept below the bloom threshold. */
function Clouds() {
  const { mat, puffs } = useMemo(() => {
    const c = document.createElement('canvas'); c.width = c.height = 128
    const g = c.getContext('2d')!
    const grd = g.createRadialGradient(64, 64, 0, 64, 64, 64)
    grd.addColorStop(0, 'rgba(255,255,255,1)'); grd.addColorStop(0.55, 'rgba(255,255,255,0.75)'); grd.addColorStop(1, 'rgba(255,255,255,0)')
    g.fillStyle = grd; g.fillRect(0, 0, 128, 128)
    const map = new THREE.CanvasTexture(c)
    const mat = new THREE.SpriteMaterial({ map, color: '#dfe7ef', transparent: true, opacity: 0.85, depthWrite: false, fog: false })
    const r = mulberry32(21)
    const puffs: { p: [number, number, number]; s: number }[] = []
    const centres: [number, number, number][] = [[-55, 30, -110], [-12, 38, -125], [30, 26, -100], [70, 34, -118], [-85, 22, -70], [95, 24, -60]]
    for (const [cx, cy, cz] of centres) {
      for (let i = 0; i < 9; i++) {
        const s = 9 + r() * 11
        puffs.push({ p: [cx + (r() - 0.5) * 30, cy + (r() - 0.3) * 5, cz + (r() - 0.5) * 8], s })
      }
    }
    return { mat, puffs }
  }, [])
  return (
    <>
      {puffs.map((p, i) => <sprite key={i} position={p.p} scale={[p.s * 1.6, p.s, 1]} material={mat} />)}
    </>
  )
}

/** A kite on a long string, high over the trees: the farthest thing that moves. */
function Kite() {
  const ref = useRef<THREE.Group>(null)
  const reduced = useMemo(prefersReducedMotion, [])
  const { body, tail, line } = useMemo(() => {
    const g = new THREE.BufferGeometry()
    const pts = [0, 0.9, 0, -0.55, 0, 0, 0, -1.2, 0, 0.55, 0, 0]
    g.setAttribute('position', new THREE.Float32BufferAttribute(pts, 3))
    g.setIndex([0, 1, 2, 0, 2, 3])
    g.computeVertexNormals()
    const body = new THREE.Mesh(g, new THREE.MeshStandardMaterial({ color: '#d9822b', side: THREE.DoubleSide, roughness: 0.7 }))
    const tail = Array.from({ length: 5 }, (_, i) => i)
    const lg = new THREE.BufferGeometry().setFromPoints([new THREE.Vector3(0, -1.1, 0), new THREE.Vector3(14, -24, -12)])
    const line = new THREE.Line(lg, new THREE.LineBasicMaterial({ color: '#f4efe4', transparent: true, opacity: 0.5 }))
    return { body, tail, line }
  }, [])
  useFrame(({ clock }) => {
    if (!ref.current || reduced) return
    const t = clock.elapsedTime
    ref.current.rotation.set(0.15, 0.2, Math.sin(t * 0.8) * 0.18)
    ref.current.position.y = 15 + Math.sin(t * 0.5) * 0.6
  })
  return (
    <group ref={ref} position={[9, 15, -34]} rotation={[0.15, 0.2, 0]}>
      <primitive object={body} />
      <primitive object={line} />
      {tail.map((i) => (
        <mesh key={i} position={[Math.sin(i * 1.3) * 0.18, -1.45 - i * 0.42, 0]} rotation={[0, 0, Math.PI / 4]}>
          <planeGeometry args={[0.2, 0.2]} />
          <meshStandardMaterial color={i % 2 ? '#2f6f78' : '#e9e1cc'} side={THREE.DoubleSide} />
        </mesh>
      ))}
    </group>
  )
}

/** An old bronze sundial on a stone pillar: the near reference behind the finger. */
function Sundial({ position }: { position: [number, number, number] }) {
  const gnomon = useMemo(() => {
    const s = new THREE.Shape()
    s.moveTo(0, 0); s.lineTo(0.24, 0); s.lineTo(0, 0.17); s.closePath()
    const g = new THREE.ExtrudeGeometry(s, { depth: 0.012, bevelEnabled: false })
    g.translate(-0.12, 0, -0.006)
    return g
  }, [])
  const bronze = useMemo(() => new THREE.MeshStandardMaterial({ color: '#a8743c', metalness: 0.85, roughness: 0.38 }), [])
  const stone = useMemo(() => new THREE.MeshStandardMaterial({ color: '#857b6c', roughness: 0.92 }), [])
  return (
    <group position={position} rotation={[0, 0.5, 0]}>
      <mesh material={stone} position={[0, 0.05, 0]} castShadow receiveShadow>
        <cylinderGeometry args={[0.36, 0.4, 0.1, 8]} />
      </mesh>
      <mesh material={stone} position={[0, 0.5, 0]} castShadow receiveShadow>
        <cylinderGeometry args={[0.17, 0.22, 0.82, 8]} />
      </mesh>
      <mesh material={stone} position={[0, 0.94, 0]} castShadow receiveShadow>
        <cylinderGeometry args={[0.3, 0.26, 0.08, 8]} />
      </mesh>
      <mesh material={bronze} position={[0, 0.988, 0]} castShadow receiveShadow>
        <cylinderGeometry args={[0.26, 0.26, 0.016, 40]} />
      </mesh>
      {Array.from({ length: 12 }, (_, i) => {
        const a = (i / 12) * Math.PI * 2
        return (
          <mesh key={i} material={stone} position={[Math.cos(a) * 0.21, 0.998, Math.sin(a) * 0.21]} rotation={[0, -a, 0]}>
            <boxGeometry args={[0.05, 0.004, 0.008]} />
          </mesh>
        )
      })}
      <mesh geometry={gnomon} material={bronze} position={[0, 0.996, 0]} castShadow />
    </group>
  )
}

/** The bench the child sits on: wooden slats on two stone feet, no back. */
function Bench({ position }: { position: [number, number, number] }) {
  const wood = useMemo(() => new THREE.MeshStandardMaterial({ color: '#8a5d3b', roughness: 0.8 }), [])
  const stone = useMemo(() => new THREE.MeshStandardMaterial({ color: '#7f7566', roughness: 0.92 }), [])
  return (
    <group position={position}>
      {[-0.13, 0, 0.13].map((z) => (
        <mesh key={z} material={wood} position={[0.15, SEAT_Y - 0.025, z]} castShadow receiveShadow>
          <boxGeometry args={[1.5, 0.05, 0.115]} />
        </mesh>
      ))}
      {[-0.45, 0.75].map((x) => (
        <mesh key={x} material={stone} position={[x, (SEAT_Y - 0.05) / 2, 0]} castShadow receiveShadow>
          <boxGeometry args={[0.12, SEAT_Y - 0.05, 0.4]} />
        </mesh>
      ))}
    </group>
  )
}

/** Things the child was playing with: a striped ball and a small stack of blocks. */
function Toys({ position }: { position: [number, number, number] }) {
  const ballMap = useMemo(() => {
    const t = canvasTexture(256, (g) => {
      for (let i = 0; i < 6; i++) { g.fillStyle = i % 2 ? '#e9e1cc' : '#c2452b'; g.fillRect((i * 256) / 6, 0, 256 / 6 + 1, 256) }
    }, 1)
    t.wrapS = t.wrapT = THREE.ClampToEdgeWrapping
    return t
  }, [])
  const blocks: { p: [number, number, number]; r: number; c: string }[] = [
    { p: [-0.75, 0.045, -0.3], r: 0.2, c: '#d9a23b' },
    { p: [-0.64, 0.045, -0.36], r: -0.3, c: '#2f6f78' },
    { p: [-0.7, 0.135, -0.33], r: 0.6, c: '#e9e1cc' },
  ]
  return (
    <group position={position}>
      <mesh position={[0.95, 0.11, -0.65]} rotation={[0.4, 0.3, 0.2]} castShadow>
        <sphereGeometry args={[0.11, 32, 20]} />
        <meshStandardMaterial map={ballMap} roughness={0.45} />
      </mesh>
      {blocks.map((b, i) => (
        <mesh key={i} position={b.p} rotation={[0, b.r, 0]} castShadow receiveShadow>
          <boxGeometry args={[0.09, 0.09, 0.09]} />
          <meshStandardMaterial color={b.c} roughness={0.7} />
        </mesh>
      ))}
    </group>
  )
}

/** Short grass blades around the bench, so the near ground has texture in the close shots. */
function Tufts({ centre }: { centre: [number, number, number] }) {
  const mesh = useMemo(() => {
    const r = mulberry32(3)
    const g = new THREE.ConeGeometry(0.014, 0.08, 3)
    g.translate(0, 0.04, 0)
    const n = 9000
    const im = new THREE.InstancedMesh(g, new THREE.MeshStandardMaterial({ roughness: 0.9 }), n)
    const m = new THREE.Matrix4(), q = new THREE.Quaternion(), c = new THREE.Color()
    const tones = ['#4a7a2e', '#5f9040', '#3d6a27', '#6f9f4a']
    for (let i = 0; i < n; i++) {
      const a = r() * Math.PI * 2, d = 0.4 + Math.sqrt(r()) * 6
      const x = centre[0] + Math.cos(a) * d, z = centre[2] + Math.sin(a) * d
      const onPath = Math.abs((z - 1.6) * Math.cos(0.32) + x * Math.sin(0.32)) < 0.95
      q.setFromEuler(new THREE.Euler((r() - 0.5) * 0.5, r() * 3, (r() - 0.5) * 0.5))
      // blades thin out toward the edge of the patch, so it has no visible rim
      const s = onPath ? 0 : (0.6 + r() * 0.9) * (1 - THREE.MathUtils.smoothstep(d, 3.2, 6.4))
      m.compose(new THREE.Vector3(x, 0, z), q, new THREE.Vector3(s, s * (0.7 + r() * 0.8), s))
      im.setMatrixAt(i, m)
      im.setColorAt(i, c.set(tones[Math.floor(r() * tones.length)]))
    }
    im.instanceMatrix.needsUpdate = true
    return im
  }, [centre])
  return <primitive object={mesh} />
}

interface ParkProps {
  /** where the child sits; the bench, toys and sun are placed around it */
  kidAt: [number, number, number]
}

export default function Park({ kidAt }: ParkProps) {
  const sun = useRef<THREE.DirectionalLight>(null)
  const target = useMemo(() => new THREE.Object3D(), [])
  useLayoutEffect(() => {
    target.position.set(kidAt[0], 0.4, kidAt[2] - 1.2)
    target.updateMatrixWorld()
    if (sun.current) sun.current.target = target
  }, [kidAt, target])
  return (
    <group>
      <Sky />
      <Clouds />
      <Hills />
      <Ground />
      <Path />
      <Trees />
      <Kite />
      <Sundial position={[-0.6, 0, 0.5]} />
      <Bench position={kidAt} />
      <Toys position={kidAt} />
      <Tufts centre={kidAt} />
      <primitive object={target} />
      <hemisphereLight args={['#bcd6f0', '#4f6d34', 1.15]} />
      <directionalLight
        ref={sun}
        position={[kidAt[0] - 5, 9, kidAt[2] + 6]}
        intensity={2.4}
        color="#fff0d8"
        castShadow
        shadow-mapSize={[2048, 2048]}
        shadow-bias={-0.0004}
        shadow-normalBias={0.02}
        shadow-camera-left={-6}
        shadow-camera-right={6}
        shadow-camera-top={6}
        shadow-camera-bottom={-6}
        shadow-camera-near={1}
        shadow-camera-far={30}
      />
    </group>
  )
}
