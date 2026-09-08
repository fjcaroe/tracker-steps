# Handoff — Fase 3, corte 3

**Addon:** `step_management_costs` · **De:** `18.0.8.0.0` → **A:** `18.0.9.0.0`
**Fecha:** 2026-09-03 · **Autor:** Claude · **Estado:** implementado y verificado, sin despliegue

## 1. Alcance

Carga normalizada de la **estimación de cosecha desde Excel** (Anexo 1.6.4.1)
con staging, reutilizando el patrón ya probado de `budget_import.py` (D10).

- **`step.management.estimation.import`** — cabecera de carga multiempresa:
  archivo `.xlsx`, `version_id`, `unit_id`, `method` (`plants|hectares|kilos`),
  `default_yield_ue`, `species`/`variety` por defecto y, opcionalmente, las
  tres curvas validadas. Estados `draft → validated → imported` (+ `cancelled`).
- **`step.management.estimation.import.line`** — filas de staging con los
  valores en crudo (`raw_*`), los valores resueltos y `state` (`ok`/`error`)
  con detalle por fila.
- **`action_validate`**: abre el libro (sólo `.xlsx`, ≤10 MB, Base64 válido,
  sin fórmulas), localiza la cabecera en las primeras 15 filas, corta a
  `MAX_DATA_ROWS` y para tras dos filas vacías, resuelve el centro/cuartel por
  **código o nombre dentro de la empresa** (no encontrado/ambiguo → error),
  valida hectáreas/plantas/rendimiento/kilos y marca **centro repetido** en el
  archivo como error de la 2ª fila en adelante.
- **`action_import`** (todo-o-nada, o «sólo filas válidas»):
  - rechaza reimportar el mismo archivo (`file_hash` + `state = imported`);
  - exige una sola temporada;
  - crea una **`step.management.estimation` en BORRADOR** con `import_id`,
    las curvas (si se indicaron) y una línea por fila válida. Los valores del
    Excel mandan; cuando una celda viene vacía se toma el dato del centro
    (hectáreas, plantas, fundo, cuartel, especie, variedad).
  - **nunca** valida la estimación: el operador revisa y el aprobador valida
    con las tres curvas (corte 2).
- Campo `import_id` (M2o, `readonly`, `copy=False`) agregado a
  `step.management.estimation` (no destructivo).

**No implementado** (por instrucción): informes documentales (D18 → Fase 7).

## 2. Seguridad

- ACL: `estimation.import` — consulta lee; usuario crea/edita (sin `unlink`);
  administrador CRUD. `estimation.import.line` — sólo lectura para
  consulta/usuario; la mutación del staging ocurre dentro del servicio con
  `sudo` (igual que `budget_import`). Un operador no puede alterar filas
  validadas (`AccessError`).
- Reglas globales por empresa: `rule_estimation_import_company`,
  `rule_estimation_import_line_company`.
- `check_company=True` en `version_id`, `unit_id`, las tres curvas y
  `center_id` de la fila; `_check_company_auto` en ambos modelos;
  `@api.constrains` de coherencia de empresa en la fila.

## 3. Interfaz

- Menú **Gestión y Costos > Estimaciones > Carga desde Excel**
  (`action_estimation_import`, secuencia 7, entre «Estimaciones» y «Curvas»).
- Formulario con botones Validar / Importar / Restablecer / Cancelar, alertas
  de filas OK/error y pestaña de filas con `raw_*` y detalle de error.

## 4. Migración

- Manifiesto `18.0.9.0.0`.
- `upgrades/18.0.9.0.0/post-migration.py` **idempotente**: sin backfill (modelos
  nuevos + columna nullable `estimation.import_id`); registra el conteo de
  cargas y de estimaciones con carga de origen. Sin IDs numéricos, sin
  `commit()`.
- `data/management_sequences.xml`: secuencia `step.management.estimation.import`
  (`IMPEST/%(year)s/`).

## 5. Pruebas

Pruebas nuevas: **14** (87 → **101** en la suite), en
`tests/test_fase3_estimation_import.py` (`TestFase3EstimationImport`):

- carga feliz método plantas (valores del Excel, plantas heredadas del centro
  cuando la celda viene vacía, factor kg aplicado una sola vez);
- método hectáreas: el Excel sobrescribe las hectáreas del centro;
- método kilos: cada fila exige kilos > 0; con «sólo válidas» importa el resto;
- todo-o-nada (centro inexistente) y luego «sólo filas válidas»;
- idempotencia por `file_hash` (segundo import del mismo archivo falla);
- rechazo de fórmulas;
- corte en filas residuales del libro;
- centro repetido en el archivo = error;
- cabecera fuera de la primera fila;
- `.xlsm` rechazado;
- operador no puede alterar staging validado (`AccessError`);
- centro de otra empresa no se resuelve; unidad de otra empresa rechazada al
  crear la carga;
- la estimación importada queda en borrador y **fluye a la validación** del
  corte 2 (tres ejes concilian con `total_kg`).

### Verificación local

- `py_compile` de todos los `.py`: OK.
- Parseo de los 20 XML: OK.
- `git diff --check`: OK (sólo avisos LF/CRLF).

### Verificación Odoo real en `odoo-new` (sólo bases desechables)

| Escenario | Resultado |
|---|---|
| Upgrade de clon de `LAB_TAREAS` (`18.0.4.0.0` → `18.0.9.0.0`) | RC 0 · **0 failed, 0 error(s) of 101 tests** |
| Instalación limpia sin demo (`--without-demo=all`) | RC 0 · **0 failed, 0 error(s) of 101 tests** |

Migraciones `18.0.5.0.0`→`18.0.9.0.0` ejecutadas en el upgrade; la
`18.0.9.0.0/post-migration.py` registró «0 carga(s)… 0 estimación(es)…» sin
error. Logs en `odoo-new`: `/tmp/mc_f3c3_upg_20260903_033806.log`,
`/tmp/mc_f3c3_clean_20260903_033806.log`.

Bases `MC_F3C3_UPG` / `MC_F3C3_CLEAN`, dump, `data-dir` temporal, tar y script
remoto eliminados al terminar; logs conservados en
`/tmp/mc_f3c3_upg_*.log` y `/tmp/mc_f3c3_clean_*.log`. Ruido preexistente
inofensivo del clon: `steps_api` ausente y `product_template.grupo_labor`
NOT NULL.

## 6. Decisiones y supuestos

- La carga **no** valida la estimación: separa «cargar datos» de «aprobar el
  cálculo» (segregación de funciones, corte 2).
- El método (`plants|hectares|kilos`) es de documento, se elige en la carga;
  el Excel es por centro/cuartel.
- Resolución de maestros por clave de empresa (código o nombre exactos); nunca
  coincidencia difusa. Centro repetido = error, coherente con
  `unique(estimation_id, center_id)`.
- Celda vacía ⇒ se hereda el dato del centro; celda presente e inválida ⇒
  error de fila (no se «arregla» en silencio).
- Idempotencia real por `file_hash`; el `line_hash` es evidencia por fila.

## 7. Límites y siguiente corte

- Sin informes documentales de estimación (Fase 7, D18).
- La estimación aún no alimenta plan semanal ni necesidades de stock (Fase 4).
- Worktree `C:\Users\tito4\Documents\Odoo-gestion-costos`, rama
  `codex/gestion-costos`. Todo sin commit ni push. Sin despliegue ni escritura
  en `LAB_TAREAS`, `STEPS_DEMO` ni `STEPS_DEMO_SYS`.

Siguiente: Fase 4 corte 1 — `period_service` (ISO-8601, W53, semanas que
cruzan mes prorrateadas por días, D04) y derivación de tareas semanales desde
el presupuesto/estimación vigente, vinculando `step.management.plan`.
