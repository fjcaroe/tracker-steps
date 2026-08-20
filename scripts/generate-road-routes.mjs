#!/usr/bin/env node
// Genera rutas viales reales (depósito -> entrada de cada predio) usando el
// servidor de demostración público de OSRM sobre datos de OpenStreetMap
// (licencia ODbL). Es una herramienta de desarrollo que se ejecuta una vez
// para producir el fixture versionado en src/demo/fixtures/roadRoutes.json;
// la app en producción nunca llama a este servidor, solo lee el fixture.
//
// Uso: npm run generate:road-routes

import { mkdir, writeFile } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { DEMO_FIELDS, REGIONS } from "../src/demo/scenario.ts";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const OUT_PATH = path.join(__dirname, "..", "src", "demo", "fixtures", "roadRoutes.json");
const OSRM_BASE = "https://router.project-osrm.org/route/v1/driving";

// El servidor de demo de OSRM es un recurso comunitario compartido: se
// espacian las solicitudes para no saturarlo (esto solo corre en desarrollo,
// nunca en el navegador del usuario final).
const REQUEST_DELAY_MS = 400;

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

async function fetchRoute(origin, destination) {
  const coords = `${origin.lon},${origin.lat};${destination.lon},${destination.lat}`;
  const url = `${OSRM_BASE}/${coords}?overview=full&geometries=geojson`;
  const res = await fetch(url, { headers: { "User-Agent": "tracker-steps-demo-dataset-generator (dev tool, not deployed)" } });
  if (!res.ok) throw new Error(`OSRM respondió HTTP ${res.status} para ${coords}`);
  const body = await res.json();
  if (body.code !== "Ok" || !body.routes?.length) throw new Error(`OSRM sin ruta para ${coords} (${body.code})`);
  const route = body.routes[0];
  return {
    distanceM: route.distance,
    durationS: route.duration,
    geometry: route.geometry.coordinates.map(([lon, lat]) => ({ lat, lon })),
  };
}

async function main() {
  const generatedAt = new Date().toISOString();
  const routes = [];
  let failures = 0;

  for (const field of DEMO_FIELDS) {
    const region = REGIONS.find((r) => r.id === field.regionId);
    if (!region) continue;
    // La geometría del predio ya representa una entrada/esquina razonable;
    // no inventamos un punto de acceso separado.
    const destination = field.polygon[0];
    process.stdout.write(`Calculando ruta ${region.name} -> ${field.name}... `);
    try {
      const route = await fetchRoute(region.depot, destination);
      routes.push({ fieldId: field.id, regionId: field.regionId, ...route });
      console.log(`ok (${(route.distanceM / 1000).toFixed(1)} km, ${route.geometry.length} puntos)`);
    } catch (err) {
      failures += 1;
      console.log(`FALLÓ: ${err.message}`);
    }
    await sleep(REQUEST_DELAY_MS);
  }

  const fixture = {
    datasetVersion: `${generatedAt.slice(0, 10)}-osrm-v1`,
    generatedAt,
    synthetic: true,
    label: "Rutas por caminos (depósito -> predio) - dataset demostrativo",
    routing: {
      provider: "OSRM demo server (router.project-osrm.org)",
      profile: "driving",
      attribution: "(c) Contribuyentes de OpenStreetMap - ruteo vía OSRM (https://project-osrm.org/), datos bajo licencia ODbL",
      generatedAt,
    },
    routes,
  };

  await mkdir(path.dirname(OUT_PATH), { recursive: true });
  await writeFile(OUT_PATH, `${JSON.stringify(fixture, null, 2)}\n`, "utf8");
  console.log(`\nEscrito ${routes.length}/${DEMO_FIELDS.length} rutas en ${path.relative(process.cwd(), OUT_PATH)}`);
  if (failures > 0) {
    console.log(`${failures} ruta(s) fallaron; vuelve a correr el script (el fixture solo tiene las rutas que sí se calcularon).`);
    process.exitCode = 1;
  }
}

main().catch((err) => {
  console.error(err);
  process.exitCode = 1;
});
