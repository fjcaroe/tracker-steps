# Handoff — Fase 7, corte 2 (revisión R1–R6 + Orden de Producción)

**Addon:** `step_management_costs` · **De:** `18.0.13.0.0` → **A:** `18.0.14.0.0`
**Fecha:** 2026-09-04/05 · **Autor:** Claude · **Estado:** implementado y
verificado en Odoo real, sin despliegue

## 1. Alcance

Continuación de `REVISION_CORTE1_Y_CONTINUACION_CLAUDE_CORTE2_2026-09-04.md`,
que revisó `18.0.13.0.0` (no desplegada) y encontró 6 defectos reales
(R1–R6) a cerrar **en la misma versión** antes de tocar el Corte 2. Este
handoff entrega ambas cosas, en el orden que pedía el documento: primero
R1–R6, verificados en verde contra Odoo real; recién entonces la Orden de
Producción (`18.0.14.0.0`).

### Fase A — R1–R6 (siguen en `18.0.13.0.0`)

- **R1 — contrato de huella para la vista previa semanal.**
  `models/planning.py`: la validación de estado del plan
  (`draft`/`planned`) se movió **dentro de**
  `_build_weekly_task_commands()` (antes sólo vivía en
  `action_generate_weekly_tasks()`, así que un wizard instanciado por RPC
  directo se saltaba el gate). Nueva
  `StepManagementPlan._weekly_task_fingerprint(commands, season)`: sha256
  determinista sobre los comandos y la temporada. El wizard
  (`wizard/plan_weekly_preview.py`) guarda la huella en `default_get()` y
  `action_confirm()` la recalcula y compara antes de aplicar: si el
  presupuesto o el plan cambiaron entre la vista previa y la confirmación,
  no escribe nada y pide abrir una vista previa nueva.
- **R2 — normalizar UdM antes de consolidar necesidades de stock.**
  `models/stock_requirement.py`: nuevo `_bucket_quantity()` convierte cada
  cantidad a `product_id.uom_id` con `uom.uom._compute_quantity(...,
  raise_if_failure=True)` antes de acumularla; rechaza con error accionable
  una fuente sin UdM o de categoría incompatible. El bucket ya no guarda la
  UdM de la primera fuente, sino la del producto.
  `models/crop_program_import.py`: sin UdM en el Excel, se asume la del
  producto; si el Excel sí la informa, se valida que sea de la misma
  categoría.
- **R3 — faltante acumulado cronológico.** `stock_requirement.py`:
  `shortage_quantity` deja de ser un `compute` por línea aislada y pasa a
  calcularse una sola vez en `action_compute()`, recorriendo los períodos
  de cada producto en orden cronológico y consumiendo su disponibilidad
  **una sola vez** (no una foto repetida en cada semana/mes).
  `available_quantity` sigue siendo la foto informativa (igual para todos
  los períodos del producto).
- **R4 — coherencia completa de variedad.** Nueva función compartida
  `crop_program.py::check_center_variety_coherence()` (y su interna
  `_variety_issue()`), usada tanto por `crop_program.py` como por
  `crop_program_import.py`: normaliza con `strip().casefold()`, exige que
  la variedad del encabezado coincida con la única variedad de los
  centros, y trata la mezcla de centros con/sin variedad informada como
  error (antes se ignoraba el centro vacío). Si **todos** los centros
  quedan sin variedad, se permite guardar/calcular en borrador pero
  `action_approve()` lo bloquea. El importador auto-completa la variedad
  del encabezado desde los centros sólo si está vacía y es inequívoca. El
  preflight de `upgrades/18.0.13.0.0/post-migration.py` se reescribió para
  reutilizar la misma función (vía ORM, no SQL crudo) en modo sólo lectura.
- **R5 — endurecer el importador Excel.** `crop_program_import.py`: semana,
  carencia y reingreso ya no truncan `20.5`/`7.5`/`12.5` — nuevo
  `_to_int_strict()` los rechaza como error de fila si no son enteros. La
  idempotencia pasa de `(empresa, archivo)` a `import_key_hash` (empresa +
  temporada + tipo + centros normalizados + archivo), protegida además por
  un **índice único parcial de Postgres** (`init()`,
  `WHERE state='imported'`) — el `search()` previo sigue como atajo rápido,
  pero el índice es el resguardo real ante concurrencia (`action_import()`
  envuelve la escritura en un `savepoint()` y traduce el
  `IntegrityError` a un mensaje legible).
- **R6 — sólo documentación.** `DECISION_LOG.md` D20 reescrito separando
  hecho técnico / incógnita funcional / decisión temporal, sin tocar
  `step_hr`. Nueva D21 documenta el supuesto de dosis cero (ver §6).

### Fase B — Corte 2: Orden de Producción (`18.0.14.0.0`)

Nuevo `models/production_order.py`
(`step.management.production.order` + `.line`): una OP por **empresa,
temporada, año/semana ISO, especie y centro de costo** (el cuartel es un
atributo informativo del centro, no crea otra OP). Consolida, sin
duplicar, dos fuentes ya existentes en el núcleo — `step.management.plan.line`
(tareas planificadas no canceladas) y
`step.management.crop.program.application` (aplicaciones de un programa
**aprobado** de la misma temporada) — mediante el mismo contrato de huella
que R1 (`_build_op_commands()` + `_op_fingerprint()`, vista previa vía
`wizard/production_order_preview.py`). `action_authorize()` (sólo
`group_management_approver`) vuelve a comparar la huella antes de congelar
`approval_snapshot`/`approval_hash`; una OP autorizada es inmutable y las
correcciones son una nueva revisión (mismo patrón que `crop_program.py`:
`revision`/`revision_of_id`/`superseded_by_id`, líneas **no** se copian —
se regeneran, igual que `crop_program.application_ids`).

Identidad y concurrencia: índice único parcial de Postgres
(`company_id, center_id, iso_year, iso_week, species_key` **WHERE
state='authorized'**) impide dos OP vigentes para la misma clave; una
revisión legítima primero reemplaza (`superseded`) el origen y luego se
autoriza a sí misma **dentro del mismo `savepoint()`**, para no chocar con
su propio origen mientras éste sigue "authorized".

PDF QWeb (`views/production_order_report.xml`,
`report_production_order`/`_document`): usa `web.basic_layout` (no
`web.external_layout` — esta instancia de `LAB_TAREAS` tiene el layout
externo estándar customizado vía Studio con un campo `x_name` que no
existe en modelos nuevos, y rompe cualquier reporte nuevo que dependa de
él; es un defecto del entorno, no del addon, documentado aquí en vez de
"corregido" porque tocar el layout compartido está fuera de mandato).
`_report_payload()` usa el snapshot autorizado si existe (nunca vuelve a
consultar `product_id`/`center_id` en vivo); en borrador arma la misma
forma de datos en vivo, sin garantía de estabilidad.

Envío simulado: `action_send_report()` exige OP autorizada y al menos un
destinatario (`recipient_ids`, `res.partner`, sin default), adjunta el PDF
y **encola** un `mail.mail` (`state='outgoing'`) — nunca llama `.send()`,
así que nunca se contacta un servidor SMTP real, ni en producción por
error de este corte ni en las pruebas.

API interna para el futuro puente OT: `get_bridge_payload()` rechaza
cualquier OP no autorizada; ningún otro módulo la consume todavía. Este
corte **no crea OT** ni escribe en addons operacionales.

**Cosecha queda fuera de este corte** (bloqueo real, no decisión de
diseño): `harvest.plan.line` es semanal agregado y no tiene `center_id`;
la OP es por centro. No hay forma determinista de repartir kilos por
centro sin inventar un prorrateo, así que no se reparte (ver D22 en
`DECISION_LOG.md` — pendiente añadir esa entrada si Codex la solicita
formalmente; por ahora queda descrita aquí y en el código).

## 2. Seguridad

- ACL nuevas: `production.order(.line)` y los dos wizard de vista previa,
  mismo patrón `readonly ⊂ user ⊂ manager` de `ir.model.access.csv`
  (aprobar/autorizar es un gate de rol en Python, no de ACL, igual que
  `crop_program.action_approve`).
- Reglas globales por empresa nuevas para `production.order(.line)` en
  `management_security.xml`.
- `check_company=True` en `center_id`, `plan_line_id`,
  `program_application_id`, `budget_group_id`. `_check_company_auto=True`
  en ambos modelos nuevos.
- `action_authorize`, `action_confirm` del wizard y `action_send_report`
  validan rol/estado explícitamente (no confían sólo en ACL), incluso por
  RPC directo — probado con `with_user(self.user_operator)`.
- Sin bypass por contexto: `write()`/`unlink()` de la OP y sus líneas
  bloquean cambios cuando `state in ('authorized', 'superseded')`, igual
  patrón que `crop_program.py`.

## 3. Interfaz

- Menú **Gestión y Costos > Planificación > Orden de Producción**.
- Formulario de OP: botones «Generar líneas» (abre la vista previa),
  «Autorizar» (sólo aprobador), «Nueva revisión», «Cancelar», «Enviar»;
  pestañas Líneas / Autorización / Destinatarios y envío.
- Wizard de vista previa: mismo patrón visual que el de tareas semanales
  (conteo a reemplazar/crear + detalle línea a línea, huella oculta).

## 4. Migración

- Manifiesto `18.0.14.0.0`; sin dependencias nuevas del manifiesto (usa
  `mail` ya presente para `mail.mail`).
- `upgrades/18.0.14.0.0/post-migration.py`: modelo enteramente nuevo, sin
  backfill; sólo un log informativo idempotente.
- `upgrades/18.0.13.0.0/post-migration.py` (Fase A): reescrito para
  reutilizar `_variety_issue()` vía ORM; sigue sin bloquear el upgrade ni
  corregir nada automáticamente.
- Secuencia nueva `step.management.production.order` (`OP/%(year)s/`).
- Índices únicos parciales creados en `init()` (no en la migración): uno
  nuevo para la identidad de la OP, uno nuevo para `import_key_hash` de
  `crop_program_import` (R5). Ambos `CREATE UNIQUE INDEX IF NOT EXISTS`,
  reejecutables sin efecto.

## 5. Pruebas

- **R1–R6:** `tests/test_fase7_hardening.py` (25 pruebas nuevas): huella
  de vista previa (sin cambios, presupuesto/plan cambiado entre medio, RPC
  directo, otra empresa, tareas manuales intactas, usuario sin rol);
  conversión de UdM (kg↔g, categoría incompatible, UdM por defecto del
  producto en el importador); faltante acumulado (ejemplo del documento —
  100 de stock, dos períodos de 60 — varios productos, stock negativo,
  orden mayo→abril); coherencia de variedad (mayúsculas/espacios,
  encabezado contradictorio, mezcla vacío/informado, todos vacíos bloquean
  aprobación, auto-completar en importación); importador (enteros
  estrictos, dosis cero bloquea aprobación, misma receta en dos
  temporadas, intento duplicado idéntico bloqueado).
- **Corte 2:** `tests/test_fase7_corte2_production_order.py` (18 pruebas
  nuevas), los 11 puntos de la puerta de salida: identidad
  especie+centro+semana (especie debe calzar con la del centro cuando
  ambas están informadas); W01/cruce de año (verificado con
  `period_service.iso_weeks`) y W53 (temporada `2020/2021`, que sí tiene
  semana 53 ISO); vista previa sin escritura + detección de fuente
  cambiada (mismo contrato que R1); conciliación independiente
  tareas/fito-ferti; no duplicación de fuentes (constraint SQL); sólo
  aprobador autoriza (incluso por RPC); snapshot/hash + inmutabilidad +
  revisión (las líneas de una revisión se regeneran, no se copian);
  concurrencia de autorización (dos OP independientes con la misma
  identidad — la segunda choca contra el índice único parcial); PDF desde
  snapshot (verificado sobre el HTML renderizado — cambiar
  producto/centro después de autorizar no altera el texto ya renderizado);
  destinatarios + envío simulado (`mail.mail` en estado `outgoing`, nunca
  se llama `.send()`); API futura de OT (rechaza borrador, acepta
  autorizada).
- Se auditaron y ajustaron fixtures de `tests/test_fase5_programs.py` y
  `tests/test_fase6_stock.py` (variedad de `center_a`/`center_a2`, UdM por
  defecto en líneas de programa) para no romper con las reglas más
  estrictas de R2/R4.

### Verificación local

- `py_compile` de todos los `.py` del addon (existentes + nuevos): OK.
- Parseo de los 28 XML del addon: OK.
- `git diff --check`: OK (mismos avisos LF/CRLF preexistentes ya
  documentados en cortes anteriores, ninguno nuevo).

### Verificación Odoo real en `odoo-new` (sólo bases desechables)

Mismo patrón que `HANDOFF_FASE7_CORTE1.md`: SSH a `odoo-new` (GCP
`stepsconsulting`), clon de `LAB_TAREAS` vía `pg_dump`/`pg_restore` a una
base desechable, addon copiado a un `addons_path` temporal con precedencia
sobre la copia existente en `/opt/dev_odoo18/odoo_agriculture`, proceso
real (`/usr/bin/python3.10` + `PYTHONPATH=/opt/odoo18`, sin el venv).
`LAB_TAREAS` sólo se leyó (`pg_dump`), nunca se escribió.

**Ronda 1 — Fase A (R1–R6), sin subir aún el manifiesto a `18.0.14.0.0`:**

| Escenario | Resultado |
|---|---|
| Upgrade de clon de `LAB_TAREAS` (`18.0.4.0.0` → `18.0.13.0.0`) | RC 0 · **0 failed, 0 error(s) de 186 tests** (`odoo.tests.stats`: 220 tests, 249.0s, 70847 queries) |
| Instalación limpia sin demo (`--without-demo=all`) | RC 0 · **0 failed, 0 error(s) de 186 tests** (`odoo.tests.stats`: 220 tests, 51.1s, 32279 queries) |

**Ronda 2 — Fase B (Corte 2), manifiesto en `18.0.14.0.0`:**

Se detectaron y corrigieron 3 problemas reales durante la verificación
(ninguno visible con sólo `py_compile`/parseo XML, porque son errores de
render de QWeb y de una suposición de test incorrecta):

1. El primer intento del PDF falló con `ValueError: Not naive datetime`:
   la plantilla combinaba `context_timestamp(...)` (que ya convierte a la
   zona horaria del usuario) con `t-options="{'widget': 'datetime'}"`
   (que intenta convertir *de nuevo*). Se corrigió formateando la fecha
   con `.strftime(...)` directamente, sin el widget.
2. Con eso corregido, el PDF seguía fallando: `web.external_layout` en
   esta instancia de `LAB_TAREAS` está customizado (Studio) para mostrar
   un campo `x_name` que no existe en modelos nuevos como
   `step.management.production.order` — es un defecto de personalización
   de este entorno específico, no del addon (probablemente rompe
   cualquier reporte nuevo de cualquier módulo en esta base). Se cambió a
   `web.basic_layout` (plantilla estándar de Odoo sin esa dependencia) en
   vez de intentar corregir el layout compartido, que está fuera de
   mandato de este addon.
3. `test_revision_supersedes_origin_on_authorize` asumía que las líneas de
   la OP se copiaban al crear una revisión; en realidad son derivadas
   (mismo criterio que `crop_program.application_ids`) y deliberadamente
   no se copian — se corrigió el test para regenerar la vista previa de la
   revisión antes de autorizarla, no el comportamiento del modelo.

| Escenario | Resultado |
|---|---|
| Upgrade de clon de `LAB_TAREAS` (`18.0.4.0.0` → `18.0.14.0.0`) | RC 0 · **0 failed, 0 error(s) de 203 tests** (`odoo.tests.stats`: 239 tests, 261.3s→237.3s, ~77300 queries) |
| Instalación limpia sin demo (`--without-demo=all`) | RC 0 · **0 failed, 0 error(s) de 203 tests** (`odoo.tests.stats`: 239 tests, 54.1s, 36478 queries) |

**Discrepancia conocida, aún sin explicar (heredada de `HANDOFF_FASE7_CORTE1.md`):**
`odoo.tests.stats` informa más pruebas (220 en Fase A, 239 en Corte 2) que
las que cuenta `odoo.tests.result` (186 y 203 respectivamente, que sí
coinciden exactamente con 161+25 y 186+18 — la suma exacta de los métodos
`test_*` de este addon). La brecha (34 y 36 respectivamente) es la misma
naturaleza del defecto ya señalado en el corte anterior (174 vs 161): no
se investigó a fondo de nuevo por no ser bloqueante — **0 failed, 0
error(s)** es la línea que realmente certifica el resultado, y coincide
exactamente con el conteo de pruebas de este addon en ambos casos.

Bases (`MC_R1R6_UPG`, `MC_R1R6_CLEAN`, `MC_C2_UPG`, `MC_C2_CLEAN`), dumps de
`LAB_TAREAS`, directorios temporales de addons/logs y scripts desechables
eliminados al terminar cada ronda; no quedaron bases ni archivos temporales
en `odoo-new`. `LAB_TAREAS` no se tocó.

## 6. Decisiones y supuestos

- Ver `DECISION_LOG.md`: D20 reescrito (R6); D21 nueva (dosis cero,
  R5, pendiente de confirmación de Agronomía/Compras).
- **Cosecha fuera de la OP** (Corte 2): decisión temporal, no de diseño —
  `harvest.plan.line` no tiene `center_id`. Repartir kilos por centro sin
  una fuente determinista sería inventar un prorrateo; se documenta el
  bloqueo en vez de hacerlo. Siguiente entrega: decidir si se agrega
  `center_id` a `harvest.plan.line` (con su propio costo de migración) o
  se define otra fuente auditable de reparto por centro.
- **Estados válidos de fuente para la OP** (supuesto abierto, sin
  confirmación del cliente): tareas planificadas se incluyen si el plan y
  la tarea no están cancelados (no hay una lista cerrada de "estados
  válidos" del cliente); aplicaciones de programa se incluyen si el
  programa está **aprobado**. Acotado a `_build_op_commands()` si cambia.
- **PDF vía `web.basic_layout`, no `web.external_layout`**: decisión
  técnica forzada por una customización de Studio en `LAB_TAREAS` (ver
  §5). No es una limitación del addon; en una base sin esa customización
  también funcionaría con `web.external_layout` si se prefiere el
  membrete completo — queda como mejora opcional, no como deuda.
- **Verificación del PDF sobre HTML, no sobre el binario**: `_render_qweb_html`
  en vez de extraer texto de un PDF real, más simple y determinista en
  pruebas; el contenido es el mismo antes del paso final a PDF
  (`wkhtmltopdf`), que sólo cambia el formato de salida, no los datos.
- **Envío nunca real**: `action_send_report()` sólo crea el `mail.mail`
  (`state='outgoing'`); nunca se llama `.send()`. El cron de correo
  saliente de Odoo (fuera del alcance de este addon) sería quien entrega
  de verdad en producción.

## 7. Límites y siguiente corte

- Sin integración con Órdenes de Trabajo (OT): `get_bridge_payload()` es
  sólo el contrato; ningún módulo lo consume todavía.
- Sin puente de maestros con Actividades (`step_management_costs_agriculture`)
  — sigue bloqueado por D20.
- Sin cosecha en la OP — bloqueado por falta de `center_id` en
  `harvest.plan.line` (ver §6).
- La discrepancia `odoo.tests.stats` vs `odoo.tests.result` sigue sin
  explicarse a fondo (heredada, no bloqueante).
- Worktree `C:\Users\tito4\Documents\Odoo-gestion-costos`, rama
  `codex/gestion-costos`. Todo sin commit ni push. Sin despliegue ni
  escritura en `LAB_TAREAS`, `STEPS_DEMO` ni `STEPS_DEMO_SYS`. No se tocó
  Demo-SyS ni las sesiones de Claude que trabajan en Previred/Tesorería en
  el otro worktree.

Siguiente: decidir la fuente de cosecha por centro para completar la OP;
puente de maestros con Actividades (D20); integración real con OT
consumiendo `get_bridge_payload()`.
