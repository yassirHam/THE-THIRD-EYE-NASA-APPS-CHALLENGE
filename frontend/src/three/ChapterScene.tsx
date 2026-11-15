import { Suspense, useRef } from 'react'
import { Canvas, useFrame } from '@react-three/fiber'
import * as THREE from 'three'
import Globe from './Globe'
import ThirdEye from './ThirdEye'
import Armillary from './Armillary'
import FireTerrain from './FireTerrain'
import { Embers, Stars } from './Atmosphere'
import Effects from './Effects'
import Lights from './Lights'
import type { Art } from '../story/chapters'
import type { FieldView } from '../lib/field'

type V3 = [number, number, number]
const VIEWS: Record<Art['kind'], { cam: V3; look: V3 }> = {
  // the subject sits right of centre; the caption takes the lower left
  third: { cam: [-1.2, 0.9, 11.2], look: [-1.2, 0.9, 0] },
  field: { cam: [0, 7.6, 8.4], look: [0, -0.3, 0.5] },
  seam: { cam: [0, 2.6, 4.2], look: [0, -0.4, -3.4] },
  // the eye sits to the right, clear of the five verdict cards on the left
  verdict: { cam: [-1.55, 0.1, 8], look: [-1.55, 0.1, 0] },
}

function Rig({ kind }: { kind: Art['kind'] }) {
  const look = useRef(new THREE.Vector3())
  const target = useRef(new THREE.Vector3())
  useFrame((st, dt) => {
    const v = VIEWS[kind]
    const t = st.clock.elapsedTime
    // on narrow, portrait stages the off-centre compositions re-centre on their subject
    const ox = st.size.width / st.size.height < 1.1 ? -v.look[0] : 0
    target.current.set(v.cam[0] + ox + st.pointer.x * 0.6 + Math.sin(t * 0.15) * 0.3, v.cam[1] + st.pointer.y * 0.3, v.cam[2])
    st.camera.position.lerp(target.current, 1 - Math.exp(-dt * 2.5))
    look.current.lerp(new THREE.Vector3(v.look[0] + ox, v.look[1], v.look[2]), 1 - Math.exp(-dt * 3))
    st.camera.lookAt(look.current)
  })
  return null
}

const one = { current: 1 }
const seamOn = { current: 1 }
const zero = { current: 0 }
const eyeOpen = { eyeOpen: 1 }

function Content({ art, fieldView }: { art: Art; fieldView: FieldView | null }) {
  if (art.kind === 'third') {
    return (
      <>
        <group position={[0, -1.4, 0]} scale={0.85}>
          <Globe radius={2} fires={{ modis: 1, viirs: 1 }} />
          <Armillary seam={zero} modis={one} viirs={one} years={zero} />
        </group>
        <ThirdEye source={eyeOpen} size={4} position={[0, 2.5, -0.4]} />
      </>
    )
  }
  if (art.kind === 'field') return <FireTerrain view={fieldView ?? art.view} clouds={art.clouds} cloudsAsZero={art.cloudsAsZero} />
  // the seam chart is drawn in SVG over this stage; the 3D layer stays a quiet backdrop
  if (art.kind === 'seam') return null
  return (
    <>
      <ThirdEye source={eyeOpen} size={3.3} />
      <group scale={0.6} position={[0, 0, -2]}>
        <Armillary seam={seamOn} modis={one} viirs={one} years={zero} radius={4} />
      </group>
    </>
  )
}

export default function ChapterScene({ art, fieldView, paused = false }: { art: Art; fieldView: FieldView | null; paused?: boolean }) {
  return (
    <Canvas
      frameloop={paused ? 'demand' : 'always'}
      dpr={[1, 1.6]}
      camera={{ fov: 40, near: 0.1, far: 150, position: VIEWS[art.kind].cam }}
      gl={{ antialias: false, toneMapping: THREE.ACESFilmicToneMapping }}
    >
      <color attach="background" args={['#050708']} />
      <fog attach="fog" args={['#050708', 12, 40]} />
      <Suspense fallback={null}>
        <Lights />
        <Stars count={1500} />
        <Embers count={160} spread={16} y={-4} height={9} />
        <Content art={art} fieldView={fieldView} />
        <Rig kind={art.kind} />
        <Effects bloom={1.05} />
      </Suspense>
    </Canvas>
  )
}
