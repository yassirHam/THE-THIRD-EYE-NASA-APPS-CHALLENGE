import { useId, type CSSProperties } from 'react'
import { blink } from '../lib/pointer'

export type EyeTone = 'modis' | 'viirs' | 'third'

const TONE: Record<EyeTone, { iris: string; ring: string }> = {
  modis: { iris: 'var(--amber)', ring: 'var(--oxide)' },
  viirs: { iris: 'var(--teal)', ring: '#3f5d60' },
  third: { iris: 'var(--ivory)', ring: 'var(--amber)' },
}

interface EyeProps {
  tone: EyeTone
  size?: number
  /** 'horizontal' for MODIS/VIIRS, 'vertical' for the third eye. */
  orientation?: 'horizontal' | 'vertical'
  className?: string
  style?: CSSProperties
  title?: string
}

/** Line-art eye. The `.eye__lids` group is what GSAP scales to blink or open.
 *  The iris carries a pixel grid: coarse for MODIS, fine for VIIRS, both for the third eye. */
export default function Eye({ tone, size = 160, orientation = 'horizontal', className, style, title }: EyeProps) {
  const t = TONE[tone]
  const cells = tone === 'modis' ? 4 : tone === 'viirs' ? 9 : 6
  const id = `eye-${tone}-${useId().replace(/[^a-zA-Z0-9]/g, '')}`
  return (
    <svg
      className={`eye eye--${tone} is-blinkable ${className ?? ''}`}
      viewBox="-100 -100 200 200"
      width={size}
      height={size}
      style={{ transform: orientation === 'vertical' ? 'rotate(90deg)' : undefined, ...style }}
      role={title ? 'img' : undefined}
      aria-hidden={title ? undefined : true}
      aria-label={title}
      data-cursor="Blink"
      onPointerDown={(e) => { if (e.button === 0) blink(e.currentTarget.querySelector('.eye__blink')) }}
    >
      <defs>
        <clipPath id={`${id}-almond`}>
          <path d="M-92 0 Q0 -66 92 0 Q0 66 -92 0 Z" />
        </clipPath>
        <radialGradient id={`${id}-glow`}>
          <stop offset="0%" stopColor={t.iris} stopOpacity="0.55" />
          <stop offset="100%" stopColor={t.iris} stopOpacity="0" />
        </radialGradient>
      </defs>

      <circle className="eye__glow" r="96" fill={`url(#${id}-glow)`} opacity="0.35" />

      <g className="eye__blink">
      <g className="eye__lids">
        <g clipPath={`url(#${id}-almond)`}>
          <rect x="-100" y="-70" width="200" height="140" fill="var(--void)" />
          <g className="eye__iris">
            <circle r="34" fill="none" stroke={t.ring} strokeWidth="10" />
            <circle r="28" fill={t.iris} opacity="0.92" />
            {/* sensor pixel grid inside the iris */}
            <g opacity="0.55" stroke="var(--void)" strokeWidth={tone === 'viirs' ? 0.8 : 1.4}>
              {Array.from({ length: cells - 1 }, (_, i) => {
                const p = -28 + ((i + 1) * 56) / cells
                return (
                  <g key={i}>
                    <line x1={p} y1="-28" x2={p} y2="28" />
                    <line x1="-28" y1={p} x2="28" y2={p} />
                  </g>
                )
              })}
            </g>
            <circle r="11" fill="var(--void)" />
            <circle cx="-9" cy="-10" r="4" fill="var(--ivory)" opacity="0.85" />
          </g>
        </g>
        <path d="M-92 0 Q0 -66 92 0 Q0 66 -92 0 Z" fill="none" stroke="var(--ivory)" strokeWidth="3" />
        <path d="M-70 -30 Q0 -78 70 -30" fill="none" stroke="var(--ivory)" strokeWidth="1.2" opacity="0.5" />
      </g>
      </g>
    </svg>
  )
}
