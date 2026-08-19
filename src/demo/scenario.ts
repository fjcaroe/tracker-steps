export type GeoPoint = { lat: number; lon: number };

export type DemoField = {
  id: string;
  name: string;
  crop: string;
  costCenter: string;
  color: string;
  areaHa: number;
  polygon: GeoPoint[];
  workPath: GeoPoint[];
};

export type DemoVehicle = {
  id: string;
  name: string;
  plate: string;
  driver: string;
  fieldId: string;
  status: "working" | "turning" | "paused" | "returning";
  progress: number;
  speedKmh: number;
  fuelPct: number;
  engineHours: number;
  distanceKm: number;
  coveredHa: number;
  position: GeoPoint;
  bearing: number;
};

export type DemoSession = {
  id: string;
  machine: string;
  driver: string;
  field: string;
  startedAt: string;
  durationHours: number;
  distanceKm: number;
  coveredHa: number;
  fuelLiters: number;
  avgSpeedKmh: number;
  status: "active" | "completed" | "paused";
};

const METERS_PER_LAT = 111_320;

function localToGeo(center: GeoPoint, eastM: number, northM: number): GeoPoint {
  return {
    lat: center.lat + northM / METERS_PER_LAT,
    lon: center.lon + eastM / (METERS_PER_LAT * Math.cos((center.lat * Math.PI) / 180)),
  };
}

function rotate(x: number, y: number, degrees: number) {
  const angle = (degrees * Math.PI) / 180;
  return { x: x * Math.cos(angle) - y * Math.sin(angle), y: x * Math.sin(angle) + y * Math.cos(angle) };
}

function createField(
  id: string,
  name: string,
  crop: string,
  costCenter: string,
  center: GeoPoint,
  widthM: number,
  heightM: number,
  rotation: number,
  color: string,
): DemoField {
  const halfW = widthM / 2;
  const halfH = heightM / 2;
  const corners = [
    [-halfW, -halfH], [halfW, -halfH], [halfW, halfH], [-halfW, halfH],
  ].map(([x, y]) => {
    const point = rotate(x, y, rotation);
    return localToGeo(center, point.x, point.y);
  });

  const margin = 16;
  const rowSpacing = 22;
  const rowCount = Math.max(3, Math.floor((heightM - margin * 2) / rowSpacing));
  const path: GeoPoint[] = [];
  for (let row = 0; row <= rowCount; row += 1) {
    const y = -halfH + margin + (row * (heightM - margin * 2)) / rowCount;
    const startX = row % 2 === 0 ? -halfW + margin : halfW - margin;
    const endX = -startX;
    const start = rotate(startX, y, rotation);
    const end = rotate(endX, y, rotation);
    path.push(localToGeo(center, start.x, start.y), localToGeo(center, end.x, end.y));
  }

  return {
    id,
    name,
    crop,
    costCenter,
    color,
    areaHa: Number(((widthM * heightM) / 10_000).toFixed(1)),
    polygon: corners,
    workPath: path,
  };
}

export const DEMO_FIELDS: DemoField[] = [
  createField("north", "Lote Norte A", "Avellano europeo", "Fundo San Javier", { lat: -35.7369, lon: -71.5967 }, 440, 270, 12, "#2f9e72"),
  createField("canal", "Lote Canal 4", "Arándano", "Fundo San Javier", { lat: -35.7423, lon: -71.5898 }, 340, 230, -8, "#4c8ad6"),
  createField("station", "Cuartel Estación", "Cerezo", "Panimávida", { lat: -35.7502, lon: -71.6041 }, 390, 250, 21, "#d94835"),
  createField("south", "Lote Sur 2", "Nogal", "Panimávida", { lat: -35.7551, lon: -71.5936 }, 470, 300, -16, "#8a68cc"),
];
function interpolatePath(path: GeoPoint[], progress: number) {
  const safe = ((progress % 1) + 1) % 1;
  const scaled = safe * (path.length - 1);
  const index = Math.min(path.length - 2, Math.floor(scaled));
  const fraction = scaled - index;
  const a = path[index];
  const b = path[index + 1];
  const position = {
    lat: a.lat + (b.lat - a.lat) * fraction,
    lon: a.lon + (b.lon - a.lon) * fraction,
  };
  const bearing = (Math.atan2(b.lon - a.lon, b.lat - a.lat) * 180) / Math.PI;
  return { position, bearing };
}

const vehicleSeeds = [
  { id: "demo-01", name: "Tractor 01", plate: "DEMO-01", driver: "Operador Demo A", fieldId: "north", offset: 0.07, speed: 8.4 },
  { id: "demo-02", name: "Tractor 02", plate: "DEMO-02", driver: "Operador Demo B", fieldId: "canal", offset: 0.31, speed: 6.8 },
  { id: "demo-03", name: "Pulverizador 03", plate: "DEMO-03", driver: "Operador Demo C", fieldId: "station", offset: 0.54, speed: 10.2 },
  { id: "demo-04", name: "Tractor 04", plate: "DEMO-04", driver: "Operador Demo D", fieldId: "south", offset: 0.76, speed: 7.5 },
];

export function getDemoVehicles(elapsedSeconds: number, speedMultiplier = 1): DemoVehicle[] {
  return vehicleSeeds.map((seed, index) => {
    const field = DEMO_FIELDS.find((item) => item.id === seed.fieldId) ?? DEMO_FIELDS[0];
    const progress = (seed.offset + elapsedSeconds * 0.00085 * speedMultiplier * (1 + index * 0.06)) % 1;
    const { position, bearing } = interpolatePath(field.workPath, progress);
    const isTurning = Math.abs(progress * (field.workPath.length - 1) - Math.round(progress * (field.workPath.length - 1))) < 0.025;
    const distanceKm = 18.6 + index * 4.3 + elapsedSeconds * 0.0018 * speedMultiplier;
    return {
      id: seed.id,
      name: seed.name,
      plate: seed.plate,
      driver: seed.driver,
      fieldId: seed.fieldId,
      status: isTurning ? "turning" : "working",
      progress,
      speedKmh: isTurning ? 3.1 : seed.speed + Math.sin(elapsedSeconds / 13 + index) * 0.7,
      fuelPct: Math.max(28, 88 - index * 9 - elapsedSeconds * 0.002),
      engineHours: 1240 + index * 318 + elapsedSeconds / 3600,
      distanceKm,
      coveredHa: 4.2 + index * 2.1 + elapsedSeconds * 0.00045 * speedMultiplier,
      position,
      bearing,
    };
  });
}

export const DEMO_SESSIONS: DemoSession[] = [
  { id: "DS-2401", machine: "Tractor 01", driver: "Operador Demo A", field: "Lote Norte A", startedAt: "Hoy, 07:42", durationHours: 4.8, distanceKm: 23.4, coveredHa: 11.8, fuelLiters: 31.2, avgSpeedKmh: 8.1, status: "active" },
  { id: "DS-2402", machine: "Tractor 02", driver: "Operador Demo B", field: "Lote Canal 4", startedAt: "Hoy, 08:06", durationHours: 4.3, distanceKm: 19.1, coveredHa: 8.5, fuelLiters: 27.8, avgSpeedKmh: 6.9, status: "active" },
  { id: "DS-2399", machine: "Pulverizador 03", driver: "Operador Demo C", field: "Cuartel Estación", startedAt: "Hoy, 06:55", durationHours: 5.6, distanceKm: 27.8, coveredHa: 13.2, fuelLiters: 38.6, avgSpeedKmh: 9.8, status: "active" },
  { id: "DS-2398", machine: "Tractor 04", driver: "Operador Demo D", field: "Lote Sur 2", startedAt: "Hoy, 07:21", durationHours: 5.1, distanceKm: 24.7, coveredHa: 12.1, fuelLiters: 34.5, avgSpeedKmh: 7.4, status: "active" },
  { id: "DS-2397", machine: "Tractor 01", driver: "Operador Demo A", field: "Lote Canal 4", startedAt: "Ayer, 13:10", durationHours: 3.7, distanceKm: 16.9, coveredHa: 7.6, fuelLiters: 24.1, avgSpeedKmh: 7.8, status: "completed" },
  { id: "DS-2396", machine: "Tractor 04", driver: "Operador Demo D", field: "Lote Norte A", startedAt: "Ayer, 08:14", durationHours: 6.2, distanceKm: 31.5, coveredHa: 15.4, fuelLiters: 42.7, avgSpeedKmh: 7.2, status: "completed" },
];

export const DEMO_DAILY = [
  { day: "Lun", hectares: 31.4, distance: 72, fuel: 94, efficiency: 82 },
  { day: "Mar", hectares: 36.8, distance: 81, fuel: 101, efficiency: 86 },
  { day: "Mié", hectares: 28.2, distance: 67, fuel: 88, efficiency: 79 },
  { day: "Jue", hectares: 42.6, distance: 93, fuel: 112, efficiency: 91 },
  { day: "Vie", hectares: 39.7, distance: 87, fuel: 106, efficiency: 88 },
  { day: "Sáb", hectares: 46.1, distance: 98, fuel: 119, efficiency: 93 },
  { day: "Hoy", hectares: 45.6, distance: 95, fuel: 114, efficiency: 92 },
];

export const DEMO_EVENTS = [
  { time: "12:41", title: "Pasada completada", detail: "Tractor 01 · Lote Norte A", tone: "success" },
  { time: "12:38", title: "Giro de cabecera", detail: "Pulverizador 03 · Cuartel Estación", tone: "info" },
  { time: "12:31", title: "Consumo actualizado", detail: "Tractor 04 · 6,8 L/h", tone: "neutral" },
  { time: "12:22", title: "Cobertura 75 %", detail: "Tractor 02 · Lote Canal 4", tone: "warning" },
];
