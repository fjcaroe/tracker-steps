# Handoff — Fase 4, corte 1 (Plan semanal y cosecha)

**Addon:** `step_management_costs` · **De:** `18.0.9.0.0` → **A:** `18.0.10.0.0`
**Fecha:** 2026-09-03 · **Autor:** Claude · **Estado:** implementado y verificado, sin despliegue

## 1. Alcance

Servicio de períodos + derivación de tareas semanales desde el presupuesto
aprobado + plan de cosecha semanal desde la estimación validada. Cumple la
puerta de salida de Fase 4 del plan («el plan reconcilia presupuesto y
estimación»). No incluye programas fito/ferti, necesidades de stock ni OP
(Fases 5–6); tampoco informes documentales (Fase 7).

### 1.1 `step.management.period.service` (AbstractModel, sin tabla)

Utilidades deterministas (D04):

- `season_bounds("2026/2027")` → `(2026-05-01, 2027-04-30)`. Mes de inicio
  configurable vía `ir.config_parameter step_management_costs.season_start_month`
  (por defecto 5 = mayo).
- `iso_weeks(desde, hasta)` → semanas ISO-8601 (lunes-domingo) que intersectan
  el rango, con `iso_year`, `iso_week`, `label` (`W01`…`W53`), `monday`,
  `sunday` y `days_in_range`. **Semana 53 soportada.**
- `distribute_monthly_to_weeks(temporada, {mes: cantidad})` → reparte cada mes
  entre sus semanas **a prorrata de los días naturales** de cada semana que
  caen en ese mes y en la temporada; el **residuo de redondeo va a la última
  semana del mes**. Devuelve **todas** las semanas de la temporada (las
  vacías en cero, C3). Concilia exactamente mes a mes.

### 1.2 Tareas semanales (`step.management.plan`)

- Campos nuevos: `season`, `source_type` (`manual`/`budget`),
  `generated_line_count`; en `plan.line`: `week_label`, `iso_year`,
  `iso_week`, `generated`, `budget_line_id`.
- `action_generate_weekly_tasks()`:
  - exige `budget_id` en estado **aprobado / cerrado / reemplazado** (fuente
    conciliada e inmutable, F4-A4) y de la misma empresa;
  - temporada = `plan.season` o `budget.season`;
  - por cada línea de presupuesto reparte sus meses en semanas ISO con
    `distribute_monthly_to_weeks` (redondeo por `uom.rounding`);
  - **borra y recrea sólo las tareas `generated`**; las manuales no se tocan;
  - **verifica la conciliación** por línea: Σ semanas == Σ meses del
    presupuesto, o aborta con detalle;
  - idempotente y transaccional.

### 1.3 Plan de cosecha (`step.management.harvest.plan` + `.line`)

- Multiempresa, folio `COS/…`, `estimation_id` (estado **validado**, misma
  empresa), `container_unit_id`, `round_up_containers` (D08), `state`
  `draft/confirmed`.
- `action_generate()`: toma la distribución semanal de kilos de la estimación
  (eje `week`), crea una línea por semana con `kg` y
  `envases = techo(kg / kg_factor)` (o división exacta si se desmarca el
  redondeo). **Concilia** Σ kg del plan con `total_kg` de la estimación
  (incluye semanas > W50, C3). Regenerable en borrador.
- `action_confirm()` congela el plan (write/unlink de cabecera y líneas
  bloqueados); `action_reset_to_draft()` sólo para el rol aprobador.

## 2. Seguridad

- ACL `harvest.plan`: consulta lee; usuario CRUD sin `unlink`; administrador
  full. `harvest.plan.line`: usuario CRUD; administrador full. `period.service`
  no tiene tabla ni ACL.
- Reglas globales por empresa: `rule_harvest_plan_company`,
  `rule_harvest_plan_line_company`.
- `check_company=True` en `harvest_plan.estimation_id` / `container_unit_id` /
  `harvest_plan_id`, y en `plan.line.budget_line_id`; `_check_company_auto` en
  ambos modelos nuevos.
- Gate de rol en `action_reset_to_draft` (aprobador), válido también por RPC.

## 3. Interfaz

- Menú **Gestión y Costos > Planificación** pasa a ser contenedor con
  **Tareas semanales** (`action_management_plan`) y **Plan de cosecha**
  (`action_harvest_plan`).
- Plan operacional: botón «Generar tareas semanales», campos de temporada /
  origen, columna de semana ISO y marca «generada» en el detalle.

## 4. Migración

- Manifiesto `18.0.10.0.0`.
- `upgrades/18.0.10.0.0/post-migration.py` **idempotente**: `plan_line.generated`
  NULL → `FALSE`; tablas del plan de cosecha creadas por el ORM; registra el
  conteo preservado. Sin IDs numéricos, sin `commit()`.
- `data/management_sequences.xml`: secuencia `step.management.harvest.plan`
  (`COS/%(year)s/`).

## 5. Pruebas

Pruebas nuevas: **16** (101 → **117** en la suite), en
`tests/test_fase4_planning.py` (`TestFase4Planning`):

- `period_service`: `season_bounds` mayo–abril; `iso_weeks` con W53 y
  `days_in_range` acotado; reparto de un mes que concilia y cubre todas las
  semanas de la temporada; reparto de meses que cruzan el año.
- tareas semanales: conciliación con el presupuesto; idempotencia;
  preservación de tareas manuales; exige presupuesto aprobado; sin presupuesto
  falla; roles (operador genera, consulta no crea); presupuesto de otra
  empresa rechazado.
- plan de cosecha: concilia con `total_kg` y **no pierde semanas > W50** (C3);
  envases = techo(kg/kg_factor) y división exacta con el redondeo desmarcado;
  exige estimación validada; inmutabilidad tras confirmar + reapertura por
  aprobador; unidad de envase de otra empresa rechazada.

### Verificación local

- `py_compile` de todos los `.py`: OK.
- Parseo de los 21 XML: OK.
- `git diff --check`: OK (sólo avisos LF/CRLF).

### Verificación Odoo real en `odoo-new` (sólo bases desechables)

| Escenario | Resultado |
|---|---|
| Upgrade de clon de `LAB_TAREAS` (`18.0.4.0.0` → `18.0.10.0.0`) | RC 0 · **0 failed, 0 error(s) of 117 tests** |
| Instalación limpia sin demo (`--without-demo=all`) | RC 0 · **0 failed, 0 error(s) of 117 tests** |

Migraciones `18.0.5.0.0`→`18.0.10.0.0` ejecutadas en el upgrade; la
`18.0.10.0.0/post-migration.py` registró «0 plan(es) de cosecha preservados»
sin error. Logs en `odoo-new`: `/tmp/mc_f4_upg_20260903_040455.log`,
`/tmp/mc_f4_clean_20260903_040455.log`.

Bases `MC_F4_UPG` / `MC_F4_CLEAN`, dump, `data-dir` temporal, tar y script
remoto eliminados al terminar; logs conservados en `/tmp/mc_f4_upg_*.log` y
`/tmp/mc_f4_clean_*.log`.

## 6. Decisiones y supuestos (pendientes de validación de Operaciones)

- **F4-A1**: temporada = 12 meses desde el mes de inicio configurable
  (por defecto mayo).
- **F4-A2**: semana = ISO-8601; semana 53 soportada.
- **F4-A3**: prorrateo semana↔mes por **días naturales** (no hábiles);
  residuo a la última semana del mes.
- **F4-A4**: tareas semanales sólo desde presupuesto **aprobado/cerrado**.
- **F4-A5**: envases = techo(kg / kg_factor) — D08 «indivisibles al alza»;
  configurable por documento.
- **F4-A6**: plan de cosecha desde estimación **validada**; inmutable al
  confirmar.

Todas estas suposiciones están concentradas en `period_service.py` y
`harvest_plan.py`; cambiarlas es un cambio acotado. Las preguntas al cliente
están en `Preguntas_Cliente_Gestion_Costos_2026-09-03.docx`.

## 7. Límites y siguiente corte

- Sin recursos detallados de cosecha (personal, cuadrillas, fletes) más allá
  del conteo de envases; sin plan fito/ferti ni stock (Fases 5–6).
- Sin PDF ni informes (Fase 7).
- Worktree `C:\Users\tito4\Documents\Odoo-gestion-costos`, rama
  `codex/gestion-costos`. Todo sin commit ni push. Sin despliegue ni escritura
  en `LAB_TAREAS`, `STEPS_DEMO` ni `STEPS_DEMO_SYS`.

Siguiente: Fase 5 — motor común de programas fitosanitarios y de fertilización
(amplificación por hectárea siempre, C2), o cierre de Fase 4 con recursos de
cuadrilla/rendimiento de cosecha una vez validado D04/D08 con Operaciones.
