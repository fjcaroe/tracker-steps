import type { Zone } from '../services/fleetZones';
import TrackerIcon from './TrackerIcon';
import { useCallback, useEffect, useMemo, useState, type CSSProperties } from "react";
import {
  GoogleMap,
  OverlayViewF,
  PolygonF,
  PolylineF,
  useJsApiLoader,
} from "@react-google-maps/api";
import { MAPS_LIBRARIES, MAPS_LOADER_ID } from "../mapsConfig";
import { getRoadRoute } from "../demo/roadRoutes";
import type { DemoField, DemoVehicle, GeoPoint } from "../demo/scenario";

type OperationsMapProps = {
  zones?: Zone[];
  onSelectZone?: (id: string) => void;
  fields: DemoField[];
  vehicles: DemoVehicle[];
  selectedVehicleId: string | null;
  onSelectVehicle: (id: string | null) => void;
  showRows: boolean;
  showRoadRoute: boolean;
  onRoadRouteStatus?: (message: string | null) => void;
  compact?: boolean;
  depot: GeoPoint;
  followVehicle: boolean;
  onUserInteracted?: () => void;
  markerLabels?: Record<string, string>;
  markerTypes?: Record<string, string>;
};

const containerStyle: CSSProperties = { width: "100%", height: "100%" };

function toMapPoint(point: GeoPoint): google.maps.LatLngLiteral {
  return { lat: point.lat, lng: point.lon };
}

function TractorMarker({ vehicle, selected, label, type }: { vehicle: DemoVehicle; selected: boolean; label?: string; type?: string }) {
  return (
    <div className={`ops-map-vehicle ${selected ? "is-selected" : ""}`}>
      <span className="ops-map-vehicle__pulse" />
      <span className="ops-map-vehicle__icon" style={{ transform: `rotate(${vehicle.bearing}deg)` }}>
        <TrackerIcon name={type === 'truck' ? 'truck' : !type || type === 'tractor' || type === 'machinery' ? 'tractor' : 'fleet'}/>
      </span>
      <span className="ops-map-vehicle__copy"><b>{vehicle.name}</b><small>{label ?? `${vehicle.speedKmh.toFixed(1)} km/h`}</small></span>
    </div>
  );
}

export default function OperationsMap({
  fields,
  zones = [],
  onSelectZone,
  vehicles,
  selectedVehicleId,
  onSelectVehicle,
  showRows,
  showRoadRoute,
  onRoadRouteStatus,
  compact = false,
  depot,
  followVehicle,
  onUserInteracted,
  markerLabels,
  markerTypes,
}: OperationsMapProps) {
  const { isLoaded, loadError } = useJsApiLoader({
    id: MAPS_LOADER_ID,
    googleMapsApiKey: import.meta.env.VITE_GOOGLE_MAPS_API_KEY as string,
    libraries: MAPS_LIBRARIES,
  });
  const [map, setMap] = useState<google.maps.Map | null>(null);

  // Sin selección = toda la flota de la región actual, sin centrar en ninguna máquina.
  const selectedVehicle = selectedVehicleId ? vehicles.find((vehicle) => vehicle.id === selectedVehicleId) ?? null : null;
  const selectedField = selectedVehicle ? fields.find((field) => field.id === selectedVehicle.fieldId) ?? null : null;
  const selectedLat = selectedVehicle?.position.lat;
  const selectedLon = selectedVehicle?.position.lon;
  const depotPoint = useMemo(() => toMapPoint(depot), [depot]);

  const boundsKey = JSON.stringify([...fields.flatMap((field) => field.polygon), ...zones.flatMap(z => z.vertices), ...(markerLabels ? vehicles.map(v => v.position) : [])]);
  const fieldBounds = useMemo(() => (JSON.parse(boundsKey) as GeoPoint[]).map(toMapPoint), [boundsKey]);

  const fitScenario = useCallback((instance: google.maps.Map) => {
    if (!fieldBounds.length) return;
    const bounds = new google.maps.LatLngBounds();
    fieldBounds.forEach((point) => bounds.extend(point));
    instance.fitBounds(bounds, compact ? 34 : 58);
  }, [compact, fieldBounds]);

  const handleLoad = useCallback((instance: google.maps.Map) => {
    setMap(instance);
    fitScenario(instance);
  }, [fitScenario]);

  // Re-encuadra toda la flota solo cuando cambia el conjunto de predios (cambio de
  // región), nunca al seleccionar/deseleccionar un vehículo: deseleccionar no debe
  // tirar abajo el zoom/encuadre que el usuario armó para revisar una ruta.
  useEffect(() => {
    if (!map) return;
    fitScenario(map);
  }, [map, fieldBounds, fitScenario]);

  // Solo persigue al vehículo si hay selección Y "Seguir vehículo" está activo.
  // Se apaga solo si el usuario arrastra o hace zoom manualmente (ver onDragStart).
  useEffect(() => {
    if (!map || !followVehicle || selectedLat == null || selectedLon == null || !selectedVehicleId) return;
    map.panTo({ lat: selectedLat, lng: selectedLon });
  }, [map, selectedLat, selectedLon, selectedVehicleId, followVehicle]);

  // La ruta por caminos ya no se calcula en vivo: viene de un fixture
  // pregenerado con OSRM/OpenStreetMap (ver scripts/generate-road-routes.mjs),
  // así que no depende de que la Directions API esté habilitada para la clave
  // de Maps ni de la disponibilidad de un servicio externo en cada vista.
  const roadRoute = selectedField ? getRoadRoute(selectedField.id) : undefined;

  useEffect(() => {
    if (!showRoadRoute || !selectedField) return;
    if (roadRoute) {
      onRoadRouteStatus?.(`Ruta por caminos: ${(roadRoute.distanceM / 1000).toFixed(1)} km · datos OpenStreetMap vía OSRM`);
    } else {
      onRoadRouteStatus?.("Todavía no hay ruta por caminos generada para este predio (ejecuta \"npm run generate:road-routes\").");
    }
  }, [showRoadRoute, selectedField, roadRoute, onRoadRouteStatus]);

  if (loadError) return <div className="ops-map-state">Google Maps no pudo cargar. La lista operacional sigue disponible.</div>;
  if (!isLoaded) return <div className="ops-map-state"><span className="view-loader__spinner" /> Cargando cartografía…</div>;

  return (
    <GoogleMap
      mapContainerStyle={containerStyle}
      center={depotPoint}
      zoom={14}
      onLoad={handleLoad}
      onClick={() => onSelectVehicle(null)}
      onDragStart={onUserInteracted}
      options={{
        mapTypeId: "satellite",
        disableDefaultUI: true,
        zoomControl: true,
        fullscreenControl: true,
        gestureHandling: "greedy",
        clickableIcons: false,
        tilt: 0,
      }}
    >
      {zones.map(z => <PolygonF key={z.id} paths={z.vertices.map(toMapPoint)} options={{ fillColor: z.color, strokeColor: z.color, fillOpacity: .18, strokeWeight: 2 }} onClick={() => onSelectZone?.(z.id)}/>)}
      {fields.map((field) => (
        <PolygonF
          key={field.id}
          paths={field.polygon.map(toMapPoint)}
          options={{
            strokeColor: field.color,
            strokeOpacity: 1,
            strokeWeight: selectedField?.id === field.id ? 3 : 2,
            fillColor: field.color,
            fillOpacity: selectedField?.id === field.id ? 0.24 : 0.14,
          }}
        />
      ))}

      {showRows && fields.map((field) => (
        <PolylineF
          key={`rows-${field.id}`}
          path={field.workPath.map(toMapPoint)}
          options={{ strokeColor: field.color, strokeOpacity: 0.9, strokeWeight: 3 }}
        />
      ))}

      {showRoadRoute && roadRoute && (
        <PolylineF
          path={roadRoute.geometry.map(toMapPoint)}
          options={{ strokeColor: "#d8ff62", strokeWeight: 5, strokeOpacity: 0.95 }}
        />
      )}

      {vehicles.map((vehicle) => (
        <OverlayViewF key={vehicle.id} position={toMapPoint(vehicle.position)} mapPaneName="overlayMouseTarget">
          <button
            type="button"
            className="ops-map-vehicle-button"
            onClick={(event) => { event.stopPropagation(); onSelectVehicle(selectedVehicleId === vehicle.id ? null : vehicle.id); }}
            aria-label={selectedVehicleId === vehicle.id ? `Quitar foco de ${vehicle.name}` : `Enfocar ${vehicle.name}`}
            aria-pressed={selectedVehicleId === vehicle.id}
          >
            <TractorMarker vehicle={vehicle} selected={selectedVehicleId === vehicle.id} label={markerLabels?.[vehicle.id]} type={markerTypes?.[vehicle.id]} />
          </button>
        </OverlayViewF>
      ))}
    </GoogleMap>
  );
}
