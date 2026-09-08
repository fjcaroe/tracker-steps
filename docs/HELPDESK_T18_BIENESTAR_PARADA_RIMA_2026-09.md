# Helpdesk #18 — Servicio de Bienestar / Valentina Parada — RIMA licencia médica

**Empresa:** Sociedad de Bienestar Integral y Mantenimiento de la Salud Ltda.
**Trabajadora:** Valentina Parada Benítez — RUT 18.656.818-4
**Período:** agosto 2026 · **Base:** S&S (`http://35.222.25.110:8070/odoo`)
**Rama:** `ticket/18-bienestar-parada-rima` (sobre `ticket/17-somed-medel-licencia-medica`)
**Área:** Nómina / PreviRed — licencia médica (corte 2)

## 1. Caso

Mes **parcial**: 11 días trabajados (imponible propio 192.500) + licencia
médica 22-07-2026 → 20-08-2026 (línea anexa 01). En agosto la licencia cubre
20 días.

El motor **no** informa la RIMA (campo 92 sale vacío en el archivo de
revisión). El ticket pide calcular la RIMA en el motor y rebasar las
cotizaciones patronales.

### RIMA pedida por el cliente

Como no hay sueldo del mes anterior completo:

    RIMA = (sueldo base 420.000 + gratificación 105.000) / 30 × 20 días
         = 525.000 / 30 × 20
         = 350.000

### Base y valores esperados

Base = imponible del mes 192.500 + RIMA 350.000 = **542.500**

| Campo | Correcto | Regla |
|---|---|---|
| 29 SIS | 9.657 | 542.500 × 1,78 % |
| 71 Acc. Trabajo ISL | 5.045 | 542.500 × 0,93 % |
| 92 RIMA | 350.000 | calcular en el motor |
| 94 Expectativa de Vida | 3.906 | 542.500 × 0,72 % |
| 95 Rentabilidad Protegida | 4.883 | 542.500 × 0,90 % |
| 100 Renta Imp. Seguro Cesantía | 542.500 | imponible + RIMA |
| 102 AFC empleador | 13.020 | 542.500 × 2,4 % |
| 97 Renta Imponible Mutual | 0 | cotiza en INP/ISL, no mutual |

### Correcciones al TXT que pide el ticket

* Campo 13 de la línea anexa (01) = 0
* Campo 71 de la línea anexa (01) = 0
* Campo 97 = 0 (cotiza en INP)

## 2. Qué queda implementado (compartido con el ticket #17)

`step_hr_previred 18.0.3.8.0` — `PreviredExtractor._set_medical_leave_bases`.
Cuando el motor informa la RIMA en el campo 92, la base de 29 / 71 / 94 / 95 /
100 / 102 pasa a `campo 27 + campo 92` y cada cotización se recalcula con su
tasa estatutaria. Prueba con los números de esta trabajadora:
`test_dataset.py::test_medical_leave_partial_month_rebases_taxable_plus_rima`
(base 542.500 ⇒ 29 = 9.657, 71 = 5.045, 94 = 3.906, 95 = 4.883, 100 = 542.500,
102 = 13.020).

## 3. Qué falta para cerrar este ticket

1. **Cálculo de la RIMA en sí.** El motor no emite el campo 92 para esta
   trabajadora, así que el recálculo anterior no se dispara. Falta el «corte
   2»: leer sueldo base del contrato + gratificación legal
   (`min(25 % devengado, 4,75 × IMM ÷ 12)`; IMM ago-2026 = 553.553, ya en
   `previred.minimum_wage`), contar los días de licencia médica del mes, y
   fijar `campo 92 = 350.000`. Esto vive en la extracción, no en el motor:
   se puede hacer en `previred_extractor.py` sin tocar `:8070`.
2. **Líneas anexas.** El ticket pide campo 13 y campo 71 de la anexa = 0. El
   recálculo actual sólo toca la línea principal.
3. **Campo 97 = 0.** Confirmar que el exportador ya lo emite en 0 para quien
   cotiza en INP; si el motor lo llena, forzar 0 en este caso.
4. **Validación funcional.** No hay acceso desde esta automatización a la
   base `:8070` (motor del proveedor) ni a SyS. `demo-sys` no tiene esta
   liquidación. La rama se entrega para validar con datos reales.

## MUEVE MONTOS DECLARADOS A PREVIRED — REQUIERE VALIDACIÓN FUNCIONAL ANTES DE SyS

Supuestos: tasas estatutarias (SIS 1,78 %, ISL básica 0,93 %, CEV 0,72 %,
Rent. Protegida 0,90 %, AFC 2,4 % indefinido); la mutualidad no suma RIMA;
gratificación 105.000 = 25 % de 420.000, bajo el tope IMM; días de licencia
del mes = 20.
## 5. Confirmado contra SyS (solo lectura) — 2026-09-08 · RIMA implementada

Liquidación real de Valentina Parada en SyS (SLIP/671, agosto 2026, `done`):

- `worked_days`: `LIC` 20 días, `WORK100` 11 días.
- Contrato `wage` = 420.000 (calendario «Estándar de 9 horas a la semana»).
- `BASIC` 154.000 (11/30), `GRAT50` 38.500, `GROSS` = **192.500** (imponible
  del mes; coincide con el campo 27 del archivo de revisión).
- **No hay línea `SUBSIDIO`** — el motor no emite la RIMA. Julio fue mes
  completo de licencia y junio tuvo 9 días de licencia: no hay mes previo
  trabajado completo.

`18.0.3.8.0` ahora **calcula la RIMA** (`_compute_medical_leave_rima`):
`gratificación = min(0,25 × 420.000, 4,75 × 553.553 ÷ 12) = min(105.000;
219.115) = 105.000`; `RIMA = (420.000 + 105.000) / 30 × 20 = 350.000`.
Base = 192.500 + 350.000 = 542.500. Recálculo:

| Campo | 18.0.3.8.0 | Esperado (ticket) |
|---|---|---|
| 92 RIMA | 350.000 | 350.000 |
| 29 SIS | 9.657 | 9.657 |
| 71 ISL | 5.045 | 5.045 |
| 94 CEV | 3.906 | 3.906 |
| 95 Rent. Protegida | 4.883 | 4.883 |
| 100 R.I. Seg. Cesantía | 542.500 | 542.500 |
| 102 AFC empleador | 13.020 | 13.020 |

Prueba: `test_medical_leave_computes_rima_from_contract_when_motor_omits_it`.

### Sigue pendiente

- Líneas anexas: campo 13 y campo 71 de la anexa = 0.
- Campo 97 = 0 (cotiza en INP): confirmar que el exportador ya lo emite en 0.
- **No aplicado**: SyS es solo lectura para esta automatización; `demo-sys`
  no tiene esta liquidación y el módulo ahí está en 18.0.3.6.0 sin ruta de
  deploy. La rama queda para despliegue y verificación por una persona.
## 6. VALIDADO EN demo-sys (STEPS_DEMO_SYS) — 2026-09-08

`step_hr_previred 18.0.3.8.1` desplegado y `-u` en `demo-sys`. Respaldo:
`/opt/steps_backups/demosys_previred_deploy/STEPS_DEMO_SYS_20260908-193204.dump`.

TXT PreviRed consolidado de **Sociedad de Bienestar…** (perfil v98), período
202608, contra la liquidación real de Valentina Parada — línea principal
(RUT 18.656.818-4):

| Campo | 18.0.3.8.1 | Esperado (ticket) |
|---|---|---|
| 29 SIS | **9.657** | 9.657 |
| 71 Acc. Trabajo ISL | **5.045** | 5.045 |
| 92 RIMA | **350.000** | 350.000 |
| 94 Expectativa de Vida | **3.906** | 3.906 |
| 95 Rentabilidad Protegida | **4.883** | 4.883 |
| 97 Renta Imponible Mutual | **0** | 0 (cotiza en INP) |
| 98 Cotización Mutual | **0** | 0 |
| 100 R.I. Seguro Cesantía | **542.500** | 542.500 |
| 102 AFC empleador | **13.020** | 13.020 |

La RIMA (350.000) la calculó la extracción: `(420.000 sueldo base + 105.000
gratificación) / 30 × 20 días de licencia`. Hallazgo
`medical_leave_bases_rebased` con ese detalle.

**Pendiente:** en `demo-sys` la compañía tiene un trabajador **sin
departamento** que bloquea el lote completo (`error: without_department`) —
es un dato de la base demo, no del cálculo; la línea de Valentina se genera
correcta. Confirmar en SyS que todos los trabajadores tienen departamento
antes de generar el archivo definitivo. **Nada persistido; SyS intacto.**
# Revisión 2 — línea adicional 01 (2026-09-08)

El cliente confirmó que la línea adicional tipo `01` debe informar cero en
los campos 13 (Días Trabajados), 71 (Accidente del Trabajo ISL) y 92 (RIMA).
Los valores `11`, `1790` y `350000` pertenecen a la línea principal y no deben
replicarse en la anexa. El resto del archivo fue aprobado en la revisión.

## 7. Revisión 2 corregida y validada en Demo-Sys — 2026-09-08

Se desplegó `step_hr_previred 18.0.3.8.2` en `STEPS_DEMO_SYS`, con respaldo
previo en
`/opt/steps_backups/ticket18_r2_18_0_3_8_2_20260908-210858/demosys`.

La prueba Odoo específica terminó con **0 fallos y 0 errores**. Además, el
generador real de SimpleDigital se ejecutó sobre la liquidación `SLIP/655` de
Valentina Parada (agosto 2026) y produjo:

| Línea | Campo 13 | Campo 71 | Campo 92 | Campo 93 |
|---|---:|---:|---:|---:|
| `00` principal | 11 | 5.045 | 350.000 | 1 |
| `01` adicional | **0** | **0** | **0** | 1 |

El dataset dejó el hallazgo auditable `medical_leave_annex_zeroed`. El
servicio `odoo18-demo-sys.service` quedó activo y respondió HTTP 200.

## 8. Desplegado y validado en producción SyS — 2026-09-08

Con autorización explícita del usuario se desplegó `step_hr_previred
18.0.3.8.2` en SyS. Antes de actualizar se respaldaron la base y el addon en:

`/opt/steps_backups/ticket18_r2_18_0_3_8_2_20260908-225020/sys`

La actualización terminó sin errores y `odoo18-sys.service` quedó activo;
los accesos local y público respondieron HTTP 200. La regeneración de solo
lectura con el motor real sobre `SLIP/671` confirmó:

| Línea | Campo 13 | Campo 71 | Campo 92 | Campo 93 |
|---|---:|---:|---:|---:|
| `00` principal | 11 | 5.045 | 350.000 | 2 |
| `01` adicional | **0** | **0** | **0** | 2 |

También se verificó que la principal mantiene los campos 97 y 98 en cero y
que el hallazgo `medical_leave_annex_zeroed` se produjo durante la extracción.
