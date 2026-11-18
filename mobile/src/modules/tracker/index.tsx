import type { ModuleProps } from '../registry';
import { lazy, Suspense } from 'react';
import TrackerDemo from '../../testing/TrackerDemo';
const TrackerModule = lazy(() => import('./TrackerModule'));

/** Adaptador del módulo Tracker: conserva su login, su API y sus datos locales sin cambios de formato. */
export default function TrackerEntry({ runtime, onExit }: ModuleProps) {
  // The legacy client defaults to the production API and may have a saved token.
  // Never mount it under a fictitious portal identity.
  return runtime.demo ? <TrackerDemo onExit={onExit} /> : <Suspense fallback={<p>Abriendo Tracker…</p>}><TrackerModule onExit={onExit} /></Suspense>;
}
