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
