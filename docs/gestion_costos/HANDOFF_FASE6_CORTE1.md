# Handoff — Fase 6, corte 1 (Necesidades de stock consolidadas)

**Addon:** `step_management_costs` · **De:** `18.0.11.0.0` → **A:** `18.0.12.0.0`
**Fecha:** 2026-09-03 · **Autor:** Claude · **Estado:** implementado y verificado, sin despliegue

## 1. Alcance

Consolidación de necesidades de stock por **semana / mes / temporada** a
partir de fuentes **aprobadas** y conciliadas. Cumple la parte «stock
concilia; sin duplicidad» de la puerta de salida de Fase 6.

**No** incluye la Orden de Producción como documento ni la integración con
módulos de OT (D25–D27 pendientes de validación del cliente; ver Word de
preguntas). La marca «fuera de OP» (D11) requiere que exista la OP.

### `step.management.stock.requirement` (+ `.line`)

- Cabecera multiempresa: folio `STK/…`, temporada, `granularity`
  (`week`/`month`/`season`), interruptores `include_budgets` /
  `include_programs` y M2m opcionales `budget_ids` / `program_ids`
  (vacío = todas las fuentes aprobadas de la temporada).
- `action_compute()`:
  - **Presupuestos** (estado `approved`/`closed`): sólo líneas de categoría
    **«insumo agrícola»** con producto; su distribución mensual se reparte a
    la granularidad elegida — semanal con `period_service.distribute_
    monthly_to_weeks` (residuo a la última semana del mes), mensual/temporada
    por suma directa.
  - **Programas** (estado `approved`): cada aplicación expandida aporta su
    `quantity` en la semana de su receta; en granularidad mensual/temporada
    se agrega al mes/temporada correspondiente; sin semana → cubo
    «Sin semana».
  - Agrega por `(producto, período)` en dos columnas separadas
    (`budget_quantity`, `program_quantity`); `total_quantity` = suma. **No se
    duplica.**
  - Idempotente (borra y recrea) y transaccional; pasa a `computed`.
- `step.management.stock.requirement.line`:
  `unique(requirement_id, product_id, period_key)`; `period_index` para
  ordenar los períodos (semana en orden de temporada, mes mayo→abril).

### `period_service` — método nuevo

`week_of_season(temporada, nº_semana_ISO)` → ubica una semana ISO (1–53)
dentro de la temporada y devuelve su etiqueta, mes, año e índice de orden, o
`False` si no cae en el rango.

## 2. Seguridad

- ACL: `stock.requirement` y `.line` — consulta lee; usuario CRUD;
  administrador full. `action_compute` lo puede correr el operador.
- Reglas globales por empresa para ambos modelos.
- `check_company=True` en `requirement_id`; `_check_company_auto` en ambos;
  `@api.constrains` de coherencia de empresa para los M2m de fuentes.
- Constraint SQL `unique(requirement_id, product_id, period_key)`.

## 3. Interfaz

- Menú **Gestión y Costos > Planificación > Necesidades de stock**.
- Formulario con granularidad, selección de fuentes y detalle
  producto × período con columnas Presupuesto / Programas / Total.

## 4. Migración

- Manifiesto `18.0.12.0.0`.
- `upgrades/18.0.12.0.0/post-migration.py` **idempotente**: sin backfill
  (modelos nuevos); registra el conteo preservado. Sin IDs numéricos, sin
  `commit()`.
- `data/management_sequences.xml`: secuencia
  `step.management.stock.requirement` (`STK/%(year)s/`).

## 5. Pruebas

Pruebas nuevas: **12** (132 → **144** en la suite), en
`tests/test_fase6_stock.py` (`TestFase6Stock`):

- consolidación semanal que **concilia** con el mes del presupuesto;
- granularidad mensual que fusiona presupuesto y programa en el mismo cubo;
- granularidad temporada (un cubo por producto);
- **fuentes no duplicadas** (columnas separadas, total = suma);
- sólo líneas de categoría «insumo» del presupuesto;
- sólo fuentes **aprobadas** (borrador/calculado excluidos);
- programa sin semana → cubo «Sin semana»;
- idempotencia del recálculo;
- aislamiento entre empresas y rechazo de fuente de otra empresa;
- roles (operador calcula, consulta no crea);
- constraint SQL `unique(requirement_id, product_id, period_key)`.

### Verificación local

- `py_compile` de todos los `.py`: OK.
- Parseo de los 23 XML: OK.
- `git diff --check`: OK (sólo avisos LF/CRLF).

### Verificación Odoo real en `odoo-new` (sólo bases desechables)

| Escenario | Resultado |
|---|---|
| Upgrade de clon de `LAB_TAREAS` (`18.0.4.0.0` → `18.0.12.0.0`) | RC 0 · **0 failed, 0 error(s) of 144 tests** |
| Instalación limpia sin demo (`--without-demo=all`) | RC 0 · **0 failed, 0 error(s) of 144 tests** |

Migraciones `18.0.5.0.0`→`18.0.12.0.0` ejecutadas en el upgrade; la
`18.0.12.0.0/post-migration.py` registró «0 consolidación(es)…» sin error.
Logs en `odoo-new`: `/tmp/mc_f6_upg_20260904_000316.log`,
`/tmp/mc_f6_clean_20260904_000316.log`.

Bases `MC_F6_UPG` / `MC_F6_CLEAN`, dump, `data-dir` temporal, tar y script
remoto eliminados al terminar; logs conservados en `/tmp/mc_f6_upg_*.log` y
`/tmp/mc_f6_clean_*.log`.

## 6. Decisiones y supuestos

- El presupuesto sólo aporta **insumos** (categoría `input`); mano de obra,
  maquinaria y servicios no son necesidades de stock.
- El plan de cosecha (envases por semana) **no** se consolida aquí: es un
  recurso de otra naturaleza; se puede sumar en un corte posterior si el
  cliente lo pide.
- La semana de un programa se toma de su receta (`week_number`); si no la
  tiene, la demanda va al cubo «Sin semana» y se reparte manualmente.
- Reparto mes→semana: mismo criterio determinista que el plan semanal
  (días naturales, residuo a la última semana del mes — D04, F4-A3).

## 7. Límites y siguiente corte

- Sin Orden de Producción (documento), sin «fuera de OP» (D11), sin
  integración OT — dependen de definiciones del cliente (D25–D27).
- Sin PDF ni informes (Fase 7).
- Worktree `C:\Users\tito4\Documents\Odoo-gestion-costos`, rama
  `codex/gestion-costos`. Todo sin commit ni push. Sin despliegue ni escritura
  en `LAB_TAREAS`, `STEPS_DEMO` ni `STEPS_DEMO_SYS`.

Siguiente: cuando el cliente responda D25–D27, la Orden de Producción semanal
que agrupa tareas + programas + cosecha en una unidad autorizable; o Fase 7
(informes y endurecimiento) con el catálogo D18.
