import { useEffect, useState } from 'react'
import { prefersReducedMotion } from '../lib/random'

/* Previews for the three mode cards. Story Mode exists, so its card shows real frames from it.
   The Lab and mission cards show a line drawing of the screen, labelled as a sketch,
   with no numbers that could pass for data. */

// WebP encodes (quality 0.82) of the masters in frontend/source-textures/previews/
const FRAMES = [
  { src: '/previews/story-1-park.webp', label: 'The park' },
  { src: '/previews/story-2-finger.webp', label: 'Parallax' },
  { src: '/previews/story-3-two-eyes.webp', label: 'Two eyes' },
  { src: '/previews/story-4-third-eye.webp', label: 'Third eye' },
]

export function StoryPreview() {
  const [i, setI] = useState(0)
  useEffect(() => {
    if (prefersReducedMotion()) return
    const id = window.setInterval(() => setI((n) => (n + 1) % FRAMES.length), 2600)
    return () => window.clearInterval(id)
  }, [])
  return (
    <span className="preview preview--story">
      {FRAMES.map((f, n) => (
        <img key={f.src} src={f.src} alt="" className={n === i ? 'is-on' : ''} loading="eager" decoding="async" />
      ))}
      <span className="preview__steps" aria-hidden="true">
        {FRAMES.map((f, n) => (
          <span key={f.label} className={n === i ? 'is-on' : n < i ? 'is-past' : ''}>{f.label}</span>
        ))}
      </span>
      <span className="preview__tag">From the story</span>
    </span>
  )
}

const MONTHS = 'JFMAMJJASOND'

export function LabPreview() {
  return (
    <span className="preview preview--plan">
      <svg viewBox="0 0 320 140" preserveAspectRatio="xMidYMid meet" aria-hidden="true">
        {/* area picker: a map frame with a drawn boundary */}
        <rect className="plan__frame" x="6" y="14" width="104" height="116" />
        <path className="plan__area" d="M26 52 L52 34 L84 42 L96 70 L80 104 L44 110 L22 86 Z" />
        <circle className="plan__pin" cx="58" cy="72" r="3" />
        <path className="plan__grid" d="M6 52h104M6 92h104M44 14v116M78 14v116" />
        {/* the fire calendar: months across, years down, cells left empty */}
        <g transform="translate(126 14)">
          {Array.from(MONTHS).map((m, c) => (
            <text key={c} className="plan__label" x={c * 15.5 + 7} y="7" textAnchor="middle">{m}</text>
          ))}
          {Array.from({ length: 6 }, (_, r) =>
            Array.from({ length: 12 }, (_, c) => (
              <rect key={`${r}-${c}`} className="plan__cell" x={c * 15.5} y={14 + r * 15.5} width="12" height="12" />
            )),
          )}
          <rect className="plan__scan" x="-2" y="11" width="16" height="96" />
        </g>
      </svg>
      <span className="preview__tag">Sketch</span>
    </span>
  )
}

export function MissionPreview() {
  const steps = ['Question', 'Evidence', 'Answer']
  return (
    <span className="preview preview--plan">
      <svg viewBox="0 0 320 140" preserveAspectRatio="xMidYMid meet" aria-hidden="true">
        <path className="plan__route" d="M44 70 H292" />
        <path className="plan__route plan__route--done" d="M44 70 H292" pathLength="1" />
        {steps.map((s, n) => (
          <g key={s} transform={`translate(${44 + n * 88} 70)`}>
            <rect className="plan__node" x="-36" y="-17" width="72" height="34" />
            <text className="plan__step" textAnchor="middle" y="4">{s}</text>
            <text className="plan__label" textAnchor="middle" y="-24">{String(n + 1).padStart(2, '0')}</text>
          </g>
        ))}
        {/* the time budget as a dial, empty until the case runs */}
        <g transform="translate(290 70)">
          <circle className="plan__frame" r="22" />
          <circle className="plan__dial" r="22" pathLength="1" transform="rotate(-90)" />
          <text className="plan__label" textAnchor="middle" y="3">60–90 s</text>
        </g>
      </svg>
      <span className="preview__tag">Sketch</span>
    </span>
  )
}
