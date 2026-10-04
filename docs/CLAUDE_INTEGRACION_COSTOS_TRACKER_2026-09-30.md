# Integración de Costos y Gastos con Steps Tracker

Fecha de revisión: 30 de septiembre de 2026.

## Encargo para Claude

Implementa la vinculación entre Steps Tracker y los módulos Odoo de gastos y costos. El resultado debe permitir traer recorridos a las rendiciones, navegar entre el vehículo y sus gastos, y consultar costos por vehículo y centro de costo. Ejecuta el trabajo por entregas verificables; no te detengas en una propuesta conceptual ni vuelvas a preguntar si debes comenzar por revisar los módulos.

Primero identifica cuál es la pantalla de costos que usa el cliente. En el código hay un módulo **Gestión y Costos** (`step_management_costs`), mientras que tu respuesta anterior proponía trabajar sobre **Rendición de Gastos** (`step_expense_report`). Son funciones complementarias, pero no son el mismo módulo. No presentes un botón de importación en Gastos como si completara toda la integración con Gestión y Costos.

Este documento entrega contexto y una especificación de implementación. No afirma que esa integración ya exista. Para ejecutar, respeta `AGENTS.md`, `CLAUDE.md` y las instrucciones del ambiente objetivo. La validación inicial es en Desarrollo o una copia aislada. Una solicitud de modificar el código no autoriza contabilizar gastos reales ni publicar cambios en Cerro El Plomo por defecto.

## 1. Respuestas a las preguntas de tu diagnóstico anterior

| Pregunta | Respuesta y acción |
|---|---|
| ¿En qué rama está el rediseño? | `codex/web-tracker-redesign`, repositorio `fjcaroe/tracker-steps`. Sigue la rama remota actual, no una copia antigua de `develop`. |
| ¿Dónde está el código nuevo local? | `C:/Users/tito4/.codex/worktrees/tracker-layout-protection/Odoo`. Es una referencia de lectura: otra tarea está trabajando allí. No uses ese checkout para tus cambios. |
| ¿Qué revisión se inspeccionó? | `d49a6ccac9481c74be79476cdde5ffc6afdc0dfc`, cuyo mensaje es `feat(tracker): launch mobility home and tenant GPS SIM configuration`. Comprueba el remoto al comenzar: puede haber commits posteriores. |
| ¿Sigue existiendo la API histórica? | Sí. Conserva login, maestros, sesiones y partes. Las rutas concretas se describen abajo; no supongas un listado `GET /sessions`. |
| ¿Qué agregó el rediseño? | Un dominio GPS independiente bajo `/v1`, con activos, dispositivos, asignaciones, posiciones y Protección, y un puente autenticado desde la sesión Odoo. |
| ¿Está instalado `step_tracker_odoo` en Desarrollo? | La tarea de despliegue del 30-09 verificó que estaba instalado en Desarrollo, Demo y Cerro El Plomo. Además instaló `step_tracker_portal`. Revalida versión y estado actual, sin pedir al usuario que averigüe esa información técnica. |
| ¿La rendición pertenece a una máquina o conductor? | Inspecciona el modelo real de `step_expense_report`. El vehículo debe identificarse en la línea de uso; el empleado de cabecera no demuestra por sí solo quién condujo cada recorrido. Usa los vínculos explícitos de vehículo y conductor. |

La entrega inicial del portal fue verificada en los tres ambientes. Al preparar este documento, la otra tarea estaba trabajando en una segunda entrega de portada, alta de vehículos y configuración GPS/SIM. Un commit local no demuestra por sí solo que esa segunda entrega ya esté publicada.

## 2. Archivos que debes leer

Las rutas siguientes son relativas al checkout de Tracker que vas a revisar, excepto donde se indica otra ubicación.

| Archivo | Qué comprobar |
|---|---|
| `docs/STEPS_TRACKER_ENTREGA_20260930.md` | Evidencia de la entrega inicial, arquitectura, ambientes y pendientes. Está en el worktree indicado arriba. |
| `docs/DEPLOY_WEB_TRACKER.md` | Proceso obligatorio de publicación y distinción entre sitio compartido y portal Odoo. |
| `step_tracker_odoo/models/step_tracker.py` | Modelos espejo, claves externas y relaciones hacia Odoo. |
| `step_tracker_odoo/models/step_tracker_sync.py` | Login, sincronización, transformaciones y límites. |
| `step_tracker_odoo/data/step_tracker_cron.xml` | Intervalo de 15 minutos; el XML lo define inactivo por defecto. Comprobar estado real en la base. |
| `step_tracker_odoo/security/ir.model.access.csv` | Permisos del espejo; revisar también reglas de registro efectivas. |
| `step_tracker_portal/controllers/portal.py` | Contexto de compañía, permisos, firma y proxy autorizado. |
| `step_tracker_portal/signing.py` | Identidad servidor a servidor. No copiar claves a clientes. |
| `step_tracker_portal/models/summaries.py` | Ejemplo existente de sincronización incremental y vínculo activo → vehículo. |
| `step_tracker_portal/views/menu.xml` | Accesos desde Odoo a portada, mapa, flota, Protección y configuración. |
| `backend/tracker_py/app/routers/sessions.py` y `schemas/sessions.py` | Contrato real de sesiones y defecto de IDs descrito abajo. |
| `backend/tracker_py/app/routers/work_orders.py` | Partes diarios y lecturas de horómetro/combustible. |
| `backend/tracker_py/app/models/fleet.py` y `routers/fleet.py` | Activos, identidad de cliente, posiciones y contratos `/v1`. |
| `backend/tracker_py/app/routers/fleet_configuration.py` | GPS y SIM: evitar interferir con la entrega concurrente. |
| `src/services/fleetApi.ts`, `src/pages/FleetWorkspace.tsx`, `src/components/FleetAssetDetail.tsx` | Portal nuevo y lugar para enlazar costos. |
| `src/services/trackerApi.ts`, `src/pages/OperationsWorkspace.tsx` | Flujo histórico de sesiones; no confundirlo con el portal nuevo. |

En `C:/Users/tito4/Documents/Odoo` también se revisaron:

- `step_management_costs/models/cost_center.py`: `step.management.cost.center`, con `analytic_account_id`.
- `step_management_costs/models/historical_cost.py`: `step.management.historical.cost`, con `center_id`, `quantity`, `actual_amount`, `budget_amount`, `currency_id` y fecha.
- `step_management_costs/models/management_dashboard.py`: tablero que consume costos históricos y presupuestos.
- `step_machinery/models/real_cost_machinery.py` y `real_cost_machinery_line.py`: costos de maquinaria y registros operativos existentes. Revisarlos antes de crear otra fuente que contabilice lo mismo.

`step_expense_report` no se encontró en los checkouts revisados para este documento. Eso **no** demuestra que falte en el servidor. Localiza su fuente mediante el `addons_path` efectivo del servicio de Desarrollo y revisa el modelo instalado, vistas, estados, permisos y vínculos contables. No inventes sus nombres de campos a partir de las etiquetas de pantalla.

La carpeta local `step_management_costs_machinery` observada no tenía `__manifest__.py`; su mera presencia tampoco acredita un módulo instalable. Busca su versión real antes de depender de ella.

## 3. Arquitectura actual que debes conservar

### 3.1 API histórica y espejo Odoo

Existen los siguientes contratos históricos:

| Ruta | Uso y límite observado |
|---|---|
| `POST /auth/login` | Autenticación histórica de Tracker, distinta de la sesión Odoo del portal. |
| `GET /machines`, `/drivers`, `/fields`, `/cost_centers` | Maestros históricos. |
| `GET /sessions_recent?limit=500` | Ruta que consume actualmente el sincronizador Odoo. Solo trae las últimas N sesiones; no garantiza un período completo. |
| `GET /sessions/search?from=...&to=...&machine_id=...&status=closed&limit=...` | Filtra por **inicio** de sesión, con inicio inclusivo y fin exclusivo. Límite máximo observado: 5.000, sin cursor en ese contrato. No cubre automáticamente sesiones iniciadas antes del período que lo atraviesan. |
| `GET /sessions/{session_id}` | Detalle de sesión; verificar respuesta tipada y permisos. |
| `GET /sessions/{session_id}/track` | Recorrido de la sesión. |
| `GET /work_orders` | Partes diarios; no son órdenes de compra ni rendiciones. |

No reemplaces la autenticación histórica por la identidad `/v1` ni supongas que sus permisos son equivalentes.

**Defecto concreto que debes resolver:** `_sync_sessions` busca `item.get('driver_id')` y `item.get('cost_center_id')`. En la revisión citada, `SessionSummaryOut` no declara esos campos y `/sessions_recent` y `/sessions/search` tampoco los pasan al construir ese resultado. Declara y entrega ambos IDs a partir de `TrackingSession`, de forma compatible con clientes anteriores, y agrega una prueba del JSON efectivamente serializado. No basta con agregar claves a un diccionario que luego elimina el `response_model`.

Después de corregirlo, resincroniza una muestra controlada y comprueba que el conductor y el centro de costo se resuelvan por ID y compañía. No intentes compensar el defecto buscando nombres coincidentes. Si el dato de origen no existe, mantenlo sin asignar y muestra el motivo.

El espejo actual también convierte distancias ausentes en cero y lecturas ausentes en `0.0`. Para la importación económica conserva una indicación explícita de dato disponible/origen/calidad; no conviertas un dato desconocido en una lectura real de cero.

### 3.2 Portal nuevo y dominio GPS

El navegador obtiene su contexto desde `GET /steps_tracker/context`. Para la API GPS usa `/steps_tracker/api/<path>`, que Odoo traduce hacia `/v1/<path>` con identidad firmada de corta duración. Las escrituras pasan por POST con protección CSRF y el método real en el formulario. Reutiliza `fleetApi.ts` y el controlador existente.

Contratos relevantes ya presentes en el código:

- `GET /v1/fleet/snapshot` con paginación `after` y `next_cursor`.
- `GET /v1/assets/{asset_id}`.
- `GET /v1/assets/{asset_id}/positions` con paginación `before` y `next_cursor`; la revisión inspeccionada no ofrece filtro de fechas en esta ruta.
- `PUT /v1/assets`, utilizado por `POST /steps_tracker/import-fleet` para importar vehículos de Odoo.
- `GET /v1/sync/changes`, consumido por la sincronización de Protección. **No es un feed de sesiones históricas ni de costos.**

El servidor resuelve el cliente por emisor/base Odoo y compañía. No aceptes un `tenant_id` arbitrario enviado por el navegador.

Los activos importados desde Odoo tienen `source_id = odoo:fleet.vehicle:<id>` dentro de su cliente. Los creados en el portal usan `manual:<uuid>` y necesitan un vínculo explícito antes de consultar gastos Odoo. La respuesta pública de activo expone `linked_to_odoo`, pero no devuelve actualmente todo el `source_id`: no pretendas reconstruir el ID de vehículo desde ese booleano.

El campo `gps_assets.cost_center` es texto, no una clave de `account.analytic.account`. No lo uses como relación contable.

## 4. Correspondencias obligatorias

| Entidad de Tracker | Relación Odoo existente o por construir |
|---|---|
| Máquina histórica con ID entero | `step.tracker.machine.tracker_id`, por compañía; vínculo existente `vehicle_id → fleet.vehicle`. |
| Conductor histórico | `step.tracker.driver.tracker_id`; vínculo existente `employee_id → hr.employee`. |
| Sesión histórica UUID | `step.tracker.session.tracker_id`, de tipo Char, por compañía. |
| Parte diario histórico | `step.tracker.work_order.tracker_id`; contiene `hourmeter_initial`, `hourmeter_final` y datos de combustible. |
| Predio/centro histórico | Correspondencia explícita hacia `account.analytic.account`; no resolver solo por nombre. |
| Activo nuevo UUID | Correspondencia servidor a servidor `base + compañía + asset_id ↔ fleet.vehicle`, validando propiedad. |
| Centro de Gestión y Costos | `step.management.cost.center.analytic_account_id ↔ account.analytic.account`. Puede necesitar selección explícita si varias fichas usan la misma cuenta. |

Un `machine_id` entero, un `asset_id` UUID y un `fleet.vehicle.id` no son intercambiables. Tampoco `fleet.vehicle.driver_id` —habitualmente un contacto— equivale a `hr.employee.id`.

Antes de ampliar `step.tracker.*`, verifica qué addon es dueño de cada modelo/XML ID en esa base: hay definiciones históricas en `step_hr` además del módulo independiente. Usa herencia sobre el modelo correcto; no crees una segunda definición para resolver dependencias.

Si falta una tabla de correspondencias entre el portal nuevo y Odoo, agrégala en un módulo puente, con restricciones de unicidad, compañía obligatoria, validación de ambos extremos e historial cuando corresponda. No reasignes activos automáticamente por patente ni alteres sus asignaciones GPS para conectar costos.

## 5. Entrega A — Importar uso del vehículo a Gastos

Implementa un asistente **Traer desde Tracker** en la rendición o sección de uso de vehículo que realmente exista en `step_expense_report`.

Flujo esperado:

1. La compañía procede de la rendición y debe ser accesible al usuario.
2. El usuario elige el vehículo y el período. El conductor se propone desde una relación válida, pero se muestran diferencias y sesiones sin conductor identificado.
3. El asistente muestra una vista previa de sesiones cerradas: fecha, vehículo, conductor, inicio, término, duración, kilómetros, centro de costo, origen y si ya fueron utilizadas.
4. Se seleccionan los recorridos a incorporar. La búsqueda y la vista previa no crean gastos.
5. Confirmar crea líneas de uso en borrador, conservando las referencias a las sesiones/partes y los valores importados.
6. Cada línea permite abrir su origen y consultar cuándo se importó. La rendición mantiene su aprobación y contabilización habituales.

### Semántica de los campos

| Campo de destino | Regla |
|---|---|
| Fecha | Usar la zona horaria configurada de la operación; almacenar datetimes según la convención UTC de Odoo. Considerar cambios de hora. |
| Inicio/final | `started_at`/`ended_at` solo si el campo representa una hora del día. |
| Horómetro inicial/final | Importar lecturas reales del parte asociado, si existen y son válidas. La duración de una sesión no permite inventar el horómetro acumulado. |
| Kilómetros | Usar la distancia GPS disponible. API histórica en metros; espejo Odoo en kilómetros. Convertir una sola vez. Distancia recorrida no es lectura acumulada de odómetro. |
| Recorrido | Referencia descriptiva a la sesión y acceso a su trazado. No inventar direcciones de origen y destino a partir de dos nombres. |
| Litros | Mantener el ingreso del comprobante o un dato de recarga registrado y seleccionado explícitamente. `estimated_fuel_liters` no es combustible comprado ni consumido medido. |
| Centro de costo | Relación validada con la cuenta analítica y, si aplica, el centro de Gestión y Costos. |

“Hr inicial/final” en la pantalla es ambiguo: comprueba tipo, ayuda y cálculo del modelo antes de mapearlo. No mezcles reloj, duración, horómetro y horas de motor.

### Integridad de la importación

- Preferir el espejo Odoo cuando su cobertura y permisos sean suficientes. Si está incompleto, completar la sincronización del período por una API autorizada; no confiar en las últimas 500 sesiones.
- Añadir paginación estable para búsquedas completas si hace falta. Elevar simplemente el límite no resuelve el problema. Comprobar también sesiones superpuestas y aquellas que cruzan la medianoche o el límite del período.
- No prorratear kilómetros por tiempo sin evidencia. Si no hay detalle para dividir un recorrido, mostrarlo completo, fuera de rango parcial, y resolver explícitamente su asignación.
- Usar una clave idempotente persistida y una restricción en base de datos, no solo una búsqueda previa. Dos confirmaciones concurrentes no deben duplicar la misma línea de uso.
- Una sesión puede respaldar distintos documentos de gastos; eso no permite duplicar su kilometraje u horas en agregados. Separar el vínculo documental del hecho de uso y de su eventual distribución.
- Conservar una instantánea de los valores importados y referencias a su fuente. Las actualizaciones posteriores no deben sobrescribir correcciones manuales ni rendiciones aprobadas/contabilizadas. Permitir actualización explícita en borrador con trazabilidad.
- Mostrar sesiones sin relación o con datos insuficientes. No escoger el primer conductor, vehículo o centro encontrado.

## 6. Entrega B — Navegación desde Tracker hacia los gastos

En el detalle del vehículo del portal y en su ficha Odoo, añade acceso a **Gastos del vehículo** y a sus rendiciones relacionadas, filtrado por compañía, vehículo y período.

Para servir gastos al portal, la opción preferida es un endpoint Odoo del mismo origen: los costos y sus permisos ya viven allí. No hace falta copiar los documentos financieros a la base GPS ni exponer credenciales de Odoo al frontend.

Contrato propuesto, **nuevo, no existente**: `GET /steps_tracker/costs/assets/<asset_id>?from=...&to=...`. Puede residir en el módulo puente. Debe resolver el activo autorizado en el servidor, localizar su correspondencia Odoo y consultar los registros con los permisos efectivos del usuario. Devuelve solo los campos necesarios, con moneda, período, estado y vínculos de navegación autorizados.

No agregues ese path a la lista del proxy FastAPI como si `/v1/costs` ya existiera. Si eliges otra arquitectura, documenta el contrato y sus pruebas antes de conectarlo al frontend.

Los roles de Tracker no conceden acceso financiero automáticamente. Un operador del mapa sin acceso a Gastos/Costos no debe ver importes, nombres de documentos ni totales. El endpoint debe comprobar esto aunque el botón esté oculto. No uses `sudo()` sobre los gastos para resolver errores de acceso.

No inventes parámetros de enlace a una sesión o vehículo que la aplicación no lea. Si necesitas una selección profunda, implementa y prueba el contrato de navegación. Conservar selección al volver desde Odoo.

## 7. Entrega C — Gestión y Costos y costo por vehículo

Integra las cantidades operativas con Gestión y Costos, además del acceso a Gastos. Reutiliza `step.management.cost.center` y su cuenta analítica, los presupuestos existentes y las fuentes financieras efectivas.

Antes de sumar importes, identifica el circuito actual: rendición → documento contable → distribución analítica → costo histórico o maquinaria. Una misma factura no puede sumarse como rendición, línea contable y costo histórico a la vez. No vuelques agregados sobre `step.management.historical.cost` sin origen, período y clave de actualización idempotente.

Define por separado:

- **Costo real:** fuente financiera autoritativa ya utilizada por el módulo; para una vista de importes contabilizados, usar solo los estados publicados y considerar anulaciones/notas de crédito. Mostrar la base de cálculo.
- **Gasto pendiente:** documentos en borrador o aprobación, separado del costo real.
- **Cantidad operativa:** kilómetros válidos, horas de sesión o lecturas de horómetro, con la métrica identificada. No denominarlas indistintamente horas de motor.
- **Presupuesto:** el presupuesto del centro y período; no sustituirlo por el costo real importado.

Indicadores mínimos:

| Indicador | Condición |
|---|---|
| Costo por km | Costo atribuible al vehículo y período / kilómetros válidos del mismo alcance. |
| Costo por hora | Costo del mismo alcance / horas de la métrica elegida. Etiquetar, por ejemplo, “por hora de sesión” cuando eso sea lo disponible. |
| Costo por centro | Importes distribuidos por la cuenta analítica vinculada al centro, sin duplicar múltiples planes analíticos. |
| Desviación presupuestaria | Comparación de real y presupuesto en igual moneda, período y alcance. |

Si el denominador es cero, falta cobertura GPS, no existe tipo de cambio o no se puede atribuir un importe al vehículo, mostrar **No disponible / información incompleta**. No presentar una razón parcial como costo unitario completo. No repartir gastos de un centro compartido entre vehículos sin una regla de distribución explícita y trazable.

Usar los mecanismos de moneda y conversión existentes. No sumar monedas diferentes ni asumir que la moneda es CLP. Reutilizar las reglas del módulo para impuestos y redondeo; mostrar si se informa neto, bruto u otra base. No alterar asientos ni publicar gastos para calcular indicadores.

## 8. Organización de cambios y preflight

1. Lee las instrucciones vigentes y consulta `git status`, ramas y remoto. El checkout principal tiene cambios ajenos. No los limpies ni los incorpores a tu entrega.
2. Prepara tu propio checkout/rama basada en la referencia correcta. La tarea del portal sigue activa: no cambies, resetees ni actualices su worktree.
3. Consulta estado y versión de `step_tracker_odoo`, `step_tracker_portal`, `step_expense_report`, `step_management_costs`, `step_machinery` y sus dependencias en Desarrollo. Descubre el servicio, base y `addons_path` reales; no adivines el nombre de base a partir de la URL.
4. Consulta metadatos de `ir.model`, `ir.model.fields`, `ir.model.data`, vistas y reglas. Registra los nombres reales de cabecera, línea de vehículo, empleado, estados y documento contable de Gastos.
5. Compara el contrato del código con el OpenAPI y una respuesta autenticada del ambiente. No registres tokens, contraseñas ni encabezados de autenticación en archivos de evidencia.
6. Documenta un mapa de campos origen/destino antes de implementar. Los campos de este documento que pertenecen a Gastos son conceptos funcionales, no nombres de modelo inventados.
7. Crea módulos puente cuando eviten dependencias obligatorias entre productos. Nombres sugeridos, por confirmar: `step_expense_tracker` para Gastos y `step_management_costs_tracker` para Gestión y Costos. Mantén separada la dependencia agrícola para que el servicio GPS de autos no necesite `step_hr` completo.
8. Conserva compatibilidad de rutas y modelos durante la evolución. Una extensión del esquema de sesiones requiere comprobar a todos sus consumidores, no solo el nuevo asistente.

No es necesario un GPS físico para probar el vínculo de software con sesiones y posiciones controladas. Usa datos de prueba en una copia aislada y evidencia real solo donde exista. No mezcles el laboratorio sintético del navegador con fuentes de gastos reales.

## 9. Pruebas y criterios de aceptación

| Caso | Resultado esperado |
|---|---|
| Sesión cerrada con máquina, conductor y centro válidos | La vista previa y la línea creada conservan IDs, fecha y distancia correctos. |
| JSON de `/sessions_recent` y `/sessions/search` | Incluye `driver_id` y `cost_center_id` cuando existen; el espejo resuelve las relaciones. |
| 12.345 metros de origen | 12,345 kilómetros en destino, sin doble conversión. |
| Sesión de 2 horas sin lecturas de horómetro | No inventa lecturas acumuladas ni afirma 2 horas de motor. |
| Litros estimados, ausentes y recarga registrada | Se distinguen; no se contabilizan litros estimados como compra. |
| Repetición o concurrencia del asistente | No duplica la línea de uso ni su cantidad en indicadores. |
| Más de 500 sesiones y búsqueda por encima de un límite de página | Se recupera todo el período o se señala incompletitud; nunca se da por completo un truncamiento silencioso. |
| Cruce de medianoche, cambio de hora y sesión que empieza antes del rango | Selección y asignación temporal coherentes, sin duplicar cantidades. |
| Sesión abierta o incompleta | No se incorpora como un hecho cerrado válido por defecto. |
| Otra compañía o un ID de activo manipulado | Acceso rechazado tanto en la API como en ORM; sin datos financieros cruzados. |
| Usuario con acceso a mapa, pero sin acceso a Gastos | No recibe datos financieros al consultar directamente el endpoint. |
| Activo manual del portal sin vehículo Odoo asociado | Se explica que falta la asociación; no se crea un vínculo por nombre o patente. |
| Sesión asociada a dos documentos financieros | Trazabilidad documental válida, sin duplicar el kilometraje del vehículo. |
| Cambio de sesión tras aprobación de la rendición | No modifica silenciosamente la rendición aprobada. |
| Factura reflejada en rendición y contabilidad | Se cuenta una sola vez en el costo real. |
| Nota de crédito, gasto cancelado y varias monedas | Indicadores y exclusiones conciliables con Odoo. |
| Costos por centro con distribución analítica | Respeta porcentajes y planes sin multiplicar el total. |
| Tracker caído o timeout | Se conserva la rendición y el estado anterior; mensaje claro y reintento seguro. |
| Acceso desde móvil y desde la app Odoo | Importación, navegación y regreso funcionan con los permisos correspondientes. |

Prueba con un usuario operativo sin privilegios administrativos, además del administrador. Las ACL del espejo histórico no demuestran por sí solas aislamiento por compañía: audita y completa las reglas necesarias antes de usarlo como origen financiero.

La entrega debe incluir al menos un ejemplo reproducible con vehículo, sesión, rendición y costo asociado, mostrando el origen de cada dato y la conciliación del total. No uses gastos reales para fabricar esa evidencia.

## 10. Publicación y resultado que debes entregar

Separa cambios de backend, frontend y addons. El `npm build` no instala módulos Odoo. Si el encargo de ejecución incluye publicar, sigue `docs/DEPLOY_WEB_TRACKER.md` y el runbook del servicio Odoo objetivo; toma respaldo y comprueba que no haya otra actualización sobre la misma base. No sobrescribas la nueva portada, configuración GPS/SIM ni permisos del trabajo concurrente.

No subas `.env` ni `.env.production`; no copies claves privadas a variables `VITE_*`. Para el portal multiambiente, consulta el despliegue efectivo: la entrega inicial usó `/var/www/web_tracker_portal/`, distinta del sitio compartido `/var/www/web_tracker/`.

Al finalizar entrega:

- Rama, commits, módulos modificados y versión de cada uno.
- Mapa definitivo de modelos, campos y relaciones.
- Evidencia del asistente de importación, navegación y consulta de costos.
- Pruebas de idempotencia, integridad de cantidades y aislamiento por compañía.
- Estado por entrega A, B y C: implementada, probada, publicada o pendiente, sin confundir estas etapas.
- Procedimiento de actualización y reversión, y cualquier decisión de negocio que impida cerrar una parte concreta.

Avanza con las comprobaciones técnicas y el trabajo verificable. Si una decisión de negocio no se puede inferir —por ejemplo, cómo distribuir un costo compartido entre vehículos— plantea solo esa decisión, conserva el importe como no atribuido y continúa con las demás partes. No vuelvas a pedir la rama, el nombre del endpoint o la instalación de un módulo cuando puedes comprobarlos directamente.
