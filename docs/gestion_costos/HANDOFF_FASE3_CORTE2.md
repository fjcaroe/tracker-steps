# Handoff — Fase 3, corte 2

**Addon:** `step_management_costs` · **De:** `18.0.7.0.0` → **A:** `18.0.8.0.0`
**Fecha:** 2026-09-03 · **Autor:** Claude · **Estado:** implementado y verificado, sin despliegue

## 1. Alcance

Documento de estimación de cosecha por centro/cuartel, construido sobre los
maestros y las curvas validadas del corte 1. Se implementó:

- **Maestro `step.management.estimation.version`** — multiempresa, con `code`,
  `name`, `season`, `deadline_date`, `state` (`draft/open/closed`) y unicidad
  SQL `unique(code, company_id)`. **No** reemplaza el `season` `Char` de
  presupuestos (D03 sigue abierta).
- **Cabecera `step.management.estimation`** y **detalle
  `step.management.estimation.line`** con: empresa, versión, temporada,
  especie/variedad (`Char`, D13), unidad de estimación, método de cálculo
  (`plants|hectares|kilos`), rendimiento por defecto, y una curva validada de
  cada tipo (`week_curve_id`, `caliber_curve_id`, `class_curve_id`).
- **Snapshot reproducible al detalle**: `action_compute_lines` copia por
  centro `hectares`, `plants`, `farm`, `plot`, `species`, `variety` y congela
  `kg_factor` desde la unidad. Es idempotente (reejecutar no duplica ni
  cambia totales).
- **Campo `plants` en `step.management.cost.center`** — `Float`, `default 0`,
  no destructivo (D13: los `Char` agrícolas no se tocan).
- **Fórmula D05** en `estimation.line._compute_formula`:
  - plantas:   `total_ue = plants   * yield_ue`
  - hectáreas: `total_ue = hectares * yield_ue`
  - kilos:     `total_kg = total_kg_input` (entrada directa)
  - plantas/hectáreas: `total_kg = total_ue * kg_factor`
  - nunca se multiplica dos veces por `yield_ue`.
  - `kg_per_ha` / `kg_per_plant` devuelven `0` cuando el divisor es `0`
    (cabecera y línea), nunca `#DIV/0!`.
- **`action_validate`** (rol aprobador): exige las tres curvas validadas,
  activas, del tipo correcto y de la misma empresa; genera
  `step.management.estimation.distribution` normalizada por semana, grupo de
  calibre y clase.
- **Conciliación exacta por eje**: política determinista — cada porción se
  redondea a la precisión de peso (`decimal.precision "Estimación de cosecha"`,
  2 dígitos) y el **residuo se asigna a la última línea ordenada**
  (`sequence, id`). Cada eje suma exactamente `total_kg`; hay un chequeo de
  conciliación que aborta si no cuadra.
- **Idempotente y transaccional**: la generación borra y recrea las
  distribuciones dentro de la misma transacción del método, de forma
  determinista.
- **Inmutabilidad**: una estimación validada, su detalle y sus distribuciones
  son inmutables (`write`/`unlink`/`create` bloqueados por estado del padre,
  sin banderas de `context`). Para corregir se crea una **revisión**
  (`_create_revision` / `action_new_revision` / `_do_reopen(reason)`); al
  validar la revisión el origen pasa a `superseded`.

**No implementado en este corte** (por instrucción): carga Excel de estimación
e informes documentales.

## 2. Seguridad

- **ACL encadenadas**: consulta (`readonly`) sólo lee; usuario (operador) crea
  y calcula el detalle; aprobador valida; administrador mantiene los maestros
  (`estimation.version`, `estimation.unit`, etc.). `action_validate` tiene
  gate de rol propio (`_ensure_approver`) válido también por RPC.
- **Reglas globales multiempresa** nuevas: `rule_estimation_version_company`,
  `rule_estimation_company`, `rule_estimation_line_company`,
  `rule_estimation_distribution_company` (dominio
  `company_id in company_ids or company_id = False`).
- **`check_company=True`** en `version_id`, `unit_id`, las tres curvas,
  `estimation_id`, `center_id`, `caliber_group_id`, `fruit_class_id`;
  `_check_company_auto = True` en los cuatro modelos. Los `center_ids` (M2m,
  sin `check_company` nativo) se validan con `@api.constrains`.
- **Constraints SQL**: `unique(code, company_id)` en la versión;
  `unique(estimation_id, center_id)` en el detalle.

## 3. Interfaz

- Menú **Gestión y Costos > Estimaciones > Estimaciones**
  (`action_estimation`). Curvas quedan en la misma sección.
- **Maestros > Versiones de estimación** (`action_estimation_version`,
  sólo administrador).
- Formulario de estimación: cabecera (versión, temporada, método,
  rendimiento, tres curvas), pestañas Centros / Detalle / Distribución
  normalizada / Validación (snapshot + hash), botones «Calcular detalle»,
  «Validar» (aprobador) y «Nueva revisión» (aprobador).
- `cost_center`: campo **Plantas** en formulario y lista.

## 4. Migración

- Manifiesto `18.0.8.0.0`.
- `upgrades/18.0.8.0.0/post-migration.py` **idempotente**: normaliza
  `cost_center.plants` NULL → 0 (reejecutable sin efecto) y registra el
  conteo de versiones/estimaciones preservadas. Las tablas nuevas las crea el
  ORM. Sin IDs numéricos, sin `commit()`.
- `data/estimation_data.xml` (`noupdate="1"`) crea la precisión decimal
  «Estimación de cosecha» (2 dígitos).
- `data/management_sequences.xml`: secuencia `step.management.estimation`
  (`EST/%(year)s/`).

## 5. Pruebas

Pruebas nuevas: **21** (66 → **87** en la suite), en `tests/test_fase3_estimation.py`
(`TestFase3Estimation`, `ManagementCostsCommon`):

- tres métodos de cálculo (`plants` / `hectares` / `kilos`);
- conversión a kilos con `kg_factor` aplicado una sola vez;
- conciliación de los tres ejes con `total_kg`;
- redondeo y **residuo en la última línea ordenada** (caso `1000.01` que
  distingue el residuo del reparto ingenuo);
- semana 53;
- idempotencia de `action_compute_lines` y determinismo de la generación;
- inmutabilidad de estimación/detalle/distribución validados y flujo de
  revisión + `superseded`;
- snapshot + hash SHA-256;
- roles y RPC (operador crea/calcula, no valida ni por llamada directa;
  consulta no crea; aprobador valida);
- curvas incorrectas o incompletas (sin validar, faltante, tipo equivocado)
  y `total_kg = 0`;
- relaciones entre compañías (unidad y centro de otra empresa rechazados;
  aislamiento por regla global);
- constraints SQL (`unique(code, company_id)` de versión,
  `unique(estimation_id, center_id)` de línea);
- campo `plants` con default 0 y no negativo (proxy de preservación en
  upgrade).

### Verificación local

- `py_compile` de todos los `.py`: OK.
- Parseo de los 19 XML: OK.
- `git diff --check`: OK (sólo avisos LF/CRLF).

### Verificación Odoo real en `odoo-new` (sólo bases desechables)

| Escenario | Resultado |
|---|---|
| Upgrade de clon de `LAB_TAREAS` (`18.0.4.0.0` → `18.0.8.0.0`) | RC 0 · **0 failed, 0 error(s) of 87 tests** |
| Instalación limpia sin demo (`--without-demo=all`) | RC 0 · **0 failed, 0 error(s) of 87 tests** |

Migraciones `18.0.5.0.0`→`18.0.8.0.0` ejecutadas en el upgrade; la
`18.0.8.0.0/post-migration.py` registró «0 versión(es) y 0 estimación(es)
preservadas» sin error. Logs: `/tmp/mc_f3c2_upg_20260903_030029.log` y
`/tmp/mc_f3c2_clean_20260903_030029.log` en `odoo-new`.

Comandos exactos (por base desechable, `odoo` OS user, conf de Dev):

```
odoo-bin -c /etc/dev_odoo18.conf -d MC_F3C2_UPG \
  --addons-path=/tmp/mc_test_addons,/opt/rrhh,/opt/odoo18/addons,/opt/odoo18/odoo/addons,/opt/dev_odoo18/odoo_agriculture \
  --data-dir=/tmp/mc_f3c2_datadir -u step_management_costs \
  --test-enable --test-tags=/step_management_costs --stop-after-init \
  --no-http --http-port 8991 --gevent-port 8992
# ídem con -i y base nueva + --without-demo=all
```

Ruido preexistente e inofensivo del clon: `steps_api` ausente y
`product_template.grupo_labor` NOT NULL (histórico de `step_hr`).

Bases `MC_F3C2_UPG` / `MC_F3C2_CLEAN`, `data-dir` temporal, tar y scripts
remotos eliminados al terminar. Logs conservados en
`/tmp/mc_f3c2_upg_*.log` y `/tmp/mc_f3c2_clean_*.log`.

## 6. Decisiones y supuestos

- **D05**: se aplica la interpretación «conversión a kg», sin doble
  rendimiento (contradicción C1 registrada; sigue pendiente de Agronomía).
- **D03**: la versión de estimación tiene su propia `season` `Char`; no se
  crea el maestro de temporada ni se toca `operational.budget.season`.
- **D13**: `species`/`variety` de la estimación y `plants` del centro son
  campos propios (no maestros); el puente `_agriculture` los sustituirá.
- **Precisión de peso**: 2 decimales, configurable vía `decimal.precision`.
  El residuo de redondeo va siempre a la última línea del orden
  `(sequence, id)` de la curva.
- **Revisión**: sólo una sucesora activa por origen; una revisión sólo
  reemplaza un origen aún `validated`. Sin bypass por `context`.

## 7. Límites y siguiente corte

- Sin carga Excel de estimación ni informes (cortes posteriores).
- La estimación aún no alimenta plan semanal ni necesidades de stock
  (Fase 4).
- Worktree `C:\Users\tito4\Documents\Odoo-gestion-costos`, rama
  `codex/gestion-costos`. Todo sin commit ni push. Sin despliegue ni
  escritura en `LAB_TAREAS`, `STEPS_DEMO` ni `STEPS_DEMO_SYS`.

Siguiente: Fase 3 corte 3 — carga Excel de estimación (staging + idempotencia,
D10) e informes de estimación; o Fase 4 (plan semanal derivado del
presupuesto/estimación vigente, `period_service` con W53 y semanas que cruzan
mes, D04).
