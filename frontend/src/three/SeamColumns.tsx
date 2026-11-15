import { useMemo, useRef } from 'react'
import { useFrame } from '@react-three/fiber'
import { Text } from '@react-three/drei'
import * as THREE from 'three'
import { SEAM, type SeamView } from '../lib/field'
import fontUrl from '@fontsource/chakra-petch/files/chakra-petch-latin-500-normal.woff?url'

const R = 4.2
const ARC = Math.PI * 0.95
const H = 0.035 // world units per indicator unit

/** The made-up yearly record as a ring of standing columns, like a calendar of stones.
 *  Amber columns: the coarse eye. Teal: the fine eye. */
export default function SeamColumns({ view }: { view: SeamView }) {
  const n = SEAM.years.length
  const iV = SEAM.years.indexOf(SEAM.start)
  const angle = (i: number) => -ARC / 2 + (i / (n - 1)) * ARC
  const amber = useRef<(THREE.Mesh | null)[]>([])
  const teal = useRef<(THREE.Mesh | null)[]>([])
  const mats = useMemo(
    () => ({
      amber: new THREE.MeshStandardMaterial({ color: '#c88a36', emissive: new THREE.Color('#e5a43b'), emissiveIntensity: 0.9, metalness: 0.8, roughness: 0.35 }),
      teal: new THREE.MeshStandardMaterial({ color: '#4f7f82', emissive: new THREE.Color('#7fc3c6'), emissiveIntensity: 1.1, metalness: 0.6, roughness: 0.35 }),
      base: new THREE.MeshStandardMaterial({ color: '#3b2f22', metalness: 0.9, roughness: 0.4 }),
      seam: new THREE.MeshBasicMaterial({ color: new THREE.Color('#e5d9bc').multiplyScalar(2.5), toneMapped: false }),
    }),
    [],
  )

  useFrame((_, dt) => {
    for (let i = 0; i < n; i++) {
      const before = i < iV
      // amber: coarse eye. Stitched view shows it only before 2012; other views show all years.
      const aT = view === 'stitched' ? (before ? SEAM.coarse[i] : 0) : view === 'both-eyes' ? SEAM.coarse[i] : before ? SEAM.coarse[i] : 0
      // teal: fine eye from 2012, raw or rescaled
      const tT = before ? 0 : view === 'corrected' ? SEAM.fine[i] * SEAM.factor : SEAM.fine[i]
      const a = amber.current[i], t = teal.current[i]
      if (a) { a.scale.y = THREE.MathUtils.damp(a.scale.y, Math.max(aT * H, 0.0001), 4, dt); a.position.y = a.scale.y / 2 }
      if (t) { t.scale.y = THREE.MathUtils.damp(t.scale.y, Math.max(tT * H, 0.0001), 4, dt); t.position.y = t.scale.y / 2 }
    }
  })

  const twin = view === 'both-eyes'
  return (
    <group position={[0, -1.6, 0]}>
      <mesh rotation={[-Math.PI / 2, 0, 0]} material={mats.base}>
        <ringGeometry args={[R - 0.3, R + 0.3, 128, 1, Math.PI / 2 - ARC / 2 - 0.08, ARC + 0.16]} />
      </mesh>
      {SEAM.years.map((y, i) => {
        const a = angle(i)
        const x = Math.sin(a) * R, z = -Math.cos(a) * R
        const off = twin && i >= iV ? 0.13 : 0
        return (
          <group key={y} position={[x, 0, z]} rotation={[0, -a, 0]}>
            <mesh ref={(m) => { amber.current[i] = m }} material={mats.amber} position={[-off, 0, 0]} scale={[0.16, 0.0001, 0.16]}>
              <boxGeometry args={[1, 1, 1]} />
            </mesh>
            <mesh ref={(m) => { teal.current[i] = m }} material={mats.teal} position={[off, 0, 0]} scale={[0.16, 0.0001, 0.16]}>
              <boxGeometry args={[1, 1, 1]} />
            </mesh>
            {(y === SEAM.start || (y - SEAM.start) % 4 === 0) && (
              <Text font={fontUrl} position={[0, 0.02, 0.42]} rotation={[-Math.PI / 2, 0, 0]} fontSize={y === SEAM.start ? 0.2 : 0.14} color={y === SEAM.start ? '#e5d9bc' : '#a98a5c'} anchorX="center">
                {String(y)}
              </Text>
            )}
          </group>
        )
      })}
      {/* the seam itself: a bright line where the second eye opens */}
      <group rotation={[0, -(angle(iV) - (ARC / (n - 1)) / 2), 0]}>
        <mesh material={mats.seam} position={[0, 1.25, -R]}>
          <boxGeometry args={[0.012, 2.5, 0.012]} />
        </mesh>
      </group>
    </group>
  )
}
