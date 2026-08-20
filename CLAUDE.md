# Web Tracker — contexto para Claude Code

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
