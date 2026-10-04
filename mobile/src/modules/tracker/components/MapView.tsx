import { lazy, Suspense, type ComponentProps } from 'react';

const LiveMap = lazy(() => import('./LiveMap'));

/** Carga el mapa (Leaflet) solo cuando se necesita, para no pesar en la primera pantalla. */
export default function MapView(props: ComponentProps<typeof LiveMap>) {
  return <Suspense fallback={<p className="muted center" role="status">Cargando mapa…</p>}><LiveMap {...props} /></Suspense>;
}
export type { MapMarker, MapField } from './LiveMap';
