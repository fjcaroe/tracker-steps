# Auditoría previa — Libro de Remuneraciones (Fase 0)

Fecha: 2026-08-21 · Módulo auditado: `step_hr_remuneration_book` `18.0.1.0.0`
Entorno de auditoría: Desarrollo (`desarrollo.stepsapp.cl`, base `LAB_TAREAS`).

> Este documento **no contiene datos reales** de EMCA ni de ninguna empresa: sólo
> estructura, conteos agregados y decisiones de diseño. El Excel entregado se usó
> únicamente en el equipo local para reconciliar estructura y totales.

---

## 1. Estado verificado del entorno

| Hecho | Resultado |
|---|---|
| Módulo instalado en Desarrollo | `step_hr_remuneration_book 18.0.1.0.0`, estado `installed` |
| `l10n_cl_simpledigital_payroll` en Desarrollo | **`uninstalled`** (el código fuente sí está en `custom_addons`) |
| `l10n_cl_hr_electronic_book` en Desarrollo | `installed` (18.0.0.1) |
| Motor de reglas vigente en Desarrollo | `l10n_cl_hr_payroll_extended_14` (79 reglas salariales, estructura «l10n cl Pay») |
| Empresas en Desarrollo | 1 |
| Liquidaciones en Desarrollo | 2 en `done`, 14 en `verify` (un solo período: 2025-09) |
| Departamentos en Desarrollo | 5 |

**Consecuencia:** en Desarrollo **no es posible** validar el perfil SimpleDigital
(no está instalado) ni reconciliar contra datos EMCA. Toda la validación funcional
se hace con **fixture sintético**, tal como exige el encargo.

## 2. Pruebas actuales (Fase 0.1)

```
odoo-bin -d LAB_TAREAS -u step_hr_remuneration_book --test-enable --stop-after-init
→ step_hr_remuneration_book: 4 tests 0.70s 148 queries — sin fallos (exit 0)
```

Cobertura real: normalización de CSV corto y partición en pares. **Cero** cobertura
de negocio, de archivos y de seguridad.

Nota operativa: `--no-http` no impide el bind del puerto cuando el servicio de
Desarrollo está arriba; hay que añadir `--http-port=8199` (puerto libre) o el
arranque falla con `OSError: [Errno 98]`.

## 3. Salida actual generada en Desarrollo (Fase 0.2)

Ejecutado `_step_build_book_data()` sobre el único período con liquidaciones
Hechas:

| Métrica | Valor |
|---|---|
| Fuente resuelta | Libro de Remuneraciones Electrónico |
| Columnas exportadas al Excel | **147** |
| Filas de detalle | 2 |
| Fichas generadas en el PDF | 2 (≈2 páginas cada una) |

Confirma el diagnóstico: hoy se exporta el LRE ancho completo, no el libro
consolidado de 24 columnas.

## 4. Auditoría del Excel EMCA (sólo estructura)

Verificado programáticamente sobre el archivo entregado:

| Aspecto | Resultado |
|---|---|
| Hojas | 1 (`Libro impreso2`) |
| Área de impresión | `A1:X92` (24 columnas) |
| Títulos de impresión repetidos | filas `1:4` |
| Papel | `paperSize=5` → **Legal**, horizontal, escala 59 %, `fitToHeight=3` |
| Encabezado | fila 4, altura 57.6 |
| Líneas de detalle | 81 |
| Grupos con subtotal | 6 |
| Fila final | `Total general` |
| Fórmulas en el archivo | 2 (el resto son valores escritos) |
| Filtros / tabla / paneles congelados | ninguno |
| Formato de importes | `numFmtId=3` (`#,##0`), todos enteros, sin decimales |
| RUT | texto en 80 de 81 filas; **1 fila numérica** y **1 fila sin RUT** |
| Columna `Cantidad` | vacía en detalle, con conteo en subtotal y total |

### Matriz de reconciliación (agregada, sin datos personales)

| Comprobación | Resultado |
|---|---|
| Columnas | 24/24 |
| Grupos | 6/6 |
| Líneas de detalle | 81/81 |
| Subtotales que cuadran con su bloque | 6/6 |
| Total general = suma de subtotales | sí |
| `Cantidad` de subtotal = nº de líneas del grupo | 6/6 |
| `5201 − 5301 = 5501` por línea | 81/81 |
| `2101 + 2113 + 2106 = 5210` | 81/81 |
| `5210 + 2302 + 2301 + 2311 = 5201` | 81/81 |
| Suma visible de descuentos vs `5301` | **20 líneas difieren**: +1 en 16, −1 en 4 |

**Origen de la diferencia de ±1 (explicado, no supuesto):** el proveedor trunca a
entero *cada componente por separado* (`int(float(x))`) y toma `5301` de una regla
salarial propia, no de la suma de los componentes truncados. Por eso la suma de
columnas visibles puede desviarse un peso por línea. Se confirma la regla: **usar
siempre el valor oficial** de `5210`, `5201`, `5301` y `5501`; la suma visible sólo
alimenta alertas de conciliación con tolerancia configurable (inicial ±1).

## 5. Contrato de la fuente instalada (SimpleDigital) — sólo lectura

`l10n_cl_simpledigital_payroll` construye el CSV LRE en
`controllers/libro_remuneraciones.py` leyendo **líneas de liquidación ya calculadas**
por código de regla salarial. Correspondencia observada para las 24 columnas:

| Código DT | Origen en SimpleDigital |
|---|---|
| 1101 | `employee.identification_id` sin puntos |
| 1115 | días del `work_entry_type` `WORK100` |
| 2101 | regla `BASIC` |
| 2106 | reglas `GRAT47`, `GRAT50` |
| 2113 | movimientos `hr.employee.movement.line` con `movement_type_id.bono_ok` |
| 2301 | regla `COLA` |
| 2302 | reglas `MOV`, `MOV_15` |
| 2311 | regla `ASIG_FAM` |
| 3141 | reglas `AFP`, `IPS` |
| 3143 | regla `SALUD` |
| 3144 | regla `ISAPRE_EXTRA` |
| 3151 | regla `AFC_T` |
| 3155 | `contract.cotizacion_apvi` si `has_apvi` |
| 3161 | regla `IMP_RETENIDO` |
| 3110 | `hr.ccaf.deduction` tipo `credit` + `insurance` |
| 3183 | `hr.ccaf.deduction` tipo `other` + regla `CUENTA2` |
| 3188 | `hr.employee.movement.line` de tipo Anticipo/Préstamo |
| 5301 | **regla `TOTAL_DSCTOS`** (valor oficial) |
| 5210 | suma de haberes imponibles, cada componente truncado a entero |
| 5201 | `5210 + 5220 + 5230 + 5240` |
| 5501 | `5201 − 5301` |

Limitaciones del proveedor que **no** debemos heredar: todo el cálculo vive dentro
de un `http.Controller` y usa `request.env`, por lo que no funciona desde cron,
tests ni motor de reportes.

## 6. Motor alternativo instalado en Desarrollo

`l10n_cl_hr_payroll_extended_14` usa **otro juego de códigos**. Equivalencias
verificadas por nombre de regla:

| Código DT | Regla en Desarrollo | Nombre |
|---|---|---|
| 2101 | `SUELDO` | SUELDO BASE |
| 2106 | `GRAT` | GRATIFICACION LEGAL |
| 2113 | `BONO`, `BONLAB`, `PROD` | otros imponibles / bono labor / bono producción |
| 2301 | `COL` | COLACION |
| 2302 | `MOV` | MOVILIZACION |
| 2311 | `ASIGFAM` | ASIGNACION FAMILIAR |
| 3141 | `AFP` | AFP X PAGAR |
| 3143 | `SALUD` | SALUD |
| 3144 | `ADISA` | ADICIONAL ISAPRE |
| 3151 | `SECE` | SEGURO CESANTIA |
| 3155 | `APV` | APORTE AL AHORRO VOLUNTARIO |
| 3161 | `IMPUNI` | IMPUESTO UNICO |
| 3110 | `PCCAF` | PRESTAMOS CCAF |
| 3183 | `TOD` | OTROS DESCUENTOS |
| 3188 | `ASUE`, `PREST` | anticipo de sueldo / préstamos empresa |
| **5210** | `TOTIM` | TOTAL IMPONIBLE |
| **5201** | `HAB` | TOTAL HABERES |
| **5301** | `TDE` | TOTAL DESCUENTOS |
| **5501** | `LIQ` | ALCANCE LIQUIDO |

**Decisión:** el mapeo no puede estar hardcodeado a un proveedor. Se implementa un
**perfil de mapeo configurable** (modelo Odoo con datos semilla para ambos motores),
resuelto por empresa y autodetectado según las reglas realmente presentes.

## 7. Departamento histórico (Fase 0.4) — verificado en la base

| Campo | Tipo real en `LAB_TAREAS` | ¿Sirve como histórico? |
|---|---|---|
| `hr.contract.department_id` | many2one **almacenado y propio** | **Sí** — es el departamento pactado en el contrato vigente |
| `hr.payslip.department_id` | many2one **related a `employee_id.department_id`, `store=True`** | **No** — al ser related almacenado, se **recalcula** si luego se mueve al trabajador |
| `hr.employee.department_id` | many2one almacenado | No — refleja siempre el estado actual |

**Prioridad adoptada:** `contrato → liquidación → empleado (con advertencia)`.
Se difiere de la sugerencia del encargo (que ponía la liquidación primero) porque
en esta base la liquidación **no** guarda un snapshot: es un related recalculable.
Sin departamento en ninguno de los tres, la línea va al grupo visible
**«Sin departamento»** con advertencia, nunca se descarta.

## 8. Fuente oficial DT (Fase 0.5)

Confirmado en la ficha oficial de la Dirección del Trabajo: la carga masiva del LRE
debe ser **CSV o TXT delimitado por punto y coma**, con los encabezados oficiales y
**sin agregar ni quitar columnas**. El encabezado oficial completo está presente en
la fuente instalada (`l10n_cl_hr_electronic_book`, 147 campos) y coincide en códigos
con el suplemento. Por tanto:

- el libro consolidado de 24 columnas **no** se ofrece como archivo para Mi DT;
- el CSV oficial se expone como salida separada y se reutiliza íntegro;
- el módulo **no** declara ante Mi DT ni confirma aceptación.

## 9. Matriz existe / parcial / falta

| Requisito | Estado actual | Acción |
|---|---|---|
| Addon separado de SimpleDigital | Existe | conservar |
| Filtro por empresa/período y estados Hecho/Pagado | Existe | conservar, mover a mes calendario |
| Reutiliza valores oficiales del proveedor | Parcial | reemplazar por extractor propio sobre líneas de liquidación |
| 24 columnas del libro consolidado | **Falta** | Fase 1–2 |
| Mapeo por código DT (no por posición) | **Falta** | Fase 1 |
| Agrupación por departamento | **Falta** | Fase 1 |
| Subtotales y total general | **Falta** | Fase 1 |
| Departamento histórico | **Falta** | Fase 1 |
| Correspondencia segura fila↔liquidación | **Falta** (hoy hay fallback por índice) | Fase 1 — eliminar |
| Varias liquidaciones por RUT en el mes | **Falta** (dict por RUT las colapsa) | Fase 1 |
| Validador y conciliaciones | **Falta** | Fase 1 |
| Excel consolidado con layout Steps | **Falta** | Fase 2 |
| PDF consolidado horizontal | **Falta** (hoy es ficha individual) | Fase 2 |
| Ficha detallada individual | Existe, mal rotulada | Fase 2 — renombrar |
| CSV oficial expuesto en el wizard | **Falta** (el manifiesto lo promete) | Fase 2 |
| Previsualización de conteos y advertencias | **Falta** | Fase 3 |
| Control de grupo/compañía en el controlador | Parcial (`auth="user"` + chequeo de compañía) | Fase 3 — exigir grupo |
| Auditoría de exportaciones sin PII | **Falta** | Fase 3 |
| Pruebas de negocio, archivos y seguridad | **Falta** | Fases 1–3 |

## 10. Decisiones tomadas en esta auditoría

1. **Extractor propio Steps** que lee las líneas de liquidación ya calculadas y las
   mapea a códigos DT mediante perfil configurable. No se llama al controlador de
   SimpleDigital, no se copia ninguna fórmula previsional y no se modifica el módulo
   del proveedor.
2. **Dataset único tipado** consumido por Excel, PDF consolidado y previsualización.
3. **Valores oficiales** para `5210`, `5201`, `5301` y `5501`; las sumas visibles
   sólo generan advertencias con tolerancia configurable (±1 inicial).
4. **Departamento**: contrato → liquidación → empleado (advertido), con grupo
   «Sin departamento».
5. **Una línea por liquidación**, tal como la muestra: dos liquidaciones del mismo
   trabajador en el mes son dos líneas y cuentan dos. Se expone además el conteo de
   trabajadores únicos, rotulado aparte.
6. **Papel Legal horizontal** para el PDF consolidado, igual que el archivo EMCA
   original (`paperSize=5`), en vez de A3: es el formato que la contadora ya imprime.
7. **Sin fallback por índice**: si una línea no se puede resolver de forma
   determinística, el informe se bloquea y explica el caso.

## 11. Preguntas escaladas

| Pregunta | Respuesta adoptada por defecto | ¿Requiere confirmación? |
|---|---|---|
| ¿De dónde sale Departamento? | Contrato primero (la liquidación no es histórica en esta base) | conveniente |
| ¿Dos liquidaciones = dos líneas? | Sí, como la muestra | conveniente |
| ¿PDF en A3 o Legal? | Legal horizontal (igual que el original) | conveniente |
| ¿Orden de departamentos? | Alfabético estable; «Sin departamento» al final | conveniente |
| ¿Se conserva la ficha individual? | Sí, como cuarta salida explícita | conveniente |
| ¿Tolerancia de ±1 informativa o bloqueante? | Informativa y configurable | conveniente |

Ninguna bloquea la implementación: el parser, el dataset, la seguridad y las
pruebas se construyen de modo que la política se pueda cambiar por configuración.

---

## 12. Actualización 2026-08-22 — verificado contra una instalación real

Las secciones 5 y 6 se escribieron **leyendo el código** del proveedor, sin poder
ejecutarlo. Al validar sobre la copia aislada `STEPS_DEMO_SYS` —una base con
`l10n_cl_simpledigital_payroll` realmente instalado— dos puntos de la sección 5
resultaron inexactos y quedan corregidos aquí:

| Punto de la §5 | Lo verificado en la base real |
|---|---|
| «5210 = suma de haberes imponibles, cada componente truncado a entero» | Es correcto **como descripción del generador del proveedor**, pero el valor equivalente ya existe como regla salarial: `GROSS`. El Libro Steps toma `GROSS`; la diferencia con la suma truncada del proveedor es de **±1 peso en unas pocas líneas** |
| `NETO` como regla del líquido | **No existe**. La regla es `NET` |
| `habIMP` como origen de 5210 | El generador oficial **no la usa** para 5210 |
| `MOV_20…MOV_24` como indemnizaciones | En la base observada esos códigos corresponden a **tipos de movimiento distintos** (bonos, tratos). Es una limitación del proveedor que **no** se hereda: el Libro Steps no mapea esos códigos a indemnizaciones |

La matriz completa `código DT → origen`, la conciliación agregada y la causa de
cada diferencia están en
[ENTREGA_LIBRO_REMUNERACIONES.md](ENTREGA_LIBRO_REMUNERACIONES.md) §8.
