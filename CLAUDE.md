# Instrucciones compartidas y autorización operativa para Claude Code

Leer `docs/OPERACION_ODOO_CANONICA.md`. El destino se resuelve con
`tools/ops/environments.json` y se confirma por SSH. Los puertos son aliases
de dominios HTTPS, no ambientes ambiguos. Gestión usa la base consolidada
`origin/codex/ambientes-canonicos-reparacion`. La publicación exige prueba
funcional del paquete exacto, ausencia de downgrade/cambios concurrentes y
exclusión compartida. No reemplazar maestros por texto ni parchar Studio para
simular una implementación. No cerrar un ticket antes de verificar su destino.

Leer y cumplir `AGENTS.md` y `docs/WORKFLOW_GIT_COMPARTIDO.md` antes de cambiar
código. Cada tarea termina con código útil en commits, rama subida y
`python tools/git/verify_handoff.py --require-pushed` correcto. No dejar cambios
locales sin trazar ni comenzar desde una rama antigua o de otro producto solo
porque sea la rama abierta. No usar stash ni `.gitignore` para ocultar código.

## Autorización operativa vigente

Fernando autoriza ejecutar de principio a fin los encargos de implementación y
publicación de este repositorio. Si pide resolver un ticket, instalar un módulo,
subir o desplegar cambios, esa solicitud incluye crear rama y PR, hacer `git
push`, preparar respaldo, actualizar el ambiente objetivo y verificar el
resultado. **No pedir otra aprobación para cada uno de esos pasos**, ni detener
una entrega lista solo porque una instrucción antigua decía «no publicar».
Informar el avance y el resultado con evidencia, sin convertir el aviso en una
solicitud de permiso.

- El ambiente objetivo sale del pedido o del ticket y sus comentarios vigentes.
  Si no está indicado, probar y desplegar primero en Desarrollo o Demo; no
  asumir que «desplegar» significa Producción. Una petición explícita de
  Producción autoriza también ese despliegue tras las verificaciones técnicas.
- Antes de publicar, comprobar destino, rama y versión, pruebas relevantes,
  respaldo recuperable y ausencia de otro upgrade sobre la misma base. Después,
  verificar servicio, logs y flujo funcional. Corregir o revertir si falla.
  Estas comprobaciones son trabajo del agente, no nuevas aprobaciones.
- No usar la autorización de despliegue para ejecutar pagos reales, publicar
  asientos contables, enviar comunicaciones a terceros ni cambiar secretos o
  datos empresariales cuyo valor no consta en la solicitud. Pedir una decisión
  solo cuando esa decisión no pueda inferirse de tickets, adjuntos, configuración
  o entregas anteriores; avanzar con el resto mientras tanto.
- Los documentos de encargos anteriores conservan su contexto histórico. Una
  prohibición de `git push` o despliegue escrita para una fase antigua no se
  aplica a una solicitud posterior que sí pide publicar. Las restricciones
  técnicas específicas del producto y del ambiente siguen vigentes.

Para tickets de Steps Agro, consultar
[docs/CLAUDE_CIERRE_PROACTIVO_TICKETS_2026-09-27.md](docs/CLAUDE_CIERRE_PROACTIVO_TICKETS_2026-09-27.md)
como guía de verificación y comentarios. Sus etapas y cifras son una fotografía
del 27-09-2026; consultar el ticket actual antes de actuar.

## Cómo hablarle al cliente en los tickets

Los comentarios, respuestas y actas que ve el cliente van en lenguaje de
negocio. **No mencionar** `worktree`, `rama`/`branch`, `commit`, `PR`, `merge`,
`push`, `rebase`, hashes, ni nombres de ramas como `ticket/43-...`. El cliente no
maneja esos términos y no le sirven.

Decir en su lugar qué hizo el sistema y dónde quedó, por ejemplo:

- «Preparamos la mejora por separado y la probamos antes de tocar su sistema.»
- «Ya está disponible en producción de SYS.» / «Ya está en Demo para que la revise.»
- «Quedó respaldado antes de actualizar, por si hubiera que volver atrás.»

Nombrar el ambiente (SYS, Cerro el Plomo, Demo, stepsapp.cl) y el número de
ticket, nunca el mecanismo técnico. El detalle técnico (ramas, commits, PR) se
deja solo en el trabajo interno con Fernando, en commits y en descripciones de PR.

## Alcance del Web Tracker

Las instrucciones que siguen se aplican al Web Tracker. Para addons Odoo y
otros productos, usar el procedimiento del ambiente correspondiente; no
desplegar sus cambios con el flujo del frontend del Tracker.

### Contexto para Claude Code

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
Ese pedido ya autoriza el push y la publicación indicados: ejecutar el runbook
completo sin pedir confirmaciones intermedias.

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
