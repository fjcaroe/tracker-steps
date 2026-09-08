
---

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
