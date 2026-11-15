import { useEffect } from 'react'
import { Link } from 'react-router-dom'
import Hud from '../components/Hud'
import Eye from '../art/Eye'

const COPY = {
  lab: {
    title: 'Research Lab',
    hint: 'Being built during the event.',
    body: 'The Lab will let you pick an area and read its fire calendar from real NASA MODIS and VIIRS data, with every check visible. No data is loaded yet, so nothing is shown here rather than a made-up chart.',
  },
  mission: {
    title: 'Quick Mission',
    hint: 'Being built during the event.',
    body: 'The mission will walk through one real, independently replayed case from start to finish. It needs the held-out test result first.',
  },
}

export default function Pending({ mode }: { mode: 'lab' | 'mission' }) {
  const c = COPY[mode]
  useEffect(() => {
    document.title = `${c.title} - THE THIRD EYE`
  }, [c.title])
  return (
    <Hud objective={{ title: c.title, hint: c.hint }} bottom={<Link className="chip" to="/">Back to start</Link>}>
      <div style={{ position: 'absolute', inset: 0, display: 'grid', placeItems: 'center', padding: '0 8vw' }}>
        <div style={{ display: 'grid', gap: 24, justifyItems: 'center', textAlign: 'center', maxWidth: 560 }}>
          <Eye tone="third" orientation="vertical" size={120} />
          <p style={{ fontFamily: 'var(--prose)', fontSize: 22, lineHeight: 1.5, margin: 0 }}>{c.body}</p>
          <Link className="chip" to="/story">Watch the story instead</Link>
        </div>
      </div>
    </Hud>
  )
}
