# Rutas por caminos del dataset demo

"Ruta por caminos" (vista Monitoreo) no llama a ningún servicio en vivo: lee
un fixture pregenerado en
[`src/demo/fixtures/roadRoutes.json`](../src/demo/fixtures/roadRoutes.json)
con la geometría real (depósito → entrada del predio) de cada uno de los
`DEMO_FIELDS` de [`src/demo/scenario.ts`](../src/demo/scenario.ts).

## Procedencia y licencia

- **Motor de ruteo:** [OSRM](https://project-osrm.org/) (servidor de
  demostración público `router.project-osrm.org`), perfil `driving`.
- **Datos viales:** OpenStreetMap, licencia **ODbL** — se conserva la
  atribución en el propio fixture (`routing.attribution`) y en el footer del
  mapa ("Caminos: OpenStreetMap vía OSRM").
- El fixture incluye `datasetVersion` y `generatedAt` para saber cuándo y con
  qué versión se generó cada ruta.
- No se usa Google Directions/Routes para esto: el brief de rediseño pide
  evitar depender de un servicio que no garantiza poder persistir su
  geometría indefinidamente. Google Maps JavaScript (el mapa satelital en sí)
  sigue usándose y es un caso de licenciamiento distinto, permitido para uso
  en vivo con una clave restringida por dominio.

## Regenerar el fixture

```bash
npm run generate:road-routes
```

El script ([`scripts/generate-road-routes.mjs`](../scripts/generate-road-routes.mjs))
importa `REGIONS` y `DEMO_FIELDS` directamente desde `scenario.ts` (Node 24+
puede ejecutar `.ts` sin build previo), así que nunca hay riesgo de que las
coordenadas del fixture queden desalineadas con las que usa la app. No
requiere ninguna clave ni credencial: el servidor de demo de OSRM es público.
Como es un recurso comunitario compartido, el script espacia las solicitudes
(~400 ms entre cada una) y solo corre en desarrollo — nunca se llama desde el
navegador del usuario final.

Si se agrega un predio nuevo a `DEMO_FIELDS`, hay que volver a correr el
script para que tenga una ruta por caminos; si no la tiene, "Ruta por
caminos" muestra un aviso indicándolo en vez de fallar en silencio.

## Producción con un motor propio

Para un volumen mayor o SLA de disponibilidad, reemplazar la URL pública de
OSRM en el script por una instancia propia (self-hosted OSRM/Valhalla/OSRM) o
por Valhalla/OpenRouteService, sin cambiar el esquema del fixture ni el
código que lo consume (`src/demo/roadRoutes.ts`).
