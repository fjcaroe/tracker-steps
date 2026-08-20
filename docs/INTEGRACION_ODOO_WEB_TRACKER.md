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
  `step.tracker.machine`, `step.tracker.driver`, `step.tracker.activity`,
  `step.tracker.labor`, `step.tracker.implement`, `step.tracker.field`,
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

Los mantenedores web requieren además que la API desplegada junto con Odoo en
GCP conserve estos contratos:

| Recurso | Contratos administrativos requeridos |
|---|---|
| Conductores | `GET/POST /drivers`, `PATCH/DELETE /drivers/{id}` |
| Actividades | `GET/POST /activities`, `PUT/DELETE /activities/{id}` |
| Labores | `GET/POST /labors`, `PUT/DELETE /labors/{id}` |
| Implementos | `GET/POST /implements`, `PATCH/DELETE /implements/{id}` |

Los `DELETE` de esos cuatro recursos son desactivaciones lógicas: no borran las
referencias que Odoo o Tracker necesitan para mostrar información histórica.
La vigencia del release puede comprobarse con `GET /health/capabilities`; debe
informar al menos `odoo_sync_v1` y las capacidades `master_*_crud` usadas por
los mantenedores.

`GET /work_orders`, `POST /work_orders` y `PUT /work_orders/{id}` están
versionados en el backend. Desde el release 2026.08.20 el listado devuelve
`machine_id` y `fuel_tank_end_liters`, de modo que el ingreso manual y el espejo
de Odoo pueden reconstruir el parte completo.

Desde el 2026-08-20 el código fuente del backend FastAPI productivo está
versionado en `backend/tracker_py/`. Los contratos pueden verificarse mediante
sus pruebas y el OpenAPI generado. Antes de activar la sincronización en
producción se debe ejecutar "Sincronizar ahora" y revisar el log de Odoo.

## Cómo activarlo

1. Instalar/actualizar el módulo `step_hr` en el Odoo real (copiar al
   `addons_path` del servidor y `-u step_hr`, o desde
   *Ajustes → Apps → Actualizar*).
2. Ir a **Ajustes → Labores y Tareas → Web Tracker** y completar:
   - URL de la API: **`https://stepsapp.cl/tracker-steps`** (confirmado
     directamente en `/etc/nginx/sites-available/stepsapp` del servidor:
     `location ^~ /tracker-steps/ { rewrite ^/tracker-steps/(.*)$ /$1 break;
     proxy_pass http://127.0.0.1:8000; }` — coincide con
     `VITE_API_BASE_URL` del frontend en producción). **No** usar
     `stepsapp.cl/web_tracker/`, que es el sitio estático, ni
     `stepsapp.cl/api/steps-truck/`, que es un backend distinto (puerto
     9000, otra app).
   - Usuario y contraseña de una cuenta de servicio en Web Tracker
     (recomendado crear una cuenta dedicada de solo-lectura, no reusar la
     de un operador).
3. Presionar **Sincronizar ahora** y revisar el mensaje / el log en
   **Steps Tracker → Integración → Sincronizaciones**.
4. Si todo se ve bien, activar el interruptor "Sincronización automática" y
   activar el cron `ir_cron_step_tracker_sync` (queda inactivo por
   instalación, a propósito).
5. En **Steps Tracker → Maestros → Máquinas/Conductores/Predios**, vincular manualmente
   cada registro espejo con su ficha real en Odoo (`fleet.vehicle`,
   `hr.employee`, `account.analytic.account`) para que las sesiones
   filtren correctamente por centro de costo real.

## Aplicación nativa en Odoo

Al actualizar `step_hr`, el selector principal de `https://stepsapp.cl/odoo`
muestra una aplicación de primer nivel llamada **Steps Tracker**. No reemplaza
el frontend cartográfico: presenta en Odoo la copia sincronizada y mantiene los
vínculos con los módulos que ya usa la empresa.

- **Resumen:** tablero ejecutivo de 7, 30 o 90 días con sesiones, distancia,
  horas, partes, combustible, máquinas, conductores y estado del último sync.
- **Operación:** sesiones GPS y partes diarios en listas y formularios nativos.
- **Reportes:** gráficos y tablas dinámicas de sesiones, máquinas, labores y
  combustible, con exportación estándar de Odoo.
- **Maestros:** máquinas, conductores, predios, actividades, labores e
  implementos sincronizados.
- **Integración:** logs y configuración, visible para administradores.
- **Abrir mapa Web Tracker:** abre `/web_tracker/` en otra pestaña cuando se
  necesita mapa, reproducción o edición de polígonos.

Los enlaces funcionales son:

- máquina Tracker → `fleet.vehicle` de **Flota**;
- conductor Tracker → `hr.employee` de **Empleados**;
- predio o parte Tracker → `account.analytic.account` de **Contabilidad**.

El tablero está implementado como una acción cliente OWL de Odoo 18 y sus
recursos se declaran en `web.assets_backend`. Tras `-u step_hr`, si el navegador
conserva recursos anteriores, cerrar sesión, volver a entrar y recargar una vez
con `Ctrl+F5`.

## Qué falta / próximos pasos
- Decidir si conviene mostrar el mapa embebido en Odoo (`iframe` a Web
  Tracker con la sesión seleccionada) en vez de solo datos tabulares — hoy
  la vista de sesión no trae mapa.
- Mover la contraseña de servicio a un mecanismo más seguro que un `Char`
  plano si el estándar de seguridad de la empresa lo exige (el resto del
  módulo `step_hr` tampoco cifra secretos, así que por ahora se mantuvo
  consistente con esa convención).
- Paginar `/sessions_recent` si el volumen supera el límite fijo actual
  (`SESSIONS_PAGE_SIZE = 500` en `step_tracker_sync.py`).
- El 2026-08-19 se confirmó por SSH la URL real de la API
  (`https://stepsapp.cl/tracker-steps`, ver más arriba) y que el servidor
  tiene Odoo corriendo en el mismo host (proxy `/` → `:8069`), pero **no
  se instaló ni probó esta versión de `step_hr` contra ese Odoo real** — falta
  copiarlo al `addons_path` que use esa instancia, actualizarlo
  (`-u step_hr` o desde Apps) y correr "Sincronizar ahora" con una cuenta
  de servicio real para validar el contrato de datos de
  `/machines`, `/drivers`, `/fields` y `/sessions_recent`.
