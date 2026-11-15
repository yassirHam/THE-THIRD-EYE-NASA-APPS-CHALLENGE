import { useEffect, useMemo } from 'react'
import { Canvas, useFrame, useThree } from '@react-three/fiber'
import * as THREE from 'three'
import { arrival, curves, HOLD, END } from './arrival'

/* The first-visit opening film, drawn by one full-screen fragment shader so it needs no
   downloads to start: a dust nebula, the third eye opening inside it, a dive through the
   pupil into a warp, then deep space and the approach to the night side of the Earth.
   The Earth uses the same NASA Blue Marble and Black Marble maps as the site once they
   arrive, and a procedural stand-in until then. */

const vert = /* glsl */ `
varying vec2 vUv;
void main(){ vUv = uv; gl_Position = vec4(position.xy, 0.0, 1.0); }`

const frag = /* glsl */ `
precision highp float;
uniform vec2 uRes; uniform float uTime;
uniform float uFade, uEyeLine, uEye, uDive, uEyeScale, uWarp, uDist, uNeb, uSpace;
uniform float uEarthR, uEarthY, uSunY, uSunS, uRays, uTex;
uniform sampler2D uDay; uniform sampler2D uLights;
varying vec2 vUv;

#define TAU 6.28318530718

float hash(vec2 p){ p = fract(p * vec2(123.34, 456.21)); p += dot(p, p + 45.32); return fract(p.x * p.y); }
float noise(vec2 p){
  vec2 i = floor(p), f = fract(p); vec2 u = f * f * (3.0 - 2.0 * f);
  return mix(mix(hash(i), hash(i + vec2(1, 0)), u.x), mix(hash(i + vec2(0, 1)), hash(i + vec2(1, 1)), u.x), u.y);
}
float fbm(vec2 p){
  float v = 0.0, a = 0.5; mat2 m = mat2(1.6, 1.2, -1.2, 1.6);
  for (int i = 0; i < 5; i++){ v += a * noise(p); p = m * p; a *= 0.5; }
  return v;
}

/* round points of light, at most one per grid cell, about a pixel and a half wide */
float stars(vec2 p, float scale, float thr, float seed){
  vec2 g = p * scale + seed; vec2 id = floor(g); vec2 f = fract(g) - 0.5;
  float h = hash(id + seed);
  vec2 o = vec2(hash(id + 3.1), hash(id + 5.7)) - 0.5;
  float d = length(f - o * 0.7) / scale;
  float px = 2.0 / uRes.y;
  float tw = 0.75 + 0.25 * sin(uTime * (1.0 + h * 3.0) + h * 50.0);
  return step(thr, h) * smoothstep(px * 1.4, 0.0, d) * (h - thr) / (1.0 - thr) * tw;
}

/* dust nebula: a band of amber and violet gas, white filaments, a bright knot near the centre.
   p is the zoomed texture position; sp is the screen position, which keeps the band and the
   knot in place while the camera flies in. */
vec3 nebula(vec2 p, vec2 sp, float seed){
  vec2 x = p + vec2(seed * 3.7, seed * 1.9);
  vec2 q = vec2(fbm(x * 1.6 + vec2(0.0, uTime * 0.025)), fbm(x * 1.6 + vec2(5.2, 1.3) - uTime * 0.02));
  float n = fbm(x * 3.0 + q * 2.2);
  float fine = fbm(x * 9.0 + q * 3.0);
  float ridge = 1.0 - abs(n * 2.0 - 1.0);
  float band = exp(-pow(sp.y * 1.8 + (q.x - 0.5) * 0.9, 2.0) * 2.4);
  float dens = smoothstep(0.45, 0.85, n * 0.72 + fine * 0.38) * band;
  vec3 col = vec3(0.016, 0.008, 0.012) * band;
  col += mix(vec3(0.6, 0.27, 0.1), vec3(0.4, 0.3, 0.62), smoothstep(0.4, 0.65, q.y)) * dens * 0.75;
  col += vec3(1.0, 0.9, 0.8) * pow(ridge, 9.0) * smoothstep(0.45, 0.8, fine) * band * 1.6;
  vec2 k = sp - vec2(0.05, 0.0);
  float core = exp(-dot(k, k) * 3.2);
  col += vec3(0.95, 0.93, 1.0) * pow(dens, 1.6) * core * 2.4;
  // dust grains glinting inside the gas
  col += vec3(1.0, 0.85, 0.7) * stars(x, 160.0, 0.9, seed) * dens * 3.0;
  return col;
}

/* endless zoom: two nebula layers one octave apart, crossfaded as the camera moves in */
vec3 nebulaZoom(vec2 p, float L){
  float f = fract(L), i = floor(L);
  float s = exp(-f * 0.6931);
  vec3 a = nebula(p * s, p, i);
  vec3 b = nebula(p * s * 2.0, p, i + 1.0);
  return mix(a, b, f);
}

/* light streaks flying outward from the centre */
float streaks(vec2 p, float d, float N, float seed){
  float a = atan(p.y, p.x);
  float r = length(p);
  float cell = (a / TAU + 0.5) * N;
  float id = floor(cell);
  float h = hash(vec2(id, seed)), h2 = hash(vec2(id + 7.1, seed * 1.7));
  float z = fract(h + d * (0.5 + h2 * 0.6));
  float head = 0.04 + pow(z, 2.4) * 2.4;
  float len = (0.03 + 0.6 * uWarp) * pow(z, 1.4);
  float along = smoothstep(head - len, head, r) * (1.0 - smoothstep(head, head + 0.004, r));
  float w = abs(fract(cell) - 0.5 + (h2 - 0.5) * 0.5) * (TAU / N) * r;
  float px = 2.0 / uRes.y;
  float line = 1.0 - smoothstep(px * 0.35, px * 1.25, w);
  return line * along * smoothstep(0.0, 0.25, z) * step(0.3, h);
}

/* the Milky Way seen edge on: a grey band with dark dust lanes, warm near the middle */
vec3 galaxy(vec2 p){
  float ca = cos(-0.14), sa = sin(-0.14);
  vec2 r = mat2(ca, -sa, sa, ca) * p;
  float n = fbm(r * vec2(1.6, 5.5) + 3.0);
  float d = fbm(r * vec2(3.5, 11.0) + 11.0);
  float band = exp(-pow(r.y * 4.2 + (n - 0.5) * 0.9, 2.0));
  float dust = smoothstep(0.48, 0.72, d);
  vec3 col = vec3(0.24, 0.23, 0.26) * band * n;
  col *= 1.0 - dust * 0.85 * band;
  col += vec3(0.45, 0.26, 0.13) * band * pow(n, 2.5) * exp(-r.x * r.x * 1.5) * 0.7;
  col += vec3(0.8, 0.78, 0.85) * stars(r, 260.0, 0.72, 4.0) * band * 0.7;
  return col;
}

vec3 sunGlow(vec2 p, vec2 s, float size){
  vec2 d = p - s; float r = length(d);
  float a = atan(d.y, d.x);
  vec2 ring = vec2(cos(a), sin(a));
  float n1 = noise(ring * 7.0 + uTime * 0.04);
  float n2 = noise(ring * 19.0 - uTime * 0.03 + 9.0);
  float rays = (pow(n1, 5.0) * 1.2 + pow(n2, 8.0) * 1.6) * exp(-r / (size * 9.0 + 0.04)) * uRays;
  float core = exp(-r / (size * 0.22)) * 2.2;
  float halo = exp(-r / (size * 2.4)) * 0.45 + exp(-r / (size * 12.0 + 0.05)) * 0.12;
  return vec3(1.0, 0.82, 0.55) * (core + halo) + vec3(1.0, 0.7, 0.4) * rays;
}

/* lens ghosts along the line from the sun through the centre of the frame */
vec3 ghosts(vec2 p, vec2 s, float k){
  vec3 col = vec3(0.0);
  for (int i = 0; i < 6; i++){
    float fi = float(i);
    float at = 0.45 + fi * 0.33;
    vec2 g = s + (vec2(0.0, -0.2) - s) * at;
    float rad = 0.018 + hash(vec2(fi, 2.0)) * 0.04;
    float d = length(p - g);
    float disc = smoothstep(rad, rad * 0.75, d) * 0.6 + exp(-abs(d - rad) * 220.0) * 0.4;
    vec3 tint = fi < 2.0 ? vec3(0.7, 0.5, 0.9) : (fi < 4.0 ? vec3(0.9, 0.6, 0.35) : vec3(0.45, 0.65, 0.7));
    col += tint * disc * 0.07;
  }
  return col * k;
}

vec3 earth(vec2 p, vec2 c, float R, vec2 sunP, out float mask){
  vec2 q = (p - c) / R;
  float r = length(q);
  float px = 2.0 / uRes.y / R;
  mask = smoothstep(1.0, 1.0 - px * 1.5, r);
  vec2 toSun = normalize(sunP - c);
  vec3 L = normalize(vec3(toSun * 0.55, -0.83));
  vec3 col = vec3(0.0);
  if (r < 1.0){
    vec3 n = vec3(q, sqrt(max(0.0, 1.0 - r * r)));
    float lat0 = 0.36, lon0 = 0.28 + uTime * 0.012;
    vec3 m = vec3(n.x, n.y * cos(lat0) + n.z * sin(lat0), -n.y * sin(lat0) + n.z * cos(lat0));
    float lon = atan(m.x, m.z) + lon0;
    vec2 uv = vec2(fract(0.5 + lon / TAU), 0.5 + asin(clamp(m.y, -1.0, 1.0)) / 3.14159265);
    vec3 day = texture2D(uDay, uv).rgb;
    float lights = texture2D(uLights, uv).r;
    // procedural stand-in while the maps are still downloading
    float land = smoothstep(0.5, 0.56, fbm(vec2(uv.x * 9.0, uv.y * 4.5) + 2.0));
    vec3 pDay = mix(vec3(0.03, 0.07, 0.13), vec3(0.22, 0.19, 0.12), land);
    // sparse fine points, gathered into clusters like cities
    float towns = smoothstep(0.52, 0.75, fbm(uv * vec2(40.0, 20.0) + 7.0));
    float pLights = land * towns * pow(noise(uv * vec2(2400.0, 1200.0)), 7.0) * 2.2;
    day = mix(pDay, day, uTex);
    lights = mix(pLights, lights, uTex);
    float sd = dot(n, L);
    float lit = smoothstep(-0.06, 0.4, sd);
    col = vec3(0.006, 0.01, 0.016) + day * lit * 1.1;
    col += vec3(1.0, 0.56, 0.2) * pow(lights, 1.3) * 1.7 * (1.0 - lit);
    float fres = pow(1.0 - n.z, 2.5);
    col += vec3(0.42, 0.62, 0.72) * fres * (0.08 + 1.4 * smoothstep(-0.3, 0.6, sd));
    col *= mask;
  }
  // thin atmosphere outside the limb, brightest toward the sun
  float rim = exp(-max(r - 1.0, 0.0) / 0.035) * (1.0 - mask);
  float side = 0.15 + 1.6 * pow(max(dot(normalize(q + 1e-5), toSun), 0.0), 2.0);
  col += vec3(0.55, 0.72, 0.8) * rim * side * 0.6;
  return col;
}

void main(){
  vec2 frag = vUv * uRes;
  vec2 p = (frag - 0.5 * uRes) / uRes.y * 2.0;
  float px = 2.0 / uRes.y;
  vec3 col = vec3(0.0);

  // ---------- nebula, the eye and the warp ----------
  if (uNeb > 0.001){
    float L = uTime * 0.035 + uDist * 1.3;
    vec3 nb = nebulaZoom(p, L);
    // in the warp the gas thins to a dark tunnel so the streaks carry the speed
    nb *= 1.0 - 0.55 * uWarp;
    // the eye focuses: brighter inside the opening, dimmer outside
    vec2 pe = p / uEyeScale;
    float H = 0.44, W = 0.19 * uEye;
    float yy = clamp(pe.y / H, -1.0, 1.0);
    float w = W * (1.0 - yy * yy);
    float inside = abs(pe.y) < H ? smoothstep(px, -px, (abs(pe.x) - w) * uEyeScale) : 0.0;
    inside *= uEyeLine;
    nb *= mix(1.0, mix(0.55, 1.35, inside), uEye * uEyeLine);
    col += nb * uNeb;

    float rimD = abs(pe.y) < H ? abs(abs(pe.x) - w) : length(vec2(pe.x, abs(pe.y) - H));
    rimD *= uEyeScale;
    float rim = (1.0 - smoothstep(px * 0.6, px * 1.8, rimD)) + exp(-rimD / (px * 9.0)) * 0.25;
    col += vec3(0.95, 0.88, 0.74) * rim * uEyeLine * uFade;

    float ir = length(pe) * uEyeScale;
    float irisR = 0.085 * uEye;
    float iris = (1.0 - smoothstep(px * 0.7, px * 2.0, abs(ir - irisR))) * uEye;
    float ang = atan(pe.y, pe.x);
    float dash = step(0.5, fract(ang * 9.0 / 3.14159 + uTime * 0.15));
    float inner = (1.0 - smoothstep(px * 0.5, px * 1.6, abs(ir - irisR * 0.68))) * dash * uEye;
    col += (vec3(0.9, 0.64, 0.23) * iris + vec3(0.69, 0.48, 0.24) * inner * 0.8) * inside;
    float pupil = exp(-ir / (0.01 + 0.02 * uEye)) * 1.6 + exp(-ir / 0.07) * 0.35 * uEye;
    col += vec3(1.0, 0.8, 0.5) * pupil * inside * uEye;

    // diving into the pupil: its light swallows the frame, then gives way to the warp
    float flare = smoothstep(0.25, 0.7, uDive) * (1.0 - smoothstep(0.7, 1.0, uDive));
    col += vec3(1.0, 0.86, 0.66) * exp(-length(p) / (0.05 + uDive * 0.5)) * flare * 1.6;

    float sk = streaks(p, uDist, 170.0, 1.0) + streaks(p, uDist * 1.25 + 0.3, 260.0, 2.0) * 0.7;
    vec3 sc = mix(vec3(0.95, 0.93, 1.0), vec3(1.0, 0.62, 0.3), smoothstep(0.3, 1.1, abs(p.x)) * 0.6);
    col += sc * sk * uWarp * 1.4;
    col += vec3(0.9, 0.9, 1.0) * stars(p * (1.0 + uWarp * 0.2), 90.0, 0.93, 1.0) * uFade * 0.5 * (1.0 - uWarp);
  }

  // ---------- space: the Milky Way, the Sun and the Earth ----------
  if (uSpace > 0.001){
    float zoomS = 1.0 + (uEarthR - 0.01) * 0.25;
    vec3 sp = galaxy(p / zoomS) * 0.85;
    sp += vec3(0.85, 0.85, 0.95) * (stars(p, 70.0, 0.955, 7.0) + stars(p, 150.0, 0.94, 9.0) * 0.6);
    vec2 sunP = vec2(-0.02, uSunY);
    float m;
    vec3 e = earth(p, vec2(0.0, uEarthY), uEarthR, sunP, m);
    sp = sp * (1.0 - m) + e;
    sp += sunGlow(p, sunP, uSunS) * (1.0 - m * 0.55);
    sp += ghosts(p, sunP, smoothstep(0.08, 0.3, uEarthR));
    col = col * (1.0 - uSpace) + sp * uSpace;
  }

  // film finish: vignette and grain, like the rest of the site
  vec2 v = vUv - 0.5;
  col *= 1.0 - dot(v, v) * 1.1;
  col = col / (1.0 + col * 0.35);
  col += (hash(frag + fract(uTime) * 91.0) - 0.5) * 0.03;
  gl_FragColor = vec4(max(col, 0.0), 1.0);
}`

function makeFallback(rgb: [number, number, number]) {
  const t = new THREE.DataTexture(new Uint8Array([...rgb, 255]), 1, 1)
  t.needsUpdate = true
  return t
}

function Film() {
  const size = useThree((s) => s.size)
  const dpr = useThree((s) => s.viewport.dpr)
  const mat = useMemo(
    () =>
      new THREE.ShaderMaterial({
        vertexShader: vert,
        fragmentShader: frag,
        depthTest: false,
        depthWrite: false,
        toneMapped: false,
        uniforms: {
          uRes: { value: new THREE.Vector2(1, 1) },
          uTime: { value: 0 },
          uFade: { value: 0 }, uEyeLine: { value: 0 }, uEye: { value: 0 }, uDive: { value: 0 }, uEyeScale: { value: 1 },
          uWarp: { value: 0 }, uDist: { value: 0 }, uNeb: { value: 0 }, uSpace: { value: 0 },
          uEarthR: { value: 0.01 }, uEarthY: { value: 0 }, uSunY: { value: 0 }, uSunS: { value: 0.01 }, uRays: { value: 0 },
          uTex: { value: 0 },
          uDay: { value: makeFallback([0, 0, 0]) },
          uLights: { value: makeFallback([0, 0, 0]) },
        },
      }),
    [],
  )

  // the same maps the site loads; a private manager keeps them out of the site's progress count
  useEffect(() => {
    let alive = true
    const loader = new THREE.TextureLoader(new THREE.LoadingManager())
    const got: THREE.Texture[] = []
    const prep = (t: THREE.Texture) => {
      t.generateMipmaps = false
      t.minFilter = THREE.LinearFilter
      t.wrapS = THREE.RepeatWrapping
      got.push(t)
    }
    Promise.all([loader.loadAsync('/tex/earth_atmos_2048.webp'), loader.loadAsync('/tex/earth_lights_2048.webp')])
      .then(([day, lights]) => {
        prep(day); prep(lights)
        if (!alive) return
        mat.uniforms.uDay.value = day
        mat.uniforms.uLights.value = lights
        mat.userData.texReady = true
      })
      .catch(() => {})
    return () => { alive = false; got.forEach((t) => t.dispose()); mat.dispose() }
  }, [mat])

  useFrame((_, rawDt) => {
    const dt = Math.min(rawDt, 1 / 30)
    const u = mat.uniforms
    u.uTime.value += dt
    // wait on the Earth until the site has loaded
    const step = arrival.t + dt > arrival.stopAt ? 0 : dt
    arrival.t = arrival.loaded ? arrival.t + step : Math.min(arrival.t + step, HOLD)
    const c = curves(Math.min(arrival.t, END + 1))
    arrival.dist += c.warp * step * 1.7
    u.uRes.value.set(size.width * dpr, size.height * dpr)
    u.uFade.value = c.fade
    u.uEyeLine.value = c.eyeLine
    u.uEye.value = c.eye
    u.uDive.value = c.dive
    u.uEyeScale.value = c.eyeScale
    u.uWarp.value = c.warp
    u.uDist.value = arrival.dist
    u.uNeb.value = c.neb
    u.uSpace.value = c.space
    u.uEarthR.value = c.earthR
    u.uEarthY.value = c.earthY
    u.uSunY.value = c.sunY
    u.uSunS.value = c.sunS
    u.uRays.value = c.rays
    if (mat.userData.texReady) u.uTex.value = Math.min(1, u.uTex.value + dt * 1.5)
  })

  return (
    <mesh material={mat} frustumCulled={false}>
      <planeGeometry args={[2, 2]} />
    </mesh>
  )
}

export default function ArrivalScene() {
  return (
    <Canvas
      className="arrival__gl"
      dpr={[1, 1.25]}
      flat
      linear
      gl={{ antialias: false, alpha: false, powerPreference: 'high-performance', depth: false, stencil: false }}
    >
      <Film />
    </Canvas>
  )
}
