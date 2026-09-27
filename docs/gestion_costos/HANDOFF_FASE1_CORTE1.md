# Handoff a Codex — Fase 0 + primer corte de Fase 1

**Addon:** `step_management_costs`  ·  **De:** `18.0.1.1.0` → **A:** `18.0.2.0.0`
**Fecha:** 2026-09-02  ·  **Autor del corte:** Claude (ingeniería)
**Estado:** listo para revisión de Codex. **No** avanzar a otra fase.

---

## 1. Resumen del resultado y decisiones tomadas

Se completó **Fase 0** (4 documentos de diseño verificable) y un **primer corte
acotado de Fase 1**: plataforma segura del presupuesto operacional
(multiempresa, roles, aprobación inmutable con snapshot, integridad de la
distribución mensual, gate de cuenta analítica) más la infraestructura de
upgrade `18.0.2.0.0` y una batería de pruebas `TransactionCase`.

**No** se implementó: estimaciones, fito, fertilización, cosecha, OP, gasto real
contable (sólo su contrato/mapeo), importadores Excel, informes documentales,
puentes opcionales, ni ningún despliegue.

Decisiones aplicadas en este corte (detalle en `DECISION_LOG.md` y `ADR_001`):

- **D-B/C9/GES-01:** el gasto real corriente saldrá de contabilidad analítica
  (contrato + mapeo de 25 campos documentados); `historical.cost` queda
  reservado a externo/ajuste, con `origin` y bloqueo.
- **D-H/PPT-14/15:** aprobado = inmutable; reapertura sólo con motivo (asistente
  transient); “Nueva revisión” reemplaza sin sobrescribir; snapshot JSON +
  `sha256` congelado al aprobar (contrato mínimo; modelo `revision` de primera
  clase → Fase 2).
- **D-I/PPT-03/16/C11:** la distribución mensual no puede divergir del total
  (constraint con `float_compare`, nunca `==`); una distribución incompleta es
  error visible y **bloquea** la aprobación (antes se rellenaba en silencio).
- **PPT-17:** unicidad de `budget.center` por `unique(budget_id, center_id)`
  SQL, en vez del `search_count` vulnerable a carrera; `pre-migration.py`
  deduplica.
- **D-F/PPT-18:** la cuenta analítica del centro **no** se vuelve `required`;
  se exige en la aprobación de presupuestos nuevos y se inventaría en el
  upgrade.
- **D09:** segregación “el creador no aprueba” implementada como parámetro
  configurable (`step_management_costs.enforce_segregation`, por defecto
  **off**); Codex/dueño deciden si pasa a bloqueo duro.
- **SEC-04:** las 12 `ir.rule` de compañía pasan de reglas de grupo a
  **globales** (se intersectan).
- **SEC-07:** nuevos perfiles `group_management_readonly` y
  `group_management_approver`; cadena `readonly ⊂ user ⊂ approver ⊂ manager`;
  se conservan los XML IDs `group_management_user` / `group_management_manager`.

---

## 2. Worktree y rama

- **Worktree:** `C:\Users\tito4\Documents\Odoo-gestion-costos`
- **Rama:** `codex/gestion-costos` (creada con
  `git worktree add -b codex/gestion-costos … origin/codex/web-tracker-redesign`)
- **Commit base:** `9aa55c1` (`origin/codex/web-tracker-redesign`, “muchos cambios”)
- El checkout principal `C:\Users\tito4\Documents\Odoo` (rama
  `fix/previred-correcciones-2`) **no se tocó**.
- **Sin commits.** Sin `push`/`fetch`/`merge`/`rebase`/`reset`.

---

## 3. Archivos creados / modificados

### Modificados (`step_management_costs/`)

| Archivo | Cambio |
|---|---|
| `__manifest__.py` | versión `18.0.2.0.0`; añade `wizard/budget_reopen_views.xml` a `data` |
| `__init__.py` | `from . import wizard` |
| `models/budget_group.py` | `_check_company_auto` |
| `models/cost_center.py` | `_check_company_auto`; `check_company=True` + `help` en `analytic_account_id` |
| `models/exchange_rate.py` | `_check_company_auto`; `action_load_odoo_rate` exige `group_management_manager`; import `UserError` |
| `models/budget_template.py` | `_check_company_auto` (plantilla y línea); `budget.template.line.company_id` (related stored) + `check_company` en `group_id` |
| `models/planning.py` | `_check_company_auto` (plan y línea); `check_company` en `budget_id`/`center_id`; `plan.line.company_id` (related stored); `_check_company_consistency` (M2m `center_ids`) |
| `models/historical_cost.py` | `_check_company_auto`; `check_company` en `center_id`/`group_id`; campos `origin`, `source_reference`, `source_file`/`source_filename`, `locked`; `write`/`unlink` bloquean registros `locked` a no administradores; nota Var % desde totales |
| `models/operational_budget.py` | núcleo del corte: ver §5 |
| `security/management_security.xml` | 2 grupos nuevos; cadena de implicaciones; 12 `ir.rule` → globales (`groups` vaciados con `(5,0,0)`) |
| `security/ir.model.access.csv` | 12 filas `_readonly` (solo lectura) + 2 filas del asistente de reapertura |
| `views/operational_budget_views.xml` | botones Aprobar/Cerrar/Reabrir/Nueva revisión (grupo aprobador); `action_cancel` solo desde borrador/calculado; campos de revisión/aprobación/hash; aviso de distribución incompleta; columnas `monthly_quantity`/`distribution_complete`; `revision`/`approved_by_id` en lista |
| `views/historical_cost_views.xml` | `origin`, `locked`, `source_*` en formulario y lista |
| `views/menu_views.xml` | menú raíz visible para `group_management_readonly` |

### Nuevos

```
docs/gestion_costos/MATRIZ_REQUISITOS.md
docs/gestion_costos/ADR_001_ARQUITECTURA_Y_CONTABILIDAD.md
docs/gestion_costos/DECISION_LOG.md
docs/gestion_costos/DATA_MODEL.md
docs/gestion_costos/HANDOFF_FASE1_CORTE1.md            (este archivo)
step_management_costs/wizard/__init__.py
step_management_costs/wizard/budget_reopen.py          (step.management.budget.reopen.wizard)
step_management_costs/wizard/budget_reopen_views.xml
step_management_costs/upgrades/18.0.2.0.0/pre-migration.py
step_management_costs/upgrades/18.0.2.0.0/post-migration.py
step_management_costs/tests/__init__.py
step_management_costs/tests/test_management_costs.py
```

`git diff --stat` (config del repo): 14 archivos modificados, **631 (+) / 45 (−)**.

---

## 4. Matriz requisito → cambio → prueba

| Requisito (MATRIZ) | Cambio | Prueba |
|---|---|---|
| SEC-01/02/03 `_check_company_auto` + `check_company` + `company_id` faltantes | `_check_company_auto` en 10 modelos; `check_company=True` en `analytic_account_id`, `template_id`, `group_id`(×2), `center_id`(×3), `budget_id`; `company_id` related-stored en `budget.center`, `budget.template.line`, `plan.line` | `TestMultiCompany.test_check_company_rejects_cross_company_template`, `…_center`, `test_related_company_id_populated` |
| SEC-04 reglas globales | `management_security.xml`: `groups` vaciados, dominio `['|',company_id in company_ids, company_id = False]` | `TestMultiCompany.test_global_rule_isolates_centers` |
| SEC-05 constraint compañía indirecta (M2m) | `plan._check_company_consistency` | (revisión de código; sin caso dedicado — pendiente ampliar) |
| SEC-07 roles nuevos | `group_management_readonly`, `group_management_approver`, cadena de implicaciones | usados en todas las pruebas vía `new_test_user` |
| SEC-08/09 gate rol+transición por RPC | `_ensure_approver` / `_ensure_transition` en `action_approve/close/reopen/new_revision`; `action_load_odoo_rate` exige manager | `TestRolesAndTransitions.*` (operador no aprueba ni por llamada directa; estado equivocado; readonly no escribe) |
| SEC-10 auditoría de aprobación | `approved_by_id`, `approved_at`, `revision`, `reopen_reason`, `approval_snapshot`, `approval_hash` | `TestImmutabilityAndSnapshot.test_snapshot_and_hash` |
| PPT-03/16/C11 integridad distribución | `distribution_complete`/`monthly_quantity` compute; `_check_monthly_distribution`; `_check_parent_distribution`; `action_approve` bloquea incompletas | `TestBudgetIntegrity.test_incomplete_distribution_blocks_approval`, `test_monthly_distribution_constraint`, `test_complete_distribution_allows_approval` |
| PPT-17 unicidad `budget.center` | `_sql_constraints budget_center_uniq`; se retira `_check_unique_center`; `pre-migration.py` deduplica | `TestBudgetIntegrity.test_budget_center_sql_unique` |
| PPT-14 inmutabilidad | `write()`/`unlink()` override en `operational.budget`, `budget.line`, `budget.month`; estado `superseded` | `TestImmutabilityAndSnapshot.test_header_frozen…`, `test_detail_frozen…`, `test_unlink_blocked…` |
| PPT-14 reapertura trazable | `action_reopen` + asistente `budget.reopen.wizard` + `_do_reopen(reason)` | `test_reopen_requires_reason` |
| PPT-14 reemplazo, no sobrescritura | `action_new_revision`; supersede del origen al aprobar la revisión | `test_new_revision_supersedes_on_approval` |
| PPT-18/D-F cuenta analítica | `_centers_without_analytic` en `action_approve`; `post-migration.py` inventaría | `TestRolesAndTransitions.test_approve_requires_analytic_account` |
| PPT-08 idempotencia de recálculo | (sin cambio de lógica; se verifica que no duplica ni reasigna folio) | `TestBudgetIntegrity.test_generate_lines_idempotent` |
| “cero hectáreas” | constraint pre-existente `budget.center._check_hectares` | `TestBudgetIntegrity.test_zero_hectares_rejected` |
| GES-04 histórico externo | `origin`, `locked`, `source_*` + bloqueo | `TestHistoricalCost.test_locked_blocks_non_manager` |
| C5 Var % desde totales | ya se calcula así; se documenta en `help` y comentario | `TestHistoricalCost.test_variance_percent_from_totals` |
| UPG-01/02/03 | manifiesto `18.0.2.0.0` + `upgrades/18.0.2.0.0/pre|post-migration.py` idempotentes, sin IDs numéricos, sin `commit()` | **pendiente**: prueba de upgrade con runtime (ver §6) |

---

## 5. Detalle de `models/operational_budget.py`

- Constantes: `APPROVER_GROUP`, `MANAGER_GROUP`, `PROTECTED_HEADER_FIELDS`,
  `FROZEN_STATES = ('approved','closed','superseded')`.
- `operational.budget`: `_check_company_auto`; `check_company` en `template_id`;
  `state += ('superseded','Reemplazado')`; campos `approved_by_id`,
  `approved_at`, `revision`, `revision_of_id`, `superseded_by_id`,
  `reopen_reason`, `approval_snapshot`, `approval_hash`, `incomplete_line_count`.
- Helpers de guarda: `_ensure_approver`, `_ensure_transition`,
  `_incomplete_distribution_lines`, `_centers_without_analytic`,
  `_check_segregation`, `_build_approval_snapshot`.
- `action_approve` reescrito: rol + transición `calculated→approved` +
  distribución completa + cuenta analítica + segregación; congela snapshot +
  hash; supersede del `revision_of_id` si estaba aprobado.
- `action_close`/`action_cancel`/`action_set_draft`: transición explícita
  (`close` y aprobación exigen aprobador; `cancel` solo desde borrador/calculado).
- `action_reopen` (abre asistente) / `_do_reopen(reason)` / `action_new_revision`.
- `write()`: bloquea `PROTECTED_HEADER_FIELDS` (incluye `allocation_ids`,
  `line_ids`) cuando el estado está congelado; contextos `mc_supersede` /
  `mc_reopen` como escape controlado.
- `unlink()`: sólo administrador borra fuera de borrador; nunca un
  aprobado/cerrado/reemplazado.
- `budget.center`: `_check_company_auto`, `company_id` related-stored,
  `check_company` en `center_id`, `_sql_constraints budget_center_uniq`
  (se elimina `_check_unique_center`).
- `budget.line`: `_check_company_auto`; `check_company` en
  `center_id`/`group_id`/`template_line_id`; `monthly_quantity` +
  `distribution_complete` (compute stored); `_check_monthly_distribution`;
  `write()`/`unlink()` bloquean detalle congelado.
- `budget.month`: `_check_parent_distribution`, `_check_unique_month`;
  `write()`/`unlink()` bloquean cuando el presupuesto está congelado.

---

## 6. Comandos ejecutados y resultados reales

Entorno local: **sin Odoo ni PostgreSQL** (`which odoo` / `which psql` → nada).
Solo verificación estática con Python 3.12.10.

| Comando | Resultado |
|---|---|
| `python -m py_compile $(find step_management_costs -name '*.py')` | **exit 0** — sin errores de sintaxis (15 archivos) |
| `python -c "xml.dom.minidom.parse(...)"` sobre los 13 XML | **OK** — todos bien formados |
| lectura CSV `ir.model.access.csv` | 38 filas, todas con 8 columnas |
| `git diff --check HEAD` | **exit 0** — sin marcadores de conflicto ni espacios en blanco erróneos |
| `git worktree list` | worktree limpio en `Odoo-gestion-costos`, rama `codex/gestion-costos` |

Búsquedas de impacto realizadas: `grep` de `api.constrains`, de imports de
`UserError`/`ValidationError`/`float_compare`, de referencias a grupos y modelos
en el CSV y en las vistas (todas resuelven dentro del módulo).

---

## 7. Pruebas NO ejecutadas y por qué

**La suite Odoo `step_management_costs/tests/` NO se ejecutó**: no hay runtime
Odoo/PostgreSQL en este equipo. Los tests están escritos (`TransactionCase`,
21 casos) pero su verde es **hipótesis**, no evidencia.

Comandos exactos pendientes (en base **desechable**, nunca compartida):

```bash
# instalación limpia + pruebas del addon
odoo -c <conf> -d mc_clean_$(date +%s) -i step_management_costs \
     --test-enable --test-tags step_management_costs --stop-after-init --log-level=test

# upgrade desde 18.0.1.1.0 sobre un clon, con datos previos
odoo -c <conf> -d <clon_de_una_base_1_1_0> -u step_management_costs \
     --test-enable --test-tags step_management_costs --stop-after-init --log-level=test

# revisar el log por ERROR / CRITICAL / ACL / registry / vistas
grep -E "ERROR|CRITICAL|WARNING.*(rule|acl|view|registry)" <logfile>
```

Riesgos concretos que solo el runtime confirma:

1. Timing de `check_company` sobre `budget.center.company_id` (related stored)
   dentro de un `create` anidado con `allocation_ids`.
2. Que `upgrades/` (y no sólo `migrations/`) sea escaneado por esta build de
   Odoo 18. Si no lo fuera, renombrar la carpeta a
   `migrations/18.0.2.0.0/` (mismo contenido, sin cambios de código).
3. Recomputo de `distribution_complete` (stored) antes de que `action_approve`
   lo lea, en un flujo de una sola transacción.
4. Interacción del `write()` de inmutabilidad con recomputos de campos
   `store=True` de la cabecera (se cree cubierto porque el recompute usa
   `_write`, no `write`, pero hay que verlo).
5. `new_test_user(groups=...)` y la resolución de grupos implicados.

---

## 8. Migración y compatibilidad con datos existentes

- Se conservan todos los `_name`, tablas, secuencias
  (`seq_operational_budget`, `seq_management_plan`) y XML IDs. `state` sólo
  gana el valor `superseded`.
- `upgrades/18.0.2.0.0/pre-migration.py`: deduplica
  `step_management_budget_center` por `(budget_id, center_id)` **sólo si las
  filas son idénticas** (`hectares`, `notes`); si difieren, **aborta** con
  detalle para revisión manual. Idempotente.
- `upgrades/18.0.2.0.0/post-migration.py`: puebla los `company_id` nuevos
  (`budget.center`, `budget.template.line`) desde el padre
  (`WHERE company_id IS DISTINCT FROM …`); `revision = 1` donde falte;
  marca los `historical.cost` previos como `origin = 'unreviewed'` (para
  excluirlos de comparativos hasta clasificarlos, **sin** tocar importes);
  registra en el log los centros sin cuenta analítica o con cuenta de otra
  empresa (no asigna nada). Idempotente, sin IDs numéricos, sin `commit()`.
- ACL: ninguna fila existente pierde permisos; sólo se añaden filas
  `_readonly` y del asistente.
- `ir.rule`: se reescriben las 12 existentes (mismo XML ID) a globales; el
  `(5,0,0)` sobre `groups` limpia la M2M anterior en el upgrade.

---

## 9. Riesgos, decisiones humanas pendientes y siguiente corte

**Decisiones humanas pendientes (bloquean Fase 2, no este corte):**

- D01/D15 (Contabilidad): validar el mapeo de los 25 campos del gasto real,
  tratamiento de NC/reversa/multimoneda, y si “ingresos” entra en la primera
  vertical.
- D02/D17 (TI/Contabilidad): ejecutar el preflight de `account_budget` por
  base (no hacible aquí) y decidir puente vs. adaptador propio.
- D03/D06/D13/D14: maestro de temporada y clave natural de versión; propiedad
  de fundo/cuartel/especie/variedad/actividad; normalización de meses a
  líneas.
- D09: ¿la segregación “creador ≠ aprobador” pasa de parámetro a bloqueo duro?
- D16/D18: matriz de estados de estimación/OP/OT-BPA; catálogo de informes.

**Riesgos técnicos:** los 5 de §7; además el `write()` de inmutabilidad es
por lista de campos protegidos, no lista blanca — si una fase futura agrega un
campo de cabecera hay que añadirlo a `PROTECTED_HEADER_FIELDS`.

**Siguiente corte recomendado (Fase 1, corte 2 — no iniciar aún):**

1. Modelo `step.management.budget.revision` + `…snapshot.line` de primera
   clase (promoción del blob JSON) con prueba de reproducibilidad.
2. Maestro `step.management.season` con rango configurable (D03) y clave
   natural del presupuesto (D06).
3. Constraint SQL de mes único por línea y normalización de las 12 columnas de
   mes de la plantilla a líneas de período (D14), con prueba de igualdad de
   totales antes/después.
4. `budget_adapter.py` (contrato) + preflight de `account_budget`.

**Después** de eso, Fase 2: servicio `analytic_actuals` y la vertical de
desviación.

---

## 10. `git status --short` y `git diff --stat`

```
 M step_management_costs/__init__.py
 M step_management_costs/__manifest__.py
 M step_management_costs/models/budget_group.py
 M step_management_costs/models/budget_template.py
 M step_management_costs/models/cost_center.py
 M step_management_costs/models/exchange_rate.py
 M step_management_costs/models/historical_cost.py
 M step_management_costs/models/operational_budget.py
 M step_management_costs/models/planning.py
 M step_management_costs/security/ir.model.access.csv
 M step_management_costs/security/management_security.xml
 M step_management_costs/views/historical_cost_views.xml
 M step_management_costs/views/menu_views.xml
 M step_management_costs/views/operational_budget_views.xml
?? docs/gestion_costos/
?? step_management_costs/tests/
?? step_management_costs/upgrades/
?? step_management_costs/wizard/
```

```
 step_management_costs/__init__.py                  |   1 +
 step_management_costs/__manifest__.py              |   3 +-
 step_management_costs/models/budget_group.py       |   1 +
 step_management_costs/models/budget_template.py    |   6 +
 step_management_costs/models/cost_center.py        |   5 +
 step_management_costs/models/exchange_rate.py      |  10 +-
 step_management_costs/models/historical_cost.py    |  61 ++-
 step_management_costs/models/operational_budget.py | 425 ++++++++++++++++++++-
 step_management_costs/models/planning.py           |  30 +-
 step_management_costs/security/ir.model.access.csv |  14 +
 step_management_costs/security/management_security.xml | 103 ++++-
 step_management_costs/views/historical_cost_views.xml  |   4 +-
 step_management_costs/views/menu_views.xml         |   2 +-
 step_management_costs/views/operational_budget_views.xml | 11 +-
 14 files changed, 631 insertions(+), 45 deletions(-)
```

---

## 11. Confirmación explícita

**No hubo `git push`, ni despliegue, ni conexión con escritura a Desarrollo /
Demo / Demo-SyS, ni ejecución de `migrate_steps_qa_data.py` /
`migrate_currency_conversion.py` / `validate_template_budget.py`, ni `commit`,
`merge`, `rebase`, `reset` o modificación de ramas remotas.** Todo el trabajo
está en el worktree local `C:\Users\tito4\Documents\Odoo-gestion-costos` (rama
`codex/gestion-costos`), sin commitear.
