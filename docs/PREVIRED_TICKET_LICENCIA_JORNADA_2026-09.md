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
| e | **El "+RIMA" aplica SOLO a SIS (29) y Expectativa de Vida (94), NO a Mutual** (usuario, 2026-09-08, resolviendo el conflicto tickets #13 vs #15). Mutual (97/98) = imponible del mes × tasa de la empresa, sin RIMA. Cuando días trabajados = 0, la base SIS/CEV es RIMA (imponible del mes ≈ 0) y la base Mutual también ≈ 0 (o 0 por la regla de los 30 días). |

### Lo que falta cerrar antes de codificar

1. **Valor del IMM por período** para el tope de gratificación (`4,75 × IMM ÷ 12`).
   **Confirmado (usuario, 2026-09-07):** IMM agosto 2026 = **553.553** (el
   valor que nombra el propio error de PreviRed). Codificar `imm(period)`
   análoga a `life_expectancy_rate` con `202608 → 553553` y bloquear con
   hallazgo auditable los períodos no cubiertos.
2. **Identificación de «licencia médica»** entre las líneas de ausencia de la
   liquidación (distinguirla de vacaciones y permisos): ¿por `code` del
   `hr.work.entry.type`, por marca en el tipo, o por rótulo?
   **Pendiente:** el usuario revisará en `demo-sys` / `desarrollo` qué
   `hr.work.entry.type` usa la base para licencia médica antes de implementar.
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

## 2.bis Ticket relacionado — Cotización Mutual con licencia médica parcial

**Origen:** correo «Ticket, error en accidentes laborales» (2026-09-08) +
recibo de nómina adjunto.

**Caso:** EMCA, agosto 2026, Celestina Peñaloza Medina (RUT 12359103-8).
Auxiliar de Aseo, contrato indefinido desde 2018. Días del mes: **19 de
asistencia + 12 de licencia médica** (mes parcial, no días = 0).

| Concepto (recibo) | Monto |
|---|---|
| Sueldo Base (19 días) | 350.584 |
| Gratificación Legal Art. 50 | 87.646 |
| **Sueldo imponible** | **438.229** |

* Tasa Mutual de la empresa: **0,93 %**.
* `438.229 × 0,93 % = 4.075,53` ⇒ **4.076** (valor correcto que indica el
  cliente).
* El sistema informa **4.159**, que equivale a una base de
  `4.159 ÷ 0,0093 ≈ 447.204`, es decir **≈ 8.975 más** que el sueldo
  imponible.

**Conclusión:** la Renta Imponible Mutual (campo 97) debe ser el **sueldo
imponible de la liquidación** (438.229) — que ya refleja sólo los días
trabajados y la gratificación proporcional — y el campo 98 = campo 97 ×
tasa Mutual de la empresa. En un mes de licencia **parcial** no se agrega
RIMA ni subsidio a la base Mutual (a diferencia del SIS y la CEV). El motor
está inflando la base ~8.975 por los 12 días de licencia.

**Resuelto el punto pendiente (archivo de revisión EMCA 202608, fila
RUT 12359103-8):**

| Campo | Valor en el archivo | Correcto | Estado |
|---|---|---|---|
| 97 Renta Imponible Mutual | `438229` | 438229 | ✅ correcto (= GROSS, bajo el tope AFP) |
| 98 Cotización Acc. Trabajo Mutual | `4159` | 4076 | ❌ (438229 × 0,93 % = 4.075,53 → 4.076) |

El **campo 97 está bien**. El errado es el **campo 98**, y **no lo calcula
el exportador**: según `step_hr_previred_simpledigital/models/field_matrix.py`
línea 114, el campo 98 se toma tal cual de la línea de nómina con código
**`APORTE_MUTUAL`**. Es decir, la regla salarial `APORTE_MUTUAL` del motor de
nómina devolvió 4.159 en vez de 4.076 para esta trabajadora (mes con 12 días
de licencia médica). El resto de los trabajadores del archivo cuadran exacto
a `imponible × 0,93 %`.

Base implícita del 4.159 = `4.159 ÷ 0,0093 ≈ 447.204`, unos **8.975 más** que
el imponible reportado (438.229) — el equivalente a cargar Mutual también
sobre una porción de los 12 días de licencia. Fernando indica que el valor
correcto es sólo `imponible_trabajado × tasa` (4.076), sin porción de
licencia.

### Dónde se corrige

`APORTE_MUTUAL` es una **regla salarial del motor de nómina de terceros**
(`l10n_cl_simpledigital_payroll` / `l10n_cl_hr`), que **no está en este
repositorio** — vive en el `addons_path` del servidor. Opciones:

1. **Corregir la regla en el motor** (servidor). Requiere acceso al módulo
   del proveedor y su despliegue propio.
2. **Override desde un módulo Steps.** Hay precedente: `step_hr_previred_
   simpledigital/hooks.py` ya sobre-escribe `condition_python` de reglas del
   proveedor (`apply_salary_rule_overrides`, caso tipo 3). Se puede extender
   para forzar `APORTE_MUTUAL` = `round(renta_imponible_mutual × tasa_mutual_
   empresa)`. Corrige la liquidación **y** el TXT, con el flujo de despliegue
   de este repo.
3. **Red de seguridad en el exportador**: `step_hr_previred` normaliza el
   campo 98 = campo 97 × tasa de la empresa cuando son inconsistentes. Sólo
   arregla el TXT, no la liquidación.

**Regla confirmada (usuario, 2026-09-08):** Mutual va sólo sobre el imponible
trabajado, sin RIMA, también en licencia parcial (ver fila `e` de la tabla de
arriba). Por lo tanto el campo 98 = `round(renta_imponible_mutual × tasa_
mutual_empresa)` sin más matices.

**Falta para implementar la opción 2:** acceso a la base de nómina (`:8070`)
para leer el `amount_python_compute` y el `xmlid` de la regla `APORTE_MUTUAL`,
y ubicar en qué campo/registro vive la tasa Mutual de la empresa
(¿`res.company`, una mutualidad, `previred_indicator`?).

**Además:** este recibo resuelve el punto 2 de arriba — el tipo de entrada de
licencia médica en esta base aparece rotulado **«Licencia Médica»**
(coincidencia por rótulo `licencia`; el `code` técnico sigue por confirmar).

## 3. Verificación de este corte

* `python -m py_compile` de los archivos tocados: _(ver commit)_.
* Suite `--test-tags=/step_hr_previred` en `odoo-new`: **pendiente** (no se
  corrió; el entorno local no la levanta).
* No se tocó ningún ambiente (`demo`, `desarrollo`, `demo-sys`, `SyS`).

## 4. Respuestas del cliente — tickets Helpdesk #17 y #18 (2026-09-08)

Dos casos nuevos de licencia médica, con archivo de revisión de PreviRed y
valores esperados. El cliente respondió las preguntas abiertas del corte 2.

### 4.1 Ticket #17 — Somed, Carolina Medel (RUT 17.932.663-9), agosto 2026

Mes **completo** de licencia médica (campo 13 = 0). Licencia continua
20-07 → 31-08 (~43 días corridos). El motor **sí** informa la RIMA en el
campo 92.

Respuestas del cliente:

1. La base 1.205.761 **es la RIMA**: como todo agosto está con licencia, el
   imponible del mes es 0 y la RIMA se calcula porque el mes anterior tampoco
   se trabajó completo ⇒ RIMA = sueldo base del contrato + gratificación
   (rama a' del punto 2).
2. **La misma base** (1.205.761) para SIS (29), CEV (94), Rentabilidad
   Protegida (95) y AFC empleador (102). El ticket #18 agrega ISL (71) y
   Renta Imponible Seguro Cesantía (100).
3. La base es **sólo** 1.205.761. El valor 81.148 es la **suma** de las
   cotizaciones patronales a pagar, no un campo aparte
   (21.463 + 8.681 + 10.852 + 11.214 + 28.938 = 81.148).
4. Campo 71 (ISL): con 12 días en julio y 18 en agosto, correspondería
   prorratear, pero **para simplificar el cliente carga todo agosto al
   empleador** ⇒ campo 71 = 1.205.761 × 0,93 % = 11.214.
5. El +40.196 que el motor sumaba a la base de SIS/AFC es **un error del
   motor**. El recálculo del exportador lo corrige sin tocar :8070.

Valores esperados (base 1.205.761):

| Campo | Motor | Correcto | Tasa |
|---|---|---|---|
| 29 SIS | 22.178 | **21.463** | 1,78 % |
| 71 Acc. Trabajo ISL | 362 | **11.214** | 0,93 % |
| 94 Expectativa de Vida | 8.681 | 8.681 | 0,72 % |
| 95 Rentabilidad Protegida | 0 | **10.852** | 0,90 % |
| 100 Renta Imp. Seg. Cesantía | 1.205.761 | 1.205.761 | — |
| 102 AFC empleador | 29.903 | **28.938** | 2,4 % |

### 4.2 Ticket #18 — Servicio de Bienestar, Valentina Parada (RUT 18.656.818-4)

Mes **parcial**: 11 días trabajados (imponible propio 192.500) + licencia
médica 22-07 → 20-08 (20 días de agosto). El motor **no** informa la RIMA.

RIMA pedida por el cliente = (sueldo base 420.000 + gratificación 105.000) ÷
30 × 20 días de licencia del mes = **350.000**.

Base = imponible del mes 192.500 + RIMA 350.000 = **542.500**.

| Campo | Correcto | Tasa |
|---|---|---|
| 29 SIS | 9.657 | 1,78 % |
| 71 Acc. Trabajo ISL | 5.045 | 0,93 % |
| 92 RIMA | 350.000 | (calcular en el motor) |
| 94 Expectativa de Vida | 3.906 | 0,72 % |
| 95 Rentabilidad Protegida | 4.883 | 0,90 % |
| 100 Renta Imp. Seg. Cesantía | 542.500 | — |
| 102 AFC empleador | 13.020 | 2,4 % |
| 97 Renta Imponible Mutual | 0 | (cotiza en INP/ISL) |

Correcciones al TXT que pide el ticket #18 y **no** cubre este corte:
campo 13 de la línea anexa = 0; campo 71 de la línea anexa = 0; campo 97 = 0.

### 4.3 Qué implementa `18.0.3.8.0`

`_set_medical_leave_bases` recalcula 29/71/94/95/100/102 sobre
`campo 27 + campo 92` **cuando el motor ya informó la RIMA** (caso #17). Para
el caso #18 (motor sin RIMA) deja el hallazgo `medical_leave_rima_missing`:
falta el cálculo de la RIMA en sí.

### 4.4 Qué sigue pendiente para cerrar el corte 2

* **Cálculo de la RIMA cuando el motor no la informa** (ticket #18): leer
  sueldo base del contrato + gratificación legal (`min(25 % devengado,
  4,75 × IMM ÷ 12)`, IMM ya en `minimum_wage`), contar los días de licencia
  del mes, y decidir entre la rama a (liquidación previa completa) y la a'
  (mes previo también con licencia). Requiere datos de contrato/liquidación
  que esta automatización no puede validar contra la base real (:8070 / SyS).
* **Conflicto de alcance del «+RIMA».** El punto 2 fila `e` decía «sólo SIS
  (29) y CEV (94)»; los tickets #17 y #18 lo extienden a 71, 95, 100 y 102.
  Se asume la lista extendida (la mutualidad 97/98 sigue **sin** RIMA).
  Confirmar con el usuario.
* **Tasa AFC del campo 102**: 2,4 % indefinido / 3,0 % plazo fijo. El
  recálculo la deriva de `contract.date_end`; validar en casos reales.
* **Líneas anexas**: el ticket #18 pide campo 13 y campo 71 de la anexa = 0.
  El recálculo sólo toca la línea principal; los campos de la anexa se
  entregan tal cual del motor.
* **`hr.work.entry.type` de licencia médica**: sigue identificándose por
  rótulo; el `code` técnico no está confirmado.

## 5. Confirmado contra datos reales de SyS (solo lectura, 2026-09-08)

Con la key de SyS (`https://sys.stepsapp.cl`, db `SyS`) en modo **solo
lectura** se revisaron las liquidaciones reales. Cierra varios puntos
abiertos del §2:

### 5.1 Identificación de la licencia médica (punto 2)

`hr.work.entry.type`: la licencia médica es el código **`LIC`**
(«Licencia Médica», `is_leave = True`); accidente del trabajo es **`ACCTR`**.
Ambos son deterministas por `code`. `_is_medical_leave_entry` los reconoce
por código y, de respaldo, por `is_leave` + nombre que contenga «licencia».

### 5.2 RIMA — cómo la calcula hoy el motor y qué falta

* **Carolina Medel (Somed), agosto 2026** — `hr.payslip` SLIP/689, estado
  `verify`. `worked_days`: `LIC` 30 días, `WORK100` 0. Línea `SUBSIDIO` =
  **1.205.761** = `BASIC` 986.646 (sueldo contrato) + `GRAT50` 219.115
  (gratificación **topada** al IMM: `4,75 × 553.553 ÷ 12 = 219.114,73`; el
  25 % daría 246.661). `GROSS` = 0 (imponible del mes). El motor sí emite la
  RIMA (campo 92). Las cotizaciones patronales del motor están sobre una base
  inflada: SIS 22.178 ⇒ base implícita `22.178 ÷ 0,0178 ≈ 1.245.955`
  (**+40.194** sobre 1.205.761, el «error del motor» que menciona el
  cliente); `RENT_PROT` = 0; `APORTE_MUTUAL` (línea de accidente) = 362.
* **Valentina Parada (Serv. Bienestar), agosto 2026** — SLIP/671, estado
  `done`. `worked_days`: `LIC` 20 días, `WORK100` 11. Contrato `wage` =
  420.000. `BASIC` = 154.000 (11/30), `GRAT50` = 38.500, `GROSS` = 192.500.
  **No hay línea `SUBSIDIO`**: el motor no emite la RIMA (campo 92 vacío).
  Julio fue mes completo de licencia y junio tuvo 9 días de licencia, así que
  no hay «mes anterior trabajado completo» del que tomar la renta imponible.

### 5.3 Fórmula de la RIMA (implementada en `18.0.3.8.0`)

```
gratificación = min(0,25 × wage, 4,75 × IMM(período) ÷ 12)
RIMA          = (wage + gratificación) / 30 × días_licencia_médica_del_mes
```

Comprobación con los dos casos reales:

| Trabajadora | wage | gratificación | días lic. | RIMA | Coincide con |
|---|---|---|---|---|---|
| Carolina Medel | 986.646 | 219.114 (tope IMM) | 30 | **1.205.761** | línea `SUBSIDIO` + campo 92 del archivo de revisión |
| Valentina Parada | 420.000 | 105.000 (25 %) | 20 | **350.000** | valor pedido en el ticket #18 |

### 5.4 Lo que sigue pendiente

* **Rama a (mes anterior trabajado completo).** Ninguno de estos dos casos la
  ejercita (ambos son rama a': mes previo con licencia). Para Carolina la
  fórmula coincide con la renta imponible de junio (mes completo), así que
  para licencia de mes completo ambas ramas convergen; sólo divergirían si el
  mes previo tuvo horas extra o bonos. Confirmar con el usuario si en ese
  caso la RIMA debe ser la renta imponible real del mes previo.
* **Tasa AFC del campo 102** (2,4 % / 3,0 %): sigue derivándose de
  `contract.date_end`. Ambos contratos reales son indefinidos (`date_end`
  vacío) ⇒ 2,4 %, que es lo que esperan los tickets.
* **Líneas anexas** (ticket #18: campo 13 y campo 71 de la anexa = 0) y
  **campo 97 = 0 para quien cotiza en INP**: aún no cubiertos por el
  recálculo, que sólo toca la línea principal.
* **Aplicación y verificación**: SyS es solo lectura para esta automatización
  (no hay autorización de escritura en chat, ni dry-run en demo-sys, ni
  respaldo). `step_hr_previred` en SyS está en 18.0.3.6.0 y no hay ruta de
  deploy de código documentada. La rama queda para que una persona la
  despliegue, regenere el TXT de Somed y de Serv. Bienestar y compare.
