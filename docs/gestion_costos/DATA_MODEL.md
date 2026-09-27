# Modelo de datos — Steps Gestión y Costos

**Fase:** 0. Refleja el código del commit base del worktree
`codex/gestion-costos` (`step_management_costs 18.0.1.1.0`) y la **propuesta de
extensión** para el primer corte de Fase 1 (`18.0.2.0.0`).

Convención de la columna “V1”: **conserva** (sin cambio de estructura),
**agrega** (campo/constraint nuevo), **deprecado** (se mantiene pero se
desaconseja / pasa a `readonly`/`compute` en fase futura — **nada se borra**
en `18.0.2.0.0`).

---

## 1. Modelos actuales

Tabla = `_name` con puntos → guiones bajos (Odoo estándar). Ninguno declara
`_table` explícito.

### 1.1 `step.management.cost.center` — tabla `step_management_cost_center`
Centro de costo operativo. `_inherit`: `mail.thread`, `mail.activity.mixin`.
`_order = "code, name"`.

| Campo | Tipo | Notas | V1 |
|---|---|---|---|
| `name` | Char req, tracking | | conserva |
| `code` | Char req, index, tracking | | conserva |
| `company_id` | M2o `res.company` req, default `env.company`, index, tracking | | agrega `_check_company_auto` a nivel modelo |
| `cost_type` | Selection(`crop/operational/machinery/administrative/other`) req | default `crop` | conserva |
| `hectares` | Float(16,4), tracking | `@api.constrains` ≥ 0 | conserva |
| `farm`, `plot`, `species`, `variety` | Char, tracking | **texto libre** (D13) | deprecado (se mantienen; FK en puente `_agriculture`, Fase 2) |
| `analytic_account_id` | M2o `account.analytic.account`, domain `company_id in [False, company_id]` | opcional | **agrega** `check_company=True`; gate en aprobación (ADR D-F) — **no** `required` |
| `responsible_id` | M2o `res.users` | | conserva |
| `notes` | Html | | conserva |
| `active` | Boolean default True | | conserva |

**Constraints:** `_sql_constraints`
`code_company_unique = unique(code, company_id)`; `_check_hectares` (≥ 0).
**XML IDs vista:** `view_cost_center_list/_form/_search`, `action_cost_center`.

### 1.2 `step.management.budget.group` — tabla `step_management_budget_group`
Grupo de presupuesto. Sin `mail.thread`. `_order = "code, name"`.

| Campo | Tipo | V1 |
|---|---|---|
| `name` | Char req | conserva |
| `code` | Char req, index | conserva |
| `company_id` | M2o `res.company` req, index | agrega `_check_company_auto` |
| `parent_id` | M2o self, `ondelete=restrict` | conserva |
| `account_id` | M2o `account.account` | conserva (sin `check_company` — `account.account` company puede ser company_ids; se evalúa Fase 2) |
| `color` | Integer | conserva |
| `active` | Boolean | conserva |

**Constraints:** `code_company_unique = unique(code, company_id)`.
**XML IDs:** `view_budget_group_list/_form`, `action_budget_group`.

### 1.3 `step.management.exchange.rate` — tabla `step_management_exchange_rate`
Tipo de cambio **estimado** mensual. `_order = "year desc, month desc,
currency_id"`. `_rec_name = "name"`.

| Campo | Tipo | Notas | V1 |
|---|---|---|---|
| `name` | Char compute stored (`_compute_name`) | “USD · Enero 2026” | conserva |
| `company_id` | M2o `res.company` req, index | | agrega `_check_company_auto` |
| `company_currency_id` | M2o related `company_id.currency_id` stored | | conserva |
| `currency_id` | M2o `res.currency` req, index, domain `active` | | conserva |
| `year` | Integer req, index | `_check_values` 1900..+20 | conserva |
| `month` | Selection `01`..`12` req, index | | conserva |
| `rate_date` | Date compute stored (`_compute_date`) | 1er día del mes | conserva |
| `company_value_per_unit` | Float(16,6) req | > 0; = 1 si moneda = moneda empresa | conserva |
| `inverse_value` | Float(16,10) compute | | conserva |
| `source` | Selection(`manual/odoo`) req | | conserva |
| `notes` | Char | | conserva |
| `active` | Boolean | | conserva |

**Constraints:** `currency_period_company_unique =
unique(currency_id, year, month, company_id)`; `_check_values`.
**Métodos públicos:** `action_load_odoo_rate`, `_currency_value` (`@api.model`),
`get_conversion` (`@api.model`). — **V1:** `get_conversion` /
`_currency_value` no mutan; se dejan igual. La escritura de tasas ya es
`manager`-only en ACL; se añade que `action_load_odoo_rate` exija
`group_management_manager`.
**XML IDs:** `view_exchange_rate_list/_form/_search/_graph`,
`action_exchange_rate`.

### 1.4 `step.management.budget.template` — tabla `step_management_budget_template`
Plantilla por hectárea. `_inherit`: mail. `_order = "active desc, name"`.

Campos clave: `name`, `version` (Char default `1.0`), `company_id` (M2o req),
`currency_id`, `conversion_currency_id`, `conversion_date`,
`conversion_rate_type` (`estimated/actual`), `base_hectares` (Float req, > 0),
`species`, `expected_yield_kg_ha`, `notes`, `line_ids` (O2m),
`total_per_ha` (Monetary compute stored), `line_count` (compute stored),
`state` (`draft/active/archived`), `active`. Conversión: `conversion_available`,
`conversion_factor`, `conversion_target_value`, `total_per_ha_converted`
(todos compute, no stored).

**Constraints:** `_check_base_hectares` (> 0).
**Métodos:** `action_activate`, `action_set_draft`, `action_archive_template`.
**V1:** agrega `_check_company_auto`. Sin más cambios estructurales
(normalización de meses → Fase 2, D14).
**XML IDs:** `view_budget_template_list/_kanban/_form/_search`,
`action_budget_template`.

### 1.5 `step.management.budget.template.line` — tabla `step_management_budget_template_line`
`_order = "sequence, id"`. **Sin `company_id`.**

| Campo | Tipo | V1 |
|---|---|---|
| `template_id` | M2o req, `ondelete=cascade`, index | conserva |
| `sequence` | Integer default 10 | conserva |
| `category` | Selection(`labor/input/machinery/service/other`) req | conserva |
| `group_id` | M2o `step.management.budget.group` req, domain `company_id = parent.company_id` | **agrega** `check_company=True` (requiere `company_id` en la línea) |
| `indicator` | Char req | conserva |
| `activity` | Char | conserva |
| `product_id` | M2o `product.product` | conserva |
| `uom_id` | M2o `uom.uom` | conserva |
| `base_quantity` | Float(16,4) | conserva |
| `unit_price` | Monetary | conserva |
| `currency_id` | M2o related `template_id.currency_id` stored | conserva |
| `conversion_*` | related | conserva |
| `may`..`apr` | 12 × Float(16,4) | **deprecado** (canónico = líneas de mes, Fase 2) — se conserva |
| `quantity_per_ha`, `cost_per_ha` | compute stored | conserva |
| `unit_price_converted`, `cost_per_ha_converted` | compute | conserva |
| `notes` | Char | conserva |
| **`company_id`** | — | **AGREGA:** `related="template_id.company_id", store=True, index=True` + `_check_company_auto` |

**Constraints actuales:** `_check_non_negative`.
`_compute_amounts` (`:167-174`): **V1 lo ajusta** para no “rellenar” con
`base_quantity` cuando la línea forma parte de una distribución (ver D-I); la
plantilla en sí conserva el comportamiento, el control de 100% vive en
`budget.line`.

### 1.6 `step.management.operational.budget` — tabla `step_management_operational_budget`
Presupuesto operacional. `_inherit`: mail. `_order = "date desc, id desc"`.
Secuencia `step.management.operational.budget` (`PPO/%(year)s/…`, padding 5,
`company_id = False`).

| Campo | Tipo | Notas | V1 |
|---|---|---|---|
| `name` | Char req, `copy=False`, readonly, index | folio de secuencia | conserva |
| `description` | Char req, tracking | | conserva |
| `company_id` | M2o req, index, tracking | | agrega `_check_company_auto` |
| `currency_id` | M2o `res.currency` req | | conserva |
| `conversion_currency_id`, `conversion_rate_type` | | | conserva |
| `conversion_available/_factor/_target_value` | compute | | conserva |
| `date` | Date req, default today, tracking | | conserva |
| `season` | Char req, tracking | **texto libre** (D03/C12) | deprecado como texto (maestro Fase 2) |
| `template_id` | M2o `step.management.budget.template` req, domain company+active, tracking | | **agrega** `check_company=True` |
| `responsible_id` | M2o `res.users` req, default `env.user`, tracking | | conserva |
| `allocation_ids` | O2m `step.management.budget.center` (`budget_id`), `copy=True` | | conserva |
| `line_ids` | O2m `step.management.budget.line` (`budget_id`), `copy=False` | | conserva |
| `total_hectares`, `total_amount`, `cost_per_ha`, `line_count` | compute stored | | conserva |
| `total_amount_converted`, `cost_per_ha_converted` | compute | | conserva |
| `state` | Selection(`draft/calculated/approved/closed/cancelled`) req, tracking, index | | **agrega valor** `superseded` |
| `notes` | Html | | conserva |
| `active` | Boolean | | conserva |
| **`approved_by_id`** | M2o `res.users` readonly, `copy=False` | | **AGREGA** |
| **`approved_at`** | Datetime readonly, `copy=False` | | **AGREGA** |
| **`revision`** | Integer default 1, `copy=False`, tracking | | **AGREGA** |
| **`revision_of_id`** | M2o self, `copy=False`, `ondelete=set null` | origen de la revisión | **AGREGA** |
| **`superseded_by_id`** | M2o self, `copy=False`, `ondelete=set null` | revisión que lo reemplaza | **AGREGA** |
| **`reopen_reason`** | Text, `copy=False` | motivo de la revisión correctiva | **AGREGA** |
| **`approval_snapshot`** | Text, `copy=False`, readonly | JSON congelado al aprobar | **AGREGA** |
| **`approval_hash`** | Char(64), `copy=False`, readonly | sha256 del snapshot | **AGREGA** |

**Constraints actuales:** ninguno `_sql`. `create` asigna folio de secuencia.
`_onchange_template_id` copia moneda/conversión.
**Métodos:** `action_generate_lines` (valida estado, plantilla, ≥1 centro,
hectáreas > 0; `unlink()` + recrea; → `calculated`), `action_approve`
(hoy sólo `write state`), `action_close`, `action_cancel`, `action_set_draft`.
**V1 — cambios de comportamiento:**
- `action_approve`: gate de rol (`group_management_approver`), transición
  `calculated → approved`, D-I (distribución completa), D-F (cuenta analítica
  por centro), D09 (segregación configurable); fija auditoría + snapshot +
  hash.
- `action_close`/`action_cancel`: gate de rol aprobador + transición.
- `write()`: bloquea campos protegidos si `state in
  ('approved','closed','superseded')`.
- `unlink()`: prohíbe borrar si `state != 'draft'` (salvo `manager`); en
  cualquier caso prohíbe borrar `approved/closed/superseded`.
- **nuevos métodos:** `action_reopen` (wizard con `reason`, crea una copia),
  `action_new_revision`. El aprobado nunca vuelve a borrador.
**XML IDs:** `view_operational_budget_list/_kanban/_form/_search`,
`action_operational_budget`, `action_operational_budget_create`,
`view_budget_line_pivot/_graph/_list/_search`, `action_budget_analysis`,
`view_budget_month_pivot/_graph`, `action_budget_month_analysis`.

### 1.7 `step.management.budget.center` — tabla `step_management_budget_center`
Centro incluido en un presupuesto. `_order = "center_id"`. **Sin `company_id`.**

| Campo | Tipo | V1 |
|---|---|---|
| `budget_id` | M2o req, `ondelete=cascade`, index | conserva |
| `center_id` | M2o `step.management.cost.center` req, domain `company_id = parent.company_id` | **agrega** `check_company=True` |
| `registered_hectares` | Float related `center_id.hectares` readonly | conserva |
| `hectares` | Float(16,4) req | `_check_hectares` > 0 | conserva |
| `notes` | Char | conserva |
| **`company_id`** | — | **AGREGA:** `related="budget_id.company_id", store=True, index=True` + `_check_company_auto` |

**Constraints actuales:** `_check_hectares` (> 0); `_check_unique_center`
(**`search_count`, vulnerable a carrera**).
**V1:** `_check_unique_center` → se **elimina** y se sustituye por
`_sql_constraints = [('budget_center_uniq', 'unique(budget_id, center_id)',
'No puede seleccionar dos veces el mismo centro de costo.')]`.
`pre-migration.py` deduplica antes de crear la constraint.

### 1.8 `step.management.budget.line` — tabla `step_management_budget_line`
Línea extrapolada. `_order = "center_id, group_id, category, id"`.

Campos: `budget_id` (M2o req cascade index), `company_id` (M2o **related
`budget_id.company_id` stored index** — ya existe), `currency_id`/
`conversion_*` related, `center_id` (M2o req index), `template_line_id` (M2o
`ondelete=restrict`), `category` (Selection req index), `group_id` (M2o req
index), `indicator` (Char req), `activity`, `product_id`, `uom_id`,
`hectares` (Float req), `quantity_per_ha`, `quantity` (Float), `unit_price`
(Monetary), `amount` (Monetary compute stored `= quantity*unit_price`),
`unit_price_converted`/`amount_converted` (compute), `month_ids` (O2m
`step.management.budget.month`).

**Constraints actuales:** ninguno.
**V1 — agrega:**
- `_check_company_auto = True`; `check_company=True` en `center_id`,
  `group_id`, `template_line_id` (todos los comodelos tienen `company_id`;
  `budget.template.line` lo gana en esta versión). Esto cubre la coherencia de
  compañía indirecta sin `@api.constrains` adicional.
- `monthly_quantity` (Float compute stored) = Σ `month.quantity`.
- `distribution_complete` (Boolean compute stored): `True` sólo si hay
  `month_ids` **y** `float_compare(Σ month.quantity, quantity, rounding) == 0`
  (rounding = `uom_id.rounding` → `currency_id.rounding` → `0.01`). Sin meses
  ⇒ `False`.
- `@api.constrains('month_ids', 'quantity', 'uom_id')`
  `_check_monthly_distribution`: con `month_ids`, la suma debe cuadrar con
  `quantity` dentro de tolerancia; si no, `ValidationError`.
- `write()`: bloquea `quantity/unit_price/hectares/quantity_per_ha/center_id/
  group_id/category/month_ids` si `budget_id.state` está congelado.
- `unlink()`: prohibido si `budget_id.state in
  ('approved','closed','superseded')`.
- `quantity` **no** se deriva aún de los meses en V1 (se hace en Fase 2 con la
  normalización de períodos, D14); la no-divergencia la garantiza la
  restricción anterior. Ver `ADR_001` D-I.

### 1.9 `step.management.budget.month` — tabla `step_management_budget_month`
Distribución mensual de una línea. `_order = "month, id"`.

Campos: `budget_line_id` (M2o req cascade index), `budget_id`/`center_id`/
`group_id`/`currency_id` related stored, `company_id` related (**no stored**),
`conversion_*` related, `conversion_date` (Date compute
`_compute_conversion_date` — interpreta la temporada `2026/2027`),
`month` (Selection `may`..`apr` req index), `quantity` (Float), `unit_price`
(Monetary), `amount` (Monetary compute stored), `*_converted` (compute).

**Constraints actuales:** ninguno.
**V1 — agrega:**
- `@api.constrains('budget_line_id', 'month')` `_check_unique_month`:
  un mes no puede repetirse dentro de la misma línea (constraint Python; SQL
  en Fase 2 tras normalizar períodos).
- `@api.constrains('quantity', 'month')` `_check_parent_distribution`:
  revalida `budget_line_id._check_monthly_distribution()` cuando se edita un
  mes directamente (el `@api.constrains` del One2many padre no se dispara al
  escribir el hijo).
- `write()`/`unlink()`: bloqueados si el presupuesto está congelado
  (aprobado/cerrado/reemplazado).
- `company_id` related se deja **sin `store` y sin `_check_company_auto`**
  (budget.month no tiene `Many2one` con `check_company`; el aislamiento llega
  por la `ir.rule` vía `budget_line_id.company_id`).

### 1.10 `step.management.plan` / `.plan.line` — `step_management_plan(_line)`
Planificación manual de tareas. `plan`: `_inherit` mail;
secuencia `step.management.plan` (`PLAN/%(year)s/…`). Campos:
`name` (folio), `description` req, `company_id` (M2o req index tracking),
`responsible_id`, `budget_id` (M2o `operational.budget`), `center_ids`
(**M2m** `cost.center`), `date_start`/`date_end` (Date req), `week_reference`,
`line_ids` (O2m), `progress` (Float compute stored), `state`
(`draft/planned/in_progress/done/cancelled`), `notes`.
`plan.line`: `plan_id` (M2o req cascade index), `sequence`, `date` (Date req),
`center_id` (M2o), `indicator` (Char req), `responsible_id`, `quantity`,
`uom_id`, `state`, `notes`.

**Constraints actuales:** `_check_dates` (fin ≥ inicio).
**V1 — agrega:**
- `_check_company_auto = True` en `plan`.
- `check_company=True` en `budget_id`.
- `@api.constrains('center_ids', 'budget_id', 'company_id')`
  `_check_company_consistency`: todos los `center_ids` y el `budget_id` deben
  ser de `company_id` (Odoo no valida M2m con `check_company`).
- `plan.line`: `company_id` related stored desde `plan_id` + `check_company`
  en `center_id` (relación indirecta) — **o** constraint Python
  `line.center_id.company_id == plan_id.company_id`. Se elige la constraint
  Python para no añadir stored en la línea en este corte.

### 1.11 `step.management.historical.cost` — `step_management_historical_cost`
Costo histórico. `_inherit` mail. `_order = "date desc, id desc"`.
Campos: `name` req, `company_id` (M2o req index), `date` (Date req index),
`center_id` (M2o req index), `group_id` (M2o index), `indicator`, `quantity`,
`currency_id`, `conversion_currency_id`, `conversion_rate_type`
(`actual/estimated`), `actual_amount`, `budget_amount`, `variance`
(Monetary compute stored `= actual - budget`), `variance_percent`
(Float compute stored `= variance*100/budget`), `*_converted` (compute),
`notes`.

**Constraints actuales:** ninguno.
**V1 — agrega:**
- `_check_company_auto = True`; `check_company=True` en `center_id`,
  `group_id`.
- `origin` (Selection `external/adjustment/unreviewed`, default `external`,
  req). El `post-migration.py` marca los registros previos como `unreviewed`.
- `source_reference` (Char) y `source_document` (`ir.attachment` vía
  `Binary`/`Many2many`? — se usa **`Char` + campo `Binary` `source_file` con
  `source_filename`** para no crear relación nueva en este corte).
- `locked` (Boolean, default False) + `write()`/`unlink()` bloqueado cuando
  `locked` y el usuario no es `manager`.
- `variance_percent`: se mantiene la fórmula (ya se calcula desde los
  totales, **no** suma de %). Se añade nota en el `help`.
- Los comparativos (Fase 2) **excluyen** `origin = 'unreviewed'`.

---

## 2. Grupos, reglas y ACL actuales

**`security/management_security.xml`:**
- `module_category_management_costs` (`ir.module.category`).
- `group_management_user` → implica `base.group_user`.
- `group_management_manager` → implica `group_management_user`.
- `base.group_system` → implica `group_management_manager`.
- 12 `ir.rule` `rule_*_company`, **atadas a `group_management_user`**, dominio
  `[('company_id','in',company_ids)]` (o vía relación para líneas/meses/
  asignaciones/tareas/plantilla-línea).

**`security/ir.model.access.csv`:** 25 líneas, pares `_user` / `_manager` por
modelo. `user`: `read=1`, `write/create` variables, `unlink=0` salvo
`budget.center`, `budget.month`, `plan.line` (`unlink=1`). `exchange.rate` y
`budget.group`: `user` sólo `read`. `manager`: CRUD completo.

### V1 — propuesta

**Grupos (se conservan los XML IDs actuales; se agregan 2):**

| XML ID | Nombre | Implica | ACL (resumen) |
|---|---|---|---|
| `group_management_readonly` *(nuevo)* | Consulta Gestión y Costos | `base.group_user` | `read` en todos los modelos del addon |
| `group_management_user` *(conserva)* | Usuario de gestión y costos | `group_management_readonly` | como hoy: `read/write/create`, sin `unlink` de detalle; **sin** aprobar/cerrar/reabrir/cambiar tasas |
| `group_management_approver` *(nuevo)* | Aprobador / Control | `group_management_user` | como `user` + `write` sobre presupuestos aprobados (para cerrar/reabrir/nueva revisión); gate de métodos de aprobación |
| `group_management_manager` *(conserva)* | Administrador de gestión y costos | `group_management_approver` | CRUD completo + maestros + tasas + `unlink` |

*(“Planificador/Presupuestador” = `group_management_user` en V1; se separa en
Fase 2 cuando existan estimaciones/programas. Documentado en D09/D16.)*

**Reglas:** las 12 `rule_*_company` se **reescriben como globales** (sin
`<field name="groups">`), dominio
`['|', ('company_id','in',company_ids), ('company_id','=',False)]` para los
modelos con `company_id` directo, y la variante por relación
(`budget_line_id.company_id` / `plan_id.company_id` / `template_id.company_id`
/ `budget_id.company_id`) para el resto. Se **agrega** `rule_budget_month_*`
ya existente (vía `budget_line_id.company_id`) y se revisa que
`budget.template.line` quede cubierta por `company_id` propio nuevo.

**ACL nuevas:** filas `_readonly` (todas `1,0,0,0`) y `_approver` (igual a
`_user` salvo `write=1` en `operational_budget`, `budget_line`,
`budget_center`, `budget_month` incluso aprobados — el bloqueo fino lo hace
`write()`), más `historical_cost` `_approver`. Ninguna fila pierde permisos
respecto de hoy para `user`/`manager`.

---

## 3. Mapeo del gasto real (25 campos, `Anexo 1.6.10.1`) — D15

Propuesto. **Requiere validación de Contabilidad.** No se implementa en V1;
es el contrato para el servicio `analytic_actuals` de Fase 2.

| # | Campo anexo | Fuente propuesta | Signo / reversa / NC / moneda |
|---|---|---|---|
| 1 | Tipo Registro | Constante `Steps` para lo contable; `Externo` para `historical.cost` | — |
| 2 | Comprobante Contable | `account.move.name` | — |
| 3 | Tipo Doc | `account.move.move_type` / `l10n_latam_document_type_id` | — |
| 4 | Num Doc | `account.move.ref` / `payment_reference` / `name` | — |
| 5 | Glosa contable | `account.move.line.name` | — |
| 6 | Fecha | `account.move.date` | — |
| 7 | OP | enriquecimiento desde origen (OP semanal, Fase 6) — vacío en V1/V2 | — |
| 8 | OT | enriquecimiento desde origen (OT, módulos de operaciones) — vacío en V1/V2 | — |
| 9 | Temporada | plan analítico “temporada” de `analytic_distribution`, o `step.temporada` por rango de fecha (D03) | — |
| 10 | Año | `account.move.line.date`.year | — |
| 11 | Mes | `account.move.line.date`.month | — |
| 12 | Fundo | `cost.center.farm` del centro imputado (texto hoy; FK en puente) | — |
| 13 | Especie | `cost.center.species` | — |
| 14 | Variedad | `cost.center.variety` | — |
| 15 | Tipo CCosto | `cost.center.cost_type` | — |
| 16 | Centro de costos | cuenta analítica → `cost.center` (relación por `analytic_account_id`) | — |
| 17 | Origen | del `product.category`/`product.template` (grupo→origen, D-B/PPT-21) o del diario | — |
| 18 | Grupo Presupuesto | `product.template.budget_group_id` → subcategoría → categoría (PPT-21, Fase 2) | — |
| 19 | Actividad | plan analítico “actividad”, o `account.analytic.line` | — |
| 20 | Producto-labor | `account.move.line.product_id` | — |
| 21 | UdM | `account.move.line.product_uom_id` | — |
| 22 | Cantidad | `account.move.line.quantity` (con signo del `move_type`) | reversa/NC invierten `quantity` |
| 23 | Valor Real $ | `account.analytic.line.amount` (o `aml.balance` imputado) en moneda de la compañía | reversa/NC ⇒ importe negativo; nunca se “corrige” a mano |
| 24 | TC Real | `res.currency._convert` a la fecha del asiento (moneda documento → compañía) | multimoneda: se guarda el factor aplicado |
| 25 | Valor Real US$ | `Valor Real $` convertido con `exchange.rate` (`rate_type` a definir: estimado vs real, D01) | — |

---

## 4. Qué se conserva / agrega / deprecia (resumen `18.0.2.0.0`)

**Se conserva sin cambio de estructura:** todos los `_name`, todas las
tablas, todas las secuencias (`seq_operational_budget`, `seq_management_plan`),
todos los XML IDs de vistas/acciones/menús, todos los `state` actuales, todos
los `_sql_constraints` actuales salvo el reemplazo controlado de la unicidad
de `budget.center` (se **añade** el `unique(budget_id, center_id)`; el
`_check_unique_center` Python se retira porque es el que sufre la carrera).

**Se agrega:**
- Campos: `budget.center.company_id`, `budget.template.line.company_id`
  (related stored); en `operational.budget`: `approved_by_id`, `approved_at`,
  `revision`, `revision_of_id`, `superseded_by_id`, `reopen_reason`,
  `approval_snapshot`, `approval_hash`; en `historical.cost`: `origin`,
  `source_reference`, `source_file`, `source_filename`, `locked`;
  en `budget.line`: `calculation_mode`, `direct_amount`, `monthly_quantity`,
  `monthly_amount` y `distribution_complete` (compute stored); en
  `budget.month`: `direct_amount`; en `operational.budget`:
  `incomplete_line_count` (compute).
- Valor de selección: `operational.budget.state += ('superseded',
  'Reemplazado')`.
- `_check_company_auto = True` en 10 modelos; `check_company=True` en ~9
  Many2one.
- `_sql_constraints`: `budget_center_uniq`.
- `@api.constrains`: distribución mensual, unicidad de mes por línea,
  coherencia de compañía indirecta (plan M2m, budget.line, plan.line).
- Grupos `group_management_readonly`, `group_management_approver`; filas ACL
  `_readonly`/`_approver`.
- `ir.rule` globales (reescritura de las 12 existentes).
- `upgrades/18.0.2.0.0/pre-migration.py` y `post-migration.py`.
- `tests/` (paquete nuevo).
- Wizard `step.management.budget.reopen` (transient, campo `reason`) que crea
  una nueva revisión y abre la copia editable.

**Se deprecia (se mantiene, no se borra):**
- `budget.template.line.may..apr` (12 columnas) y
  `operational.budget`/`budget.line` meses como estructura no normalizada →
  canónico serán líneas de período en Fase 2 (D14).
- `operational.budget.season` como `Char` → maestro de temporada Fase 2 (D03).
- `cost.center.farm/plot/species/variety` como `Char` → FK en puente
  `_agriculture` Fase 2 (D13).
- `step.management.historical.cost` como vía de gasto real corriente → sólo
  externo/ajuste (ADR D-C).

---

## 5. Fase 3A — maestros y curvas de estimación (`18.0.7.0.0`)

```text
estimation.unit                    estimation.curve
  company_id                        company_id
  code, name                        code, name
  kg_factor                         curve_type: week|caliber|class
                                    state: draft|validated
fruit.category                      total_percentage
  company_id                        validated_by_id / validated_at
  code, name                               |
       |                                   | 1:N
       +--< fruit.class                     v
              use_harvest/packing    estimation.curve.line
                                      dimension_key (única por curva)
caliber.group                        week_number, o
       |                              caliber_group_id, o
       +--< fruit.caliber             fruit_class_id
                                      percentage (0, 100]
```

Reglas del corte:

- toda relación dimensional respeta compañía mediante `_check_company_auto`
  y `check_company=True`;
- una curva puede guardarse incompleta en borrador, pero sólo se valida si
  tiene líneas y suma exactamente 100 % con precisión de cuatro decimales;
- semana válida: 1–53, presentada como `W01`…`W53`;
- `dimension_key` almacenada más constraint SQL evita duplicados incluso bajo
  concurrencia;
- una curva validada y sus líneas son inmutables hasta que un administrador la
  devuelve explícitamente a borrador;
- este corte no calcula cosecha: D05 se aplica en el documento de estimación
  del siguiente corte.

---

## 6. Corte V2 A — cosecha por centro/semana y recursos (`18.0.15.0.0`)

> **Nota de mantenimiento:** las Fases 3B–7 y los Cortes 1–2 (estimación por
> centro, programas fito/ferti, necesidades de stock, Orden de Producción)
> se implementaron y documentaron en sus propios handoffs
> (`HANDOFF_FASE*.md`, `HANDOFF_FASE7_CORTE*.md`) pero no se volcaron aquí
> retroactivamente — deuda de documentación preexistente, no introducida por
> este corte. Esta sección sólo cubre lo nuevo/reescrito en V2 A.

### 6.1 `step.management.harvest.plan` — reescrito

Gana el patrón de revisión/inmutabilidad de `crop_program.py`:
`revision`, `revision_of_id`, `superseded_by_id`, `reopen_reason`,
`confirmed_by_id`, `confirmed_at`, `confirmation_snapshot`,
`confirmation_hash`. `state` gana `superseded`. `line_ids` y `resource_ids`
son ambos `copy=True`/`copy=False` respectivamente en el sentido de que
`resource_ids` (la configuración) SÍ se copia a una revisión nueva;
`line_ids` (derivado) NO — se regenera con `action_generate()`.

### 6.2 `step.management.harvest.plan.line` — campos nuevos

`center_id` (M2o `cost.center`, **opcional** — compatibilidad con planes
confirmados antes de este corte, nunca se asigna retroactivamente),
`species`, `variety` (Char, snapshot). `_sql_constraints`:
`unique(harvest_plan_id, center_id, week_number)` (Postgres no aplica esto a
filas heredadas con `center_id IS NULL`, documentado en el `help`).

### 6.3 `step.management.harvest.resource` — nuevo

Nodo configurable de una cadena de factores (Corte V2 A, `Anexo 1.6.9 plan
de cosecha V2.xlsx`). Campos: `harvest_plan_id` (M2o req cascade),
`resource_key` (Selection, ≥ 11 valores: cajas, unidad de traslado,
cosecheros, supervisor, jefe de cuadrilla, anotadores, tractoristas,
cargador, pallets/día, viajes/día, maquinaria), `label`, `source_type`
(`harvest_kg`/`resource`), `source_resource_id` (M2o self, `check_company`),
`factor` (Float, divisor — **nunca hardcodeado**, `@api.constrains` bloquea
cero), `rounding_policy` (`precision`/`ceil`/`none`), `uom_id`,
`is_reusable_container` (Boolean), `product_id` (M2o `product.product`,
`check_company`), `coverage_multiplier` (Float, default 3.0),
`weekly_max_value`/`target_inventory`/`on_hand_quantity`/`inventory_gap`
(compute stored, sólo si `is_reusable_container`). `_compute_weeks()`
resuelve la cadena en orden topológico y escribe `week_ids`.

### 6.4 `step.management.harvest.resource.week` — nuevo

Snapshot semanal congelado: `resource_id` (M2o req cascade),
`week_number`/`week_label`, `source_value`, `factor_snapshot`, `value`.
`_sql_constraints`: `unique(resource_id, week_number)`. `write()` siempre
lanza `UserError` — es un cálculo del sistema, nunca editable a mano; sólo
`_compute_weeks()` lo recrea (unlink + create).

### 6.5 `step.management.production.order.line` — campo nuevo

`harvest_plan_line_id` (M2o `harvest.plan.line`, `ondelete=set null`,
`check_company`) + `source_type` gana `harvest_line`. Mismo contrato de
exclusividad/no-duplicación (`_sql_constraints unique(order_id,
harvest_plan_line_id)`) que las otras dos fuentes.

## 7. Corte V2 B — hechos históricos normalizados (`18.0.16.0.0`)

**`step.management.historical.cost` — campos nuevos** (todos opcionales;
registros manuales previos quedan con `dataset_kind` vacío, sin cambios):
`dataset_kind` (`budget`/`actual`), `import_batch_id` (M2o al lote,
`ondelete=restrict`), `record_type_label`, `budget_version`, `season_code`,
`season`, `year`, `month`, `farm`, `species`, `variety`,
`cost_center_type_label`, `center_label`, `origin_label`,
`budget_group_label`, `activity_label`, `product_label`, `uom_label`
(snapshots de texto tal cual el archivo), `source_amount`,
`source_exchange_rate`, `source_amount_usd` (snapshot numérico tal cual el
archivo, nunca recalculado — el valor "normalizado" que usa el sistema es
`budget_amount`/`actual_amount`, ya existentes).

**`step.management.historical.template.version` — nuevo.** Maestro global
(sin `company_id` — un único formato para todas las empresas, mantenido
sólo por el Administrador): `code`, `kind`, `schema_version`,
`header_signature` (Text, una cabecera normalizada por línea, en orden),
`is_current`, `template_file`. `_check_single_current` impide dos versiones
vigentes del mismo `kind`.

**`step.management.historical.import.batch` — nuevo.** El "lote":
`company_id`, `dataset_kind`, `template_version_id` (resuelto al validar,
por firma de cabecera exacta), `file`/`file_hash`, `batch_key_hash`
(protegido por índice único parcial, `init()`), `exclude_exact_duplicates`,
`import_valid_only`, `reversal_of_id` (self), `state`
(`draft/validated/entered/approved/blocked/cancelled`), `line_ids`
(staging, `copy=False`), `cost_ids` (hechos creados, `copy=False`).

**`step.management.historical.import.line` — nuevo.** Fila de staging:
mismos campos que el hecho final más `is_duplicate`/`duplicate_of_row`
(detección de duplicados exactos dentro del lote) y `dup_hash`/`line_hash`.

## 8. Corte V2 C — comprometido de compras (`18.0.17.0.0`)

**Nueva dependencia del manifiesto:** `purchase`.

**`step.management.stock.requirement.line` — campos nuevos:**
`committed_quantity` (Float, informativo — misma foto para todos los
períodos del producto, calculada desde `purchase.order.line` confirmadas y
no facturadas por completo, convertida a la UdM del producto),
`net_to_buy` (Float — faltante acumulado menos lo comprometido,
consumiendo ambos una sola vez, comprometido después de stock; con
`availability_metric='forecasted'` no se descuenta de nuevo),
`committed_purchase_line_ids` (M2m `purchase.order.line`, trazabilidad).

## 9. Corte V2 D — addon puente `step_management_costs_agriculture` (`18.0.1.0.0`)

Addon nuevo y separado (no forma parte de `step_management_costs`),
`auto_install=True`, depende de `step_management_costs` + `step_hr`.

**`step.management.cost.center` (extensión, sólo lectura):** `agri_farm_id`,
`agri_species_id`, `agri_variety_id`, `agri_variety_group_id` (M2o a los
maestros reales de `step_hr`, `related` a través de `analytic_account_id`),
`agri_plants`, `agri_hectares` (Integer, `related` a
`analytic_account_id.plant_cost`/`.has_cost`).

**`step.management.estimation` (extensión):** `harvest_labor_id` (M2o
`product.template`, opcional — labor usada para la precedencia de
rendimiento). `action_compute_lines()` extendido: si el centro tiene cuenta
analítica con `plant_cost`, lo usa como `plants`; si hay `harvest_labor_id`,
busca rendimiento estándar en `step.rendimiento.line` (centro) →
`step.variedad.line` (variedad) → `step.grupo.variedad.line` (grupo),
todas indexadas también por `labor_id`.

**`step.management.estimation.line` (extensión):** `plants_source`,
`yield_source` (Char, readonly) — procedencia congelada al validar
(`PROTECTED_LINE_FIELDS` del núcleo, extendido por este puente).

`upgrades/18.0.1.0.0/post-migration.py`: copia `farm`/`species`/`variety`
del maestro real al `Char` del núcleo sólo cuando éste está vacío.
