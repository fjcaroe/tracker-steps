# Handoff — Fase 2, corte 1

**Addon:** `step_management_costs`  ·  **De:** `18.0.2.0.0` → **A:** `18.0.3.0.0`
**Fecha:** 2026-09-02  ·  **Autor:** Claude (ingeniería)  ·  **Estado:** para revisión de Codex.

## 1. Alcance

Primer corte de la Fase 2 (MVP vertical), elegido por el usuario:
**ingreso/costo + carga normalizada desde Excel con staging**. No incluye
gasto real contable, desviación, presupuesto general ni maquinaria.

### A. Distinción ingreso / costo
- `step.management.budget.group.flow_type` (`cost` / `income`, default `cost`).
- `flow_type` propagado (related stored) a `budget.template.line`,
  `budget.line` (indexado) y usado en `budget.month` vía la línea.
- `operational.budget`: `total_amount` pasa a ser **sólo costo**; nuevos
  `total_income` y `margin` (= ingreso − costo). El snapshot de aprobación
  incluye `flow_type` por línea y los tres totales.
- Pivote de análisis: se quita "hectáreas" como medida (contradicción C4);
  se agrega `flow_type` como columna.

### B. Grupo presupuesto en producto / categoría (PPT-21)
- `product.template.management_budget_group_id` y
  `product.category.management_budget_group_id` (núcleo portable; sólo depende
  de `product`).
- `product.(product|template)._get_management_budget_group(company=None)`:
  resuelve **producto → subcategoría → categoría ascendente**; sin
  coincidencias vagas. La coherencia de empresa se valida al usar el producto.

### C. Carga Excel del Anexo 1.6.2.1 con staging (D10)
- Modelos: `step.management.budget.import` (lote, secuencia `IMP/%(year)s/`) y
  `step.management.budget.import.line` (fila de staging con columnas crudas +
  resueltas + `state ok/error` + `error`).
- Parseo con **openpyxl** (`data_only=False`, `read_only=True`):
  - cabecera localizada por nombres normalizados en las primeras 15 filas;
  - **límite de 5000 filas** y corte tras 2 filas vacías consecutivas — no se
    confía en `max_row` (contradicción C8);
  - sólo se leen las columnas mapeadas (no se recorren dimensiones residuales);
  - **fórmulas rechazadas** por fila (`=...`).
- Resolución de maestros por **clave única de empresa** (código o nombre):
  centro, grupo; `origen` → categoría; producto y UdM opcionales. Ambiguo o no
  encontrado ⇒ error de fila.
- Vista previa con error por fila; **todo-o-nada** (`action_import`), con
  casilla `import_valid_only` para importar sólo las válidas (D10).
- **Idempotencia**: `file_hash` (sha256) — un archivo ya importado no se
  vuelve a cargar; `line_hash` por fila para reconciliación futura.
- La importación crea un `operational.budget` nuevo en estado `calculated`,
  con `origin_type = 'import'`, `import_id`, agrupando filas por
  (centro, grupo, categoría, producto/actividad) en líneas con distribución
  mensual que cuadra por construcción.
- `operational.budget.template_id` pasa a **opcional**; `origin_type`
  (`template` / `import` / `manual`) computado. `action_generate_lines` se
  bloquea para presupuestos de origen `import`.

### D. Seguridad, vistas, migración
- ACL (`readonly` lectura, `user` CRU sin unlink, `manager` full) y
  `ir.rule` globales por empresa para los 2 modelos nuevos.
- Vistas: formulario/lista/búsqueda de la carga; menú
  **Presupuesto → Carga desde Excel**; campos en formularios de producto y
  categoría; `flow_type` en grupo presupuesto y en el detalle del presupuesto;
  cards de ingreso/margen en el presupuesto.
- `upgrades/18.0.3.0.0/post-migration.py`: `flow_type='cost'` donde falte;
  `flow_type` poblado en líneas/indicadores desde el grupo; `origin_type`
  inicializado. Idempotente, sin IDs numéricos, sin `commit()`.

## 2. Pruebas — EJECUTADAS

En `odoo-new`, bases desechables (ya eliminadas):

| Escenario | Resultado |
|---|---|
| Upgrade `18.0.2.0.0 → 18.0.3.0.0` sobre clon de `LAB_TAREAS` + suite | **RC=0 · 31/31 tests OK** |
| Instalación limpia en base nueva + suite | **RC=0 · 31/31 tests OK** |

`tests/test_fase2_import.py` (9 casos): totales ingreso/costo/margen;
resolución de grupo producto→subcat→cat; import happy path (crea presupuesto,
meses cuadran, totales concilian); todo-o-nada (falla y no crea nada; con
`import_valid_only` importa el resto); idempotencia por archivo; rechazo de
fórmula; corte ante filas residuales; grupo de ingreso incoherente; cabecera
fuera de la primera fila.

## 3. Riesgos / notas

- **Ruido conocido:** `-u step_management_costs` ahora dispara el `ERROR
  odoo.schema: Table 'product_template': unable to set NOT NULL on column
  'grupo_labor'` — es un defecto **preexistente de `step_hr`** (columna con
  NULLs históricos), inofensivo (Odoo continúa), que ahora también aparece
  bajo el upgrade de este módulo porque hereda `product.template`.
- `origin`→categoría no cubre todos los textos posibles del anexo; los no
  reconocidos son error de fila (correcto, pero puede requerir ampliar el
  mapa).
- La importación siempre **crea** un presupuesto nuevo. Anexar a un borrador
  existente con dedup por clave natural de línea queda para un corte posterior
  (el `line_hash` ya está preparado).
- Sin maestro de Temporada/Versión (D03/D06): `season` y `budget_version` son
  texto libre tomados del archivo.
- Falta revisión de Codex (DoD §7).

## 4. Siguiente corte sugerido

Fase 2, corte 2: **gasto real contable + desviación** — servicio
`analytic_actuals` (lectura de `account.move.line` publicados imputados por
analítica, bucketing por `management_budget_group_id` del producto/categoría
ya disponible), vista comparativa Budget/Actual/Var$/Var% con drill-down, e
inventario de `historical.cost` `unreviewed`.
