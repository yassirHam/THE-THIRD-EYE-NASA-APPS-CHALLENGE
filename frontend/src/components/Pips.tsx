/** Dice-face pips for 1 to 6, used as chapter markers in the top bar. */
const LAYOUT: Record<number, [number, number][]> = {
  1: [[0.5, 0.5]],
  2: [[0.28, 0.28], [0.72, 0.72]],
  3: [[0.25, 0.25], [0.5, 0.5], [0.75, 0.75]],
  4: [[0.28, 0.28], [0.72, 0.28], [0.28, 0.72], [0.72, 0.72]],
  5: [[0.26, 0.26], [0.74, 0.26], [0.5, 0.5], [0.26, 0.74], [0.74, 0.74]],
  6: [[0.28, 0.22], [0.72, 0.22], [0.28, 0.5], [0.72, 0.5], [0.28, 0.78], [0.72, 0.78]],
}

export default function Pips({ n, size = 34 }: { n: number; size?: number }) {
  return (
    <svg viewBox="0 0 1 1" width={size} height={size} aria-hidden="true">
      {(LAYOUT[n] ?? []).map(([x, y], i) => (
        <circle key={i} cx={x} cy={y} r={0.1} fill="currentColor" />
      ))}
    </svg>
  )
}
