import { useMemo } from 'react'
import { useFrame } from '@react-three/fiber'
import * as THREE from 'three'
import { mulberry32 } from '../lib/random'

const starVert = /* glsl */ `
attribute float aSize; attribute float aSeed; uniform float uTime; uniform float uPR; varying float vA;
void main(){ vec4 mv = modelViewMatrix * vec4(position,1.0);
  vA = 0.55 + 0.45 * sin(uTime * (0.5 + aSeed * 2.0) + aSeed * 30.0);
  gl_PointSize = aSize * uPR; gl_Position = projectionMatrix * mv; }`
const starFrag = /* glsl */ `
varying float vA;
void main(){ float d = length(gl_PointCoord - 0.5); float s = smoothstep(0.5, 0.0, d);
  gl_FragColor = vec4(vec3(0.93, 0.87, 0.74) * s * vA, s * vA); }`

/** Distant stars on a shell around the scene. */
export function Stars({ count = 2500, radius = 60 }: { count?: number; radius?: number }) {
  const { geom, mat } = useMemo(() => {
    const r = mulberry32(99)
    const pos = new Float32Array(count * 3), size = new Float32Array(count), seed = new Float32Array(count)
    for (let i = 0; i < count; i++) {
      const u = r() * 2 - 1, t = r() * Math.PI * 2, s = Math.sqrt(1 - u * u)
      const d = radius * (0.7 + r() * 0.3)
      pos.set([s * Math.cos(t) * d, u * d, s * Math.sin(t) * d], i * 3)
      size[i] = r() < 0.04 ? 3.2 : 1 + r() * 1.6
      seed[i] = r()
    }
    const g = new THREE.BufferGeometry()
    g.setAttribute('position', new THREE.BufferAttribute(pos, 3))
    g.setAttribute('aSize', new THREE.BufferAttribute(size, 1))
    g.setAttribute('aSeed', new THREE.BufferAttribute(seed, 1))
    const m = new THREE.ShaderMaterial({ vertexShader: starVert, fragmentShader: starFrag, transparent: true, depthWrite: false, blending: THREE.AdditiveBlending, uniforms: { uTime: { value: 0 }, uPR: { value: 1 } } })
    return { geom: g, mat: m }
  }, [count, radius])
  useFrame((st, dt) => { mat.uniforms.uTime.value += dt; mat.uniforms.uPR.value = st.gl.getPixelRatio() })
  return <points geometry={geom} material={mat} />
}

const emberVert = /* glsl */ `
attribute float aSeed; uniform float uTime; uniform float uPR; uniform float uHeight; varying float vA;
void main(){ vec3 p = position;
  float t = fract(uTime * (0.03 + aSeed * 0.05) + aSeed);
  p.y += t * uHeight; p.x += sin(t * 9.0 + aSeed * 20.0) * 0.4; p.z += cos(t * 7.0 + aSeed * 12.0) * 0.3;
  vA = smoothstep(0.0, 0.15, t) * (1.0 - smoothstep(0.6, 1.0, t));
  vec4 mv = modelViewMatrix * vec4(p, 1.0);
  gl_PointSize = (6.0 + aSeed * 10.0) * uPR / -mv.z; gl_Position = projectionMatrix * mv; }`
const emberFrag = /* glsl */ `
varying float vA;
void main(){ float d = length(gl_PointCoord - 0.5); float s = pow(smoothstep(0.5, 0.0, d), 2.0);
  gl_FragColor = vec4(vec3(1.0, 0.45, 0.12) * s * vA * 2.0, s * vA); }`

/** Rising embers: the fire motif drifting through the scene. */
export function Embers({ count = 400, spread = 14, height = 10, y = -5 }: { count?: number; spread?: number; height?: number; y?: number }) {
  const { geom, mat } = useMemo(() => {
    const r = mulberry32(7)
    const pos = new Float32Array(count * 3), seed = new Float32Array(count)
    for (let i = 0; i < count; i++) {
      pos.set([(r() - 0.5) * spread, y + r() * 2, (r() - 0.5) * spread * 0.6], i * 3)
      seed[i] = r()
    }
    const g = new THREE.BufferGeometry()
    g.setAttribute('position', new THREE.BufferAttribute(pos, 3))
    g.setAttribute('aSeed', new THREE.BufferAttribute(seed, 1))
    const m = new THREE.ShaderMaterial({ vertexShader: emberVert, fragmentShader: emberFrag, transparent: true, depthWrite: false, blending: THREE.AdditiveBlending, uniforms: { uTime: { value: 0 }, uPR: { value: 1 }, uHeight: { value: height } } })
    return { geom: g, mat: m }
  }, [count, spread, height, y])
  useFrame((st, dt) => { mat.uniforms.uTime.value += dt; mat.uniforms.uPR.value = st.gl.getPixelRatio() })
  return <points geometry={geom} material={mat} frustumCulled={false} />
}
