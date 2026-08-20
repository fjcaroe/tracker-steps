import { DEMO_FIELDS, DEMO_SESSIONS, REGIONS, getDemoVehicles } from "./scenario";

export type DemoCatalogKey = "machines" | "drivers" | "activities" | "labors" | "implements" | "costCenters" | "species" | "varieties" | "regions" | "communes" | "fundos" | "sectors" | "fields";
export type DemoCatalogItem = { id: number; name: string; [key: string]: unknown };

const unique = (values: string[]) => [...new Set(values)];
const named = (values: string[]) => unique(values).map((name, index) => ({ id: index + 1, name }));

const vehicles = getDemoVehicles(0);
const activities: DemoCatalogItem[] = [
  { id: 1, name: "Manejo del cultivo", code: "MAN" },
  { id: 2, name: "Cosecha y transporte", code: "COS" },
  { id: 3, name: "Operación forestal", code: "FOR" },
];
const laborNames = unique(DEMO_SESSIONS.map((session) => session.labor));
const labors: DemoCatalogItem[] = laborNames.map((name, index) => ({
  id: index + 1,
  name,
  activity_id: /forestal|volteo/i.test(name) ? 3 : /cosecha|transporte/i.test(name) ? 2 : 1,
}));
const costCenters = named(DEMO_FIELDS.map((field) => field.costCenter));
const species = named(DEMO_FIELDS.map((field) => field.crop));
const regionItems = REGIONS.map((region, index) => ({ id: index + 1, name: region.name, code: region.id.toUpperCase() }));

export const DEMO_MASTER_CATALOGS: Record<DemoCatalogKey, DemoCatalogItem[]> = {
  machines: vehicles.map((vehicle, index) => ({ id: index + 1, name: vehicle.name, plate: vehicle.plate, region_id: REGIONS.findIndex((region) => region.id === vehicle.regionId) + 1 })),
  drivers: named(vehicles.map((vehicle) => vehicle.driver)),
  activities,
  labors,
  implements: named(["Rastra de discos", "Pulverizador", "Carro de cosecha", "Subsolador", "Desbrozadora"]),
  costCenters,
  species,
  varieties: species.map((item) => ({ id: item.id, name: `${item.name} · variedad demo`, species_id: item.id })),
  regions: regionItems,
  communes: regionItems.map((region) => ({ id: region.id, name: String(region.name).split(" (")[0], region_id: region.id })),
  fundos: costCenters.map((center) => {
    const field = DEMO_FIELDS.find((item) => item.costCenter === center.name);
    return { id: center.id, name: center.name, region_id: REGIONS.findIndex((region) => region.id === field?.regionId) + 1 };
  }),
  sectors: costCenters.map((center) => ({ id: center.id, name: `Sector operacional · ${center.name}`, fundo_id: center.id })),
  fields: DEMO_FIELDS.map((field, index) => ({
    id: index + 1,
    name: field.name,
    color: field.color,
    crop: field.crop,
    hectares: field.areaHa,
    cost_center_id: costCenters.find((center) => center.name === field.costCenter)?.id,
    region_id: REGIONS.findIndex((region) => region.id === field.regionId) + 1,
    polygon: field.polygon,
  })),
};

export type DemoWorkOrder = {
  id: number;
  code: string;
  work_date: string;
  season: string;
  machine_id: number;
  activity_id: number;
  labor_id: number;
  cost_center_id: number | null;
  field_id: number | null;
  implement_id: number | null;
  hourmeter_initial: number | null;
  hourmeter_final: number | null;
  fuel_tank_start_liters: number | null;
  fuel_refill_liters: number | null;
  fuel_tank_end_liters: number | null;
  notes: string;
};

export const DEMO_WORK_ORDERS: DemoWorkOrder[] = DEMO_SESSIONS.slice(0, 18).map((session, index) => {
  const machine = DEMO_MASTER_CATALOGS.machines.find((item) => item.name === session.machine);
  const field = DEMO_MASTER_CATALOGS.fields.find((item) => item.name === session.field);
  const labor = labors.find((item) => item.name === session.labor) ?? labors[0];
  const initial = 1240 + index * 17;
  return {
    id: 90_000 + index,
    code: `DEMO-${String(index + 1).padStart(4, "0")}`,
    work_date: session.startedAtIso.slice(0, 10),
    season: `${new Date().getFullYear() - 1}-${new Date().getFullYear()}`,
    machine_id: machine?.id ?? 1,
    activity_id: Number(labor.activity_id ?? 1),
    labor_id: labor.id,
    cost_center_id: Number(field?.cost_center_id ?? 0) || null,
    field_id: field?.id ?? null,
    implement_id: (index % DEMO_MASTER_CATALOGS.implements.length) + 1,
    hourmeter_initial: initial,
    hourmeter_final: Number((initial + session.durationHours).toFixed(1)),
    fuel_tank_start_liters: 180,
    fuel_refill_liters: index % 3 === 0 ? 45 : 0,
    fuel_tank_end_liters: Number((180 - session.fuelLiters + (index % 3 === 0 ? 45 : 0)).toFixed(1)),
    notes: "Registro sintético del Laboratorio demo.",
  };
});
