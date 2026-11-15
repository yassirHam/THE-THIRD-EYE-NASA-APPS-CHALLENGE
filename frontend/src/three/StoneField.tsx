import { useMemo } from 'react'
import * as THREE from 'three'
import { mulberry32 } from '../lib/random'

const floorVert = /* glsl */ `
varying vec2 vP; void main(){ vP = position.xy; gl_Position = projectionMatrix * modelViewMatrix * vec4(position,1.0); }`
/* Observatory floor: engraved rings and hour lines radiating from the gnomon, fading into dark. */
const floorFrag = /* glsl */ `
varying vec2 vP;
float gl(float v, float w){ float g = abs(fract(v - 0.5) - 0.5); float fw = fwidth(v); return 1.0 - smoothstep(fw * w * 0.5, fw * (w * 0.5 + 1.0), g); }
float h(vec2 p){ return fract(sin(dot(p, vec2(12.9898, 78.233))) * 43758.5453); }
void main(){
  vec2 p = vP - vec2(0.0, -2.5);
  float r = length(p); float a = atan(p.y, p.x);
  float rings = gl(r * 0.5, 0.8) * (1.0 - smoothstep(4.0, 34.0, r));
  float hours = gl(a / 6.2831853 * 24.0, 0.8) * smoothstep(1.0, 2.0, r) * (1.0 - smoothstep(8.0, 28.0, r));
  float fade = 1.0 - smoothstep(3.0, 34.0, r);
  float grain = h(floor(vP * 30.0)) * 0.5 + 0.5;
  vec3 c = vec3(0.016, 0.012, 0.01) * fade * grain;
  c += vec3(0.85, 0.55, 0.26) * (rings * 0.12 + hours * 0.07) * fade;
  c += vec3(0.6, 0.22, 0.07) * exp(-r * 0.18) * 0.09;
  gl_FragColor = vec4(c, 1.0);
  #include <colorspace_fragment>
}`

/** Weathered monolith: a tall box with displaced, chipped vertices. */
function monolithGeometry(seed: number) {
  const r = mulberry32(seed)
  const g = new THREE.BoxGeometry(1, 1, 1, 3, 8, 2)
  const pos = g.attributes.position as THREE.BufferAttribute
  const v = new THREE.Vector3()
  const lean = (r() - 0.5) * 0.12
  const taper = 0.75 + r() * 0.2
  const chip = r() * 0.5
  for (let i = 0; i < pos.count; i++) {
    v.fromBufferAttribute(pos, i)
    const t = v.y + 0.5
    const n = Math.sin(v.y * 9 + seed) * 0.03 + Math.sin(v.x * 13 + v.z * 7 + seed * 3) * 0.025
    v.x *= 1 - t * (1 - taper)
    v.z *= 1 - t * (1 - taper)
    v.x += v.x * n * 2 + lean * t
    v.z += v.z * n * 2
    if (t > 0.92) v.y -= (v.x > 0 ? chip : 0.1) * 0.08 + Math.abs(Math.sin(v.z * 20)) * 0.02
    pos.setXYZ(i, v.x, v.y, v.z)
  }
  g.computeVertexNormals()
  return g
}

/** Shared stone material with carved glyph bands that glow faintly, like embers in old rock. */
function makeStoneMaterial() {
  const m = new THREE.MeshStandardMaterial({ color: '#3a2f25', roughness: 0.94, metalness: 0.02 })
  m.onBeforeCompile = (sh) => {
    sh.vertexShader = sh.vertexShader
      .replace('#include <common>', '#include <common>\nvarying vec3 vObj;')
      .replace('#include <begin_vertex>', '#include <begin_vertex>\nvObj = position;')
    sh.fragmentShader = sh.fragmentShader
      .replace('#include <common>', '#include <common>\nvarying vec3 vObj;\nfloat hh(vec2 p){ return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453); }')
      .replace(
        '#include <emissivemap_fragment>',
        `#include <emissivemap_fragment>
        vec2 gp = vec2(vObj.x * 6.0 + vObj.z * 6.0, vObj.y * 14.0);
        vec2 cell = floor(gp); vec2 f = fract(gp);
        float on = step(0.72, hh(cell)) * step(0.15, vObj.y + 0.5) * step(vObj.y + 0.5, 0.82);
        float glyph = on * (step(abs(f.x - 0.5), 0.06) + step(abs(f.y - 0.5), 0.05) * step(0.5, hh(cell + 3.0)));
        totalEmissiveRadiance += vec3(1.0, 0.45, 0.12) * glyph * 0.9;
        float strata = sin(vObj.y * 40.0 + hh(floor(vObj.xz * 3.0)) * 6.0) * 0.5 + 0.5;
        diffuseColor.rgb *= 0.75 + strata * 0.35;`,
      )
  }
  return m
}

/** Standing stones on an engraved floor. The intro places a child with a raised finger near
 *  the viewer; moving the camera sideways makes the finger jump against these stones. */
export default function StoneField() {
  const { stones, stoneMat, floorMat } = useMemo(() => {
    const r = mulberry32(31)
    const geoms = Array.from({ length: 6 }, (_, i) => monolithGeometry(i * 17 + 3))
    const list: { pos: THREE.Vector3; scale: THREE.Vector3; rot: number; g: THREE.BufferGeometry }[] = []
    for (let i = 0; i < 52; i++) {
      const ring = 8 + r() * 24
      const a = -Math.PI * 0.88 + r() * Math.PI * 0.76
      const pos = new THREE.Vector3(Math.cos(a) * ring * 1.35, 0, Math.sin(a) * ring - 3)
      const h = 1.4 + r() * 4.2
      list.push({ pos, scale: new THREE.Vector3(0.45 + r() * 0.9, h, 0.3 + r() * 0.45), rot: r() * Math.PI, g: geoms[i % geoms.length] })
    }
    return { stones: list, stoneMat: makeStoneMaterial(), floorMat: new THREE.ShaderMaterial({ vertexShader: floorVert, fragmentShader: floorFrag }) }
  }, [])

  return (
    <group>
      <mesh rotation={[-Math.PI / 2, 0, 0]} material={floorMat}>
        <planeGeometry args={[120, 120]} />
      </mesh>
      {stones.map((s, i) => (
        <mesh key={i} geometry={s.g} material={stoneMat} position={[s.pos.x, s.scale.y / 2, s.pos.z]} rotation={[0, s.rot, 0]} scale={s.scale} />
      ))}
      {/* firelight from braziers out of frame, cool rim from the sky */}
      <pointLight position={[-4, 1.4, 3]} intensity={26} distance={20} color="#ff8a3a" />
      <pointLight position={[5, 1, -8]} intensity={18} distance={26} color="#e5642b" />
      <directionalLight position={[0, 6, -14]} intensity={1.1} color="#7fb6b8" />
    </group>
  )
}
