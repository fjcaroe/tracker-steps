import { Component, useCallback, useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { GoogleMap, MarkerF, PolygonF, useJsApiLoader } from "@react-google-maps/api";
import { MAPS_LIBRARIES, MAPS_LOADER_ID } from "../mapsConfig";

export type PolygonPoint = { lat: number; lon: number };

const defaultCenter = { lat: -33.45, lng: -70.65 };

class MapEditorBoundary extends Component<{ children: ReactNode }, { failed: boolean }> {
  state = { failed: false };
  static getDerivedStateFromError() { return { failed: true }; }
  render() {
    if (this.state.failed) return <div className="master-map-state is-error"><div><b>El editor de mapa encontró un problema.</b><span>Cierre esta ventana y vuelva a abrir el predio. El resto de la aplicación sigue funcionando.</span></div></div>;
    return this.props.children;
  }
}

function numberedMarkerIcon(index: number, selected: boolean) {
  const fill = selected ? "#d8ff62" : "#123c33";
  const text = selected ? "#123c33" : "#ffffff";
  const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="34" height="42" viewBox="0 0 34 42"><path d="M17 1C8.2 1 1 8.1 1 17c0 11.5 16 24 16 24s16-12.5 16-24C33 8.1 25.8 1 17 1Z" fill="${fill}" stroke="#fff" stroke-width="2"/><text x="17" y="22" text-anchor="middle" font-family="Arial,sans-serif" font-size="13" font-weight="700" fill="${text}">${index + 1}</text></svg>`;
  return { url: `data:image/svg+xml;charset=UTF-8,${encodeURIComponent(svg)}`, scaledSize: new google.maps.Size(34, 42), anchor: new google.maps.Point(17, 41) };
}

export default function FieldPolygonEditor({ points, color, onChange }: { points: PolygonPoint[]; color: string; onChange: (points: PolygonPoint[]) => void }) {
  const { isLoaded, loadError } = useJsApiLoader({ id: MAPS_LOADER_ID, googleMapsApiKey: import.meta.env.VITE_GOOGLE_MAPS_API_KEY as string, libraries: MAPS_LIBRARIES });
  const [map, setMap] = useState<google.maps.Map | null>(null);
  const [selectedIndex, setSelectedIndex] = useState<number | null>(null);
  const fittedMapRef = useRef<google.maps.Map | null>(null);
  const center = useMemo(() => points.length ? { lat: points.reduce((sum, point) => sum + point.lat, 0) / points.length, lng: points.reduce((sum, point) => sum + point.lon, 0) / points.length } : defaultCenter, [points]);

  useEffect(() => {
    if (!map || fittedMapRef.current === map) return;
    fittedMapRef.current = map;
    if (!points.length) return;
    const bounds = new google.maps.LatLngBounds();
    points.forEach((point) => bounds.extend({ lat: point.lat, lng: point.lon }));
    map.fitBounds(bounds, 56);
  }, [map, points]);

  const addPoint = useCallback((event: google.maps.MapMouseEvent) => {
    if (!event.latLng) return;
    onChange([...points, { lat: event.latLng.lat(), lon: event.latLng.lng() }]);
    setSelectedIndex(points.length);
  }, [onChange, points]);

  const movePoint = (index: number, event: google.maps.MapMouseEvent) => {
    if (!event.latLng) return;
    onChange(points.map((point, pointIndex) => pointIndex === index ? { lat: event.latLng!.lat(), lon: event.latLng!.lng() } : point));
  };

  const removeSelected = () => {
    if (selectedIndex == null) return;
    onChange(points.filter((_, index) => index !== selectedIndex));
    setSelectedIndex(null);
  };

  if (loadError) return <div className="master-map-state">No se pudo cargar Google Maps. Puede cerrar y volver a intentar.</div>;
  if (!isLoaded) return <div className="master-map-state">Cargando editor de mapa…</div>;

  return <div className="master-polygon-editor">
    <div className="master-polygon-editor__toolbar"><p><b>{points.length} vértices.</b> Haga clic sobre el mapa para agregar puntos. Arrastre los números para corregir el contorno.</p><div><button type="button" onClick={removeSelected} disabled={selectedIndex == null}>Quitar punto seleccionado</button><button type="button" onClick={() => { onChange([]); setSelectedIndex(null); }} disabled={!points.length}>Limpiar polígono</button></div></div>
    <MapEditorBoundary><GoogleMap mapContainerClassName="master-polygon-editor__map" center={center} zoom={points.length ? 16 : 8} onLoad={setMap} onUnmount={() => setMap(null)} onClick={addPoint} options={{ mapTypeId: "satellite", streetViewControl: false, fullscreenControl: true, mapTypeControl: true }}>
      {points.length >= 3 && <PolygonF paths={points.map((point) => ({ lat: point.lat, lng: point.lon }))} options={{ fillColor: color, fillOpacity: .28, strokeColor: color, strokeOpacity: 1, strokeWeight: 3, clickable: false }} />}
      {points.map((point, index) => <MarkerF key={`${index}-${point.lat}-${point.lon}`} position={{ lat: point.lat, lng: point.lon }} icon={numberedMarkerIcon(index, selectedIndex === index)} draggable onClick={(event) => { event.domEvent?.stopPropagation(); setSelectedIndex(index); }} onDragEnd={(event) => movePoint(index, event)} opacity={selectedIndex == null || selectedIndex === index ? 1 : .68} />)}
    </GoogleMap></MapEditorBoundary>
    {points.length > 0 && points.length < 3 && <div className="master-map-warning">Agregue al menos {3 - points.length} punto{3 - points.length === 1 ? "" : "s"} más para formar un polígono.</div>}
  </div>;
}
