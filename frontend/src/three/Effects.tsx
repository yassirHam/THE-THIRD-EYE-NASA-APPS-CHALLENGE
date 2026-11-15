import { useEffect, useMemo } from 'react'
import { useFrame, useThree } from '@react-three/fiber'
import { Bloom, EffectComposer, Noise, Vignette } from '@react-three/postprocessing'
import { BlendFunction, DepthOfFieldEffect, Effect } from 'postprocessing'
import * as THREE from 'three'

const eyesFrag = /* glsl */ `
uniform float lidL; uniform float lidR;
uniform float tintL; uniform float tintR; uniform float seam; uniform float squint;
void mainImage(const in vec4 inputColor, const in vec2 uv, out vec4 outputColor){
  vec2 o = vUv;
  bool left = o.x < 0.5;
  float lid = left ? lidL : lidR;
  float tint = left ? tintL : tintR;
  vec3 c = inputColor.rgb;
  float l = dot(c, vec3(0.3, 0.59, 0.11));
  // a light colour cast per eye; the sensor grid itself is drawn on the globe, so the frame stays sharp
  vec3 tc = (left ? vec3(0.42, 0.78, 0.82) : vec3(1.0, 0.62, 0.22)) * l * 1.25;
  c = mix(c, tc, tint * 0.28);
  // curved eyelid per half: closes from top and bottom toward a lash line
  float hx = left ? o.x * 2.0 : (o.x - 0.5) * 2.0;
  float cx = hx - 0.5;
  float open = 1.0 - lid;
  float bulge = (1.0 - cx * cx * 4.0);
  float top = 0.5 + open * (0.56 + 0.14 * bulge);
  float bot = 0.5 - open * (0.56 + 0.14 * bulge);
  float aa = 0.004;
  float m = smoothstep(top + aa, top - aa, o.y) * smoothstep(bot - aa, bot + aa, o.y);
  float lash = (exp(-abs(o.y - top) * 140.0) + exp(-abs(o.y - bot) * 140.0)) * lid * (1.0 - lid) * 4.0;
  c = c * m + vec3(1.0, 0.55, 0.2) * lash * 0.9;
  float s = exp(-abs(o.x - 0.5) * resolution.x * 0.6) * seam;
  c += vec3(0.95, 0.88, 0.72) * s * 1.4;
  // a squint narrows the view softly from above and below, with no lash line
  float e = max(smoothstep(0.62, 1.1, o.y), smoothstep(0.38, -0.1, o.y));
  c *= 1.0 - squint * e * 0.85;
  outputColor = vec4(c, inputColor.a);
}`

export class EyesEffect extends Effect {
  constructor() {
    super('EyesEffect', eyesFrag, {
      blendFunction: BlendFunction.NORMAL,
      uniforms: new Map<string, THREE.Uniform<number>>([
        ['lidL', new THREE.Uniform(0)],
        ['lidR', new THREE.Uniform(0)],
        ['tintL', new THREE.Uniform(0)],
        ['tintR', new THREE.Uniform(0)],
        ['seam', new THREE.Uniform(0)],
        ['squint', new THREE.Uniform(0)],
      ]),
    })
  }
}

type EyesState = { lidL: number; lidR: number; tintL: number; tintR: number; seam: number; squint: number }

function EyesPass({ state }: { state: EyesState }) {
  const effect = useMemo(() => new EyesEffect(), [])
  useFrame(() => {
    const u = effect.uniforms
    ;(['lidL', 'lidR', 'tintL', 'tintR', 'seam', 'squint'] as const).forEach((k) => { u.get(k)!.value = state[k] })
  })
  return <primitive object={effect} dispose={null} />
}

/** What the eye is focused on, updated by the scene every frame. bokeh 0 turns the blur off. */
export interface FocusState { target: THREE.Vector3; range: number; bokeh: number }

/** Depth of field: whatever sits at `target` stays sharp, nearer and farther things soften. */
function FocusPass({ focus }: { focus: FocusState }) {
  const camera = useThree((s) => s.camera)
  const effect = useMemo(() => {
    const e = new DepthOfFieldEffect(camera, { focusDistance: 1, focusRange: 1, bokehScale: 0, resolutionScale: 0.5 })
    e.target = focus.target
    return e
  }, [camera, focus.target])
  useEffect(() => () => effect.dispose(), [effect])
  useFrame(() => {
    effect.bokehScale = focus.bokeh
    effect.cocMaterial.focusRange = focus.range
  })
  return <primitive object={effect} dispose={null} />
}

interface EffectsProps {
  bloom?: number
  eyes?: EyesState
  focus?: FocusState
}

/** Shared finishing pass: a high-threshold bloom so only the pupil and fires glow, film grain
 *  and vignette. `eyes` adds the split-screen eyelids and per-eye colour cast; `focus` adds
 *  depth of field. */
export default function Effects({ bloom = 1.1, eyes, focus }: EffectsProps) {
  if (eyes) {
    return (
      <EffectComposer multisampling={0}>
        {focus ? <FocusPass focus={focus} /> : <></>}
        <Bloom mipmapBlur intensity={bloom} luminanceThreshold={0.78} luminanceSmoothing={0.18} radius={0.6} />
        <EyesPass state={eyes} />
        <Vignette offset={0.25} darkness={0.85} />
        <Noise opacity={0.07} blendFunction={BlendFunction.OVERLAY} />
      </EffectComposer>
    )
  }
  return (
    <EffectComposer multisampling={0}>
      <Bloom mipmapBlur intensity={bloom} luminanceThreshold={0.78} luminanceSmoothing={0.18} radius={0.6} />
      <Vignette offset={0.25} darkness={0.85} />
      <Noise opacity={0.07} blendFunction={BlendFunction.OVERLAY} />
    </EffectComposer>
  )
}
