import { Environment, Lightformer } from '@react-three/drei'

/** Local studio lighting for brass and foil: a low warm key like firelight, a cool rim
 *  like Earthshine, and formed panels for reflections. No network HDRs. */
export default function Lights() {
  return (
    <>
      <ambientLight intensity={0.08} />
      <directionalLight position={[-6, 3, 5]} intensity={2.2} color="#ffcf8f" />
      <directionalLight position={[6, -2, -4]} intensity={0.9} color="#7fb6b8" />
      <Environment resolution={256} frames={1}>
        <Lightformer form="rect" intensity={3} color="#ffb766" position={[-5, 2, 3]} scale={[6, 2, 1]} />
        <Lightformer form="rect" intensity={1.5} color="#8cc6c8" position={[5, -1, -3]} scale={[4, 4, 1]} />
        <Lightformer form="ring" intensity={2} color="#e5d9bc" position={[0, 6, 0]} scale={3} />
      </Environment>
    </>
  )
}
