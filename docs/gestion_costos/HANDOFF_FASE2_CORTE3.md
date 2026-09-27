# Handoff — Fase 2, corte 3

**Addon:** `step_management_costs`  ·  **De:** `18.0.4.0.0` → **A:** `18.0.5.0.0`
**Fecha:** 2026-09-02  ·  **Autor:** Claude (ingeniería)  ·  **Estado:** para revisión de Codex.

## 1. Alcance

Cierra **PPT-11** y parte de **MEN-02**: **presupuesto general** (centros no
agrícolas, formulario libre, sin plantilla ni escala por hectárea), separado del
flujo agrícola por un campo de tipo. **No** toca la semántica contable
(`analytic_actuals.py` A1–A5 intactos, D01/D15 siguen pendientes de validación
humana). **No** incluye maquinaria (contradicción C6 `#DIV/0!` sin decidir;
Fase 6) ni la vista SQL de desviación (el asistente sigue igual).

### Cambios de modelo (`models/operational_budget.py`)

- **`step.management.operational.budget.budget_type`**: Selection
  `('agricultural', 'general')`, `default='agricultural'`, `required=True`,
  `tracking=True`, `copy=True`. Se añade a `PROTECTED_HEADER_FIELDS` (congelado
  en aprobado/cerrado/reemplazado).
- **`_check_budget_type_consistency`** (`@api.constrains`): un presupuesto
  `general` no puede tener `template_id` ni `import_id`.
- **`action_generate_lines`**: `UserError` claro si `budget_type == 'general'`
  (antes que las validaciones de plantilla).
- **`budget.center._check_hectares`**: rechaza negativos siempre; exige
  `hectares > 0` **sólo** si el presupuesto **no** es `general`. En `general`
  se admite `0` (centros sin superficie). El caso de regresión —
  `hectares = 0` en presupuesto agrícola sigue fallando— se conserva.
- **`budget.line.hectares`**: deja de ser `required` a nivel modelo. Nuevo
  `_check_line_hectares` (`@api.constrains`): rechaza negativos; exige
  hectáreas cuando el presupuesto **no** es `general`. Antes no había ninguna
  constraint (sólo `required=True` a nivel columna) — el flujo agrícola queda
  **igual de estricto** (las líneas de `action_generate_lines` y del importador
  siempre traen hectáreas > 0).
- `origin_type` de un presupuesto general sin plantilla/carga = `manual`
  (compute existente, sin cambio).

Sin cambios en `analytic_actuals.py` ni en `wizard/budget_variance.py`: el
asistente ya agrega el lado presupuesto desde `budget.month` con independencia
del origen, y el gate `_centers_without_analytic` sigue exigiendo cuenta
analítica por centro al aprobar (también en `general`), así que la comparación
con el real es conciliable igual.

### Vistas

- **`views/operational_budget_views.xml`**:
  - `budget_type` en el grupo «Definición» (readonly fuera de
    `draft/calculated`), como columna opcional de la lista, y como filtros
    «Agrícola»/«General» + agrupación «Tipo» en la búsqueda.
  - Botón «Calcular desde plantilla» y campo `template_id` ocultos cuando
    `budget_type == 'general'`.
  - Tarjetas «Superficie» y «Costo promedio / ha» ocultas en `general`;
    columnas `hectares` / `quantity_per_ha` del detalle con
    `column_invisible="parent.budget_type == 'general'"` (y `invisible` en el
    formulario de línea).
  - Alerta «Cómo funciona» con variante para `general`.
  - Página del detalle: se quita `create="false" delete="false"` de la lista
    de líneas para permitir capturar/borrar líneas a mano (necesario para
    `general`; ver §4).
  - Dos acciones nuevas: `action_operational_budget_agricultural` y
    `action_operational_budget_general` (con `domain` + `default_budget_type`),
    reutilizando las vistas existentes. `action_operational_budget`
    (sin filtro) **se conserva** — la usa el tablero OWL.
- **`views/menu_views.xml`**: el menú `menu_operational_budget` (mismo XML ID)
  pasa a llamarse «Presupuesto agrícola» y apunta a la acción agrícola; nuevo
  `menu_operational_budget_general` («Presupuesto general», seq 12).

### Migración

`upgrades/18.0.5.0.0/post-migration.py`: `UPDATE ... SET
budget_type = 'agricultural' WHERE budget_type IS NULL`. Idempotente, sin IDs
numéricos, sin `commit()`. Todos los presupuestos previos son agrícolas
(se calculaban desde plantilla o carga Excel). El `default` del campo ya lo
cubre; el UPDATE es defensivo.

### Manifiesto

`version` → `18.0.5.0.0`. Sin nuevos archivos en `data` (sólo lógica y edición
de vistas existentes).

## 2. Matriz requisito → cambio → prueba

| Requisito | Cambio | Prueba (`tests/test_fase2_general.py`) |
|---|---|---|
| PPT-11 tipo agrícola/general | `budget_type` + `PROTECTED_HEADER_FIELDS` | `test_general_budget_zero_hectares_and_totals`, `test_general_budget_approval_and_freeze` |
| PPT-11 centros sin hectáreas | `budget.center._check_hectares` condicional | `test_general_budget_zero_hectares_and_totals`; regresión `test_agricultural_allocation_still_rejects_zero_hectares` |
| PPT-11 líneas libres | `budget.line.hectares` no `required` + `_check_line_hectares` condicional | `test_general_line_without_hectares_is_valid`; regresión `test_agricultural_line_requires_hectares` |
| PPT-11 sin plantilla / carga | `_check_budget_type_consistency` + guard en `action_generate_lines` | `test_general_cannot_carry_template`, `test_generate_lines_blocked_on_general` |
| PPT-11 no regresión agrícola | (sin cambio de flujo) | `test_agricultural_flow_unchanged` |
| GES-03 comparación con real sobre general | (el asistente ya es agnóstico al origen) | `test_variance_wizard_runs_on_general_budget` |
| MEN-02 navegación | 2 acciones + 2 menús | revisión de vista / smoke |
| UPG | manifiesto `18.0.5.0.0` + `upgrades/18.0.5.0.0/post-migration.py` | **pendiente**: upgrade en base desechable (ver §3) |

Conserva todos los `_name` / tablas / secuencias / XML IDs (el XML ID
`menu_operational_budget` y la acción `action_operational_budget` se mantienen);
`state` sin tocar; ningún campo pasa a `required=True`.

## 3. Pruebas — EJECUTADAS

Verificación estática local: `py_compile` de todo el módulo → OK; parseo de
todos los XML → OK.

En `odoo-new`, bases **desechables** `MC_F2C3_*` (clon de `LAB_TAREAS` vía
`pg_dump -Fc | pg_restore`, addons-path de Desarrollo, `--http-port 8991
--gevent-port 8992 --no-http --stop-after-init`), `2026-09-03 00:17`:

| Escenario | Resultado |
|---|---|
| Upgrade `18.0.4.0.0 → 18.0.5.0.0` sobre clon de `LAB_TAREAS` + suite | **RC=0 · 0 failed, 0 error of 45 tests** |
| Instalación limpia (`--without-demo=all`) + suite | **RC=0 · 0 failed, 0 error of 45 tests** |

- `TestFase2General`: 9/9 métodos ejecutados (no *skipped*).
- `post-migration [18.0.5.0.0]` corre: `budget_type inicializado en 0
  presupuestos` — 0 porque el `default` de la columna nueva ya rellenó las
  filas antes del `UPDATE`; el `UPDATE ... WHERE budget_type IS NULL` es
  defensivo e idempotente (no encontró NULLs).
- Sin warnings de vista/campo sobre `budget_type` ni las acciones nuevas.
- Ambas `MC_F2C3_*` eliminadas al terminar.

Ruido preexistente e inofensivo confirmado (Odoo continúa): `steps_api` no
cargado; `grupo_labor` / `product_uom_id` NOT NULL.

Despliegue a Desarrollo/Demo: **pendiente de autorización del usuario por
ambiente**.

## 4. Riesgos / notas

- **Detalle de líneas ahora con `create`/`delete` en agrícola** (`draft`/
  `calculated`): decisión deliberada para no duplicar la vista del `line_ids`.
  Una línea agrícola añadida a mano se pierde al pulsar «Calcular desde
  plantilla» (mismo comportamiento que las ediciones manuales hoy, PPT-08). El
  aprobado sigue congelado por los `write()`/`unlink()` de los modelos hijos.
  Si Codex lo prefiere estricto, la alternativa es dos `<page>` con
  `invisible` por `budget_type` (más verboso, riesgo menor de campo duplicado).
- `column_invisible` / `invisible` con `parent.budget_type` requieren que
  `budget_type` esté en el formulario padre — lo está (grupo «Definición»).
- El presupuesto general admite **cualquier** centro (también agrícola, p. ej.
  gastos generales de un fundo); nunca fuerza hectáreas en ese tipo — decisión
  confirmada por el usuario en este corte.
- Ruido preexistente al hacer `-u` sin cambios: `product_template.grupo_labor`
  / `step_cosecha_registry.product_uom_id` NOT NULL, y `['steps_api']` no
  cargado. Odoo continúa.

## 5. Siguiente corte sugerido

- **Presupuesto de maquinaria** (tarifa gastos/horas, Anexo 1.6.2.5) — requiere
  primero cerrar C6 (`#DIV/0!` = horas presupuestadas 0 debe ser error de
  datos, no división). Matriz lo ubica en Fase 6.
- **Vista SQL `_auto=False`** de desviación con `company_id`/ACL/regla global y
  prueba de dos compañías (plan §5.4) — recomendable **después** de que
  Contabilidad valide A1–A5 (D01/D15), para no cristalizar supuestos en SQL.
- Fase 3 (estimaciones) según el plan.
