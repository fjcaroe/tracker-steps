# Steps Móvil — ticket 46

La rama canónica es `codex/steps-movil`. Las ramas `ticket/46-*` anteriores
están integradas en esa historia; no desplegarlas individualmente.

Antes de crear otra mejora, actualizar desde `origin/codex/steps-movil`.
Integrar y probar sobre esa base antes de publicar. Nunca volver a crear una
iteración desde un commit antiguo solo porque conserva el plan inicial.

Procedimiento: `docs/PLAN_MEJORA_STEPS_MOVIL.md`, sección de despliegue.
El script `scripts/deploy-steps-movil.sh` exige un checkout fresco de la rama
canónica y el commit exacto revisado. Respalda API/base/frontend, verifica
cambios del servidor, ensaya el esquema PostgreSQL en una copia y publica API
antes de app. No actualiza el frontend `/web_tracker/` ni addons Odoo.

Pruebas: `npm test && npm run build` en `mobile/`; `python -m pytest -q`
en `backend/tracker_py/`. No subir `.env`, tokens ni archivos de respaldo.

La lista `/sessions/my` se filtra por centros de costo, no por autor.
Retomar requiere selección y confirmación. Una ausencia en esa lista nunca
autoriza borrar una jornada local ni sus puntos pendientes.

Un rechazo permanente del servidor a los puntos (400/404/409/410/422, p. ej. jornada
ya cerrada por otro dispositivo) no se reintenta ni bloquea el cierre: el lote se
guarda aparte en `steps_movil_points_rejected` (tope 5000) y no cuenta como pendiente.
Red caída, 401, 403, 408, 429 y 5xx siguen siendo reintentos. Las jornadas con cierre
ya encolado en el teléfono no se ofrecen para retomar ni quedan como activas.

## App unificada Steps (piloto, 04-10-2026)

`mobile/` ahora es la app unificada: `src/app` (sesión, portada, pantallas), `src/modules/*` (Colaciones, Movilización y el Tracker
existente sin cambios de formato), `src/shared`, `src/platform`, `src/sync`. Documentación: `docs/STEPS_APP_*.md`.
Pruebas: `npm test && npm run build` (117 pruebas). Las pruebas de recorrido usan `src/testing/fakeServer.ts`, un servidor
falso del contrato: no sustituyen las pruebas de Odoo (`step_mobile_portal*/tests`) ni las de dispositivo.
No cambiar `cl.stepsapp.movil` ni las claves `steps_movil_*` del Tracker sin plan de migración.

## Flota Coban móvil — Cerro, 31-10-2026

La consulta GPS física usa la sesión Odoo y /steps_tracker/api/fleet/snapshot.
No usar el token clásico, IMEI como autorización ni duplicar posiciones en jornadas.
El acceso directo /truck/#gps funciona sin login clásico ni GPS del teléfono.
Mantener el watcher de una jornada ya iniciada cuando el usuario cambia de pestaña.

Para esta entrega, Desarrollo y Cerro usan overlays móviles privados bajo
/var/www/steps-mobile-releases/<commit>. Publicar con
python tools/ops/deploy_mobile_hardware_map.py qa|development|production <checkout>
desde un checkout fresco canónico, tras npm ci, npm test y npm run build:tracker.
El publicador exige copia fresca del destino y prueba TCP real hacia la proyección
de flota; compara fuentes API/receptor sin modificarlas. Conserva /web_tracker/,
Demo y la app compartida de Steps. No usar el rsync global anterior para promover
esta entrega ni asumir que actualizar el directorio compartido actualiza Cerro.
