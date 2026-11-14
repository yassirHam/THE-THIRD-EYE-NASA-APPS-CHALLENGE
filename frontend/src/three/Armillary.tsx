import { useMemo, useRef } from 'react'
import { useFrame } from '@react-three/fiber'
import { Text, Trail } from '@react-three/drei'
import * as THREE from 'three'
import Satellite from './Satellite'
import fontUrl from '@fontsource/chakra-petch/files/chakra-petch-latin-500-normal.woff?url'

const brass = new THREE.MeshStandardMaterial({ color: '#b48a4c', metalness: 1, roughness: 0.32 })
const brassDark = new THREE.MeshStandardMaterial({ color: '#6e5232', metalness: 1, roughness: 0.45 })

interface OrbitProps {
  radius: number
  tilt: [number, number, number]
  tone: 'modis' | 'viirs'
  speed: number
  phase?: number
  visible: { current: number }
}

/** An engraved brass ring carrying one satellite with a light trail. */
function Orbit({ radius, tilt, tone, speed, phase = 0, visible }: OrbitProps) {
  const sat = useRef<THREE.Group>(null)
  const holder = useRef<THREE.Group>(null)
  const ticks = useMemo(() => {
    const n = 180
    const m = new THREE.InstancedMesh(new THREE.BoxGeometry(0.006, 0.05, 0.004), brass, n)
    const o = new THREE.Object3D()
    for (let i = 0; i < n; i++) {
      const a = (i / n) * Math.PI * 2
      o.position.set(Math.cos(a) * radius, Math.sin(a) * radius, 0)
      o.rotation.set(0, 0, a + Math.PI / 2)
      o.scale.set(1, i % 15 === 0 ? 2.4 : i % 5 === 0 ? 1.5 : 1, 1)
      o.updateMatrix()
      m.setMatrixAt(i, o.matrix)
    }
    return m
  }, [radius])
  const color = tone === 'modis' ? '#e5a43b' : '#7fb6b8'
  useFrame((st) => {
    const t = st.clock.elapsedTime * speed + phase
    if (sat.current) {
      sat.current.position.set(Math.cos(t) * radius, Math.sin(t) * radius, 0)
      sat.current.rotation.z = t + Math.PI / 2
    }
    if (holder.current) holder.current.scale.setScalar(THREE.MathUtils.lerp(holder.current.scale.x, 0.0001 + visible.current, 0.08))
  })
  return (
    <group rotation={tilt}>
      <group ref={holder}>
        <mesh material={brass}><torusGeometry args={[radius, 0.012, 8, 256]} /></mesh>
        <mesh material={brassDark}><torusGeometry args={[radius + 0.05, 0.004, 6, 256]} /></mesh>
        <primitive object={ticks} />
        <Trail width={1.4} length={7} color={color} attenuation={(w) => w * w} decay={1.2}>
          <group ref={sat}>
            <Satellite tone={tone} scale={0.32} />
          </group>
        </Trail>
      </group>
    </group>
  )
}

interface ArmillaryProps {
  radius?: number
  /** 0..1: how far the year ring has turned toward 2012 */
  seam: { current: number }
  modis: { current: number }
  viirs: { current: number }
  years: { current: number }
}

const YEARS = Array.from({ length: 25 }, (_, i) => 2002 + i)

export default function Armillary({ radius = 3.1, seam, modis, viirs, years }: ArmillaryProps) {
  const yearRing = useRef<THREE.Group>(null)
  const yearHolder = useRef<THREE.Group>(null)
  const seamMat = useMemo(() => new THREE.MeshBasicMaterial({ color: new THREE.Color('#7fb6b8').multiplyScalar(3), toneMapped: false }), [])
  const step = (Math.PI * 1.6) / (YEARS.length - 1)
  useFrame((_, dt) => {
    if (yearRing.current) {
      // turn the ring so that 2012 comes to the front as `seam` goes to 1
      const target = -Math.PI / 2 - (-0.8 * Math.PI + step * 10) * seam.current + _.clock.elapsedTime * 0.02 * (1 - seam.current)
      yearRing.current.rotation.z = THREE.MathUtils.damp(yearRing.current.rotation.z, target, 2, dt)
    }
    if (yearHolder.current) yearHolder.current.scale.setScalar(THREE.MathUtils.lerp(yearHolder.current.scale.x, 0.0001 + years.current, 0.06))
    seamMat.opacity = seam.current
  })
  return (
    <group>
      <Orbit radius={radius * 0.82} tilt={[Math.PI / 2.25, 0.25, 0]} tone="modis" speed={0.32} visible={modis} />
      <Orbit radius={radius * 0.9} tilt={[Math.PI / 1.7, -0.55, 0.4]} tone="viirs" speed={0.4} phase={2} visible={viirs} />

      {/* the year ring: the record, engraved */}
      <group ref={yearHolder} rotation={[0.12, 0, 0]}>
        <group ref={yearRing}>
          <mesh material={brass}><torusGeometry args={[radius, 0.02, 10, 300, Math.PI * 1.7]} /></mesh>
          <mesh material={brassDark}><torusGeometry args={[radius + 0.22, 0.008, 8, 300, Math.PI * 1.7]} /></mesh>
          {YEARS.map((y, i) => {
            const a = -0.8 * Math.PI + i * step + Math.PI * 0.85
            const isSeam = y === 2012
            return (
              <group key={y} rotation={[0, 0, a]}>
                <mesh material={isSeam ? seamMat : brass} position={[radius + 0.11, 0, 0]}>
                  <boxGeometry args={[isSeam ? 0.26 : 0.16, isSeam ? 0.012 : 0.008, 0.01]} />
                </mesh>
                <Text
                  font={fontUrl}
                  position={[radius + 0.42, 0, 0]}
                  rotation={[0, 0, -Math.PI / 2]}
                  fontSize={isSeam ? 0.13 : 0.085}
                  color={isSeam ? '#9fd0d2' : '#c9a66b'}
                  anchorX="center"
                  anchorY="middle"
                  letterSpacing={0.06}
                >
                  {String(y)}
                </Text>
              </group>
            )
          })}
        </group>
      </group>
    </group>
  )
}
