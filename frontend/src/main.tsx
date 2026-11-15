import { StrictMode, Suspense } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter, Navigate, Route, Routes, useSearchParams } from 'react-router-dom'
import gsap from 'gsap'
import { useGSAP } from '@gsap/react'

import '@fontsource/chakra-petch/400.css'
import '@fontsource/chakra-petch/500.css'
import '@fontsource/chakra-petch/600.css'
import '@fontsource/chakra-petch/700.css'
import '@fontsource/cormorant-garamond/500.css'
import '@fontsource/cormorant-garamond/600.css'
import '@fontsource/ibm-plex-sans/400.css'
import '@fontsource/ibm-plex-sans/500.css'
import './styles/global.css'

import Landing from './pages/Landing'
import { Intro, Lab, Mission, StoryShell } from './routes'

gsap.registerPlugin(useGSAP)

function Home() {
  const [params] = useSearchParams()
  return params.get('mode') === 'lab' ? <Lab /> : <Landing />
}

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <BrowserRouter>
      {/* The other pages load on their own; Landing prefetches them once it is showing. */}
      <Suspense fallback={null}>
        <Routes>
          <Route path="/" element={<Home />} />
          <Route path="/story" element={<Intro />} />
          <Route path="/story/:chapter" element={<StoryShell />} />
          <Route path="/lab" element={<Lab />} />
          <Route path="/mission" element={<Mission />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </Suspense>
    </BrowserRouter>
  </StrictMode>,
)
