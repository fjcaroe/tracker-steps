# Helpdesk #17 — Somed SpA, Carolina Medel: error imposiciones con licencia médica (agosto 2026)

**Estado:** ANÁLISIS. No se implementa código en esta corrida — es un cambio
que mueve montos de cotizaciones previsionales declaradas a PreviRed y parte
del cálculo vive en el motor de nómina del proveedor (`:8070`), fuera de este
repositorio. **Requiere confirmación funcional** antes de codificar.
**Nada desplegado. Sin cambios de código en esta rama** (solo este documento).

- **Módulo afectado:** `step_hr_previred` (+ puente `step_hr_previred_simpledigital`).
- **Rama base:** `fix/previred-correcciones-2` (repo Odoo), versión `18.0.3.6.0`.
- **Rama de esta nota:** `ticket/17-somed-medel-licencia-medica`.
- **Relacionado:** tickets #9 (Marcelo Soto), #13 (Parada/Pereira), #15
  (Celestina Peñaloza) y el documento
  `docs/PREVIRED_TICKET_LICENCIA_JORNADA_2026-09.md` de la rama
  `correo/20260907-previred-licencia-jornada` («corte 2» de licencia médica).
  Este ticket es **otro caso** del mismo defecto y **aporta el dato que
  faltaba**: un archivo de revisión con las líneas PreviRed ya generadas por
  el ERP para un trabajador con **mes completo de licencia**.

## 1. Datos del caso

- **Empresa:** Somed SpA (RUT 77.595.645-3). **Base:** `:8070` (producción S&S).
- **Trabajadora:** Carolina Medel Gutiérrez, **RUT 17.932.663-9**, AFP código 34.
- **Período:** 082026. **Días Trabajados (campo 13) = 0** → mes completo de
  licencia médica (aplica la regla «d» del corte 2).
- **Líneas del archivo de revisión** (`PREVIRED_REVISION_775956453_202608 (2).xlsx`):
  - `00` línea principal.
  - `01` línea adicional, movimiento de personal **20-07-2026 → 28-08-2026**.
  - `01` línea adicional, movimiento de personal **29-08-2026 → 31-08-2026**.
  - ⇒ licencia **continua 20-07 → 31-08 ≈ 43 días corridos** (≥ 30 días
    continuos, contando la continuación del mes anterior).

## 2. Discrepancias (ERP generó vs. valor correcto del cliente)

Base declarada por el cliente para los aportes patronales:
**1.205.761** (hoja «a pagar» del Excel; el cliente la rotula
«imponible mes + RIMA»). RIMA (subsidio de los días de licencia sobre el
sueldo del mes anterior) = **81.148**.

| Campo | Concepto | ERP generó | Correcto (cliente) | Cálculo correcto |
|------:|----------|-----------:|-------------------:|------------------|
| 27 | Renta Imponible AFP | 0 | 0 | trabajador en licencia (lo paga la entidad pagadora de subsidio) |
| 28 | Cotización Obligatoria AFP | 0 | 0 | — |
| 29 | **Cotización SIS** | **22.178** | **21.463** | 1.205.761 × 1,78 % = 21.462,55 |
| 92 | **RIMA** | **0** | **81.148** | subsidio días de licencia s/ sueldo mes anterior |
| 94 | Cotización Expectativa de Vida | 8.681 | 8.681 | 1.205.761 × 0,72 % = 8.681,48 ✅ **coincide** |
| 95 | **Cotización Rentabilidad Protegida** | **0** | **10.852** | 1.205.761 × 0,90 % = 10.851,85 |
| 71 | Cot. Acc. Trabajo (ISL, sin Mutual) | (según archivo) | 11.214 | 1.205.761 × 0,93 % = 11.213,58 |
| 98 | Cot. Acc. Trabajo (Mutual) | — | 0 | Somed usa ISL; con Mutual sería 0 por los ≥ 30 días |
| 102 | **Aporte Empleador Seguro Cesantía** | **29.903** | **28.938** | 1.205.761 × 2,4 % = 28.938,26 |

## 3. Diagnóstico por campo

### 3.1 Campo 95 (Rentabilidad Protegida) — defecto **local del exportador**

`step_hr_previred/models/previred_extractor.py::_enrich_official_fields`
(líneas ~478-479) calcula el campo 95 así:

```python
row[previred.F_PROTECTED_RETURN - 1] = contribution(
    previred.protected_return_rate(dataset.period))
```

donde `contribution(rate)` usa `taxable_amount = Decimal(row[F_AFP_TAXABLE-1])`,
es decir **el campo 27 (Renta Imponible AFP)**. En mes completo de licencia
el campo 27 es **0**, así que el campo 95 sale **0**.

- La **tasa ya es correcta**: `protected_return_rate("202608") == "0.90"`, y
  `1.205.761 × 0,90 % = 10.851,85 → 10.852`, el valor que pide el cliente.
- El campo 94 (CEV) del mismo método sale **bien** solo porque tiene
  precedencia de la línea de nómina (`EXP_VIDA`/`CEV`): cuando esa línea trae
  monto, se usa tal cual (8.681). El campo 95 **no tiene esa precedencia** y
  siempre se recalcula sobre el campo 27.

**Esbozo de corrección (no implementado):** que el campo 95 use la misma base
que el campo 94 — primero la línea de nómina `RENT_PROT`/`Rentabilidad
Protegida` si existe; si no, la base «imponible mes + RIMA» de licencia
(campo 92 + imponible del mes), no el campo 27. Con prueba de regresión para
RUT 17.932.663-9 → campo 95 = 10.852.

### 3.2 Campos 29 (SIS) y 102 (AFC empleador) — base inflada **por el motor (`:8070`)**

Ambos vienen de líneas salariales del motor de nómina, no los calcula el
exportador. La base implícita del ERP es:

- SIS: `22.178 ÷ 0,0178 ≈ 1.245.957`.
- AFC: `29.903 ÷ 0,024 ≈ 1.245.958`.

Es decir el motor está usando **≈ 1.245.957** en vez de **1.205.761**
(**≈ +40.196**). Mismo patrón que el ticket #15 (Mutual inflada ≈ +8.975):
el motor carga parte de los días de licencia en la base de los aportes
patronales. La regla confirmada (corte 2, fila «e»): SIS y CEV van sobre
`imponible del mes + RIMA`; la base objetivo aquí es 1.205.761, no
1.245.957.

**No se corrige desde el exportador sin una de estas dos vías** (idénticas a
las del ticket #15): (1) corregir la regla en el motor del proveedor en
`:8070`, o (2) un override en `step_hr_previred_simpledigital` (patrón
`hooks.py::apply_salary_rule_overrides`, ya usado para el tipo 3) que fuerce
la base de `SIS` / `EXP_VIDA` / `AFC_EMPLEADOR` / `RENT_PROT` a
`imponible_mes + RIMA` durante licencia de mes completo. **Bloqueado por
acceso a `:8070`** para leer las reglas y ubicar de dónde sale el
`+40.196`.

### 3.3 Campo 92 (RIMA) = 0 — el exportador **no lo emite**

Coincide con el punto pendiente §2 del documento del corte 2: falta el
cálculo de RIMA (campo 92) y su emisión. El valor correcto para este caso es
**81.148**. El «esbozo de implementación» del corte 2 (constantes `F_RIMA=92`,
helper `imm(period)` con `202608 → 553.553`, método
`_set_medical_leave_bases`) cubre este campo; este ticket confirma que hace
falta.

### 3.4 Campo 94 (CEV) = 8.681 — correcto

La corrección de tasa 0,72 % (corte 1, `18.0.3.7.0`, rama
`correo/20260907-previred-licencia-jornada`) no está en `fix/previred-correcciones-2`,
pero el valor sale bien igual porque el motor dejó la línea `EXP_VIDA` con el
monto y el exportador la respeta. Sin esa línea, sobre esta base daría
`1.205.761 × 1,00 % = 12.058` (tasa de respaldo vigente en esta rama). Otro
motivo para consolidar el corte 1.

## 4. Contradicción con el supuesto del corte 2 — **requiere confirmación funcional**

El documento `PREVIRED_TICKET_LICENCIA_JORNADA_2026-09.md` §2 asume que,
cuando Días Trabajados = 0, «la base SIS/CEV es RIMA (imponible del mes ≈ 0)».
**Este caso lo contradice:** la base de los aportes patronales es
**1.205.761**, muy por encima de la RIMA (81.148). El imponible del mes NO es
≈ 0.

Preguntas abiertas para el usuario / analista funcional antes de codificar:

1. ¿Qué es exactamente **1.205.761**? ¿`sueldo base contractual +
   gratificación` (renta que la trabajadora habría tenido) usada como base de
   todos los aportes patronales durante la licencia? ¿O `imponible del mes
   real + RIMA`?
2. ¿La base de licencia de mes completo es **la misma para SIS, CEV, RENT_PROT
   y AFC empleador** (todos 1.205.761 en este archivo), o alguno cambia?
3. Campo 92 (RIMA) = 81.148 y la base de aportes = 1.205.761: ¿son
   independientes (RIMA solo informativa) o 1.205.761 = imponible_mes +
   81.148 (⇒ imponible_mes = 1.124.613)?
4. Somed opera con **ISL** (campo 71), no Mutual. Con 43 días continuos de
   licencia, ¿el campo 71 se informa igual (11.214, como dice el cliente) o
   va a 0 «porque después de 30 días paga quien reembolsa el subsidio» (nota
   de la propia hoja del cliente)? El cliente entrega 11.214, no 0 — conviene
   confirmarlo por escrito.
5. ¿El `+40.196` que agrega el motor a la base de SIS/AFC tiene una regla
   conocida (p. ej. tope, o proporción de días), o es un bug puro del motor?

## 5. Qué NO se hizo y por qué

- **No se tocó código.** El campo 95 tiene un esbozo de fix local acotado
  (§3.1) pero cambia un monto declarado a PreviRed; se deja para el corte 2
  junto con RIMA y con las respuestas de §4.
- **No se tocó `step_hr_previred_simpledigital`** (override de reglas del
  motor): bloqueado por acceso a `:8070`.
- **Nada desplegado.** No se corrió la suite (`--test-tags=/step_hr_previred`
  en `odoo-new`): pendiente.
- No se cambió la etapa del ticket (esta automatización no puede enumerar
  `helpdesk.ticket.stage`).

## 6. Recomendación de consolidación

Unificar en el corte 2 (rama `correo/20260907-previred-licencia-jornada`):

1. Cerrar §4 con el usuario (base de licencia de mes completo).
2. Implementar campo 92 (RIMA) y la base correcta de campo 95 en
   `previred_extractor.py`, con pruebas usando RUT 17.932.663-9
   (95 = 10.852) y RUT 14250811-7 (del corte 2).
3. Para SIS/AFC/ISL inflados por el motor: decidir entre override
   (`step_hr_previred_simpledigital`) o corrección en `:8070`; requiere
   acceso a esa base.
4. Consolidar el corte 1 (tasa CEV 0,72 %) en la rama base para no depender
   de la precedencia de la línea de nómina.
