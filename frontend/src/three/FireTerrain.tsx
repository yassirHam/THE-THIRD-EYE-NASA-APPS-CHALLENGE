import { useMemo } from 'react'
import { useFrame } from '@react-three/fiber'
import { useTexture } from '@react-three/drei'
import * as THREE from 'three'
import { mulberry32 } from '../lib/random'
import { EYES, FIELD_H, FIELD_W, FIRES, grid, isCloudy, type FieldView } from '../lib/field'

/* A real satellite image of eastern Angola (VIIRS true colour, 18 June 2024, NASA GIBS) laid on a
   gently curved plate, as if seen from orbit. Made-up fires glow on it as ember clusters, and each
   eye's squares are drawn onto the image as thin footprints: an outline grid, with a light fill
   where that eye detected fire. Nothing stands on the image, so no square hides a fire. */

export const FIELD_IMAGE = '/tex/field-angola-20240618.webp'
const S = 0.05 // world units per field unit: the field is 12 x 8
const BEND = 0.022 // curvature of the plate, world units of drop per unit squared

function drop(wx: number, wz: number) {
  return -(wx * wx + wz * wz) * BEND
}

const terrainVert = /* glsl */ `
varying vec2 vF; varying vec2 vUv;
void main(){
  vUv = uv;
  // field coordinates: x to the right, y toward the viewer, matching the fire and cell data
  vF = vec2(uv.x * ${FIELD_W.toFixed(1)}, (1.0 - uv.y) * ${FIELD_H.toFixed(1)});
  vec4 w = modelMatrix * vec4(position, 1.0);
  w.y += -(w.x * w.x + w.z * w.z) * ${BEND.toFixed(4)};
  gl_Position = projectionMatrix * viewMatrix * w;
}`

const terrainFrag = /* glsl */ `
uniform sampler2D uImg; uniform sampler2D uM; uniform sampler2D uV;
uniform float uWM; uniform float uWV; uniform float uWC; uniform float uDim;
varying vec2 vF; varying vec2 vUv;
float line(float v){ float g = abs(fract(v - 0.5) - 0.5); float fw = fwidth(v); return 1.0 - smoothstep(fw * 0.4, fw * 1.4, g); }
vec3 footprint(vec3 c, sampler2D tex, float cell, vec3 tint, float w){
  vec2 uvF = vF / vec2(${FIELD_W.toFixed(1)}, ${FIELD_H.toFixed(1)});
  vec4 t = texture2D(tex, uvF);
  vec2 g = vF / cell;
  float grid = max(line(g.x), line(g.y));
  vec2 f = fract(g); float e = min(min(f.x, 1.0 - f.x), min(f.y, 1.0 - f.y));
  float border = 1.0 - smoothstep(0.03, 0.055, e);
  float lit = t.r, seen = t.g;
  // unseen squares: grey haze with diagonal hatching, so "not seen" never reads as "no fire"
  float hatch = step(0.5, fract((vF.x + vF.y) * 0.35));
  c = mix(c, vec3(0.16, 0.17, 0.18) + hatch * 0.03, (1.0 - seen) * 0.75 * w * uWC);
  c += tint * grid * 0.14 * w * seen;
  c += tint * 0.16 * lit * w;
  c += tint * border * lit * 0.5 * w;
  return c;
}
void main(){
  vec3 img = texture2D(uImg, vUv).rgb;
  // the true-colour image is dim and flat; lift it a little without clipping
  img = clamp((img - 0.03) * 1.45, 0.0, 1.0);
  vec3 c = img * uDim;
  c = footprint(c, uM, ${EYES.modis.cell.toFixed(1)}, vec3(1.0, 0.64, 0.23), uWM);
  c = footprint(c, uV, ${EYES.viirs.cell.toFixed(1)}, vec3(0.45, 0.82, 0.86), uWV);
  // soft edge, so the plate reads as a window onto the ground, not a cut-out card
  vec2 e = min(vUv, 1.0 - vUv);
  float edge = smoothstep(0.0, 0.035, min(e.x, e.y * 1.5));
  gl_FragColor = vec4(c * edge, 1.0);
  #include <colorspace_fragment>
}`

const fireVert = /* glsl */ `
attribute float aK; attribute float aCore; attribute float aCloud;
uniform float uTime; uniform float uScale; uniform float uCloud; varying float vA; varying float vCore;
void main(){
  vec4 mv = modelViewMatrix * vec4(position, 1.0);
  float f = 0.75 + 0.25 * sin(uTime * (3.0 + aK * 5.0) + aK * 60.0);
  // fires under cloud fade to a faint trace: they burn, but no eye can see them
  vA = f * (1.0 - 0.8 * aCloud * uCloud); vCore = aCore;
  float size = aCore > 0.5 ? 0.1 + aK * 0.14 : 0.03 + aK * 0.03;
  gl_PointSize = size * uScale * f / -mv.z;
  gl_Position = projectionMatrix * mv;
}`
const fireFrag = /* glsl */ `
varying float vA; varying float vCore;
void main(){
  float d = length(gl_PointCoord - 0.5);
  float core = 1.0 - smoothstep(0.08, 0.2, d);
  float glow = pow(1.0 - smoothstep(0.0, 0.5, d), 2.4);
  vec3 c = vCore > 0.5 ? vec3(1.0, 0.86, 0.55) * core * 2.4 + vec3(1.0, 0.4, 0.08) * glow * 1.1 : vec3(1.0, 0.5, 0.12) * glow * 1.6;
  float a = (vCore > 0.5 ? max(core, glow) : glow) * vA;
  gl_FragColor = vec4(c * vA, a);
}`

function cellTexture(eye: 'modis' | 'viirs', clouds: boolean, countCloudy: boolean) {
  const cell = EYES[eye].cell
  const w = FIELD_W / cell, h = FIELD_H / cell
  const data = new Uint8Array(w * h * 4)
  for (const c of grid(eye, clouds, countCloudy)) {
    const i = (c.y / cell) * w + c.x / cell
    data[i * 4] = c.lit ? 255 : 0
    data[i * 4 + 1] = c.seen ? 255 : 0
    data[i * 4 + 3] = 255
  }
  const t = new THREE.DataTexture(data, w, h, THREE.RGBAFormat)
  t.magFilter = t.minFilter = THREE.NearestFilter
  t.needsUpdate = true
  return t
}

function Clouds({ show }: { show: boolean }) {
  const puffs = useMemo(() => {
    const out: [number, number, number][] = []
    for (let x = 0; x < FIELD_W; x += 8) for (let y = 0; y < FIELD_H; y += 8) {
      if (isCloudy(x, y)) {
        const wx = (x - FIELD_W / 2) * S, wz = (y - FIELD_H / 2) * S
        out.push([wx, drop(wx, wz) + 0.9 + ((x * 7 + y * 3) % 10) / 40, wz])
      }
    }
    return out
  }, [])
  const mat = useMemo(() => {
    const c = document.createElement('canvas'); c.width = c.height = 64
    const g = c.getContext('2d')!
    const grd = g.createRadialGradient(32, 32, 0, 32, 32, 32)
    grd.addColorStop(0, 'rgba(225,228,226,0.55)'); grd.addColorStop(1, 'rgba(225,228,226,0)')
    g.fillStyle = grd; g.fillRect(0, 0, 64, 64)
    return new THREE.SpriteMaterial({ map: new THREE.CanvasTexture(c), transparent: true, opacity: 0, depthWrite: false })
  }, [])
  useFrame((_, dt) => { mat.opacity = THREE.MathUtils.damp(mat.opacity, show ? 0.4 : 0, 2, dt) })
  return (
    <group>
      {puffs.map((p, i) => <sprite key={i} position={p} scale={[1.2, 0.75, 1]} material={mat} />)}
    </group>
  )
}

interface FireTerrainProps {
  view: FieldView
  clouds?: boolean
  cloudsAsZero?: boolean
}

export default function FireTerrain({ view, clouds = false, cloudsAsZero = false }: FireTerrainProps) {
  const img = useTexture(FIELD_IMAGE)
  img.colorSpace = THREE.SRGBColorSpace
  img.anisotropy = 8
  const terrain = useMemo(
    () =>
      new THREE.ShaderMaterial({
        vertexShader: terrainVert,
        fragmentShader: terrainFrag,
        uniforms: { uImg: { value: null }, uM: { value: null }, uV: { value: null }, uWM: { value: 0 }, uWV: { value: 0 }, uWC: { value: 0 }, uDim: { value: 1 } },
      }),
    [],
  )
  const textures = useMemo(() => ({ m: cellTexture('modis', clouds, cloudsAsZero), v: cellTexture('viirs', clouds, cloudsAsZero) }), [clouds, cloudsAsZero])
  terrain.uniforms.uImg.value = img
  terrain.uniforms.uM.value = textures.m
  terrain.uniforms.uV.value = textures.v

  // each fire is a hot core with a few embers around it, set on the curved plate
  const fires = useMemo(() => {
    const r = mulberry32(9)
    const pos: number[] = [], k: number[] = [], core: number[] = [], cloud: number[] = []
    const put = (fx: number, fy: number, kk: number, isCore: number) => {
      const wx = (fx - FIELD_W / 2) * S, wz = (fy - FIELD_H / 2) * S
      pos.push(wx, drop(wx, wz) + 0.02, wz)
      k.push(kk); core.push(isCore); cloud.push(isCloudy(fx, fy) ? 1 : 0)
    }
    for (const f of FIRES) {
      put(f.x, f.y, f.k, 1)
      const n = 2 + Math.floor(f.k * 5)
      for (let i = 0; i < n; i++) put(f.x + (r() - 0.5) * 3.2, f.y + (r() - 0.5) * 3.2, r() * f.k, 0)
    }
    const g = new THREE.BufferGeometry()
    g.setAttribute('position', new THREE.Float32BufferAttribute(pos, 3))
    g.setAttribute('aK', new THREE.Float32BufferAttribute(k, 1))
    g.setAttribute('aCore', new THREE.Float32BufferAttribute(core, 1))
    g.setAttribute('aCloud', new THREE.Float32BufferAttribute(cloud, 1))
    const m = new THREE.ShaderMaterial({
      vertexShader: fireVert,
      fragmentShader: fireFrag,
      transparent: true,
      depthWrite: false,
      blending: THREE.AdditiveBlending,
      uniforms: { uTime: { value: 0 }, uScale: { value: 1000 }, uCloud: { value: 0 } },
    })
    return { g, m }
  }, [])

  const size = useMemo(() => new THREE.Vector2(), [])
  useFrame((st, dt) => {
    const u = terrain.uniforms
    u.uWM.value = THREE.MathUtils.damp(u.uWM.value, view === 'modis' || view === 'both' ? 1 : 0, 4, dt)
    u.uWV.value = THREE.MathUtils.damp(u.uWV.value, view === 'viirs' || view === 'both' ? 1 : 0, 4, dt)
    u.uWC.value = THREE.MathUtils.damp(u.uWC.value, clouds ? 1 : 0, 3, dt)
    // the image dims a little under the footprints so the squares read
    u.uDim.value = THREE.MathUtils.damp(u.uDim.value, view === 'ground' ? 1 : 0.78, 3, dt)
    const fu = fires.m.uniforms
    fu.uTime.value += dt
    fu.uCloud.value = u.uWC.value
    // world-sized points: pixels per world unit at distance 1
    st.gl.getDrawingBufferSize(size)
    const cam = st.camera as THREE.PerspectiveCamera
    fu.uScale.value = size.y / (2 * Math.tan(THREE.MathUtils.degToRad(cam.fov) / 2))
  })

  return (
    <group>
      <mesh rotation={[-Math.PI / 2, 0, 0]} material={terrain}>
        <planeGeometry args={[FIELD_W * S, FIELD_H * S, 120, 80]} />
      </mesh>
      <points geometry={fires.g} material={fires.m} />
      <Clouds show={clouds} />
    </group>
  )
}
