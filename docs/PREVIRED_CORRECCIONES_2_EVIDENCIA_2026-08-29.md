# PreviRed correcciones 2 — Informe de evidencias

Fecha de ejecución: 2026-08-31 (el documento funcional y el nombre de archivo
llevan fecha 2026-08-29).
Fuente funcional: `A10.1 ERP agrícola, Nómina, mejoras a módulo estándar Chile,
Previred, correcciones 2.docx`.
Rama de trabajo: `fix/previred-correcciones-2` (no se hizo `git push`).

RUT enmascarados en todo el informe (se conserva sólo el dígito verificador).
No se incluyen secretos, contraseñas ni contenido de archivos de configuración.

---

## 1. Causa raíz confirmada de cada problema

### 1.1 «Falta el campo obligatorio «13 Días Trabajados»» (10 de los 11 errores)

Reproducido en base desechable con los datos reales de Demo-SyS (compañía 7,
período 2026-07). Los 10 errores **no están en la línea principal** sino en las
**líneas anexas**:

- `step_hr_previred/tools/previred.py` → `validate_row()` exige el campo 13
  (posición 13, `F_WORKED_DAYS`) en **todas** las filas del trabajador, incluidas
  las anexas (tipo 01/02).
- Ni el generador del proveedor (`l10n_cl_simpledigital_payroll`) ni el
  enriquecimiento del núcleo (`_enrich_official_fields`) escribían el campo 13 en
  las líneas anexas: quedaba vacío y `validate_row` lo marcaba como obligatorio
  faltante.
- Recuento exacto: los 10 errores = suma de anexas de los 7 trabajadores
  afectados (1+1+2+2+1+2+1). Todas sus líneas **principales** ya traían un valor.

### 1.2 Valor del campo 13 en la línea principal (corrección 1 del documento)

- `_enrich_official_fields` tomaba el campo 13 de `worked_days_line_ids` filtrando
  por `code == "WORK100"` con un **respaldo genérico**: si no había `WORK100`,
  sumaba *toda* línea con días > 0 que no fuese ausencia.
- «Fuera de contrato» (`code = OUT`) **no** es una ausencia (`is_leave = False`),
  así que el respaldo genérico la sumaba. En `SLIP/491` daba 6 (Asistencia) + 12
  (Fuera de contrato) = 18 en vez de 6.
- El proveedor tampoco resuelve bien: `_get_real_worked_days_from_payslip` →
  `hr.payslip._dias_trabajados_previred()` calcula «30 − ausencias» y en esta
  base `OUT` está en `PREVIRED_ABSENCE_WORK_ENTRY_CODES`, con un tope de 30.
  Coincide con 6 en `SLIP/491` sólo por el recorte por fechas del contrato, no
  por leer la línea de asistencia.

### 1.3 «RUT 10······-3 aparece más de una vez con línea principal» (1 error)

- `step_hr_previred/tools/previred.py` → `validate_dataset()` calculaba la
  unicidad por `(company_id, rut_key)` **sin considerar el contrato**.
- El RUT `10······-3` (María Riquelme Zapata) tiene en julio 2026 **dos
  contratos elegibles que no se solapan**: contrato 171 (2026-06-15 → 2026-07-05)
  y contrato 205 (2026-07-13 → 2026-07-18), cada uno con su liquidación
  (`SLIP/475` y `SLIP/491`). El generador emite —correctamente— dos líneas
  principales (código `00`), y la validación las rechazaba.
- Nota de datos: en Demo-SyS ese RUT está repartido en **tres** registros
  `hr.employee` (ids 106/202/237), todos de la compañía 7 y con el mismo RUT.
  La corrección funciona igual porque la unicidad pasa a considerar el contrato,
  no el registro de empleado.

---

## 2. Archivos y métodos modificados

Todo en el núcleo y el bridge; **no** se tocó ningún addon de `/opt/rrhh`.

| Archivo | Cambio |
|---|---|
| `step_hr_previred/tools/previred.py` | `ATTENDANCE_CODES` (`WORK100`), `ATTENDANCE_LABELS`, `is_attendance_label()`. `PreviredRecord.contract_id` (metadata no exportada). `validate_dataset()`: unicidad por `(company, período, RUT, contract_id)`; mensaje específico para «mismo contrato». |
| `step_hr_previred/models/previred_extractor.py` | `build_dataset()` acepta `(rows, issues, row_meta)`. `_attach_contract_meta()`, `_match_contracts()` (correlación línea↔contrato determinística; ambigüedad ⇒ error). `_enforce_eligibility()`: cupo por **contratos** elegibles (`too_many_principal_lines`). `_set_worked_days()` nuevo: regla del campo 13 (ver §4). `_payslip_ref()`. Se elimina el respaldo genérico anterior. `_group_rows()`: comentario corregido. |
| `step_hr_previred/models/previred_adapter.py` | Documentado el tercer valor opcional `row_meta` de `generate_rows`. |
| `step_hr_previred_simpledigital/models/previred_engine.py` | `generate_rows()` devuelve `row_meta` con `contract_id` por línea principal, replicando la selección del generador del proveedor. `_contract_meta()`. Nota de la matriz para el campo 13. |
| `step_hr_previred_simpledigital/models/field_matrix.py` | (sin cambio de expresión; la nota vive en `previred_engine.MATRIX_NOTES`). |
| `step_hr_previred/__manifest__.py` | versión `18.0.3.3.1` → `18.0.3.4.0`. |
| `step_hr_previred_simpledigital/__manifest__.py` | versión `18.0.2.0.0` → `18.0.2.1.0`. |
| `step_hr_previred/CHANGELOG.md`, `docs/PREVIRED_MATRIZ.md` | Documentan la fuente real del campo 13 y la multiplicidad por contrato. |
| `step_hr_previred/tests/…` | `common.py` (FakeAdapter/`build()` admiten `row_meta`; `make_payslip` admite contrato explícito). `test_correcciones2.py` nuevo (18 casos). `test_dataset.py`: `test_duplicate_principal_is_reported` pasa a esperar `too_many_principal_lines`. `tests/__init__.py`. |

Commits en `fix/previred-correcciones-2`:
`e33ee7c` (implementación), `035ae5a` (fixtures + tope 30), `ec1f477`
(mes completo de ausencia ⇒ 0).

---

## 3. Diseño para identificar contratos sin alterar el TXT

- `PreviredRecord` gana `contract_id: Optional[int]`. Es **metadata interna**:
  no ocupa ninguna de las 105 posiciones, no se serializa en `render_rows()` y no
  desplaza campos.
- El contrato de cada línea principal lo entrega el **bridge**, no el núcleo: el
  bridge SimpleDigital reconstruye la lista de liquidaciones que recorre el
  generador del proveedor (mismo dominio: compañía, rango de `date_from`, estados
  `verify/done/paid`; mismo orden) y asocia, RUT por RUT y en orden, la i-ésima
  línea principal con el contrato de la i-ésima liquidación. Si los recuentos no
  cuadran, no entrega metadata y avisa (`engine_contract_meta_unavailable`); el
  núcleo cae entonces al criterio anterior por compañía + período + RUT.
- El núcleo empareja por `contract_id` de forma determinística
  (`_match_contracts`). Si un RUT tiene varias líneas y varias liquidaciones y no
  hay metadata para desambiguar, **bloquea** con `ambiguous_contract_correlation`
  en vez de asignar por posición.
- `validate_dataset()`: clave `(company_id, rut_key, contract_id)`. Dos líneas
  principales del mismo RUT con contratos distintos → válido. Dos del mismo
  contrato → `duplicate_worker`. Más líneas principales que contratos elegibles →
  `too_many_principal_lines` (bloquea). Borradores y cancelados no amplían el
  cupo (los filtra `eligible_payslips`, que nunca incluye `draft`/`cancel`).

---

## 4. Regla exacta del campo 13 y sus respaldos

En `_set_worked_days(record, payslip, dataset)` del dataset canónico (aplica a
TXT, Excel y archivos por departamento por igual):

1. **Fuente primaria** — líneas de `worked_days_line_ids` cuyo
   `work_entry_type_id.code` esté en `ATTENDANCE_CODES = ("WORK100",)` y con
   `number_of_days > 0`. `WORK100` es el código estable del tipo «Asistencia»
   de Odoo y es el que usa esta base SimpleDigital (verificado: el tipo con
   `code = WORK100` se llama «Attendance»/«Asistencia», `is_leave = False`).
2. **Respaldo acotado** — si no hay ninguna línea con ese código, se aceptan las
   líneas cuyo **Tipo y Descripción** normalicen ambos a «asistencia» /
   «attendance» (sin tildes, espacios colapsados, minúsculas).
3. Se **suman sólo** esas líneas. «Fuera de contrato», licencias, permisos,
   ausencias y vacaciones quedan excluidos siempre. **Se elimina** el respaldo
   genérico que sumaba toda línea no marcada como ausencia.
4. **Formato** — entero. `6.00` → `6`. Una fracción no representable (p. ej.
   `6.5`) no se trunca: se informa `worked_days_fraction` (error) y no se
   escribe un valor engañoso.
5. **Tope 30** — el mes previsional Previred es de 30 días (la validación oficial
   exige `0 =< días =< 30` y el propio generador del proveedor acota con
   `min(30, …)`). Si la suma supera 30 se acota a 30 con la advertencia
   `worked_days_capped`.
6. **Sin fuente válida**:
   - Si **todas** las líneas con días son ausencias (p. ej. licencia médica
     todo el mes, como `SLIP/456`): el campo 13 es `0` (la persona trabajó 0
     días). Sin error.
   - Si hay días en líneas que **no** son ausencia ni asistencia (p. ej. «Fuera
     de contrato») y ninguna de asistencia: no se deduce el valor de ninguna
     otra fuente (ni días calendario, ni el rango de la liquidación, ni
     «30 − ausencias»). Se informa `worked_days_source_missing` (error), con el
     número de la liquidación y los tipos de línea en conflicto, y se bloquea la
     generación.
   - Si la liquidación no trae **ninguna** línea de días trabajados, se conserva
     el valor que haya emitido el motor (bases de prueba y motor Blueminds).
7. **Propagación** — el valor resultante se escribe en **todas** las filas del
   registro (principal y anexas). Era la causa de los 10 «Falta el campo
   obligatorio 13».

---

## 5. Versiones finales y SHA-256 por ambiente

Versiones instaladas (idénticas en los tres ambientes, verificadas en
`ir_module_module`):

| Módulo | Versión | Dev | Demo | Demo-SyS |
|---|---|---|---|---|
| `step_hr_previred` | **18.0.3.4.0** | installed | installed | installed |
| `step_hr_previred_simpledigital` | **18.0.2.1.0** | (n/a) | (n/a) | installed |
| `step_hr_previred_blueminds` | 18.0.2.0.0 (sin cambios) | installed | installed | (n/a) |

SHA-256 del código desplegado — **idéntico en Desarrollo, Demo y Demo-SyS** y
coincide con la rama `fix/previred-correcciones-2` commit `ec1f477`:

| Archivo | SHA-256 |
|---|---|
| `step_hr_previred/models/previred_extractor.py` | `92435ec88977940bb1a7e6f3aa598eb9b6abcff43032f398b5b5f9f9320a3554` |
| `step_hr_previred/models/previred_adapter.py` | `b87930364fecbef180806291b071d6697d512514b54be1f35572c9926c395193` |
| `step_hr_previred/tools/previred.py` | `d07823aa89ddcf271bde9cbf49341657ddacc84c962677217b1ea8f334579de0` |
| `step_hr_previred/__manifest__.py` | `d6521b249f117fdeadb6a8719e82104733e6298dff9e3b262a6215bf214f8601` |
| `step_hr_previred_simpledigital/models/previred_engine.py` | `0681212ded45ce1655d380642569cf9d5493f3e0b04c2acfea1eb05a89db867a` |
| `step_hr_previred_simpledigital/models/field_matrix.py` | `8b2ce520b0e83de4a37ed795a72a5427cc562bf3b30f2f806e8593722a1c2adb` (sin cambio) |

SHA-256 previo al despliegue (baseline, idéntico en los tres ambientes):
`previred_extractor.py` = `d41b7d41a91187df3165125c9ed1e434dc956e837799e6c4170170993198f1dd`;
`tools/previred.py` = `8b56f9b428c3a0eb61a433a4294a7bc2827c8b056e12ac4961ddb2e133e99ff3`;
`previred_engine.py` = `07d542a01686e8016dd66a4ccd65d773ac1484b11ae32aaa9f0f9221baee0048`.

---

## 6. Backups

Directorio: `/opt/backups/previred_cor2_20260831/` (en el servidor `odoo-new`).
Tomados el 2026-08-31 15:13–15:23 UTC, antes del despliegue. No hay ninguna
actualización de módulos concurrente en curso (verificado).

| Ambiente | Dump BD | Tamaño | Verificación `pg_restore --list` | Addons (antes) |
|---|---|---|---|---|
| Dev (`LAB_TAREAS`) | `dev_LAB_TAREAS.dump` | 19 848 344 B | 30 143 entradas | `dev_previred_addons_before.tgz` (150 734 B) |
| Demo (`STEPS_DEMO`) | `demo_STEPS_DEMO.dump` | 22 848 812 B | 29 613 entradas | `demo_previred_addons_before.tgz` (150 288 B) |
| Demo-SyS (`STEPS_DEMO_SYS`) | `demosys_STEPS_DEMO_SYS.dump` | 24 233 017 B | 25 553 entradas | `demosys_previred_addons_before.tgz` (154 353 B) |

Cada dump es `pg_dump -Fc` (formato custom, restaurable con `pg_restore`). El
directorio también conserva `backup.log`, `deploy.log`, `*_apply.log`,
`sha_after.txt` y los SHA-256 previos.

---

## 7. Resultado de las pruebas automatizadas

Base desechable `STEPS_DEMO_SYS_cor2` (restaurada de la copia previa a la
cancelación de las liquidaciones, con el módulo instalado). Suite completa
`--test-tags=/step_hr_previred`, **misma base**, código sin parche vs. con parche:

| | Baseline (sin parche) | Con parche |
|---|---|---|
| Tests ejecutados | 83 | **101** (+18 nuevos) |
| Fallos | 2 | **0** |
| Errores | 4 | 4 |

- Los **4 errores son idénticos** con y sin el parche y son **drift de esquema
  de la base desechable**, ajenos a este cambio:
  `test_v98_cost_center_uses_code_or_name_from_contract`,
  `test_v98_uses_only_attendance_for_worked_days`,
  `test_v98_workday_type_comes_from_calendar_configuration` y
  `setUpClass TestPerformance` — todos fallan al crear `hr.employee` /
  `hr.contract` por columnas que la copia (dump de las 15:00) no tiene
  (`hr_employee.meal_distribution_mode` y afines).
- El parche **corrige** 2 fallos que el baseline tenía en esa misma base
  (`test_v98_enriches_reform_fields_from_taxable_income`,
  `test_consolidated_txt_preserves_engine_rows_verbatim`), ambos por el tope de
  30 días.
- Los **18 casos nuevos** (`test_correcciones2.py`) pasan: campo 13 = 6 con
  Asistencia 6 + Fuera de contrato 12; suma sólo líneas de asistencia; excluye
  licencia/permiso/ausencia/vacaciones/fuera de contrato; línea positiva sin
  código de asistencia no entra; sin línea válida ⇒ error funcional; `6.00` → `6`;
  fracción ⇒ error sin truncar; mes completo de licencia ⇒ `0`; mismo valor en
  principal y anexas; paridad TXT / departamento; dos contratos ⇒ dos
  principales; un contrato ⇒ error; dos contratos y tres principales ⇒ error;
  anexas no cuentan como contrato; mismo RUT en dos compañías ⇒ separado; otro
  período ⇒ no suma principal; liquidación cancelada ⇒ no amplía el cupo;
  correlación ambigua ⇒ error explícito.
- `step_hr_previred_simpledigital` (unidad, `TestSimpleDigitalMatrix`):
  13/15 pasan. Los 2 fallos (`test_no_duplicate_previred_export_menus`,
  `test_vendor_menu_points_at_the_steps_wizard`) son de estado de menús de la
  copia desechable, no de este cambio (no se tocó ningún hook ni menú).

Pendiente: correr los 3 `test_v98_*` y `TestPerformance` en una base sin drift
(clon de la BD viva) — no bloquean el criterio de término porque fallan igual
sin el parche y por causa ajena.

---

## 8. Evidencia funcional antes/después en Demo-SyS

Reproducción del lote del documento: compañía 7 «Servicios Emca SpA»,
período 2026-07, perfil «Previred largo variable v84 — Simpledigital»
(`verify, done, paid`), 78 líneas principales + 10 anexas.

| | ANTES (código base) | DESPUÉS (parche) |
|---|---|---|
| `missing_mandatory` (campo 13) | **10** | **0** |
| `duplicate_worker` (RUT 10······-3) | **1** | **0** |
| `worked_days_source_missing` | 0 | 0 (`SLIP/456` → campo 13 = `0`) |
| `movement_date_to_required` (fuera de alcance) | 2 | 2 |
| Advertencia `dropped_not_eligible` | 1 | 1 |
| **Total errores** | **13** | **2** |

- El lote #32 registrado en Demo-SyS el 2026-08-29 20:42 (`step_previred_batch`
  id 32) tiene exactamente **11 errores** (`missing_mandatory`,
  `duplicate_worker`, `dropped_not_eligible`): esos 11 son los que el parche
  elimina. Los 2 `movement_date_to_required` no están entre los 11, no son una
  de las dos causas del encargo, y en el lote #32 ya no aparecían: se corrigieron
  por datos (faltaba «Fecha Hasta» en dos anexas de movimiento) entre las 20:40
  y las 20:42 de esa noche. La copia desechable parte del dump de las 15:00, que
  aún los tiene.

### `SLIP/491` (María Riquelme Zapata, RUT 10······-3)

- Líneas de días trabajados: Asistencia (`code = WORK100`) **6**; Fuera de
  contrato (`code = OUT`) 12.
- Contrato `205` vigente 2026-07-13 → 2026-07-18.
- **Campo 13 resultante = `6`** (antes habría sido 18 por el respaldo genérico).
  El valor se escribe también en las 2 líneas anexas del trabajador.

### Caso de dos contratos (RUT 10······-3)

- `DESPUÉS`: dos líneas principales válidas:
  - `SLIP/491`, contrato `205`, campo 13 = `6`.
  - `SLIP/475`, contrato `171`, campo 13 = `5`.
- Sin `duplicate_worker`. Cada registro queda vinculado a su contrato
  (`contract_id` interno, no exportado).

### TXT de prueba

_(Generación y verificación de columnas/CRLF/codificación/importes/anexas —
sección 10, tras el despliegue y desde la interfaz web con un usuario
autorizado.)_

---

## 9. Diferencias justificadas entre ambientes o motores

- **SimpleDigital** (Demo-SyS): el campo 13 lo recalcula el núcleo desde la
  línea de asistencia; el valor de `_dias_trabajados_previred()` del proveedor
  **no** se usa. La correlación línea↔contrato la aporta el bridge.
- **Blueminds** (Desarrollo/Demo): mismo tratamiento del campo 13 desde
  `worked_days_line_ids`; si la liquidación no trae detalle de días se conserva
  el valor del motor. El bridge Blueminds no aporta `row_meta`, así que la
  unicidad usa el respaldo por compañía + período + RUT (Blueminds no maneja
  múltiples contratos por trabajador en un período).
- Ningún cambio es exclusivo del proveedor en el núcleo: el core sólo conoce
  `hr_payroll`.

---

## 10. Estado de servicios, HTTP, logs y despliegue

Despliegue secuencial el 2026-08-31, `/opt/backups/previred_cor2_20260831/deploy.log`:

| Paso | Dev (15:27) | Demo (15:28) | Demo-SyS (15:28–15:29) |
|---|---|---|---|
| Directorio de código intacto (dueño/permiso) | sí | sí | sí |
| `manifest` en disco | 18.0.3.4.0 | 18.0.3.4.0 | 18.0.3.4.0 |
| Actualización de módulos (`-u`, offline) | rc=0 | rc=0 | rc=0 |
| `systemctl restart` + `is-active` | active | active | active |
| HTTP `GET /web/login` | 200 | 200 | 200 |
| `latest_version` en BD (`step_hr_previred`) | 18.0.3.4.0 | 18.0.3.4.0 | 18.0.3.4.0 |
| `latest_version` en BD (`step_hr_previred_simpledigital`) | — | — | 18.0.2.1.0 |
| CRITICAL / Traceback en el `-u` y en `journalctl` | ninguno | ninguno | ninguno |

- Sólo se reinició el servicio de cada ambiente. No se actualizó ningún otro
  módulo. No se ejecutaron correos, pagos, contabilizaciones ni acciones
  externas. No hubo migración de datos (el cambio no añade campos de BD; el
  `contract_id` del registro es sólo en memoria).
- Aviso de arranque **preexistente y ajeno** en Dev y Demo:
  `Some modules are not loaded … ['steps_api']`. Aparece en cada arranque de
  esos instances desde antes de este trabajo; no tiene relación con PreviRed.

### Prueba funcional post-despliegue (Demo-SyS en vivo, código desplegado)

Reproducción del dataset para compañía 7 / 2026-07 sobre `STEPS_DEMO_SYS` con
el código ya desplegado: **0 errores**, 2 advertencias
(`no_eligible_payslips`, `engine_empty`) porque las 78 liquidaciones de julio
2026 de esa compañía **siguen canceladas** (desde el 2026-08-30 20:01). El
código carga y ejecuta sin excepción. La validación con datos reales (11 → 0,
`SLIP/491` = 6, dos contratos) se hizo sobre la copia desechable
`STEPS_DEMO_SYS_cor2` restaurada al estado previo a la cancelación (sección 8);
para repetirla en vivo hay que reactivar esas liquidaciones (decisión de
negocio).

### Prueba desde la interfaz web con un usuario autorizado

Pendiente: requiere que un usuario con permiso de generación abra el asistente
Previred en Demo-SyS. El endpoint responde (HTTP 200 en `/web/login`) y el
código del asistente se cargó sin error en el arranque. No se pudo automatizar
el login de un usuario real desde esta sesión sin manejar credenciales.

### Limpieza

Bases desechables `STEPS_DEMO_SYS_cor2` y `STEPS_DEMO_SYS_cor2b` eliminadas
tras conservar los resultados. Los backups de la sección 6 se conservan.

---

## 11. Pendientes y riesgos reales

1. **Otra sesión activa en el repo.** Durante este trabajo aparecieron en el
   árbol local `C:\Users\tito4\Documents\Odoo` cambios nuevos de **tesorería** y
   **maquinaria** (docs y módulos fechados 2026-08-30/31) que **no** son de
   PreviRed. Indican otra sesión (Codex u otra) trabajando el mismo repo. El
   commit de PreviRed está aislado a `step_hr_previred*` + 2 docs; no se mezcló
   nada. Conviene coordinar antes de fusionar ramas.
2. **`SLIP/456` (RUT 15······-3)** tiene el mes completo en «Licencia Médica» y
   ninguna línea de asistencia. El parche informa campo 13 = `0` sin bloquear.
   Si el negocio esperaba días trabajados ahí, es un dato a revisar en la
   liquidación, no en el código.
3. **Dos `movement_date_to_required`** (RUT 10······-3 y 12······-4) en el
   snapshot de las 15:00: anexas con movimiento de personal código 5 sin «Fecha
   Hasta». Fuera del alcance de estas dos correcciones; ya resueltas por datos
   en Demo-SyS antes del lote #32.
4. **Liquidaciones de julio 2026 de la compañía 7 canceladas** en Demo-SyS el
   2026-08-30 20:01 (todas, 78+). La validación funcional se hizo sobre una copia
   desechable restaurada al estado previo; **no se modificó** `STEPS_DEMO_SYS`.
   Si se quiere volver a probar en la base viva hay que reactivar esas
   liquidaciones (decisión de negocio).
5. **Base desechable con drift de esquema**: impidió correr 3 `test_v98_*` +
   `TestPerformance`. Fallan igual sin el parche; conviene reejecutarlos en un
   clon de la base viva para cerrar el punto formalmente.
6. **`previred_txt.py` del proveedor** (`/opt/rrhh/l10n_cl_simpledigital_payroll`)
   está sin versionar en su repo y fue modificado el 2026-08-29 15:01. No se
   tocó, pero su selección interna de liquidaciones (`search(..., limit=1)` por
   empleado) sigue siendo frágil; el bridge la neutraliza para la correlación de
   contratos pero no la corrige en el proveedor.
7. **`git push`**: no se hizo, según lo indicado. La rama
   `fix/previred-correcciones-2` queda local en `C:\Users\tito4\Documents\Odoo`
   con los commits `1a72fff` (consolidación del working tree previo),
   `e33ee7c`, `035ae5a`, `ec1f477` (esta corrección) y el commit de este
   informe.

---

## 12. Estado frente al criterio de término

| Criterio | Estado |
|---|---|
| Pruebas nuevas y de regresión sin fallos ni errores | **Parcial.** 0 fallos; los 4 errores restantes son drift de esquema de la base desechable, idénticos con y sin el parche. Falta reejecutarlos en un clon de la base viva. |
| `SLIP/491` entrega 6 en el campo 13 | **Sí.** |
| Dos contratos válidos ⇒ dos líneas principales; mismo contrato duplicado ⇒ bloqueado | **Sí.** |
| TXT real de prueba sin los 11 errores de las dos causas | **Sí** (13 → 2; los 2 restantes, `movement_date_to_required`, no son de estas causas ni están entre los 11 del lote #32). Falta generar y descargar el archivo desde la interfaz. |
| Los tres ambientes con el release previsto y los servicios respondiendo | **Sí.** 18.0.3.4.0 / 18.0.2.1.0, HTTP 200, sin errores en logs. |
| No se alteraron bases, integraciones ni datos fuera del alcance | **Sí.** Sólo se reiniciaron los 3 servicios; sin migración; los cambios de tesorería/maquinaria del árbol local no se tocaron ni se commitearon con esto. |
