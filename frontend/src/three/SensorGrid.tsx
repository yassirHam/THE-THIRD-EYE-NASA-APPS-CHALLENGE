import { useMemo, useRef } from 'react'
import { useFrame } from '@react-three/fiber'
import * as THREE from 'three'

/* Sensor footprints drawn as a thin grid over a sharp globe, instead of pixelating the frame.
   The left half of the screen shows the fine grid (VIIRS), the right half the coarse grid
   (MODIS); each half fades with its own weight. The fine cells are 2.67 times smaller, the
   ratio of 1 km to 375 m. Both are drawn far larger than real, so they can be seen. */

const vert = /* glsl */ `
varying vec3 vN; varying vec3 vW;
void main(){
  vN = normalize(mat3(modelMatrix) * normal);
  vec4 w = modelMatrix * vec4(position, 1.0); vW = w.xyz;
  gl_Position = projectionMatrix * viewMatrix * w;
}`

const frag = /* glsl */ `
uniform float uFine; uniform float uCoarse; uniform vec2 uRes; uniform vec3 uCenter; uniform float uScan;
varying vec3 vN; varying vec3 vW;
#define PI 3.14159265
float gl(float v){ float g = abs(fract(v - 0.5) - 0.5); float fw = fwidth(v); return 1.0 - smoothstep(fw * 0.5, fw * 1.5, g); }
float grid(vec3 n, float cells){
  float lon = atan(n.z, n.x) / (2.0 * PI) * cells;
  float lat = asin(clamp(n.y, -1.0, 1.0)) / PI * cells * 0.5;
  return max(gl(lon), gl(lat));
}
void main(){
  vec3 N = normalize(vN);
  vec3 toCam = normalize(cameraPosition - uCenter);
  float facing = smoothstep(0.15, 0.6, dot(N, toCam));
  // the swath: a band across the visible face, tilted like an orbit track
  vec3 across = normalize(cross(toCam, normalize(vec3(0.32, 1.0, 0.0))));
  float d = abs(dot(N, across));
  float swath = 1.0 - smoothstep(0.3, 0.34, d);
  float edge = (1.0 - smoothstep(0.0, 0.006, abs(d - 0.32))) * 0.45;
  bool left = gl_FragCoord.x < uRes.x * 0.5;
  float w = left ? uFine : uCoarse;
  vec3 col = left ? vec3(0.45, 0.82, 0.86) : vec3(1.0, 0.66, 0.26);
  float lines = grid(N, left ? 107.0 : 40.0) * (left ? 0.26 : 0.38);
  // a scan line sweeping along the swath
  float along = dot(N, normalize(cross(across, toCam)));
  float scan = (1.0 - smoothstep(0.0, 0.006, abs(along - uScan))) * 0.5;
  float a = (lines * swath + edge + scan * swath) * facing * w;
  gl_FragColor = vec4(col * a, a);
  #include <colorspace_fragment>
}`

interface SensorGridProps {
  radius: number
  /** weights read every frame, 0..1 */
  state: { tintL: number; tintR: number }
}

export default function SensorGrid({ radius, state }: SensorGridProps) {
  const mat = useMemo(
    () =>
      new THREE.ShaderMaterial({
        vertexShader: vert,
        fragmentShader: frag,
        transparent: true,
        depthWrite: false,
        blending: THREE.AdditiveBlending,
        uniforms: { uFine: { value: 0 }, uCoarse: { value: 0 }, uRes: { value: new THREE.Vector2() }, uCenter: { value: new THREE.Vector3() }, uScan: { value: 0 } },
      }),
    [],
  )
  const mesh = useRef<THREE.Mesh>(null)
  useFrame((st, dt) => {
    const u = mat.uniforms
    u.uFine.value = state.tintL
    u.uCoarse.value = state.tintR
    st.gl.getDrawingBufferSize(u.uRes.value)
    u.uScan.value = ((u.uScan.value + dt * 0.35 + 1) % 2) - 1
    mesh.current?.getWorldPosition(u.uCenter.value)
  })
  return (
    <mesh ref={mesh} material={mat}>
      <sphereGeometry args={[radius * 1.006, 128, 96]} />
    </mesh>
  )
}
