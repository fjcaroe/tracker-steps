# PreviRed correcciones 2 — Auditoría previa

**Estado: AUDITORÍA PREVIA. No se ha modificado código, no se ha conectado a
servidores, no se ha desplegado.** Este documento NO es el informe de evidencias
final (`PREVIRED_CORRECCIONES_2_EVIDENCIA_2026-08-29.md`), que sólo debe
generarse cuando el trabajo esté verificado.

Fecha: 2026-08-29
Fuente funcional: `A10.1 ERP agrícola, Nómina, mejoras a módulo estándar Chile,
Previred, correcciones 2.docx` (revisado: texto + 2 imágenes sustantivas — lista
de 11 errores y liquidación `SLIP/491`).

RUT enmascarados en todo el documento (se conserva sólo el dígito verificador).

---

## 1. Qué pide el documento funcional

- **Campo 13 «Días trabajados»**: debe venir de la liquidación, de la línea
  Tipo = *Asistencia* / Descripción = *Asistencia*, valor = número de días.
  Ejemplo `SLIP/491` (María Riquelme Zapata, periodo 07/2026):
  - Asistencia / Asistencia = **6,00**
  - Fuera de contrato / Fuera de contrato (medio día) = 12,00
  - Total mostrado = 18,00
  - **Campo 13 esperado = `6`**, no `18`, y nunca vacío si existe la línea de
    asistencia.
- **Multiplicidad por contrato**: el RUT `10·······-3` aparece con más de una
  línea principal (código `00`) en la misma compañía y periodo **porque tuvo
  dos contratos ese mes**. La regla correcta: tantas líneas `00` como contratos
  elegibles tenga el trabajador en esa compañía y periodo.

### Los 11 errores actuales (imagen del documento)

| # | RUT (enmasc.) | Error |
|---|---|---|
| 1 | 14······-6 | Falta el campo obligatorio «13 Días Trabajados» |
| 2 | 21······-9 | Falta el campo obligatorio «13 Días Trabajados» |
| 3 | 15······-3 | Falta el campo obligatorio «13 Días Trabajados» |
| 4 | 15······-3 | Falta el campo obligatorio «13 Días Trabajados» |
| 5 | 10······-3 | Falta el campo obligatorio «13 Días Trabajados» |
| 6 | 10······-3 | Falta el campo obligatorio «13 Días Trabajados» |
| 7 | 10······-3 | Falta el campo obligatorio «13 Días Trabajados» |
| 8 | 10······-3 | Aparece más de una vez con línea principal en la misma compañía y periodo |
| 9 | 12······-4 | Falta el campo obligatorio «13 Días Trabajados» |
| 10 | 12······-4 | Falta el campo obligatorio «13 Días Trabajados» |
| 11 | 92·····-8 | Falta el campo obligatorio «13 Días Trabajados» |

Advertencia (1): «Se descartaron 1 trabajador(es) que el motor entregó pero que
no corresponden a una liquidación de esta compañía en estado verify, done,
paid.»

Observación: los RUT que se repiten en la lista (…-3 ×2, …-3 ×3, …-4 ×2) son
trabajadores con más de una fila (segundo contrato o líneas anexas). El campo 13
sale ausente en **todas** sus filas.

---

## 2. Causa raíz (confirmada por lectura de código)

### 2.1 Campo 13 — valor inflado (caso `SLIP/491`)

Archivo: `step_hr_previred/models/previred_extractor.py`,
`_enrich_official_fields()` (aprox. líneas 322-336).

```python
worked_lines = payslip.worked_days_line_ids.filtered(
    lambda line: line.number_of_days > 0
    and not line.work_entry_type_id.is_leave)
attendance_lines = worked_lines.filtered(
    lambda line: line.work_entry_type_id.code == "WORK100")
source_lines = attendance_lines or worked_lines
worked_days = sum(source_lines.mapped("number_of_days"))
row[previred.F_WORKED_DAYS - 1] = str(int(Decimal(str(worked_days)).quantize(
    Decimal("1"), rounding=ROUND_HALF_UP)))
```

- En SimpleDigital las líneas de días trabajados **no usan el código
  `WORK100`** (a confirmar en el servidor cuál es el código real). Por tanto
  `attendance_lines` queda vacío y `source_lines` cae al respaldo genérico
  `worked_lines` = «toda línea con días > 0 que no sea ausencia».
- «Fuera de contrato» **no** es un tipo de ausencia (`is_leave = False`), así
  que entra en la suma: **6 (Asistencia) + 12 (Fuera de contrato) = 18**.
- Ese respaldo genérico es exactamente el que el documento manda eliminar
  (corrección 1, punto 5).

### 2.2 Campo 13 — ausente («Falta el campo obligatorio»)

Archivo: `step_hr_previred/models/previred_extractor.py`, `build_dataset()`
(líneas 111-122) y `_payslip_index()` (líneas 179-205).

```python
for record in records:
    key = previred.rut_key(record.rut + record.dv)
    entries = index.get(key) or []
    if not entries:
        continue                       # <-- se salta el registro completo
    ...
    self._enrich_official_fields(record, entry["payslip"], dataset)
```

- `_enrich_official_fields()` (que rellena el campo 13) **sólo se ejecuta si el
  registro se empareja por RUT** contra `_payslip_index()`, que indexa por
  `rut_key(payslip.employee_id.identification_id)`.
- Cuando el emparejamiento falla —RUT del motor con formato/DV distinto al
  `identification_id`, o el trabajador tiene más liquidaciones elegibles que
  filas principales, o entra en el desajuste de contratos múltiples— el
  registro **se salta**: el campo 13 nunca se rellena y queda con lo que emitió
  el generador del proveedor.
- El generador de SimpleDigital declara el campo 13 como
  `self._get_real_worked_days_from_payslip(payslip)`
  (`step_hr_previred_simpledigital/models/field_matrix.py`, pos. 13). Si ese
  método devuelve vacío/0 para esas liquidaciones (a confirmar en el servidor),
  el campo llega en blanco.
- `validate_row()` (`tools/previred.py` líneas 543-550) aplica
  `MANDATORY_FIELDS` —que incluye `F_WORKED_DAYS`— **a todas las filas del
  registro, también las anexas**. Por eso un trabajador con principal + anexa
  sin campo 13 produce 2 errores «Falta el campo obligatorio «13 Días
  Trabajados»».

### 2.3 Trabajador con dos contratos marcado como duplicado

Archivo: `step_hr_previred/tools/previred.py`, `validate_dataset()`
(líneas 750-765).

```python
key = (record.company_id, rut_key("%s%s" % (record.rut, record.dv)))
if key in seen:
    issues.append(Issue(SEVERITY_ERROR, "duplicate_worker",
        "RUT %s-%s aparece más de una vez con línea principal en la misma "
        "compañía y período." % (record.rut, record.dv), ...))
seen[key] = record
```

- La unicidad se calcula por `(company_id, rut_key)` **sin considerar el
  contrato**. Dos líneas `00` legítimas (dos contratos elegibles en la misma
  compañía/periodo) disparan `duplicate_worker`.

Refuerzan el problema:

- `_group_rows()` (líneas 130-175) es **posicional** y su comentario afirma
  explícitamente «un segundo contrato del mismo trabajador es una línea anexa,
  no una principal» — contradice el documento.
- `_enforce_eligibility()` (líneas 207-241) levanta `ambiguous_engine_rows`
  cuando `generado != esperado` por RUT; hay que hacerlo consciente del
  contrato.
- Asignación posicional de liquidaciones a registros
  (`build_dataset` líneas 116-118: `entry = entries[min(position, len-1)]`) —
  el documento (corrección 2, punto 9) prohíbe la asignación silenciosa por
  posición cuando es ambigua.

---

## 3. Diseño propuesto (no implementado)

1. **Contrato del adaptador** (`previred_adapter.EngineAdapter.generate_rows`):
   permitir que el bridge devuelva, además de las filas planas, metadata
   estructurada por fila principal:
   - `contract_id` (o clave técnica equivalente, estable, no exportada);
   - `attendance_days`: días de asistencia calculados **en el bridge** desde
     `payslip.worked_days_line_ids`, usando el identificador técnico estable de
     «Asistencia» (`work_entry_type_id.code` real de SimpleDigital); si la
     instalación no tiene código estable, respaldo acotado que exija
     conjuntamente Tipo = Asistencia y Descripción = Asistencia normalizando
     mayúsculas/espacios/tildes (documentado).
   - Compatibilidad: si un adaptador no entrega metadata, el core mantiene su
     comportamiento actual salvo el punto 3.
2. **`PreviredRecord`**: campo `contract_id` (metadata interna, no exportada).
   No cambia posiciones ni el conteo de 105 campos.
3. **Campo 13 en el core**: eliminar el respaldo genérico `worked_lines`. Usar
   la fuente explícita del bridge. Si no hay fuente válida ⇒ `Issue` de error
   preciso y auditable que identifique la liquidación de forma segura (sin RUT
   completo) y diga qué dato falta. Nunca sustituir por días calendario, rango
   de la liquidación ni total del periodo. Formato entero oficial: `6.00` → `6`;
   fracción no representable ⇒ validación explícita, sin truncar en silencio.
4. **`validate_dataset()`**: clave de unicidad
   `(company_id, period, rut_key, contract_id)`.
   - Dos principales del mismo contrato ⇒ sigue siendo error.
   - N principales > N contratos elegibles ⇒ bloquea la generación.
   - Mismo RUT en otra compañía o periodo ⇒ no es duplicado (ya se conserva).
5. **Correlación fila↔contrato determinística**: por `contract_id`; si es
   ambigua, error explícito, no asignación posicional.
6. **Anexas**: siguen contiguas a su principal; no cuentan como contrato
   adicional (ya se cumple estructuralmente, revisar con el nuevo agrupamiento).
7. **Documentación**: nota del campo 13 en `field_matrix.py`,
   `docs/PREVIRED_MATRIZ.md`, `step_hr_previred/CHANGELOG.md`.

Pruebas nuevas: las 8 de campo 13 + 8 de contratos múltiples + regresión que
lista el prompt (sección «Pruebas automatizadas obligatorias»).

---

## 4. Bloqueos que requieren decisión humana

### 4.1 La precondición «sin otra sesión activa» no se cumple / no es verificable

- El repo está en la rama **`codex/web-tracker-redesign`** (rama de trabajo de
  otra herramienta, tema no relacionado) con un gran volumen de cambios sin
  commitear en módulos ajenos: `step_account_treasury*`, `step_hr` (con
  borrados en stage), `step_bpa_irrigation` (migraciones), 
  `step_accounting_multicurrency`, `step_operations_ui`.
- Documentos hermanos con fecha de hoy: `PROMPT_CLAUDE_TESORERIA_CONTABILIDAD_2026-08-29.md`,
  `TESORERIA_RELEASE_2026-08-29.md`, `MAQUINARIA_HOMOLOGACION_2026-08-29.md`.
- **Los tres módulos `step_hr_previred`, `step_hr_previred_blueminds` y
  `step_hr_previred_simpledigital` están SIN VERSIONAR (`??`) en git.** No
  existen en ninguna rama; son archivos de working tree creados por otra sesión
  reciente y todavía sin commitear. «Correcciones 2» es la continuación de un
  trabajo (corrección 1) que aún no está consolidado en git.
- El prompt (sección «Antes de escribir», punto 1) prohíbe escribir hasta
  confirmar que no hay otra sesión / copia / restauración / despliegue activo
  sobre los mismos directorios. No puedo confirmarlo y los indicios apuntan a
  lo contrario. No hay una base git limpia desde la cual ramificar ni contra la
  cual hacer diff.

### 4.2 No hay runtime de Odoo ni addons del proveedor en local

- `python -c "import odoo"` ⇒ `ModuleNotFoundError: No module named 'odoo'`.
- `l10n_cl_simpledigital_payroll` y `l10n_cl_hr` no están en este repo; viven en
  `/opt/rrhh` de los servidores.
- Consecuencia: reproducir los 11 errores, correr la suite en una base
  desechable y validar con datos de Demo-SyS **requieren conectarse por
  `gcloud compute ssh`** a los ambientes. Todo paso sustantivo es una acción
  remota.

### 4.3 Despliegue a 3 ambientes compartidos

- Backups de BD, `pg_restore --list`, upgrade de módulos y `systemctl restart`
  en Desarrollo → Demo → Demo-SyS son acciones difíciles de revertir sobre
  infraestructura compartida.
- No se ha ejecutado `gcloud` (no se ha verificado autenticación para el
  proyecto `stepsconsulting`).
- Requiere visto bueno explícito y, por separado, confirmación de que ningún
  otro despliegue está en curso.

---

## 5. Decisiones que se necesitan para continuar

1. Confirmar que **ninguna otra sesión** (Codex / Claude / Copilot / actualización
   de módulos / despliegue) está trabajando el repo local `C:\Users\tito4\Documents\Odoo`
   ni los servidores.
2. Indicar la **base sobre la que construir**: ¿los `step_hr_previred*` sin
   commitear son la base correcta y aprobada de «corrección 1»? ¿Se debe crear
   un worktree/rama nueva y desde qué commit? ¿Se commitea primero la base?
3. **Autorización para conectarse** a los servidores GCP por SSH.
4. **Autorización de despliegue** con reinicio de servicios en los 3 ambientes
   (puede darse después, tras revisar el diff y las pruebas verdes).

---

## 6. Trabajo ya hecho en esta pasada

- Lectura completa del prompt y del documento funcional (incl. imágenes).
- Auditoría de: `tools/previred.py`, `models/previred_extractor.py`,
  `models/previred_adapter.py`, `step_hr_previred_simpledigital/models/field_matrix.py`,
  `step_hr_previred_simpledigital/models/previred_engine.py`, manifiestos y
  CHANGELOG.
- Causa raíz de los dos problemas localizada en el código (ver sección 2).
- Diseño de la corrección redactado (sección 3), pendiente de validar contra el
  código del proveedor y los datos reales en el servidor.

## 7. Pendientes / riesgos

- Confirmar en el servidor el `work_entry_type_id.code` real de «Asistencia» en
  SimpleDigital y el comportamiento de `_get_real_worked_days_from_payslip`.
- Confirmar por qué exactamente falla el emparejamiento por RUT en los 10 casos
  de campo 13 ausente (formato de RUT del motor vs `identification_id`, o
  desajuste de conteo por contratos).
- Confirmar el lote/compañía/periodo exactos del documento para reproducir los
  11 errores.
- Verificar que los otros trabajos en curso en el repo no tocan
  `step_hr_previred*` ni `hr_payroll`.
