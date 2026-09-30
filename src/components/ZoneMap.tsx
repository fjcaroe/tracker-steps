import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { CircleF, GoogleMap, OverlayViewF, PolygonF, PolylineF, useJsApiLoader } from '@react-google-maps/api';
import { MAPS_LIBRARIES, MAPS_LOADER_ID } from '../mapsConfig';
import { dateLabel, type FleetAsset } from '../services/fleetApi';
import type { Vertex, Zone, ZoneReport } from '../services/fleetZones';
export type ZoneMode = 'navigate' | 'draw' | 'adjust';
const point = (p: Vertex) => ({ lat: p.lat, lng: p.lon });
const style = { width: '100%', height: '100%' };
export default function ZoneMap({ zones, selected, vertices, color, editing, mode, onMode, onVertices, onSelect, center, segments, focusKey, vehicle, trail, trailVisible, onShowTrail }: {
  zones: Zone[]; selected?: string; vertices: Vertex[]; color: string; editing: boolean; mode: ZoneMode; onMode: (mode: ZoneMode) => void;
  onVertices: (vertices: Vertex[]) => void; onSelect: (id: string) => void; center: Vertex; segments?: ZoneReport['segments']; focusKey: string;
  vehicle?: FleetAsset; trail: Vertex[][]; trailVisible: boolean; onShowTrail: () => void;
}) {
  const { isLoaded, loadError } = useJsApiLoader({ id: MAPS_LOADER_ID, libraries: MAPS_LIBRARIES, googleMapsApiKey: import.meta.env.VITE_GOOGLE_MAPS_API_KEY as string });
  const [map, setMap] = useState<google.maps.Map | null>(null);
  const polygon = useRef<google.maps.Polygon | null>(null);
  const path = useMemo(() => vertices.map(point), [vertices]);
  const current = useRef({ vertices, zones, center, onVertices });
  useEffect(() => { current.current = { vertices, zones, center, onVertices }; }, [vertices, zones, center, onVertices]);
  const [query, setQuery] = useState(''); const [places, setPlaces] = useState<google.maps.GeocoderResult[]>([]);
  const [searching, setSearching] = useState(false); const [message, setMessage] = useState('');
  const [locating, setLocating] = useState(false); const [location, setLocation] = useState<(Vertex & { accuracy: number }) | null>(null);
  const alive = useRef(true);
  useEffect(() => { alive.current = true; return () => { alive.current = false; }; }, []);
  const fitPoints = useCallback((points: Vertex[]) => {
    if (!map || !points.length) return;
    if (points.length === 1) { map.panTo(point(points[0])); map.setZoom(17); return; }
    const bounds = new google.maps.LatLngBounds(); points.forEach(p => bounds.extend(point(p))); map.fitBounds(bounds, 45);
  }, [map]);
  const fit = useCallback(() => {
    const data = current.current;
    const points = data.vertices.length ? data.vertices : data.zones.filter(z => z.active).flatMap(z => z.vertices);
    fitPoints(points.length ? points : [data.center]);
  }, [fitPoints]);
  // Camera is uncontrolled: edits, polling and mode changes never reset zoom/pan.
  useEffect(() => { fit(); }, [fit, focusKey]);
  const changed = () => { const p = polygon.current?.getPath().getArray().map(p => ({ lat: p.lat(), lon: p.lng() })); if (p) current.current.onVertices(p); };
  const search = async () => {
    if (!map || !query.trim() || searching) return;
    setMessage(''); setPlaces([]);
    const coords = query.trim().match(/^(-?\d+(?:\.\d+)?)\s*[,;]\s*(-?\d+(?:\.\d+)?)$/);
    if (coords) {
      const lat = Number(coords[1]), lon = Number(coords[2]);
      if (Math.abs(lat)>80 || Math.abs(lon)>180) { setMessage('Coordenadas fuera de rango. Usa latitud, longitud.'); return; }
      fitPoints([{lat,lon}]); setMessage('Ubicación encontrada. Elige Dibujar cuando estés listo.'); return;
    }
    setSearching(true);
    try {
      const result = await new google.maps.Geocoder().geocode({ address: query.trim(), region: 'cl' });
      if (!alive.current) return;
      setPlaces(result.results.slice(0,5));
      if (!result.results.length) setMessage('No encontramos ese lugar. Agrega comuna o usa latitud, longitud.');
    } catch { if (alive.current) setMessage('No se pudo buscar esa dirección. Prueba con comuna y región, coordenadas o Mi ubicación.'); }
    finally { if (alive.current) setSearching(false); }
  };
  const locate = () => {
    if (!navigator.geolocation) { setMessage('Este navegador no ofrece ubicación. Busca una dirección o coordenadas.'); return; }
    setLocating(true); setMessage('');
    navigator.geolocation.getCurrentPosition(p => {
      if (!alive.current) return;
      const location = { lat:p.coords.latitude, lon:p.coords.longitude, accuracy:p.coords.accuracy };
      setLocation(location); fitPoints([location]); setLocating(false); setMessage(`Tu ubicación aproximada: precisión ±${Math.round(location.accuracy)} m. No se guarda en la flota.`);
    }, error => { if (alive.current) { setLocating(false); setMessage(error.code===1 ? 'Permiso de ubicación denegado. Puedes habilitarlo en tu navegador o buscar una dirección.' : 'No pudimos obtener tu ubicación. Reintenta o busca una dirección.'); } }, { enableHighAccuracy:true, timeout:15000, maximumAge:60000 });
  };
  const drawing = editing && mode==='draw'; const adjusting = editing && mode==='adjust';
  if (loadError || !import.meta.env.VITE_GOOGLE_MAPS_API_KEY) return <div className="zone-map-fallback"><strong>Cartografía no disponible</strong><p>Puedes cargar los vértices por coordenadas y consultar las métricas. Reintenta al recuperar el mapa.</p></div>;
  if (!isLoaded) return <div className="zone-map-fallback" role="status">Cargando mapa…</div>;
  return <div className="zone-map-inner">
    <div className="zone-location-tools">
      <form className="zone-place-search" onSubmit={e=>{e.preventDefault();void search();}}><label>Buscar dirección, comuna o coordenadas<input value={query} onChange={e=>setQuery(e.target.value)} placeholder="Ej. Talca, Chile o -35.426, -71.655"/></label><button disabled={searching || !query.trim()}>{searching?'Buscando…':'Buscar lugar'}</button></form>
      {places.length>0 && <ul className="zone-search-results">{places.map(p=><li key={p.place_id}><button type="button" onClick={()=>{if(p.geometry.viewport)map?.fitBounds(p.geometry.viewport);else fitPoints([{lat:p.geometry.location.lat(),lon:p.geometry.location.lng()}]);setQuery(p.formatted_address);setPlaces([]);setMessage('Lugar seleccionado. Puedes acercarte y comenzar a dibujar.');}}>{p.formatted_address}</button></li>)}</ul>}
      <div className="zone-actions"><button type="button" onClick={locate} disabled={locating}>{locating?'Ubicando…':'Mi ubicación'}</button><button type="button" disabled={!vehicle?.last_position} onClick={()=>{if(vehicle?.last_position){fitPoints([vehicle.last_position]);setMessage(`${vehicle.name}: última posición ${dateLabel(vehicle.last_position.recorded_at)}${vehicle.position_stale?' · dato antiguo':''}.`);}}}>Ubicar vehículo</button><button type="button" disabled={!trail.length} onClick={()=>{onShowTrail();fitPoints(trail.flat());}}>Encuadrar recorrido</button><button type="button" onClick={fit}>Encuadrar zona</button></div>
      {message && <p className="zone-map-message" role="status">{message}</p>}
    </div>
    <div className="zone-map-frame"><GoogleMap mapContainerStyle={style} onLoad={instance=>{instance.setMapTypeId('hybrid');setMap(instance);}}
      onClick={e=>{if(drawing && e.latLng && vertices.length<100)onVertices([...vertices,{lat:e.latLng.lat(),lon:e.latLng.lng()}]);}}
      options={{mapTypeControl:true,streetViewControl:false,fullscreenControl:false,zoomControl:true,gestureHandling:'greedy',scrollwheel:true,draggable:true,keyboardShortcuts:true,clickableIcons:false,disableDoubleClickZoom:drawing,draggableCursor:drawing?'crosshair':'grab',tilt:0}}>
      {zones.filter(z=>z.active && z.id!==selected).map(z=><PolygonF key={z.id} paths={z.vertices.map(point)} options={{fillColor:z.color,strokeColor:z.color,fillOpacity:.1,strokeWeight:2,clickable:!editing}} onClick={()=>onSelect(z.id)}/>)}
      {vertices.length>=3 && <PolygonF key={adjusting?'edit':'view'} paths={path} onLoad={p=>{polygon.current=p;}} onUnmount={()=>{polygon.current=null;}} onMouseUp={changed} onDragEnd={changed}
        onRightClick={event=>{const e=event as google.maps.PolyMouseEvent;if(adjusting && e.vertex!==undefined && vertices.length>3)onVertices(vertices.filter((_,i)=>i!==e.vertex));}}
        options={{fillColor:color,strokeColor:color,fillOpacity:.22,strokeWeight:3,editable:adjusting,clickable:adjusting,zIndex:2}}/>}
      {drawing && <><PolylineF path={path} options={{strokeColor:color,strokeWeight:3,clickable:false}}/>{vertices.map((p,i)=><OverlayViewF key={i} position={point(p)} mapPaneName="overlayMouseTarget">{i===0 && vertices.length>=3 ? <button type="button" className="zone-vertex zone-close-vertex" aria-label="Cerrar polígono en el primer punto" onClick={e=>{e.stopPropagation();onMode('adjust');}}>✓</button> : <span className="zone-vertex">{i+1}</span>}</OverlayViewF>)}</>}
      {segments?.map((s,i)=><PolylineF key={i} path={s.path.map(point)} options={{strokeColor:s.state==='inside'?'#d9fc74':'#65c5ff',strokeWeight:5,strokeOpacity:.95,clickable:false,zIndex:3}}/>)}
      {trailVisible && trail.map((path,i)=><PolylineF key={`trail-${i}`} path={path.map(point)} options={{strokeColor:'#f2a33a',strokeWeight:4,strokeOpacity:.95,clickable:false,zIndex:4}}/>)}
      {vehicle?.last_position && <OverlayViewF position={point(vehicle.last_position)} mapPaneName="overlayMouseTarget"><div className={`zone-vehicle-marker ${vehicle.position_stale?'is-stale':''}`}><b>● {vehicle.name}</b><small>{vehicle.position_stale?'Posición antigua':'Última posición'} · {dateLabel(vehicle.last_position.recorded_at)}</small></div></OverlayViewF>}
      {location && <><CircleF center={point(location)} radius={location.accuracy} options={{fillColor:'#3388dd',fillOpacity:.12,strokeColor:'#3388dd',strokeWeight:1,clickable:false}}/><OverlayViewF position={point(location)} mapPaneName="overlayMouseTarget"><span className="zone-my-location">Tu ubicación</span></OverlayViewF></>}
    </GoogleMap>
    {drawing && <><span className="zone-center-cross" aria-hidden="true">+</span><button className="zone-add-center" type="button" disabled={vertices.length>=100} onClick={()=>{const p=map?.getCenter();if(p)onVertices([...vertices,{lat:p.lat(),lon:p.lng()}]);}}>+ Añadir punto en el centro</button></>}
    </div>
  </div>;
}
