import { forwardRef, useMemo } from 'react'
import * as THREE from 'three'
import { mulberry32 } from '../lib/random'

/** Canvas textures built once: crumpled gold foil (multi-layer insulation) and solar cells. */
function makeTextures() {
  const r = mulberry32(5)
  const foil = document.createElement('canvas')
  foil.width = foil.height = 256
  const f = foil.getContext('2d')!
  f.fillStyle = '#808080'
  f.fillRect(0, 0, 256, 256)
  for (let i = 0; i < 900; i++) {
    const x = r() * 256, y = r() * 256, w = 6 + r() * 40, h = 2 + r() * 10
    f.save(); f.translate(x, y); f.rotate(r() * Math.PI)
    const v = Math.floor(70 + r() * 120)
    f.fillStyle = `rgb(${v},${v},${v})`
    f.globalAlpha = 0.35
    f.fillRect(-w / 2, -h / 2, w, h)
    f.restore()
  }
  const cells = document.createElement('canvas')
  cells.width = 512; cells.height = 128
  const c = cells.getContext('2d')!
  c.fillStyle = '#0b1418'
  c.fillRect(0, 0, 512, 128)
  for (let i = 0; i < 16; i++) for (let j = 0; j < 4; j++) {
    const g = c.createLinearGradient(i * 32, j * 32, i * 32 + 32, j * 32 + 32)
    g.addColorStop(0, '#1d3a44'); g.addColorStop(1, '#0d1d24')
    c.fillStyle = g
    c.fillRect(i * 32 + 2, j * 32 + 2, 28, 28)
  }
  c.strokeStyle = '#b89a5e'; c.lineWidth = 2; c.strokeRect(1, 1, 510, 126)
  const foilTex = new THREE.CanvasTexture(foil)
  foilTex.wrapS = foilTex.wrapT = THREE.RepeatWrapping
  const cellTex = new THREE.CanvasTexture(cells)
  cellTex.colorSpace = THREE.SRGBColorSpace
  return { foilTex, cellTex }
}

let cache: ReturnType<typeof makeTextures> | null = null

interface SatelliteProps {
  tone: 'modis' | 'viirs'
  scale?: number
}

/** A generic Earth-observing satellite: foil-wrapped bus, one solar wing, sensor and antenna.
 *  Not a model of Aqua or Suomi NPP. */
const Satellite = forwardRef<THREE.Group, SatelliteProps>(function Satellite({ tone, scale = 1 }, ref) {
  const { foilTex, cellTex } = useMemo(() => (cache ??= makeTextures()), [])
  const accent = tone === 'modis' ? '#e5a43b' : '#729c9e'
  const mats = useMemo(
    () => ({
      foil: new THREE.MeshStandardMaterial({ color: tone === 'modis' ? '#d39a43' : '#c9b89a', metalness: 1, roughness: 0.28, bumpMap: foilTex, bumpScale: 0.6 }),
      frame: new THREE.MeshStandardMaterial({ color: '#2a2622', metalness: 0.7, roughness: 0.5 }),
      panel: new THREE.MeshStandardMaterial({ map: cellTex, metalness: 0.6, roughness: 0.25, emissive: new THREE.Color('#0e2a33'), emissiveIntensity: 0.4 }),
      lens: new THREE.MeshStandardMaterial({ color: '#050505', emissive: new THREE.Color(accent), emissiveIntensity: 3 }),
      dish: new THREE.MeshStandardMaterial({ color: '#e5d9bc', metalness: 0.3, roughness: 0.4, side: THREE.DoubleSide }),
    }),
    [tone, foilTex, cellTex, accent],
  )
  return (
    <group ref={ref} scale={scale}>
      <mesh material={mats.foil}><boxGeometry args={[0.36, 0.3, 0.3]} /></mesh>
      <mesh material={mats.frame} position={[0, 0.16, 0]}><boxGeometry args={[0.38, 0.02, 0.32]} /></mesh>
      <mesh material={mats.frame} position={[0.32, 0, 0]} rotation={[0, 0, Math.PI / 2]}><cylinderGeometry args={[0.012, 0.012, 0.3, 8]} /></mesh>
      <group position={[0.95, 0, 0]} rotation={[0.35, 0, 0]}>
        <mesh material={mats.panel}><boxGeometry args={[1.0, 0.01, 0.26]} /></mesh>
      </group>
      <mesh material={mats.lens} position={[0, -0.17, 0.05]}><cylinderGeometry args={[0.05, 0.06, 0.06, 20]} /></mesh>
      <mesh material={mats.frame} position={[-0.12, -0.16, -0.08]}><boxGeometry args={[0.1, 0.05, 0.1]} /></mesh>
      <group position={[-0.24, 0.1, 0]} rotation={[0, 0, 0.8]}>
        <mesh material={mats.frame} position={[0, 0.08, 0]}><cylinderGeometry args={[0.008, 0.008, 0.16, 6]} /></mesh>
        <mesh material={mats.dish} position={[0, 0.17, 0]}><sphereGeometry args={[0.09, 24, 8, 0, Math.PI * 2, 0, 0.9]} /></mesh>
      </group>
      <pointLight color={accent} intensity={0.6} distance={1.5} position={[0, -0.3, 0]} />
    </group>
  )
})

export default Satellite
