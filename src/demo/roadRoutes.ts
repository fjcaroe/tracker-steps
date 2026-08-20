import fixture from "./fixtures/roadRoutes.json";
import type { GeoPoint } from "./scenario";

export type RoadRoute = {
  fieldId: string;
  regionId: string;
  distanceM: number;
  durationS: number;
  geometry: GeoPoint[];
};

// Metadata de procedencia del fixture: de dónde salió la geometría, con qué
// motor y bajo qué licencia (ver scripts/generate-road-routes.mjs).
export const ROAD_ROUTES_METADATA = {
  datasetVersion: fixture.datasetVersion,
  generatedAt: fixture.generatedAt,
  provider: fixture.routing.provider,
  attribution: fixture.routing.attribution,
};

const routesByFieldId = new Map<string, RoadRoute>(
  fixture.routes.map((route) => [route.fieldId, route as RoadRoute]),
);

// Ruta vial persistida (depósito -> predio), pregenerada con OSRM/OpenStreetMap.
// No es una llamada en vivo: mismo predio siempre devuelve la misma geometría.
export function getRoadRoute(fieldId: string): RoadRoute | undefined {
  return routesByFieldId.get(fieldId);
}
