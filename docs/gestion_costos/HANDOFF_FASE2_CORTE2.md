# Handoff — Fase 2, corte 2

**Addon:** `step_management_costs`  ·  **De:** `18.0.3.0.0` → **A:** `18.0.4.0.0`
**Fecha:** 2026-09-02  ·  **Autor:** Claude (ingeniería)  ·  **Estado:** para revisión de Codex.

## 1. Alcance

Segundo corte de Fase 2: **gasto real contable + desviación auditable**. Cierra
el «pago» de la primera vertical (presupuesto aprobado → real → desviación).
No incluye importadores adicionales, presupuesto general/maquinaria, ni
`committed`.

### Servicio de lectura del real (`models/analytic_actuals.py`)
`step.management.operational.budget._read_analytic_actuals(date_from, date_to)`:
- Fuente **exclusiva**: `account.analytic.line` cuyo `move_line_id.parent_state
  == 'posted'` (apuntes publicados). Las líneas analíticas manuales sin asiento
  se excluyen.
- La cuenta analítica del centro se busca en **cualquier plan analítico**
  (`account_id` o `x_planN_id` de `account.analytic.line`) — Desarrollo/Demo
  usan el plan «Centro de costos» (`x_plan3_id`).
- Naturaleza (costo/ingreso) derivada del `account_type` de la cuenta de
  resultado del apunte (`income*` / `expense*`); otros tipos se ignoran.
- Signo: se usa `amount` (convención Odoo). Costo = `-amount` (magnitud
  positiva); nota de crédito / reversa invierten el importe con su signo real.
- Grupo presupuesto por bucket = `product_id._get_management_budget_group()`
  (producto → subcategoría → categoría). Sin producto o sin grupo →
  «Sin clasificar».
- `_season_date_range()`: rango mayo–abril derivado de `season`.
- **No persiste nada**: es sólo lectura (ADR-001 D-B).

### Asistente de desviación (`wizard/budget_variance.py`)
`step.management.budget.variance.wizard` (transient) + `.variance.line`:
- Botón **«Comparar con real»** en el presupuesto (visible en
  aprobado/cerrado/reemplazado).
- Rango de fechas editable (por defecto la temporada), casilla «sólo con
  desviación».
- `action_compute`: agrega el presupuesto por (centro, grupo, mes, naturaleza)
  desde `budget.month` y lo cruza con `_read_analytic_actuals`. Por bucket:
  `budget_amount`, `actual_amount`, `variance = real − presupuesto`,
  `variance_percent` recalculado desde los totales (nunca suma de %).
- Cada línea guarda los `account.move.line` que la componen; botón **«Ver
  asientos»** → `account.move.line` filtrados (drill-down al documento).
- Totales de cabecera: presupuesto/real/Var$/Var% de costo, e ingreso.

### Seguridad / versión
- ACL para los 2 modelos transient (todos los perfiles: lectura/escritura/
  creación). Sin cambios en modelos persistentes ⇒ **sin script de upgrade**.
- Manifiesto → `18.0.4.0.0`; nuevo `wizard/budget_variance_views.xml`.

## 2. Supuestos que requieren validación de Contabilidad (D01 / D15)

Documentados en la cabecera de `models/analytic_actuals.py` (A1–A5). Cambiar
cualquiera es una modificación acotada a ese archivo:

- A1 valor = `account.analytic.line.amount`;
- A2 naturaleza por `account_type` (`income*`/`expense*`); otros tipos se ignoran;
- A3 grupo por resolución de producto/categoría; sin grupo → «Sin clasificar»;
- A4 reversa/NC con su signo real;
- A5 multimoneda: `amount` ya en moneda de la compañía.

Pendiente de Contabilidad: qué cuentas de resultado entran, tratamiento fino
de NC/reversa, si «ingresos» entra en esta vertical, y OP/OT (dependen de
módulos aún inexistentes — hoy no se enriquecen).

## 3. Pruebas — EJECUTADAS

`tests/test_fase2_variance.py` (usa `AccountTestInvoicingCommon`):
- real sólo desde asiento **publicado** (borrador excluido); Var$ y Var%
  correctos; drill-down poblado;
- nota de crédito invierte el real;
- bucket «Sin clasificar» cuando el producto no tiene grupo;
- filtro «sólo con desviación»;
- apunte fuera del rango de temporada excluido.

Resultado en `odoo-new` (bases desechables, ya eliminadas):

| Escenario | Resultado |
|---|---|
| Upgrade `18.0.3.0.0 → 18.0.4.0.0` sobre clon de `LAB_TAREAS` + suite | **RC=0 · 36/36 tests** |
| Instalación limpia + suite | **RC=0 · 36/36 tests** |

Desplegado a Desarrollo (`LAB_TAREAS`) y Demo (`STEPS_DEMO`) el 2026-09-02:
`18.0.3.0.0 → 18.0.4.0.0`, RC=0, datos preservados, servicios OK, HTTP 200
(local y público). Demo-SyS sin tocar.

## 4. Riesgo / notas

- El asistente calcula en Python (no vista SQL). Para volumen alto habrá que
  pasar a `_read_group` / vista `_auto=False` (plan §5.4) — este corte entrega
  «el contrato y el mínimo probado».
- La detección de columnas de plan analítico se basa en el patrón
  `x_plan{N}_id`; si Odoo cambia esa convención habría que ajustar
  `_read_analytic_actuals`.
- Persiste el ruido preexistente de `step_hr` (`grupo_labor` /
  `product_uom_id` NOT NULL) al hacer `-u`.

## 5. Siguiente corte sugerido

- Presupuesto **general** (centros no agrícolas) y **maquinaria** (modelo de
  tarifa gastos/horas) para completar el menú de Presupuesto.
- Promover la comparación a vista SQL `_auto=False` con `company_id`/ACL/regla
  global y pruebas de dos compañías (plan §5.4).
- Enriquecimiento OP/OT del real cuando existan esos módulos.
