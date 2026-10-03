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
