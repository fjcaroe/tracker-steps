# Ticket #16 — Cierre contable anual Megafrut (Balance Fiscal 8 columnas)

- **Fecha análisis:** 2026-09-08
- **Cliente:** S&S Asesores Asociados SpA · Empresa: **Megafrut Limitada** (RUT 77.247.040-1)
- **Base:** S&S `http://35.222.25.110:8070/odoo` (**sin acceso desde esta automatización**)
- **Área:** Contabilidad / cierre de ejercicio + reporte *Balance Fiscal Chilena (8 columnas)* (`l10n_cl`)
- **Estado:** ANÁLISIS — no clasificable a ninguno de los worktrees (nómina, gestión de costos, task, cosecha). **Nada desplegado. Sin rama.**

## Petición del ticket (textual)

> "Cuáles son los comprobantes de cierre de año para presentar mejor los balances del año 2025 y 2026 […] la idea es que no aparezca la fila **'Beneficios no asignados de ejercicios anteriores'**, en el ejemplo aparece el resultado del año 2024 en balance 8 columnas."

Adjuntos del cliente: `balance_fiscal_chilena_(8_columnas)` de 2024, 2025 y 2026 + captura.

## Lo que muestran los balances adjuntos

| Reporte | "Pérdidas y ganancias" (resultado del año en curso) | "Beneficios no asignados de ejercicios anteriores" |
|---|---:|---:|
| 2024 | 593.873.189 | — (no aparece; 2024 es el año en curso) |
| 2025 | 320.176.031 | **593.873.189**  ← resultado 2024 |
| 2026 | 102.817.760 | **273.697.158** |

Cuentas de patrimonio relevantes en el balance 2025:
- `230290 Resultados Acumulados` — saldo **deudor** 145.128.182 (pérdidas acumuladas).
- `230510 Resultado del Ejercicio` — Débito 593.873.189 / Crédito 593.873.189 (**neto 0**): ya existe un asiento manual que pasó por esta cuenta.
- `230110 Capital Social` 403.642.479 · `230210 Revalorización Capital Propio` 37.426.124.

## Diagnóstico

1. **Odoo no usa un "asiento de cierre" físico de las cuentas de resultado.** El resultado del ejercicio ("Resultado del Ejercicio" / *Current Year Earnings*) es una línea **calculada** dinámicamente en el balance a partir de las cuentas de P&L del año fiscal de la fecha del informe. Esa es la fila **"Pérdidas y ganancias"** del reporte de 8 columnas. No hay que contabilizar nada para que aparezca.

2. **La fila "Beneficios no asignados de ejercicios anteriores"** = saldo neto de la(s) cuenta(s) de patrimonio de tipo *"Ganancias no asignadas"* (`equity_unaffected` en Odoo) correspondiente a **años fiscales anteriores** al del informe, que **todavía no ha sido reclasificado** con un asiento manual a una cuenta de patrimonio definitiva. Por eso en el balance 2025 aparece el resultado 2024 (593.873.189): Odoo lo arrastra como "no asignado" hasta que exista un **asiento de distribución / traspaso de resultado**.

3. El que la cuenta `230510 Resultado del Ejercicio` tenga Débito = Crédito = 593.873.189 sugiere que se intentó el traspaso pero **quedó dentro de la misma cuenta** (o contra una cuenta que Odoo sigue tratando como de resultados no asignados), por lo que el reporte lo sigue mostrando. La cifra 2026 (273.697.158 ≠ 593.873.189 + 320.176.031) indica que **hubo asientos parciales** de distribución/absorción, pero no completos.

## Qué necesita hacerse (para el contador de S&S — requiere su decisión)

### A. "Comprobantes de cierre de año" en Odoo

Para Megafrut, los comprobantes de cierre reales que Odoo **no genera solo** y que el contador debe evaluar contabilizar, con fecha 31-12 del año que cierra:

- **Provisión de impuesto a la renta:** `Debe: Gasto Impuesto Renta` / `Haber: Impuesto Renta por Pagar` (si corresponde según RLI).
- **Corrección monetaria del capital propio / patrimonio** (si no está ya incorporada — en 2025 aparece `320280 Corrección Monetaria Activos` y `230210 Revalorización Capital Propio`, revisar que el ciclo esté completo).
- **Asiento de distribución de resultados** del ejercicio anterior (ver punto B).
- Tras cerrar: fijar la **Fecha de bloqueo** (Contabilidad → Configuración → Ajustes → *Fechas de bloqueo* / Lock Date).

### B. Para que **desaparezca** la fila "Beneficios no asignados de ejercicios anteriores"

Contabilizar un **asiento manual de traspaso de resultado**, con fecha **01-01 del año siguiente** al que generó el resultado (p. ej. 01-01-2025 para el resultado 2024), moviendo el saldo desde la cuenta configurada como *"Ganancias no asignadas"* hacia una cuenta de patrimonio **definitiva**:

```
Fecha: 01-01-2025
Debe   230510 Resultado del Ejercicio (cuenta equity_unaffected)   593.873.189
  Haber  230290 Resultados Acumulados (patrimonio, tipo Patrimonio)   593.873.189
```

(Invertir Debe/Haber si el arrastre neto fuera pérdida; o llevar el Haber a *Dividendos / cuentas por pagar a socios* si se distribuye.)

**Requisito previo:** confirmar en Odoo **qué cuenta** está marcada como *"Cuenta de ganancias no asignadas"* de la compañía (Contabilidad → Configuración → Ajustes, o la cuenta de tipo *Equity / Current Year Earnings — Unaffected*). El asiento debe debitar/acreditar **exactamente esa cuenta**; si el traspaso previo se hizo contra otra, hay que reversarlo y rehacerlo.

Si tras el asiento la fila sigue apareciendo, la causa será: (a) fecha del asiento fuera del rango del informe, (b) cuenta equivocada, o (c) queda saldo no asignado real de ejercicios anteriores a 2024.

## Por qué no se implementa aquí

- El reporte *Balance Fiscal Chilena (8 columnas)* y la configuración contable viven en la **base :8070**, sin módulo equivalente en los worktrees de Steps y **sin acceso** desde esta automatización.
- No es un cambio de código acotado: la solución es **un asiento contable que debe decidir y contabilizar el contador** (monto, fecha, cuenta destino, si se distribuye a socios). Mover cifras de patrimonio / resultado sin confirmación funcional está fuera de alcance de esta automatización.

## Pendiente / requiere confirmación funcional

- Contador de S&S: confirmar cuenta `equity_unaffected` de Megafrut y política de distribución (a Resultados Acumulados vs. dividendos).
- Confirmar si Megafrut contabiliza provisión de impuesto renta y estado de la corrección monetaria 2024/2025/2026.
- Si S&S quiere que el reporte agrupe distinto (que ciertas cuentas 23xx no caigan en "no asignados"), eso es configuración del informe en :8070 — abrir tarea aparte con acceso a esa base.

**NADA DESPLEGADO. SIN RAMA. SOLO ANÁLISIS.**
