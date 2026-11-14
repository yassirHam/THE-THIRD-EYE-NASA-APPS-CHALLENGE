import { lazy } from 'react'

// Pages other than Landing ship as separate chunks, so the first visit only downloads the gate.
const loadIntro = () => import('./story/Intro')
const loadStory = () => import('./story/StoryShell')
const loadPending = () => import('./pages/Pending')
const loadLab = () => import('./pages/Lab')

export const Intro = lazy(loadIntro)
export const StoryShell = lazy(loadStory)
export const Pending = lazy(loadPending)
export const Lab = lazy(loadLab)

// Fetch the page chunks in the background, so moving on from the gate does not wait on the network.
export function prefetchRoutes() {
  void loadIntro(); void loadStory(); void loadPending()
}
