import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { GoogleMap, OverlayViewF, PolygonF, PolylineF, useJsApiLoader } from '@react-google-maps/api';
import { MAPS_LIBRARIES, MAPS_LOADER_ID } from '../mapsConfig';
import type { Vertex, Zone, ZoneReport } from '../services/fleetZones';

const point = (p: Vertex) => ({ lat: p.lat, lng: p.lon });
const style = { width: '100%', height: '100%' };
export default function ZoneMap({ zones, selected, vertices, color, editing, drawing, onVertices, onSelect, center, segments, focusKey }: {
  zones: Zone[]; selected?: string; vertices: Vertex[]; color: string; editing: boolean; drawing: boolean;
  onVertices: (vertices: Vertex[]) => void; onSelect: (id: string) => void; center: Vertex; segments?: ZoneReport['segments']; focusKey: string;
}) {
  const { isLoaded, loadError } = useJsApiLoader({ id: MAPS_LOADER_ID, libraries: MAPS_LIBRARIES, googleMapsApiKey: import.meta.env.VITE_GOOGLE_MAPS_API_KEY as string });
  const [map, setMap] = useState<google.maps.Map | null>(null);
  const polygon = useRef<google.maps.Polygon | null>(null);
  const path = useMemo(() => vertices.map(point), [vertices]);
  const { lat, lon } = center;
  const centerPoint = useMemo(() => ({ lat, lng: lon }), [lat, lon]);
  const current = useRef({ vertices, zones, segments, center, onVertices });
  useEffect(() => { current.current = { vertices, zones, segments, center, onVertices }; }, [vertices, zones, segments, center, onVertices]);
  const fit = useCallback(() => {
    if (!map) return;
    const data = current.current;
    const points = data.vertices.length ? [...data.vertices, ...(data.segments || []).flatMap(s => s.path)] : data.zones.filter(z => z.active).flatMap(z => z.vertices);
    if (points.length < 2) { map.setCenter(point(data.center)); map.setZoom(15); return; }
    const bounds = new google.maps.LatLngBounds(); points.forEach(p => bounds.extend(point(p))); map.fitBounds(bounds, 45);
  }, [map]);
  useEffect(() => { fit(); }, [fit, focusKey]);
  // Sync on pointer release rather than replacing the MVCArray while a handle moves.
  const changed = () => { const p = polygon.current?.getPath().getArray().map(p => ({ lat: p.lat(), lon: p.lng() })); if (p) current.current.onVertices(p); };
  if (loadError || !import.meta.env.VITE_GOOGLE_MAPS_API_KEY) return <div className="zone-map-fallback"><strong>Cartografía no disponible</strong><p>Puedes cargar los vértices por coordenadas y consultar las métricas. Reintenta al recuperar el mapa.</p></div>;
  if (!isLoaded) return <div className="zone-map-fallback" role="status">Cargando mapa…</div>;
  return <div className="zone-map-inner"><GoogleMap mapContainerStyle={style} center={centerPoint} zoom={15} onLoad={setMap}
    onClick={e => { if (drawing && e.latLng && vertices.length < 100) onVertices([...vertices, { lat: e.latLng.lat(), lon: e.latLng.lng() }]); }}
    options={{ mapTypeId: 'hybrid', mapTypeControl: true, streetViewControl: false, fullscreenControl: true, gestureHandling: 'cooperative', clickableIcons: false, disableDoubleClickZoom: drawing, draggableCursor: drawing ? 'crosshair' : undefined, tilt: 0 }}>
    {zones.filter(z => z.active && z.id !== selected).map(z => <PolygonF key={z.id} paths={z.vertices.map(point)} options={{ fillColor: z.color, strokeColor: z.color, fillOpacity: .14, strokeWeight: 2, clickable: !editing }} onClick={() => onSelect(z.id)}/>)}
    {vertices.length >= 3 && <PolygonF key={editing && !drawing ? 'edit' : 'view'} paths={path} onLoad={p => { polygon.current = p; }} onUnmount={() => { polygon.current = null; }} onMouseUp={changed} onDragEnd={changed}
      onRightClick={event => { const e = event as google.maps.PolyMouseEvent; if (editing && !drawing && e.vertex !== undefined && vertices.length > 3) onVertices(vertices.filter((_, i) => i !== e.vertex)); }}
      options={{ fillColor: color, strokeColor: color, fillOpacity: .2, strokeWeight: 3, editable: editing && !drawing, clickable: !drawing, zIndex: 2 }}/>}
    {drawing && <><PolylineF path={path} options={{ strokeColor: color, strokeWeight: 3, clickable: false }}/>{vertices.map((p,i) => <OverlayViewF key={i} position={point(p)} mapPaneName="overlayMouseTarget"><span className="zone-vertex">{i+1}</span></OverlayViewF>)}</>}
    {segments?.map((s,i) => <PolylineF key={i} path={s.path.map(point)} options={{ strokeColor: s.state === 'inside' ? '#d9fc74' : '#65c5ff', strokeWeight: 5, strokeOpacity: .95, clickable: false, zIndex: 3 }}/>) }
  </GoogleMap><button className="zone-fit" onClick={fit} type="button">Encuadrar zona</button></div>;
}
