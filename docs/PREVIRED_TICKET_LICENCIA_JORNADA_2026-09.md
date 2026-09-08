# Tickets PreviRed 2026-09 — Licencia médica y Tipo de Jornada

**Módulo:** `step_hr_previred` · **De:** `18.0.3.6.0` → **A:** `18.0.3.7.0` (parcial)
**Fecha:** 2026-09-07 · **Rama:** `correo/20260907-previred-licencia-jornada`
**Origen:** correos de fcaro.ruiz@gmail.com del 2026-09-07
(«Ticket, imposiciones Licencia médica», «Ticket, error líneas Previred»,
respuestas del usuario «Pregunta de IA» + `Tipos de Jornadas 07-09-26.docx`).
**No desplegado.** Requiere corrida de la suite en `odoo-new` y validación
funcional antes de tocar cualquier ambiente.

## 1. Corregido en `18.0.3.7.0`

### 1.1 Tasa CEV (campo 94) = 0,72 % desde 2026-08

`tools/previred.py::life_expectancy_rate` devolvía `1.00` para períodos
`>= 202608`. El usuario confirma que la tabla previsional de agosto 2026 fija
la Cotización Expectativa de Vida en **0,72 %**.

Verificación (caso RUT 14250811-7, RIMA = 673.750):
`673.750 × 0,72 % = 4.851` — coincide exacto con el valor esperado por
PreviRed. Con la tasa anterior daba `6.738`.

Prueba: `test_spec.py::test_reform_rate_schedule`.

### 1.2 Tipo de Jornada (campo 93): parcial si jornada semanal < 40 h

`models/previred_extractor.py::_enrich_official_fields`. Cambios:

* Fuente de horas: «Tiempo completo de la empresa»
  (`resource.calendar.full_time_required_hours`), con `hours_per_week` como
  respaldo. Antes se priorizaba `hours_per_week`.
* Umbral: `< 40 h` ⇒ tipo 2 (parcial). Antes era `<= 30 h`.
* `resource.calendar.previred_workday_type` explícito mantiene precedencia.

Caso EMCA agosto 2026, RUT 12588103-3 (KAREN FLIES), calendario «Jornada
parcial 24 horas» (`full_time_required_hours = 24`): salía tipo 1 y PreviRed
rechazaba el campo 27 con «Renta Imponible AFP (campo 27) no corresponde al
mínimo legal» (enviado 525.000, esperado 553.553). Con jornada parcial
declarada, PreviRed acepta una renta imponible bajo el mínimo legal.

Pruebas: `test_dataset.py::test_workday_type_part_time_under_40_hours_is_partial`,
`::test_workday_type_40_hours_is_full`.

## 2. Pendiente — RIMA en licencia médica (campos 92, 29, 94, 97, 98)

Reglas confirmadas por el usuario:

| # | Regla |
|---|---|
| d | Aplica **sólo** cuando el campo 13 (Días Trabajados) es 0 (mes completo de licencia). |
| a | RIMA (campo 92) = renta imponible AFP de la última liquidación válida **anterior al inicio de la licencia**, si ese mes se trabajó completo y **sin** licencia. |
| a' | Si el mes anterior **también** tuvo licencia: RIMA = sueldo base del contrato + gratificación legal, con gratificación = `min(25 % de lo devengado, 4,75 × IMM ÷ 12)`. |
| — | SIS (campo 29) = RIMA × 1,78 %. |
| — | CEV (campo 94) = RIMA × 0,72 % (ya en 1.1). |
| c | Mutual (campos 97 y 98) = 0 cuando hay ≥ 30 días **continuos** (corridos) de la misma licencia médica, contando la continuación de licencias de meses anteriores. |

### Lo que falta cerrar antes de codificar

1. **Valor del IMM por período** para el tope de gratificación (`4,75 × IMM ÷ 12`).
   La tabla previsional del mes lo tiene; hay que transcribir el/los valores
   vigentes (¿`553.553` que nombra el propio error de PreviRed, u otro?) a
   una función `imm(period)` análoga a `life_expectancy_rate`, con su fuente.
   Mientras no esté confirmado, la rama a' debe bloquear con un hallazgo
   auditable en vez de calcular con un número supuesto.
2. **Identificación de «licencia médica»** entre las líneas de ausencia de la
   liquidación (distinguirla de vacaciones y permisos): ¿por `code` del
   `hr.work.entry.type`, por marca en el tipo, o por rótulo? Se necesita el
   criterio estable de la base.
3. **Liquidación anterior**: buscar en `hr.payslip` la del mismo
   empleado/contrato del período `dataset.period − 1 mes`, estados válidos
   (`done`, `paid`); si no existe, ¿se bloquea o se cae a la rama a'?
4. **Continuidad de la licencia** entre meses: contar días corridos de la
   misma licencia sumando las líneas de licencia de liquidaciones anteriores
   consecutivas. Confirmar si «misma licencia» = mismo tramo continuo de
   reposo (fechas encadenadas) o mismo diagnóstico.
5. ¿Se tocan sólo la línea principal (`00`) o también las anexas? El error de
   PreviRed del RUT 14250811-7 estaba en «línea 5» (anexa).

### Esbozo de implementación (para el corte 2)

* `tools/previred.py`: constantes `F_RIMA = 92`, `F_MUTUAL_TAXABLE = 97`,
  `F_MUTUAL_CONTRIBUTION = 98`; helpers `sis_rate(period)` → `"1.78"` e
  `imm(period)` (con la tabla del punto 1).
* `models/previred_extractor.py`: método nuevo
  `_set_medical_leave_bases(record, payslip, dataset)` llamado desde
  `_enrich_official_fields` tras `_set_worked_days`, con el mismo patrón de
  hallazgos trazables y sin recalcular la nómina fuera de estas reglas.
* Pruebas con los números exactos del RUT 14250811-7: RIMA 673.750 ⇒
  campo 29 = 11.993, campo 94 = 4.851, campos 97 y 98 = 0 (60 días de
  licencia acumulada).

## 3. Verificación de este corte

* `python -m py_compile` de los archivos tocados: _(ver commit)_.
* Suite `--test-tags=/step_hr_previred` en `odoo-new`: **pendiente** (no se
  corrió; el entorno local no la levanta).
* No se tocó ningún ambiente (`demo`, `desarrollo`, `demo-sys`, `SyS`).
