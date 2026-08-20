export type GeoPoint = { lat: number; lon: number };

export type DemoRegion = { id: string; name: string; depot: GeoPoint };

export type DemoField = {
  id: string;
  name: string;
  crop: string;
  costCenter: string;
  regionId: string;
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
  regionId: string;
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
  regionId: string;
  labor: string;
  startedAt: string;
  startedAtIso: string;
  durationHours: number;
  distanceKm: number;
  coveredHa: number;
  fuelLiters: number;
  avgSpeedKmh: number;
  status: "active" | "completed" | "paused";
};

function isoAt(daysAgo: number, hour: number, minute: number): string {
  const d = new Date();
  d.setHours(hour, minute, 0, 0);
  d.setDate(d.getDate() - daysAgo);
  return d.toISOString();
}

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
  regionId: string,
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
    regionId,
    color,
    areaHa: Number(((widthM * heightM) / 10_000).toFixed(1)),
    polygon: corners,
    workPath: path,
  };
}

// Una empresa agrícola con predios en tres zonas reales de Chile, bien
// separadas entre sí (evita que el mapa quede absurdamente alejado al
// intentar encuadrar todo el país a la vez: cada región se filtra por
// separado, como en Samsara/Geotab con "sitios").
export const REGIONS: DemoRegion[] = [
  { id: "linares", name: "Linares (Región del Maule)", depot: { lat: -35.7596, lon: -71.6033 } },
  { id: "sanfernando", name: "San Fernando (O'Higgins)", depot: { lat: -34.5875, lon: -70.988 } },
  { id: "losangeles", name: "Los Ángeles (Biobío)", depot: { lat: -37.4693, lon: -72.3535 } },
];

export const DEMO_FIELDS: DemoField[] = [
  createField("north", "Lote Norte A", "Avellano europeo", "Fundo San Javier", "linares", { lat: -35.7369, lon: -71.5967 }, 440, 270, 12, "#2f9e72"),
  createField("canal", "Lote Canal 4", "Arándano", "Fundo San Javier", "linares", { lat: -35.7423, lon: -71.5898 }, 340, 230, -8, "#4c8ad6"),
  createField("station", "Cuartel Estación", "Cerezo", "Panimávida", "linares", { lat: -35.7502, lon: -71.6041 }, 390, 250, 21, "#d94835"),
  createField("south", "Lote Sur 2", "Nogal", "Panimávida", "linares", { lat: -35.7551, lon: -71.5936 }, 470, 300, -16, "#8a68cc"),

  createField("sf-vina", "Cuartel Viña Alta", "Vid vinífera", "Fundo Santa Rosa", "sanfernando", { lat: -34.5798, lon: -70.9782 }, 400, 260, 8, "#a5459c"),
  createField("sf-ciruelo", "Lote Ciruelo Sur", "Ciruelo", "Fundo Santa Rosa", "sanfernando", { lat: -34.5941, lon: -70.9946 }, 350, 220, -14, "#e0a52c"),
  createField("sf-palto", "Cuartel Palto 2", "Palto", "Fundo Los Perales", "sanfernando", { lat: -34.601, lon: -70.9701 }, 320, 240, 25, "#2f9e72"),

  createField("la-trigo", "Potrero Trigo Norte", "Trigo", "Fundo El Boldo", "losangeles", { lat: -37.4589, lon: -72.3421 }, 520, 340, -6, "#c79a2b"),
  createField("la-raps", "Lote Raps 3", "Raps", "Fundo El Boldo", "losangeles", { lat: -37.4761, lon: -72.3652 }, 410, 260, 18, "#4c8ad6"),
  createField("la-pino", "Cuartel Forestal 1", "Pino radiata", "Fundo Los Ñipas", "losangeles", { lat: -37.4832, lon: -72.3389 }, 460, 300, -22, "#3d7a4f"),
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

const DRIVER_NAMES = [
  "Fernanda Rojas", "Matías Soto", "Camila Muñoz", "Ignacio Pérez", "Valentina Torres",
  "Cristóbal Reyes", "Javiera Contreras", "Benjamín Castro", "Antonia Vargas", "Diego Fuentes",
  "Josefa Espinoza", "Tomás Herrera",
];

const vehicleSeeds = [
  { id: "demo-01", name: "Tractor 01", plate: "LNRS-01", fieldId: "north", offset: 0.07, speed: 8.4 },
  { id: "demo-02", name: "Tractor 02", plate: "LNRS-02", fieldId: "canal", offset: 0.31, speed: 6.8 },
  { id: "demo-03", name: "Pulverizador 03", plate: "LNRS-03", fieldId: "station", offset: 0.54, speed: 10.2 },
  { id: "demo-04", name: "Tractor 04", plate: "LNRS-04", fieldId: "south", offset: 0.76, speed: 7.5 },

  { id: "demo-05", name: "Tractor 05", plate: "SNFD-01", fieldId: "sf-vina", offset: 0.18, speed: 7.1 },
  { id: "demo-06", name: "Cosechadora 06", plate: "SNFD-02", fieldId: "sf-ciruelo", offset: 0.42, speed: 5.9 },
  { id: "demo-07", name: "Tractor 07", plate: "SNFD-03", fieldId: "sf-palto", offset: 0.63, speed: 8.9 },

  { id: "demo-08", name: "Tractor 08", plate: "LSAN-01", fieldId: "la-trigo", offset: 0.11, speed: 11.4 },
  { id: "demo-09", name: "Cosechadora 09", plate: "LSAN-02", fieldId: "la-trigo", offset: 0.48, speed: 9.6 },
  { id: "demo-10", name: "Tractor 10", plate: "LSAN-03", fieldId: "la-raps", offset: 0.29, speed: 8.2 },
  { id: "demo-11", name: "Forwarder 11", plate: "LSAN-04", fieldId: "la-pino", offset: 0.66, speed: 6.3 },
  { id: "demo-12", name: "Tractor 12", plate: "LSAN-05", fieldId: "la-pino", offset: 0.88, speed: 7.8 },
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
      driver: DRIVER_NAMES[index % DRIVER_NAMES.length],
      fieldId: seed.fieldId,
      regionId: field.regionId,
      status: isTurning ? "turning" : "working",
      progress,
      speedKmh: isTurning ? 3.1 : seed.speed + Math.sin(elapsedSeconds / 13 + index) * 0.7,
      fuelPct: Math.max(28, 88 - index * 6 - elapsedSeconds * 0.0015),
      engineHours: 1240 + index * 214 + elapsedSeconds / 3600,
      distanceKm,
      coveredHa: 4.2 + index * 1.6 + elapsedSeconds * 0.00045 * speedMultiplier,
      position,
      bearing,
    };
  });
}

const LABORS = [
  "Poda de formación", "Riego por goteo", "Aplicación fitosanitaria", "Rastraje", "Fertilización",
  "Cosecha mecanizada", "Raleo", "Control de malezas", "Subsolado", "Deshierbe", "Volteo forestal", "Transporte interno",
];

function seededRandom(seed: number): () => number {
  let s = seed;
  return () => {
    s = (s * 9301 + 49297) % 233280;
    return s / 233280;
  };
}

// Historial extenso (varios días, todas las regiones) para poder probar filtros
// y paginación con volumen realista, no solo un puñado de filas.
function buildDemoSessions(): DemoSession[] {
  const rand = seededRandom(20260819);
  const sessions: DemoSession[] = [];
  let counter = 2450;

  for (let daysAgo = 0; daysAgo < 6; daysAgo += 1) {
    vehicleSeeds.forEach((seed, vIndex) => {
      // no todas las máquinas trabajan todos los días
      if (rand() < 0.22) return;
      const field = DEMO_FIELDS.find((f) => f.id === seed.fieldId) ?? DEMO_FIELDS[0];
      const tripsToday = daysAgo === 0 ? 1 : rand() < 0.35 ? 2 : 1;

      for (let trip = 0; trip < tripsToday; trip += 1) {
        const hour = 6 + Math.floor(rand() * 10) + trip * 5;
        const minute = Math.floor(rand() * 60);
        const durationHours = Number((2.5 + rand() * 4.5).toFixed(1));
        const distanceKm = Number((8 + rand() * 26).toFixed(1));
        const coveredHa = Number((3 + rand() * 12).toFixed(1));
        const fuelLiters = Number((durationHours * (4 + rand() * 3)).toFixed(1));
        const isToday = daysAgo === 0;
        const status: DemoSession["status"] = isToday && trip === tripsToday - 1 && rand() < 0.6 ? "active" : "completed";
        counter += 1;
        sessions.push({
          id: `DS-${counter}`,
          machine: seed.name,
          driver: DRIVER_NAMES[vIndex % DRIVER_NAMES.length],
          field: field.name,
          regionId: field.regionId,
          labor: LABORS[Math.floor(rand() * LABORS.length)],
          startedAt: isToday ? `Hoy, ${String(hour).padStart(2, "0")}:${String(minute).padStart(2, "0")}` : `Hace ${daysAgo}d, ${String(hour).padStart(2, "0")}:${String(minute).padStart(2, "0")}`,
          startedAtIso: isoAt(daysAgo, Math.min(hour, 23), minute),
          durationHours,
          distanceKm,
          coveredHa,
          fuelLiters,
          avgSpeedKmh: Number((distanceKm / durationHours).toFixed(1)),
          status,
        });
      }
    });
  }

  return sessions.sort((a, b) => (a.startedAtIso < b.startedAtIso ? 1 : -1));
}

export const DEMO_SESSIONS: DemoSession[] = buildDemoSessions();

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
