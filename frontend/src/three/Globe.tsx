import { useMemo, useRef } from 'react'
import { useFrame } from '@react-three/fiber'
import { useTexture } from '@react-three/drei'
import * as THREE from 'three'
import { fireSites } from './fireSites'

const vert = /* glsl */ `
varying vec2 vUv; varying vec3 vN; varying vec3 vWorld;
void main(){
  vUv = uv;
  vN = normalize(mat3(modelMatrix) * normal);
  vec4 w = modelMatrix * vec4(position, 1.0);
  vWorld = w.xyz;
  gl_Position = projectionMatrix * viewMatrix * w;
}`

const frag = /* glsl */ `
uniform sampler2D uOcean; uniform sampler2D uLights; uniform sampler2D uDay;
uniform vec3 uSun; uniform float uTime; uniform float uEtch;
varying vec2 vUv; varying vec3 vN; varying vec3 vWorld;
float gl(float v, float w){ float g = abs(fract(v - 0.5) - 0.5); float fw = fwidth(v); return 1.0 - smoothstep(fw * w * 0.5, fw * (w * 0.5 + 1.0), g); }
void main(){
  vec3 N = normalize(vN);
  vec3 V = normalize(cameraPosition - vWorld);
  float oc = texture2D(uOcean, vUv).r;
  float land = 1.0 - smoothstep(0.25, 0.55, oc);
  vec3 day = texture2D(uDay, vUv).rgb;
  float lum = dot(day, vec3(0.299, 0.587, 0.114));
  float sunD = dot(N, normalize(uSun));
  float lit = smoothstep(-0.25, 0.6, sunD);

  vec3 ocean = mix(vec3(0.003, 0.006, 0.008), vec3(0.007, 0.018, 0.022), lit);
  vec3 landC = mix(vec3(0.014, 0.011, 0.008), vec3(0.075, 0.05, 0.026) * (0.5 + lum * 1.4), lit);
  // engraving: latitude hatching bent by relief, like an old etched globe
  float hatch = gl(vUv.y * 420.0 + lum * 4.0 + sin(vUv.x * 60.0) * 0.15, 1.0);
  landC += vec3(0.75, 0.6, 0.38) * hatch * (0.025 + 0.07 * lit) * uEtch;
  vec3 col = mix(ocean, landC, land);

  float edge = clamp(length(vec2(dFdx(land), dFdy(land))) * 2.5, 0.0, 1.0);
  col += vec3(0.9, 0.55, 0.2) * edge * (0.16 + 0.22 * lit);

  float grat = max(gl(vUv.x * 24.0, 1.0), gl(vUv.y * 12.0, 1.0));
  col += vec3(0.8, 0.72, 0.55) * grat * 0.05;

  vec3 lights = texture2D(uLights, vUv).rgb;
  col += vec3(1.0, 0.5, 0.15) * lights.r * (1.0 - lit) * 0.9;

  col += vec3(0.6, 0.22, 0.12) * exp(-abs(sunD) * 12.0) * 0.18;
  float fr = pow(1.0 - max(dot(N, V), 0.0), 3.0);
  col += vec3(0.25, 0.42, 0.45) * fr * 0.32;
  gl_FragColor = vec4(col, 1.0);
  #include <colorspace_fragment>
}`

const atmoVert = /* glsl */ `
varying vec3 vNv; varying vec3 vPv;
void main(){ vNv = normalize(normalMatrix * normal); vec4 mv = modelViewMatrix * vec4(position,1.0); vPv = mv.xyz; gl_Position = projectionMatrix * mv; }`
const atmoFrag = /* glsl */ `
varying vec3 vNv; varying vec3 vPv;
void main(){
  float rim = pow(1.0 - abs(dot(vNv, normalize(-vPv))), 5.0);
  vec3 c = vec3(0.3, 0.55, 0.6) * rim * 0.35;
  gl_FragColor = vec4(c, rim);
  #include <colorspace_fragment>
}`

const fireVert = /* glsl */ `
attribute float aKind; attribute float aSeed;
uniform float uTime; uniform float uModis; uniform float uViirs; uniform float uSize; uniform float uPR;
varying vec3 vColor; varying float vA;
void main(){
  vec4 mv = modelViewMatrix * vec4(position, 1.0);
  float big = 1.0 - aKind;
  float a = max(big * uModis, uViirs);
  vec3 cM = vec3(1.0, 0.42, 0.06); vec3 cV = vec3(0.25, 0.75, 0.8);
  vColor = mix(cV, cM, big * uModis);
  float flick = 0.7 + 0.3 * sin(uTime * (2.0 + aSeed * 5.0) + aSeed * 40.0);
  vA = a * flick;
  gl_PointSize = uSize * mix(1.0, 1.9, big) * uPR * flick / -mv.z;
  gl_Position = projectionMatrix * mv;
}`
const fireFrag = /* glsl */ `
varying vec3 vColor; varying float vA;
void main(){
  float d = length(gl_PointCoord - 0.5);
  float s = pow(smoothstep(0.5, 0.0, d), 2.2);
  gl_FragColor = vec4(vColor * s * vA * 3.0, s * vA);
}`

export interface FireLevels { modis: number; viirs: number }

interface GlobeProps {
  radius?: number
  /** read every frame so GSAP or scroll can drive fire visibility */
  fires?: FireLevels
  spin?: number
  sun?: [number, number, number]
}

export default function Globe({ radius = 2, fires, spin = 0.02, sun = [-4, 1.4, 0.4] }: GlobeProps) {
  const group = useRef<THREE.Group>(null)
  // WebP encodes (quality 0.82, same 2048 x 1024 size) of the masters in frontend/source-textures/
  const [ocean, lights, day] = useTexture(['/tex/earth_specular_2048.webp', '/tex/earth_lights_2048.webp', '/tex/earth_atmos_2048.webp'])
  day.colorSpace = THREE.SRGBColorSpace
  ;[ocean, lights, day].forEach((t) => { t.anisotropy = 8 })

  const mat = useMemo(
    () =>
      new THREE.ShaderMaterial({
        vertexShader: vert,
        fragmentShader: frag,
        uniforms: {
          uOcean: { value: ocean },
          uLights: { value: lights },
          uDay: { value: day },
          uSun: { value: new THREE.Vector3(...sun) },
          uTime: { value: 0 },
          uEtch: { value: 1 },
        },
      }),
    [ocean, lights, day], // eslint-disable-line react-hooks/exhaustive-deps
  )

  const atmo = useMemo(
    () => new THREE.ShaderMaterial({ vertexShader: atmoVert, fragmentShader: atmoFrag, side: THREE.BackSide, transparent: true, blending: THREE.AdditiveBlending, depthWrite: false }),
    [],
  )

  const { geom, fireMat } = useMemo(() => {
    const s = fireSites(radius * 1.004)
    const g = new THREE.BufferGeometry()
    g.setAttribute('position', new THREE.BufferAttribute(s.positions, 3))
    g.setAttribute('aKind', new THREE.BufferAttribute(s.kinds, 1))
    g.setAttribute('aSeed', new THREE.BufferAttribute(s.seeds, 1))
    const m = new THREE.ShaderMaterial({
      vertexShader: fireVert,
      fragmentShader: fireFrag,
      transparent: true,
      depthWrite: false,
      blending: THREE.AdditiveBlending,
      uniforms: { uTime: { value: 0 }, uModis: { value: 1 }, uViirs: { value: 1 }, uSize: { value: 26 }, uPR: { value: 1 } },
    })
    return { geom: g, fireMat: m }
  }, [radius])

  useFrame((st, dt) => {
    mat.uniforms.uTime.value += dt
    fireMat.uniforms.uTime.value += dt
    fireMat.uniforms.uPR.value = st.gl.getPixelRatio()
    if (fires) {
      fireMat.uniforms.uModis.value = THREE.MathUtils.damp(fireMat.uniforms.uModis.value, fires.modis, 4, dt)
      fireMat.uniforms.uViirs.value = THREE.MathUtils.damp(fireMat.uniforms.uViirs.value, fires.viirs, 4, dt)
    }
    if (group.current) group.current.rotation.y += dt * spin
  })

  return (
    <group>
      <group ref={group} rotation={[0.41, -1.2, 0]}>
        <mesh material={mat}>
          <sphereGeometry args={[radius, 128, 96]} />
        </mesh>
        <points geometry={geom} material={fireMat} />
      </group>
      <mesh material={atmo} scale={1.035}>
        <sphereGeometry args={[radius, 64, 48]} />
      </mesh>
    </group>
  )
}
