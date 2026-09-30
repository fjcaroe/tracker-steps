# Zonas y actividad de Steps Tracker

Acceso: **Steps Tracker → Zonas** o `/web_tracker/#zones`. Odoo también tiene
el menú **Steps Tracker → Zonas y actividad**. Disponible para usuarios Tracker;
solo administradores crean, editan y archivan zonas.

## Uso

1. Elegir **Nueva zona**, ingresar nombre, uso y color.
2. Tocar el mapa para marcar entre 3 y 100 vértices. Cerrar el polígono y ajustar
   sus puntos. En móvil, mover el mapa con dos dedos. Se puede trabajar también
   con una línea `latitud, longitud` por vértice en grados decimales.
3. Guardar. Se rechazan bordes cruzados, puntos repetidos, segmentos menores a
   0,5 m, superficies menores a 1 m² y zonas que se extiendan más de 2 grados
   por eje. No se admiten huecos, multipolígonos ni cruce del antimeridiano.
4. Elegir vehículo y período: 8 h, 24 h, hoy o personalizado de hasta 31 días.
   Las consultas de más de 20.000 posiciones piden reducir el período; nunca
   se entregan totales parciales como completos. Los períodos móviles pueden
   actualizarse cada minuto. Los horarios visibles son del navegador.
5. Comparar tiempo observado, distancia estimada, movimiento, detención,
   movimiento desconocido, velocidad máxima y cruces dentro/fuera.
6. Descargar CSV o el perímetro GeoJSON. Para archivar, editar y desmarcar
   **Zona activa**. **Incluir archivadas** permite abrirla y reactivarla.

El mapa general incluye las zonas activas. No se configuran alertas ni acciones
físicas al elegir «Zona restringida»: es una clasificación del lugar.

## Método y límites

- Interpolación lineal de posición y tiempo entre fixes GPS consecutivos; se
  cortan las líneas en todas las intersecciones del polígono, incluso si ambos
  extremos están fuera. El borde se considera dentro. Distancia haversine,
  repartida según la fracción del tramo; superficie en proyección local.
- No hay extrapolación antes/después del historial. Huecos >300 s, cambios de
  asignación GPS, fixes no GPS o ambiguos al mismo instante, y saltos >200 km/h
  quedan sin observación. La cobertura temporal y minutos no observados son
  visibles; falta de datos nunca se presenta como vehículo detenido.
- Movimiento: ambos extremos >2 km/h. Detenido: ambos ≤2 km/h. Si no puede
  clasificarse, movimiento desconocido. Detenido no implica motor apagado.
- Cruces y distancias estimados, no recorridos ajustados a carreteras. No se
  inventa una entrada por iniciar dentro ni cruces durante un corte de señal.
- Geometría actual, con versión explícita en reporte y exportación. Editar
  recalcula el historial con la forma nueva. La auditoría conserva la anterior.
- Zonas superpuestas se analizan independientemente; sus tiempos no deben
  sumarse. Superficie delimitada no equivale a superficie trabajada.
- Solo se dibujan los últimos 500 segmentos y se enumeran los últimos 1.000
  cruces, con aviso visible. Los totales sí abarcan toda la consulta.
- «Explorar demo» contiene un ejemplo sintético reproducible, generado por el
  mismo motor con `scripts/generate-zone-demo.py`. No crea datos reales. Si se
  modifica su geometría, ese ejemplo ya no presenta métricas del polígono viejo.

## Arquitectura y validación

Tabla aditiva `gps_zones`, segregada por tenant y protegida por JWT de compañía
firmado en Odoo. BFF con CSRF, sin credenciales en el navegador. Escrituras
versionadas (409 ante conflicto), auditoría y archivo reversible.

Rutas: GET/POST `/v1/zones`, PATCH `/v1/zones/{id}` y GET
`/v1/zones/{id}/report?asset_id=…&start=…&end=…` (fechas con zona horaria).

Pruebas: cruces con ambos fixes fuera, recorte de período, tangencias,
concavidad, cortes, calidad, cambios GPS, saltos imposibles, duplicados
ambiguos, sin extrapolación, permisos, aislamiento y control de versiones.
El ensayo PostgreSQL verifica persistencia, reporte, archivo y conflicto.

El mapa usa polígonos editables de Google Maps y eventos de clic, sin depender
de DrawingManager, retirado en la versión 3.65:
[Polígonos editables](https://developers.google.com/maps/documentation/javascript/shapes),
[retiro de Drawing Library](https://developers.google.com/maps/documentation/javascript/reference/3.65/drawing).

## Despliegue incremental

Con la versión de movilidad/configuración ya instalada, seguir el procedimiento
de clon fresco y configuración del servidor en `DEPLOY_WEB_TRACKER.md` y ejecutar
`TRACKER_RELEASE=/tmp/<clon-fresco> bash scripts/deploy-tracker-zones.sh`.
Clonar con suficiente historia para resolver la base `429d87b`.

El script verifica divergencias, respalda cuatro bases, API, frontend y módulos;
ensaya up/down/up sobre un clon PostgreSQL y actualización Odoo sobre un clon;
aplica la migración aditiva; actualiza API y solo `step_tracker_portal` en
LAB_TAREAS, STEPS_DEMO y CERRO_EL_PLOMO; publica en
`/var/www/web_tracker_portal/` y compara el hash servido en los tres dominios.
El frontend histórico de `stepsapp.cl` usa otro directorio y no forma parte
de esta entrega del portal.

Rollback: restaurar frontend, código API y addon del respaldo de esta entrega,
reiniciar API y actualizar el addon con su versión respaldada. Conservar
`gps_zones` (aditiva, no afecta versión anterior). El down que elimina la tabla
se usa exclusivamente en el ensayo sin datos; no ejecutarlo sobre datos reales.

## Entrega verificada · 30 septiembre 2026

- Código desplegado: `4d7c9b8b5e06fd7d2f7a51cb06382d057bb2e40d`.
- Respaldo: `/opt/backups/tracker-zones-20260930T223717Z/`; cuatro dumps con
  sumas verificadas y copias de API, frontend y addon de los tres ambientes.
- Bundle servido en Desarrollo, Demo y Cerro: `assets/index-CSNlemFY.js`, SHA256
  `0edbeb8333a5e8c430b30e7879fd858a475902ec0fde3eb61faca048109ca66a`.
- 31 pruebas backend aprobadas; build TypeScript/Vite y lint de archivos nuevos
  aprobados. Ensayo PostgreSQL up/down/up, persistencia y métricas aprobado.
- Actualización Odoo ensayada antes de aplicarse; pruebas HTTP autenticadas en
  los tres ambientes verifican lectura de zonas, rechazo de un polígono vacío
  sin persistencia, CSRF, menú, configuración y sincronización de incidentes.
- Navegador: alta/edición/archivo local, dibujo de cuatro vértices sobre Google
  Maps publicado, arrastre con actualización de coordenadas y guardado demo;
  descargas CSV/GeoJSON verificadas. Vista móvil a 390 y 320 px sin desborde de
  página (navegación horizontal en el menor ancho). Modo demo sin datos reales.
- Todos los servicios activos y `nginx -t` aprobado. Persisten advertencias
  anteriores de nombres HTTP duplicados en nginx, sin cambio en esta entrega.
- Evidencia local: `output/tracker-zones-20260930/zonas-escritorio.png` y
  `metricas-mobile.png` en el workspace principal. Falta la validación física
  del Coban 401C cuando esté instalado y enviando posiciones; las métricas
  reales se habilitan con su historial, no con el ejemplo sintético.
