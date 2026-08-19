# Integración Odoo ↔ Web Tracker

Fecha: 2026-08-19
Módulo: `step_hr` (nuevos archivos: `models/step_tracker.py` ampliado,
`models/step_tracker_sync.py`, `views/step_tracker_sync_views.xml`,
`data/step_tracker_cron.xml`).

## Objetivo

Que un usuario de Odoo pueda ver máquinas, conductores, predios y sesiones
de trabajo (recorridos GPS) de Web Tracker **sin entrar al sitio Web
Tracker**, navegando el menú **Actividades → Web Tracker** dentro de Odoo.

## Por qué "pull" por API y no conexión directa a la base de Web Tracker

Web Tracker tiene su propio Postgres (`tracker_steps.sql` en este repo) y su
propio backend (una API HTTP que el frontend consume en
`src/services/trackerApi.ts` y en las pantallas de `src/pages/*.tsx`,
apuntando por defecto a `http://localhost:8000`). Es una base de datos
completamente distinta a la de Odoo, en otro servicio.

Se eligió sincronizar por API REST (pull periódico, `ir.cron`) en vez de
enlazar Odoo directo a esa Postgres (FDW / dblink) porque:

- No acopla el módulo de Odoo al esquema interno de Web Tracker (si cambian
  columnas del lado de Tracker, solo se actualiza el cliente HTTP).
- Reutiliza la autenticación que Web Tracker ya expone (`/auth/login`).
- Es el mismo patrón que usa el propio frontend de Web Tracker, así que el
  contrato de datos ya está probado en producción.
- Evita depender de que la red permita conexiones Postgres directas entre
  el servidor de Odoo y el de Web Tracker.

La contraparte es que Odoo trabaja con una **copia** (espejo) de los datos,
no en vivo. Para el mapa en tiempo real y el detalle de puntos GPS de un
recorrido, la vista de sesión en Odoo no repite ese detalle: la idea es que
Odoo muestre lo operacional (duración, distancia, máquina, conductor,
centro de costo) y quien necesite el mapa/reproducción entre a Web Tracker.

## Qué se implementó

- **Modelos espejo** (solo lectura para usuarios, sin alta manual):
  `step.tracker.machine`, `step.tracker.driver`, `step.tracker.field`,
  `step.tracker.session`, `step.tracker.work_order`.
- **Vínculos opcionales** hacia los modelos reales de Odoo, para no duplicar
  maestros: `step.tracker.machine.vehicle_id → fleet.vehicle`,
  `step.tracker.driver.employee_id → hr.employee`,
  `step.tracker.field.analytic_account_id` y
  `step.tracker.session.analytic_account_id → account.analytic.account`
  (el centro de costo real de este Odoo, ver `step_centro_costo.py`).
  Estos vínculos se completan a mano la primera vez; el módulo no intenta
  adivinar la coincidencia.
- **Motor de sincronización** (`step.tracker.sync`, modelo abstracto):
  login contra `/auth/login`, cacheo del token en `ir.config_parameter`
  (uno por compañía), reintento de login si el token expiró (401), y un
  `_upsert` genérico por `tracker_id + company_id`.
- **Registro de sincronización** (`step.tracker.sync.log`): cada corrida
  queda auditada (éxito/parcial/error, cuántos registros de cada tipo,
  detalle del error) — visible en **Web Tracker → Sincronizaciones**
  (solo administradores).
- **Configuración** en *Ajustes → Labores y Tareas → Web Tracker*: URL de
  la API, usuario/contraseña de servicio, interruptor de sincronización
  automática y botón "Sincronizar ahora" para probar la conexión al
  instante.
- **Cron** (`ir.cron`, cada 15 min, **inactivo por defecto**): recorre las
  compañías con la sincronización activada y llama `run_sync`. Si una
  compañía falla, no bloquea a las demás.

## Endpoints usados, y su nivel de confianza

Confirmados leyendo el código fuente del frontend de Web Tracker
(antes de este cambio, en `src/services/trackerApi.ts`, `src/pages/OperationsWorkspace.tsx`
y el antiguo `src/pages/StatsPage.tsx`, ya eliminado por código muerto pero
revisado antes de borrarlo):

| Método | Endpoint | Uso |
|---|---|---|
| POST | `/auth/login` | obtener `access_token` |
| GET | `/machines` | maestro de máquinas |
| GET | `/drivers` | maestro de conductores |
| GET | `/cost_centers` | (no usado aún por el sync; los centros de costo reales viven en Odoo) |
| GET | `/fields` | predios/polígonos |
| GET | `/sessions_recent?limit=N` | sesiones recientes (usado para `_sync_sessions`) |

**No confirmado:** `GET /work_orders` (listado). El frontend solo usa
`POST /work_orders` y `PUT /work_orders/{id}` para crear/cerrar un parte
desde el celular del operador; nunca lista partes. `_sync_work_orders()`
intenta ese endpoint de forma defensiva (si no existe o devuelve otro
formato, se registra un aviso en el log de sincronización y el resto de la
sincronización sigue igual). **Antes de confiar en los datos de
`step.tracker.work_order`, hay que confirmar ese endpoint con quien
mantiene el backend FastAPI de Web Tracker** (o revisar su documentación
OpenAPI en `/docs` si está expuesta).

No tengo acceso en este repo al código fuente del backend FastAPI (solo al
frontend y al dump SQL), así que el contrato exacto de campos de cada
endpoint se infirió de cómo los consume el frontend. Antes de activar la
sincronización en producción, conviene probar "Sincronizar ahora" contra un
ambiente de pruebas y revisar el log.

## Cómo activarlo

1. Instalar/actualizar el módulo `step_hr` en el Odoo real (copiar al
   `addons_path` del servidor y `-u step_hr`, o desde
   *Ajustes → Apps → Actualizar*).
2. Ir a **Ajustes → Labores y Tareas → Web Tracker** y completar:
   - URL de la API (el backend, **no** `stepsapp.cl/web_tracker/`).
   - Usuario y contraseña de una cuenta de servicio en Web Tracker
     (recomendado crear una cuenta dedicada de solo-lectura, no reusar la
     de un operador).
3. Presionar **Sincronizar ahora** y revisar el mensaje / el log en
   **Web Tracker → Sincronizaciones**.
4. Si todo se ve bien, activar el interruptor "Sincronización automática" y
   activar el cron `ir_cron_step_tracker_sync` (queda inactivo por
   instalación, a propósito).
5. En **Web Tracker → Máquinas/Conductores/Predios**, vincular manualmente
   cada registro espejo con su ficha real en Odoo (`fleet.vehicle`,
   `hr.employee`, `account.analytic.account`) para que las sesiones
   filtren correctamente por centro de costo real.

## Qué falta / próximos pasos

- Confirmar el contrato real de `/work_orders` (o pedir que se agregue un
  endpoint de listado si no existe) antes de mostrar horómetro/combustible
  en Odoo con confianza.
- Decidir si conviene mostrar el mapa embebido en Odoo (`iframe` a Web
  Tracker con la sesión seleccionada) en vez de solo datos tabulares — hoy
  la vista de sesión no trae mapa.
- Mover la contraseña de servicio a un mecanismo más seguro que un `Char`
  plano si el estándar de seguridad de la empresa lo exige (el resto del
  módulo `step_hr` tampoco cifra secretos, así que por ahora se mantuvo
  consistente con esa convención).
- Paginar `/sessions_recent` si el volumen supera el límite fijo actual
  (`SESSIONS_PAGE_SIZE = 500` en `step_tracker_sync.py`).
- Este documento y el módulo se hicieron sin acceso al backend FastAPI real
  ni a un Odoo corriendo: falta probarlo contra el servidor
  (`gcloud compute ssh --zone "us-central1-c" "odoo-new" --project "stepsconsulting"`)
  antes de darlo por terminado.
