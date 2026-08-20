import { useCallback, useEffect, useMemo, useState, type CSSProperties } from "react";
import { GoogleMap, OverlayViewF, PolygonF, PolylineF, useJsApiLoader } from "@react-google-maps/api";
import { MAPS_LIBRARIES, MAPS_LOADER_ID } from "../mapsConfig";
import type { DemoField, GeoPoint } from "../demo/scenario";

type SessionTrackMapProps = {
  field?: DemoField;
  path: GeoPoint[];
  cursor: { lat: number; lon: number; headingDeg: number };
};

const containerStyle: CSSProperties = { width: "100%", height: "100%" };

function toMapPoint(point: GeoPoint): google.maps.LatLngLiteral {
  return { lat: point.lat, lng: point.lon };
}

export default function SessionTrackMap({ field, path, cursor }: SessionTrackMapProps) {
  const { isLoaded, loadError } = useJsApiLoader({
    id: MAPS_LOADER_ID,
    googleMapsApiKey: import.meta.env.VITE_GOOGLE_MAPS_API_KEY as string,
    libraries: MAPS_LIBRARIES,
  });
  const [map, setMap] = useState<google.maps.Map | null>(null);
  const routePoints = useMemo(() => path.map(toMapPoint), [path]);

  // El encuadre se ajusta solo al recorrido completo, una vez: nunca al
  // avance del cursor de reproducción (si no, el mapa "tiembla" en cada tick).
  const fitRoute = useCallback((instance: google.maps.Map) => {
    if (!routePoints.length) return;
    const bounds = new google.maps.LatLngBounds();
    routePoints.forEach((point) => bounds.extend(point));
    instance.fitBounds(bounds, 44);
  }, [routePoints]);

  const handleLoad = useCallback((instance: google.maps.Map) => {
    setMap(instance);
    fitRoute(instance);
  }, [fitRoute]);

  useEffect(() => {
    if (!map) return;
    fitRoute(map);
  }, [map, fitRoute]);

  if (loadError) return <div className="ops-map-state">Google Maps no pudo cargar.</div>;
  if (!isLoaded) return <div className="ops-map-state"><span className="view-loader__spinner" /> Cargando ruta…</div>;

  return (
    <GoogleMap
      mapContainerStyle={containerStyle}
      center={toMapPoint(cursor)}
      zoom={16}
      onLoad={handleLoad}
      options={{
        mapTypeId: "satellite",
        disableDefaultUI: true,
        zoomControl: true,
        gestureHandling: "greedy",
        clickableIcons: false,
        tilt: 0,
      }}
    >
      {field && (
        <PolygonF
          paths={field.polygon.map(toMapPoint)}
          options={{ strokeColor: field.color, strokeOpacity: 0.7, strokeWeight: 2, fillColor: field.color, fillOpacity: 0.08 }}
        />
      )}
      <PolylineF path={routePoints} options={{ strokeColor: "#123c33", strokeOpacity: 0.55, strokeWeight: 3 }} />
      <OverlayViewF position={toMapPoint(cursor)} mapPaneName="overlayMouseTarget">
        <div className="ops-track-cursor" style={{ transform: `rotate(${cursor.headingDeg}deg)` }}>
          <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M5 6h8v7h2.2l1.4-4H20l1 4v4h-2.1a3 3 0 0 1-5.8 0H9.9a3 3 0 0 1-5.8 0H2v-5h3V6Zm2 2v4h4V8H7Zm-.9 10a1.3 1.3 0 1 0 0-2.6 1.3 1.3 0 0 0 0 2.6Zm9.9-1.3a1.3 1.3 0 1 0 2.6 0 1.3 1.3 0 0 0-2.6 0Z" /></svg>
        </div>
      </OverlayViewF>
    </GoogleMap>
  );
}
