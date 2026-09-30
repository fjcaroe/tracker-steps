# Integración Steps Tracker ↔ Gastos ↔ Gestión y Costos — entrega del 30-09-2026

Ejecuta `docs/CLAUDE_INTEGRACION_COSTOS_TRACKER_2026-09-30.md`. Rama `codex/tracker-costos-integracion`
(base `origin/codex/web-tracker-redesign` @ `429d87b`). El trabajo concurrente del portal (portada, alta de
vehículos, GPS/SIM) **no se tocó**: no se modificó `step_tracker_portal` ni `step_tracker_odoo`, y el
frontend solo agrega un archivo nuevo y tres líneas en dos existentes.

## 1. Estado por entrega

| Entrega | Implementada | Probada | Publicada |
|---|---|---|---|
| **A** · Traer recorridos a Gastos | Sí (`step_tracker_usage` + `step_expense_tracker`) | Sí: 47 pruebas automáticas (17 del hecho de uso + 30 del asistente) + flujo completo contra API real aislada | **Desarrollo** (`LAB_TAREAS`, 30-09 23:27 UTC). Demo, Cerro El Plomo y producción: pendiente |
| **B** · Navegación Tracker ↔ gastos | Sí (`step_management_costs_tracker`, endpoint, vínculo activo↔vehículo, panel y enlace `?asset=`) | Sí: 21 pruebas (8 de vínculos + 13 del endpoint) + HTTP real con usuarios de prueba + panel en navegador local (escritorio y 375 px) | Módulo Odoo en **Desarrollo**. API (`/v1/asset-sources`) y frontend: **pendiente** (ver §8) |
| **C** · Gestión y Costos y costo por vehículo | Sí (servicio de costos, asistente, centros) | Sí: 28 pruebas (21 de costos: reversas, monedas, presupuesto, distribución analítica; 7 del asistente) | Módulo Odoo en **Desarrollo** |

Suite verde en copia aislada de Desarrollo: **101 pruebas Odoo** — 96 de los módulos nuevos (`step_tracker_usage` 17,
`step_expense_tracker` 30, `step_management_costs_tracker` 49) y las 5 preexistentes de `step_expense_report` con el puente instalado —
y **30 pruebas de la API** (`python -m pytest`, 8 nuevas).

## 2. Hallazgos del preflight que cambian el diseño

1. **La pantalla de costos del cliente es Gestión y Costos** (`step_management_costs`); Gastos
   (`step_expense_report`, rama `ticket/43-gastos-rendiciones`, instalado 18.0.1.0.0 en Desarrollo) es complementario. Se
   integraron ambos por separado; el asistente de Gastos no se presenta como la integración de costos.
2. **`step.tracker.*` tiene dos dueños y el último gana.** En cualquier base con `step_hr` (Desarrollo, Demo, producción),
   los modelos `step.tracker.machine|driver|session|work_order` y el servicio `step.tracker.sync` son **los de `step_hr`**:
   su definición sin `_inherit` reemplaza entera a la de `step_tracker_odoo` (se comprobó en el registro:
   `_original_module = step_hr`). Por eso no se extendió ninguno: los hechos de uso, los centros de costo y la sincronización
   por período son **modelos nuevos** en un módulo puente que solo referencia los existentes.
3. **`hr.expense.state` no sirve para separar pendiente de real**: en Odoo 18 `approved` incluye rendiciones ya
   contabilizadas y sin pagar. El pendiente se define por estado de la rendición (`draft/submit/approve`, o sin rendición) y
   se descarta cualquier gasto con apunte publicado.
4. **Permisos de Odoo**: un empleado común no puede leer `fleet.vehicle`; los aprobadores de gastos leen apuntes solo en parte.
   Se creó el grupo `Gastos: elegir vehículos de la flota` (solo lectura, reglas de compañía; lo reciben aprobadores y
   administradores de Tracker) y los importes del portal exigen *aprobador total de gastos* + *lectura contable* (ver §6).
5. **Credenciales de servicio de Tracker**: `res.company.step_tracker_username/password` eran legibles por cualquier usuario
   interno; ahora `groups='base.group_system'` (los procesos de este módulo corren con `sudo` solo para la consulta a Tracker).
6. El campo `Km` de la línea de uso de Gastos tenía 1 decimal y se recalculaba como «lectura final − inicial» (horas de
   horómetro). Para líneas importadas los km son la distancia GPS con 3 decimales y **no** se recalculan.
7. `GET /sessions_recent|search` descartaba `driver_id` y `cost_center_id` (no estaban en `SessionSummaryOut`): el
   sincronizador legado nunca pudo resolver conductor ni centro. Corregido en origen (ver §3).

## 3. Mapa de modelos, campos y relaciones

**API FastAPI (`backend/tracker_py`, release 2026.09.30, solo cambios aditivos)**

| Contrato | Cambio |
|---|---|
| `SessionSummaryOut` (`/sessions/search`, `/sessions_recent`, `/sessions/my`, `/sessions_active`) | + `driver_id`, `cost_center_id` |
| `GET /sessions/period` (nuevo) | Sesiones que **tocan** `[from, to)` (incluye las que cruzan el límite inferior y las abiertas); cursor estable `(started_at, id)`; `{items, next_cursor, complete, total}`; `limit` ≤ 1000 |
| `GET /v1/asset-sources` (nuevo) | `asset_id ↔ source_id` del cliente firmado; solo rol `manager`; fuera del prefijo `assets/` (el proxy del navegador no llega) |
| `/health/capabilities` | + `sessions_period_v1`, `session_summary_ids_v1` (el sincronizador actual no las exige) |

**`step_tracker_usage` 18.0.1.0.0** (depende de `step_tracker_odoo`, `fleet`, `hr`, `account`; no de `step_hr`)

| Modelo | Campos y reglas |
|---|---|
| `step.tracker.usage` (hecho de uso) | `company_id`, `session_uuid` (único por compañía), `machine_id`→`step.tracker.machine`, `vehicle_id` (related), `driver_id`→`step.tracker.driver`, `employee_id` (related), `cost_center_id`→`step.tracker.cost_center`, `analytic_account_id` (related), `started_at/ended_at/status`, `is_closed_fact`, `duration_hours`, `distance_km` + `distance_known`, `work_order_*`, `hourmeter_initial/final` + `hourmeter_known`, `fuel_refill_liters` + `fuel_refill_known`, `estimated_fuel_liters` (etiquetado «no es un dato medido»), `unresolved_reason` |
| `step.tracker.cost_center` | `tracker_id`, `name`, `analytic_account_id` (**vínculo explícito**, nunca por nombre), `company_id` |
| `step.tracker.usage.sync` (servicio) | `sync_period(company, from, to, machine_tracker_id)`: maestros + centros + partes + sesiones paginadas; devuelve `{complete, fetched, source, warnings}` |
| Reglas de compañía | Globales sobre `usage`, `cost_center` y los espejos `machine, driver, activity, labor, implement, field, session, work_order, sync_log` |

**`step_expense_tracker` 18.0.1.0.0** (depende de `step_expense_report`, `step_tracker_usage`, `fleet`)

| Modelo | Campos |
|---|---|
| `step.expense.vehicle.line` (hereda) | `vehicle_id`, `usage_id`→`step.tracker.usage` (único con `sheet_id`), `source`, `driver_employee_id`, `analytic_account_id`, `imported_at/by`, `liters_source`, instantánea `src_*`, `is_modified`; `distance` (16,3), lecturas (12,2) |
| `hr.expense` (hereda) | `step_vehicle_id` (atribución explícita, misma compañía) |
| `step.expense.tracker.import` (+ `.line`) | Asistente: parámetros → vista previa → confirmación |
| `fleet.vehicle` (hereda) | botones **Gastos** y **Rendiciones** |
| Grupo | `group_expense_vehicle` (lectura de `fleet.vehicle`, modelo y marca) |

**`step_management_costs_tracker` 18.0.1.0.0**

| Modelo | Campos |
|---|---|
| `step.tracker.asset.link` | `company_id`, `asset_id` (único por compañía), `vehicle_id` (un vínculo vigente por vehículo: índice parcial), `source` (`odoo_import`/`manual`), `active`, historial `mail.thread` |
| `step.tracker.cost_center` (hereda) | `management_center_id`→`step.management.cost.center` (selección explícita cuando varias fichas comparten cuenta) |
| `step.tracker.vehicle.cost` (servicio) | `compute(vehicle|center, from, to, hourly_metric)` |
| `step.tracker.cost.wizard` (+ `.line`) | Asistente «Costos Tracker» desde el vehículo y el centro |
| Endpoint | `GET /steps_tracker/costs/assets/<asset_id>?from&to&hourly` |

## 4. Semántica

* **Fecha y zona horaria**: la del contacto de la compañía (si falta, la del usuario, si no `America/Santiago`). Los límites
  `[00:00 desde, 00:00 del día siguiente a hasta)` se convierten a UTC con `zoneinfo`; el día del cambio de hora (6-sep-2026,
  23 h) queda con límites coherentes. Cada sesión pertenece a **un** período: el de su fecha local de inicio.
* **Kilómetros**: API en metros → Odoo en km, una sola conversión (`12.345 m → 12,345 km`). Distancia ausente (`null`) ≠ 0:
  `distance_known = False`. Distancia recorrida ≠ odómetro.
* **Horómetro**: solo si el parte trae ambas lecturas, `final ≥ inicial` y no son `0/0`. Un parte cubre una jornada: si
  cubre más de una sesión, su lectura y su recarga **no** se asignan a ninguna (no se duplican).
* **Litros**: el estimado de Tracker se guarda como referencia; la recarga registrada solo entra si el usuario la marca por
  línea. Los litros del comprobante se ingresan a mano.
* **Sesiones sin cerrar / sin distancia**: visibles, no seleccionables (abiertas) o no preseleccionadas (sin distancia,
  que cruzan el límite del período, o ya usadas en otra rendición sin la opción explícita).
* **Integridad**: restricción única `(rendición, sesión)` + bloqueo de la rendición al confirmar + instantánea `src_*`. Tras
  salir de borrador, las líneas importadas no se editan ni se eliminan; la actualización desde Tracker es explícita, solo en
  borrador, no pisa correcciones manuales y queda en el chatter.

## 5. Costos (Entrega C)

* **Costo real** = apuntes **publicados** de cuentas de gasto atribuidos al vehículo por `hr.expense.step_vehicle_id`, más las
  reversas (emparejadas por cuenta e importe inverso). Mismo criterio de fuente que «Presupuesto vs. real» de Gestión y Costos
  (`analytic_actuals`). Base **neta**; importes en moneda de la compañía, con el origen por moneda solo informativo.
* **No se suma** el costeo interno de `step_machinery` (horas × tarifa sobre los mismos gastos: duplicaría) ni se escribe en
  `step.management.historical.cost` (sin clave de origen/período/actualización idempotente no es seguro).
* **Gasto pendiente** separado; **no atribuido** = gastos de rendiciones que usan el vehículo pero no tienen vehículo.
* **Indicadores**: `ok`, `incomplete` (valor parcial de referencia, sin presentarlo como completo) o `unavailable`. Causas:
  denominador 0, sin gastos contabilizados, gastos sin atribuir, pendientes, sesiones excluidas, monedas sin tipo de cambio,
  perfil sin visibilidad. Costo por hora siempre indica su base (sesión u horómetro).
* **Centro**: real por porcentaje de distribución analítica, una vez por plan; fichas que comparten cuenta se avisan y no se
  comparan con presupuesto; presupuesto solo para meses completos, en la misma moneda (sin tipo de cambio = no disponible).
  No hay costo unitario por centro (no hay una regla de distribución entre vehículos).

## 6. Seguridad

* `GET /steps_tracker/costs/assets/<id>`: rol Tracker → compañía del selector **verificada** → activo resuelto solo por el
  vínculo de esa compañía (ID ajeno/inexistente → 404; formato inválido → 400; sin vínculo → explicación, sin datos).
* Importes: requieren *aprobador total de gastos* y/o *lectura contable*; la atribución al vehículo exige ver todos los
  gastos. Empleados, aprobadores de equipo y operadores de mapa reciben 403. Sin `sudo` sobre gastos ni asientos.
* Vínculos activo↔vehículo: solo administradores de Tracker; el activo se verifica contra Tracker con la identidad firmada.

## 7. Evidencia

**Pruebas automáticas** (cada fila del cuadro de aceptación del encargo):

| Caso | Prueba |
|---|---|
| Sesión válida conserva IDs/fecha/km | `test_preview_creates_nothing_and_confirm_keeps_ids_date_and_distance` |
| JSON con `driver_id`/`cost_center_id` | `test_serialized_sessions_carry_driver_and_cost_center_ids` (API) |
| 12.345 m → 12,345 km | `test_ids_resolve_by_id_and_company_and_km_converted_once` |
| 2 h sin horómetro | `test_two_hour_session_without_hourmeter_invents_nothing` |
| Litros estimados / ausentes / recarga | `test_liters_estimated_absent_and_registered_refill_are_distinguished` |
| Repetición y concurrencia | `test_repeated_confirmation…`, `test_database_constraint…`, `test_concurrent_loser…` + carrera real (abajo) |
| > 500 sesiones y límite de página | `test_more_than_500_sessions_*`, `test_period_pagination_is_complete_and_stable` |
| Medianoche, cambio de hora, empieza antes | `test_midnight_crossing…`, `test_daylight_saving_change_day…`, `test_quantities_are_a_partition…` |
| Sesión abierta | `test_open_session_is_listed_but_not_selectable_nor_importable` |
| Otra compañía / ID manipulado | `test_foreign_company_vehicle_and_usage_are_rejected`, `test_manipulated_or_foreign_asset_id…`, reglas de compañía |
| Mapa sin acceso a Gastos | `test_map_operator_without_expenses_or_costs_access_gets_no_amounts` |
| Activo manual sin vehículo | `test_manual_asset_without_vehicle_is_explained_not_linked_by_name` |
| Sesión en dos documentos | `test_same_session_in_two_sheets_needs_explicit_override_and_km_count_once` |
| Cambio tras aprobar | `test_session_change_after_approval_never_touches_the_sheet` |
| Factura en rendición y contabilidad | `test_posted_expense_counts_once_and_pending_is_separate` |
| Nota de crédito, cancelado, monedas | `test_credit_note_reversal_and_cancelled_expense…`, `test_multi_currency_*` |
| Centros con distribución analítica | `test_distribution_by_account_respects_percentages_and_plans`, `TestCenterCosts` |
| Tracker caído | `test_tracker_down_*` (asistente, sincronización, portal 503) |

**Flujo real en Desarrollo** (módulos instalados en `LAB_TAREAS`; API de este release en una instancia aislada `:8011` con base
propia y 626 sesiones sintéticas; vehículo, empleado y cuenta sintéticos `[QA Tracker]`, retirados al terminar):

* API: `driver_id`/`cost_center_id` presentes; `/sessions/period`: 500 + 126 = 626 sesiones **únicas**, `complete` falso y luego
  verdadero; la sesión que cruza el límite inferior aparece.
* Sincronizador **legado de `step_hr`** sin cambios: 625 de 626 sesiones con conductor resuelto por ID (la restante no tiene
  conductor en origen).
* Asistente: vista previa de 626 recorridos **sin crear líneas**, cobertura «completa (626 sesiones)», 3 incorporadas
  (12,345 km con horómetro 1.200→1.207,5 y recarga de 38 L elegida; 30 km que cruzan la medianoche; 8 km que empiezan antes del
  rango asignados a su fecha de inicio); doble confirmación = 3 líneas.
* **Carrera real por XML-RPC** (dos clientes a la vez): una incorpora, la otra informa «ya estaba»; 1 línea.
* Tracker caído: «No se modificó ningún documento; puede reintentar»; la rendición conserva sus 3 líneas y el reintento funciona.
* HTTP real con usuarios de prueba: finanzas 200 (km 109,345 · 623 sesiones; pendiente $45.000), operador 403 sin importes,
  sin rol Tracker 403, activo manual 200 «sin vínculo» sin datos del vehículo homónimo, activo ajeno 404, período inválido 400.
* Vínculos: `sync_from_tracker` crea 1 (el manual se omite) y es idempotente.
* Vistas: `get_views` de Rendición, Gasto, Vehículo, Centro y asistentes renderiza para un perfil financiero y para un empleado común.

**Panel del portal** (arnés local con datos sintéticos): selección preseleccionada por `?asset=`, costos completos, activo manual
con su explicación, sin desborde horizontal a 375 px.

**Ejemplo reproducible** (`test_unit_costs_complete`): vehículo con 1 sesión cerrada de 12,345 km/4 h; gasto de $123.450 contabilizado
(asiento publicado con `expense_id`), costo real $123.450, pendiente $0 → **$10.000/km** y **$30.862,5/h de sesión**; con un gasto aprobado sin
contabilizar el costo por km pasa a «información incompleta» (parcial $10.000). Cada dato tiene origen: sesión (`step.tracker.usage`), gasto
(`hr.expense.step_vehicle_id`), apunte (`account.move.line.expense_id`).

## 8. Publicación, actualización y reversión

**Hecho en Desarrollo** con `scripts/deploy-tracker-costos-dev.sh`: comprobación de que nadie actualiza la base, respaldo
verificado (`/opt/backups/trkcost-dev-20260930-232707/LAB_TAREAS.dump`, 22 MB, SHA256), copia de los 3 módulos **nuevos**
(el árbol de Desarrollo también lo leen `odoo18` y `odoo18-everfruit`, donde no están instalados), `-i step_management_costs_tracker`,
`/web/login` 200. PIDs de los servicios productivos sin cambios. Sin configuración de Tracker en esa base: los flujos reales usaron la
API aislada y se restauró todo.

**Pendiente de publicar** (no se hizo a propósito):

1. **API** (aditiva): publicar con el procedimiento de `DEPLOY_WEB_TRACKER.md`; verificar en `/openapi.json` `GET /sessions/period` y
   `GET /v1/asset-sources`. No requiere migración SQL.
2. **Frontend**: el portal compartido `/var/www/web_tracker_portal/` se actualizó hoy a las 23:05 UTC por la entrega concurrente; esta rama
   parte de `429d87b`, por lo que publicar el build actual lo sobrescribiría. Rebasar sobre la rama remota vigente, reconstruir y desplegar
   después de la API. Mientras tanto el botón «Ver costos y gastos» solo falla con un mensaje en los entornos sin el módulo.
3. **Demo / Cerro El Plomo / producción**: instalar con el mismo script (ajustando base, servicio y usuario de ejecución; Demo corre como `demo_odoo18`).
   Después: Ajustes → Tracker (URL y usuario de servicio), vincular máquinas↔vehículos, conductores↔empleados, centros de Tracker↔cuentas analíticas,
   y «Sincronizar desde Tracker» en Vínculos de activos.

**Reversión**: desinstalar los 3 módulos en orden inverso (los datos propios se eliminan) o restaurar el respaldo indicado por el script
(detiene el servicio, recrea la base, `pg_restore`, retira los 3 directorios, arranca). API: basta restaurar el código previo (cambios aditivos).

## 9. Decisiones y límites

* **Regla de distribución de costos compartidos entre vehículos**: no existe; el importe queda «no atribuido». Se necesita una decisión de negocio
  para habilitar costo unitario por centro.
* **Costeo interno de maquinaria** (`step_machinery`) y `step.management.historical.cost`: fuera del costo por vehículo; definir con Contabilidad si
  se integran y con qué regla para no duplicar.
* Sin sesión de Odoo no se pudo recorrer la interfaz web del asistente; las pantallas se validaron por compilación de vistas (`get_views`) y
  pruebas. Falta la prueba manual en móvil y en la app Odoo con un usuario real.
* El vínculo activo↔vehículo de activos importados depende de publicar `/v1/asset-sources`; los activos manuales se vinculan a mano.
