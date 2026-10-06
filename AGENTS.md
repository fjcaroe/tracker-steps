# Instrucciones compartidas para Codex y Claude

Para Odoo, leer `docs/OPERACION_ODOO_CANONICA.md` y resolver el destino con
`tools/ops/environments.json`. No desplegar migraciones o cerrar tickets con
solo sintaxis/HTTP; exigir pruebas funcionales del mismo paquete en una copia
del destino. No sustituir maestros existentes por textos ni tablas paralelas.
Rechazar downgrades y cambios concurrentes; usar exclusión y overlays privados.

## Rama, concurrencia y cierre obligatorio

- Leer `docs/WORKFLOW_GIT_COMPARTIDO.md` antes de cambiar código.
- Identificar producto y rama canónica antes de empezar. No trabajar desde la
  rama que esté abierta por casualidad si pertenece a otro ticket. Para Steps
  Móvil la base vigente es `origin/codex/steps-movil`; para Web Tracker es
  `origin/codex/web-tracker-redesign`. Actualizar la base antes de crear mejoras.
- Cada agente trabaja en un worktree propio. No cambiar la rama ni editar el
  checkout que esté usando otro agente; integrar resultados revisados al terminar.
- El pedido de desarrollar incluye guardar los cambios útiles en commits y
  subir la rama. Al terminar no dejar código nuevo/modificado sin registrar,
  ni usar stash o archivos ignorados como entrega. Los cambios previos también
  deben revisarse y preservarse; no descartarlos para obtener un status limpio.
- Código y scripts útiles van en rutas versionadas del producto o `tools/`.
  Resultados, adjuntos, capturas y respaldos van fuera del checkout, por ejemplo
  en `~/.codex/local-artifacts/`. Nunca ocultar código pendiente con `.gitignore`.
- Ejecutar `python tools/git/verify_handoff.py --require-pushed` al cerrar.
  Debe pasar antes de anunciar la tarea terminada. Para revisar todos los
  worktrees usar además `--all-worktrees`. Si hay un bloqueo real de push o
  integración, identificar el commit/rama preservados y lo que falta.

## Web Tracker — contexto específico

Monitoreo GPS de maquinaria agrícola (frontend Vite/React) con un módulo Odoo
(`step_hr`) que lee sus datos. Repo: `fjcaroe/tracker-steps` (público).

## Antes de tocar código

- **Rama de trabajo:** `codex/web-tracker-redesign`. Producción **no** sigue
  `develop` — sigue esta rama directamente. Hay un PR draft
  (`codex/web-tracker-redesign` → `develop`) abierto para consolidar más
  adelante, sin mergear.
- **`.env` y `.env.production` no están en git** (se sacaron porque el repo
  es público). Viven solo en el servidor. Ver
  [docs/DEPLOY_WEB_TRACKER.md](docs/DEPLOY_WEB_TRACKER.md) antes de intentar
  compilar o desplegar — sin ese archivo el build local funciona igual
  (usa `http://localhost:8000` por defecto) pero el deploy a producción
  necesita las claves reales que solo están ahí.

## Cuando el usuario pida "sube/despliega los cambios"

Seguir **[docs/DEPLOY_WEB_TRACKER.md](docs/DEPLOY_WEB_TRACKER.md)** paso a
paso — no improvisar el proceso. Resumen: `git push` a
`codex/web-tracker-redesign`, luego por SSH a la instancia `odoo-new`
(proyecto GCP `stepsconsulting`, zona `us-central1-c`) clonar fresco en
`/tmp`, copiar `.env`/`.env.production` desde
`/opt/fernando_odoo18/apis/tracker-steps/`, `npm ci && npm run build`,
`rsync` el `dist/` a `/var/www/web_tracker/`, `nginx -t` y
`systemctl reload nginx`. Verificar comparando el hash del JS servido en
`https://stepsapp.cl/web_tracker/` contra el que imprimió el build.

## Otros documentos relevantes

- [docs/INTEGRACION_ODOO_WEB_TRACKER.md](docs/INTEGRACION_ODOO_WEB_TRACKER.md) —
  arquitectura de la sincronización Odoo ↔ Web Tracker (construida, no
  instalada aún contra el Odoo real).
- [docs/MEJORAS_Y_PROXIMOS_PASOS_WEB_TRACKER.md](docs/MEJORAS_Y_PROXIMOS_PASOS_WEB_TRACKER.md) —
  brief original del rediseño (dataset sintético, motor de reproducción,
  etc.), en su mayoría todavía pendiente.

## Reglas duras

- Nunca poner una clave/secreto en una variable con prefijo `VITE_` a menos
  que deba quedar pública en el bundle del navegador — Vite la embebe en el
  JS servido a cualquier visitante.
- Nunca commitear `.env` ni `.env.production`.
