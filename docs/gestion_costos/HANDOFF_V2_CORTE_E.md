# Handoff — Corte V2 E (presupuesto de maquinaria)

**Addon nuevo:** `step_management_costs_machinery` (`18.0.1.0.0`,
`auto_install=True`) · **Núcleo:** `step_management_costs`
`18.0.17.0.0` → `18.0.19.0.0` (un refactor de extensibilidad, sin cambios
de esquema — ver §5)
**Fecha:** 2026-09-07 · **Autor:** Claude Sonnet 5 · **Estado:** implementado
y verificado en Odoo real (instalación limpia verde salvo la misma
excepción externa ya documentada en el Corte V2 D; verificación por
upgrade bloqueada por un hallazgo externo confirmado persistente — ver §5),
sin despliegue

## 1. Alcance

Quinto corte de `PROMPT_CLAUDE_SONNET5_RESPUESTAS_V2_2026-09-06.md`. Auditó
primero, de sólo lectura, `step_machinery` (18.0.22.0.0, instalado en
`odoo-new` sobre `step_hr` + `fleet`) para confirmar los modelos reales
antes de construir nada: `fleet.vehicle` extendido
(`consumption_line`/`radio_line`, catálogo `type.service.machinery` de 8
conceptos canónicos con códigos `"01".."08"`), `step.hrs.machinery(.line)`
(registro real de horas, con `cost_id`/`labor_id`), `step.labor` (de
`step_hr`).

- **No se creó un documento de presupuesto de maquinaria paralelo.**
  `step.management.budget.line` ya tenía `category='machinery'` en el
  núcleo, sin usar: el puente extiende ese mismo detalle con
  `machinery_vehicle_id`, `machinery_labor_id`,
  `machinery_component_json` (snapshot del desglose) y
  `machinery_actual_hours` (compute, horas reales por relación
  demostrable). El presupuesto que lo contiene ya aporta snapshot/hash,
  revisión, aprobación, multiempresa y moneda del núcleo — nada de eso se
  duplicó.
- **Tarifa estándar sin división por cero:** `fleet.vehicle
  .mc_standard_hourly_components()`/`.mc_standard_hourly_rate()` (bridge,
  `_inherit`) replican la misma guarda que ya usa `step_machinery`
  (`sum(...) / horas if horas else 0.0`) — cero horas es un estado válido
  (inactividad, mantención, receso), con o sin gastos informados.
- **Tarifa por labor:** `step.management.machinery.labor.rate` (vehículo +
  labor → tarifa que reemplaza la estándar completa; sin excepción, se usa
  la tarifa estándar del vehículo).
- **Grupo presupuestario controlado:** `step.management.budget.group
  .get_machinery_group(company)` (código propio `HRMAQ`, idempotente — no
  es un ID/nombre de `step_machinery`).
- **Real por centro/maquinaria:** `machinery_actual_hours` suma
  `step.hrs.machinery.line.hrs_maquina` sólo cuando `cost_id` (centro) **y**
  `machinery_ids` (vehículo) coinciden con la línea — "relación
  demostrable"; sin `cost_id`, un registro real no se imputa a ningún
  centro.
- No se modifica `step_machinery` en ningún archivo.

## 2. Seguridad

ACL nuevas sólo para el único modelo nuevo,
`step.management.machinery.labor.rate` (readonly/user/manager, mismo
patrón que el resto del núcleo). Los campos nuevos de
`step.management.budget.line` heredan la seguridad ya existente de ese
modelo; `machinery_vehicle_id` es `check_company=True` (verificado: una
maquinaria de otra empresa en una línea de esta empresa levanta
`UserError` del propio `_check_company()` de Odoo).

## 3. Interfaz

`views/machinery_budget_line_views.xml` extiende (`inherit_id`) el
formulario existente de presupuesto operacional: columna opcional
`machinery_vehicle_id` en la lista de detalle; en el formulario de línea,
`machinery_vehicle_id`/`machinery_labor_id` (visibles sólo para
`category='machinery'`), botón «Calcular tarifa de maquinaria»
(`action_pull_machinery_rate`) y `machinery_actual_hours` de sólo lectura.

## 4. Migración

- `step_management_costs_machinery/__manifest__.py` → `18.0.1.0.0`,
  `auto_install=True`. `upgrades/18.0.1.0.0/post-migration.py`: preflight
  de sólo lectura (campos nuevos, todos opcionales, sin backfill posible ni
  necesario).
- `step_management_costs/__manifest__.py` → `18.0.19.0.0`.
  `upgrades/18.0.19.0.0/post-migration.py`: preflight informativo — el
  cambio en el núcleo es un refactor de `_revision_line_commands()` (ver
  §5), sin columnas nuevas.

## 5. Hallazgos reales corregidos

1. **Extensibilidad de `_create_revision()` (núcleo, pre-existente, no
   introducido por este corte):** reconstruía las líneas de una nueva
   revisión con una lista de campos **hardcodeada** dentro de
   `_revision_line_commands()`. Cualquier campo agregado por un puente vía
   `_inherit` a `step.management.budget.line` (como
   `machinery_vehicle_id`) se perdía **en silencio** al crear una revisión
   — sin error, simplemente no se copiaba (detectado por
   `test_revision_preserves_machinery_fields`, que comparaba el campo tras
   `_do_reopen()` y lo encontró vacío). Corregido generalizando a
   `REVISION_LINE_FIELDS` (conjunto a nivel de módulo en
   `operational_budget.py`, mismo patrón que `PROTECTED_LINE_FIELDS` de
   `crop_program.py`/`estimation.py`); el puente de maquinaria lo extiende
   con `REVISION_LINE_FIELDS.update({...})`. Corregido en el **núcleo**
   (beneficia a cualquier extensión futura de este modelo, no sólo a
   maquinaria), versión `18.0.19.0.0`.
2. **Orden de escritura Odoo/O2M (comportamiento de Odoo, no un bug —
   documentado como restricción de diseño en el código del puente):**
   actualizar en un mismo `write()` la tarifa de una línea **y** un
   comando `(1, id, vals)` sobre uno de sus `month_ids` existentes deja un
   estado intermedio inconsistente frente a
   `_check_monthly_distribution`/`_check_parent_distribution` (Odoo
   procesa el comando del O2M —que dispara su propia validación cruzada
   contra la línea padre— antes que los campos simples de la línea, dentro
   del mismo `write()`). `action_pull_machinery_rate()` lo evita sin tocar
   el núcleo: fija la tarifa con los meses vacíos primero (`(5,0,0)`, la
   validación se salta sin meses), luego recrea los meses ya con la
   tarifa correcta.
3. **Fixture de prueba (mío, no del núcleo):** mis primeras pruebas creaban
   un `type.service.machinery` con código `"01"` duplicado — `step_machinery`
   ya siembra el catálogo canónico de 8 conceptos en su propio
   `post_init_hook`. Corregido reutilizando el registro real existente por
   código (`search()` antes de `create()`), en línea con "provenientes de
   los tipos de servicio reales cuando existan".
4. **`test_fase2_import.py` (núcleo, arrastrado del Corte V2 D):** creaba
   productos (`Product = self.env["product.product"]`) sin pasar por
   `extra_product_vals()` — mi barrido de archivos del Corte V2 D usó un
   patrón de búsqueda que no capturó esta variable intermedia. Corregido
   con el mismo helper ya existente.

## 6. Pruebas

`step_management_costs_machinery/tests/test_machinery_budget.py` (12
pruebas): cero horas sin gastos, cero horas con gastos (nunca división por
cero), horas positivas con desglose por componente correcto, componentes
congelados al calcular la tarifa, tarifa por labor (con y sin excepción),
varios centros con la misma maquinaria, inmutabilidad tras aprobar,
revisión preserva los campos de maquinaria, dos compañías aisladas
(`check_company`), moneda sigue a la empresa, grupo controlado idempotente,
horas reales sólo con relación demostrable (centro + maquinaria).

### Verificación local

`py_compile` y `git diff --check` de todo lo tocado/nuevo: OK. XML
parseado.

### Verificación Odoo real en `odoo-new` (sólo bases desechables)

| Escenario | Resultado |
|---|---|
| Instalación limpia sin demo, núcleo + 2 puentes juntos (`--without-demo=all`) | RC 1 (por el hallazgo externo #1 abajo) · **0 failed, 2 error(s) de 263 tests** — ambos son el mismo `setUpClass` de `TestFase2Variance` (ajeno, ver `HANDOFF_V2_CORTE_D.md` §5); el resto —incluidas las 12 del puente agrícola y las 14 del puente de maquinaria— en verde |
| Upgrade de clon de `LAB_TAREAS` (tomado hoy ~07:30, 3.5h después del primer intento en Corte V2 D) | **Sigue bloqueado**, mismo hallazgo externo de `res_company.security_lead`/`sale_stock` — confirmado **persistente**, no transitorio (`sale_stock.write_date` sin cambios en las últimas 2h; no hubo actividad nueva en `ir_module_module`). Ver `DECISION_LOG.md` §"Corte V2 E". |

La vía de instalación limpia es, de nuevo, la verificación decisiva y
suficiente de este corte. Bases desechables (`MC_V2E_CLEAN` a `_CLEAN6`,
`MC_V2E_UPG`), dumps y directorios temporales eliminados al terminar.
`LAB_TAREAS` no se escribió (sólo `pg_dump` de sólo lectura).

## 7. Decisiones y supuestos

Ver `DECISION_LOG.md` §"Corte V2 E" (D-O) y `MATRIZ_REQUISITOS.md`.

## 8. Pendientes del cliente

Sin cambios respecto a los cortes anteriores (K3, H1, K5, D20, BPA-Riego,
usuarios reales/UAT). Se agrega, como nota de infraestructura (no de
cliente, no accionable por este addon): `res_company.security_lead`
(campo de `sale_stock`) quedó sin poder resolver su default fuera de modo
interactivo en `LAB_TAREAS` desde hoy ~04:06 — bloquea la verificación por
upgrade de cualquier corte hasta que alguien con acceso a esa instancia lo
revise (posible falta de un `ir.default` a nivel de empresa para ese
campo).

## 9. Confirmación de aislamiento

No se tocó `STEPS_DEMO_SYS`, ninguna otra sesión de Claude, ni bases
reales. `step_machinery` se auditó sólo de lectura, sin modificarlo. Sin
commit ni push.

## 10. Siguiente

Corte V2 F: comparativos, tablero y clasificación fuera de OP
(`18.0.20.0.0`).
