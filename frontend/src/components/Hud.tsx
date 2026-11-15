import type { ReactNode } from 'react'

interface HudProps {
  objective?: { title: string; hint: string }
  top?: ReactNode
  bottom?: ReactNode
  children: ReactNode
  className?: string
}

/** The fixed frame shared by every screen: corner wedges, top and bottom rules,
 *  an objective box and a stage in between. */
export default function Hud({ objective, top, bottom, children, className }: HudProps) {
  return (
    <div className={`hud ${className ?? ''}`}>
      <span className="hud__corner hud__corner--tl" aria-hidden="true" />
      <span className="hud__corner hud__corner--tr" aria-hidden="true" />
      <span className="hud__corner hud__corner--bl" aria-hidden="true" />
      <span className="hud__corner hud__corner--br" aria-hidden="true" />

      <header className="hud__top">{top}</header>

      <main className="hud__stage">
        {objective && (
          <div className="objective">
            <span className="objective__tab" aria-hidden="true" />
            <div>
              <h1 className="objective__title">{objective.title}</h1>
              <p className="objective__hint">{objective.hint}</p>
            </div>
          </div>
        )}
        {children}
      </main>

      <footer className="hud__bottom">{bottom}</footer>
    </div>
  )
}
