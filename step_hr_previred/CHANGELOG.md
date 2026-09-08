# Changelog

## 18.0.3.8.2

Ticket Helpdesk S&S #18, **revisión 2** (Servicio de Bienestar / Valentina
Parada, agosto 2026).

* La línea adicional tipo `01` de una licencia médica ahora informa `0` en
  Días Trabajados (campo 13), Accidente del Trabajo ISL (campo 71) y RIMA
  (campo 92), tal como confirmó el cliente. La línea principal `00` conserva
  sus valores calculados (11, 5.045 y 350.000 en el caso revisado) y el resto
  de los campos de la anexa no se altera.
* La RIMA calculada por la extracción se escribe únicamente en la línea
  principal; ya no se propaga a anexas. La normalización deja un hallazgo
  auditable `medical_leave_annex_zeroed` cuando corrige valores del motor.

## 18.0.3.8.1

Correcciones tras **validar el TXT real en `demo-sys` (`STEPS_DEMO_SYS`)** con
las liquidaciones de Carolina Medel (Somed) y Valentina Parada (Serv.
Bienestar), agosto 2026. Con estas correcciones los campos 29, 71, 92, 94, 95,
97, 98, 100 y 102 del archivo generado coinciden exactamente con los valores
que pide cada ticket.

* **`_()` no admite el kwarg reservado `source`.** El hallazgo
  `medical_leave_bases_rebased` se construía con `_("… %(source)s …",
  source=…)`, que choca con el primer parámetro posicional de
  `get_text_alias` y lanzaba `TypeError` al generar el archivo. Marcador
  renombrado a `%(origen)s`.
* **Empleador ISL (sin mutualidad): campo 71 y campos 97/98.** El motor deja
  el campo 71 en 0 en licencia de mes completo aunque el empleador cotice en
  el ISL (caso Somed). Ahora, cuando el campo 96 (Código Mutualidad) viene
  vacío, el recálculo de licencia médica fija el campo 71 = base × 0,93 %
  siempre, y pone en 0 los campos 97 (Renta Imponible Mutual) y 98
  (Cotización Mutual), que no aplican a quien no está en una mutualidad
  (ticket #18: «campo 97 = 0 porque cotiza en INP»).

## 18.0.3.8.0

Tickets Helpdesk S&S #17 (Somed / Carolina Medel, RUT 17.932.663-9) y #18
(Servicio de Bienestar / Valentina Parada, RUT 18.656.818-4), nómina agosto
2026. El cliente confirmó los valores esperados y la regla el 2026-09-08.

* **Licencia médica: cotizaciones de cargo del empleador sobre imponible del
  mes + RIMA.** Nuevo `PreviredExtractor._set_medical_leave_bases`. Cuando el
  motor ya informó la RIMA en el campo 92, la base de SIS (29), Acc. Trabajo
  ISL (71, sólo si la línea usa ISL y no mutual), Expectativa de Vida (94),
  Rentabilidad Protegida (95), Renta Imponible Seguro Cesantía (100) y Aporte
  Empleador Seguro Cesantía (102) pasa a ser `campo 27 + campo 92` y cada
  cotización se recalcula con su tasa estatutaria (`sis_rate` 1,78 %;
  `isl_accident_rate` 0,93 %; `life_expectancy_rate` 0,72 %;
  `protected_return_rate` 0,90 %; `unemployment_employer_rate` 2,4 % / 3,0 %).
  No se tocan la cotización adicional AFP del campo 28 ni la mutualidad
  (97/98). Verificado contra los archivos de revisión de PreviRed de ambos
  tickets: Somed base 1.205.761 ⇒ 29=21.463, 94=8.681, 95=10.852, 71=11.214,
  102=28.938; Serv. Bienestar base 542.500 ⇒ 29=9.657, 94=3.906, 95=4.883,
  71=5.045, 102=13.020. Cada override deja un hallazgo auditable
  (`medical_leave_bases_rebased`). **Mueve montos declarados a PreviRed:**
  pendiente de validación funcional contra datos reales antes de SyS.
* **Cálculo de la RIMA cuando el motor no la informa** (nuevo
  `_compute_medical_leave_rima`). Si el campo 92 viene vacío pero la
  liquidación tiene una línea de licencia médica (tipo de entrada `LIC` o
  `ACCTR`), la RIMA se calcula = `(sueldo base del contrato + gratificación) /
  30 × días de licencia médica del mes`, con
  `gratificación = min(25 % del sueldo base, 4,75 × IMM ÷ 12)` e IMM desde
  `previred.minimum_wage`. Verificado contra las liquidaciones reales de SyS
  (agosto 2026): Carolina Medel `(986.646 + 219.114 tope IMM) / 30 × 30 =
  1.205.761` (idéntico a la línea `SUBSIDIO` del motor) y Valentina Parada
  `(420.000 + 105.000) / 30 × 20 = 350.000`. El valor calculado se escribe en
  el campo 92 y alimenta el recálculo anterior. Si falta el IMM del período o
  el sueldo base del contrato, no calcula y deja `medical_leave_rima_missing`.
* Helpers nuevos en `tools/previred.py`: `sis_rate`, `isl_accident_rate`,
  `unemployment_employer_rate`, `minimum_wage` (tabla IMM por período, 202608
  = 553.553); constantes `F_ISL_ACCIDENT`, `F_RIMA`, `F_MUTUAL_TAXABLE`,
  `F_MUTUAL_CONTRIBUTION`, `F_UNEMPLOYMENT_EMPLOYER`.

## 18.0.3.7.0

Tickets PreviRed 2026-09 (nómina agosto 2026). Dos correcciones acotadas y
verificadas por aritmética; la parte de cálculo de la RIMA en licencia médica
queda especificada aparte (`docs/PREVIRED_TICKET_LICENCIA_JORNADA_2026-09.md`).

* **Tasa de Cotización Expectativa de Vida (campo 94) = 0,72 % desde agosto
  2026.** `life_expectancy_rate` devolvía `1,00 %`, una estimación previa a la
  publicación de la tabla previsional del mes. Confirma el valor el rechazo de
  PreviRed del ticket «imposiciones licencia médica» (RUT 14250811-7): con
  RIMA 673.750, el campo 94 esperado es 4.851 = 673.750 × 0,72 %. También
  corrige el campo 94 del RUT 14250811-7 en el ticket Los Lingues.
* **Tipo de Jornada (campo 93): parcial cuando la jornada semanal es inferior
  a 40 h.** El umbral era `≤ 30 h` y la fuente de horas priorizaba
  `hours_per_week`. Ahora se toma «Tiempo completo de la empresa»
  (`full_time_required_hours`) del horario y una jornada `< 40 h` se informa
  como tipo 2. El caso EMCA agosto 2026 (RUT 12588103-3, KAREN FLIES,
  calendario «Jornada parcial 24 horas») salía como tipo 1 y PreviRed
  rechazaba el campo 27 «Renta Imponible AFP no corresponde al mínimo legal».
  `previred_workday_type` explícito del horario mantiene la precedencia.

## 18.0.3.6.0

* **Trabajador tipo 3 (activo mayor de 65 años).** El puente SimpleDigital
  conserva sólo la cotización base AFP en el campo 28 y fuerza a cero SIS
  (campo 29), expectativa de vida (campo 94) y rentabilidad protegida
  (campo 95). La liquidación deja de generar las reglas `AFP_EMP`, `SIS`,
  `EXP_VIDA` y `RENT_PROT` para estos trabajadores, usando la misma edad al
  inicio del período con que el proveedor informa el campo 12.

## 18.0.3.5.1

* **Campo 93 consistente en líneas anexas.** El Tipo de Jornada se calcula
  una vez desde el calendario del contrato y se replica en todas las líneas
  `00/01/02/03` del trabajador. Corrige el rechazo de PreviRed que se produce
  cuando una línea adicional informa un valor distinto de su principal
  (caso EMCA, agosto 2026, RUT 12358793-6).

## 18.0.3.5.0

Ticket PreviRed 2026-08 (Agrícola Los Lingues y Megafrut Limitada, nómina
agosto 2026): 4 de los 7 errores reportados por el portal eran el mismo
defecto.

* **Campo 105 «Centro de Costos, Sucursal, Agencia» en ASCII puro.** Un
  nombre de cuenta analítica o centro de costo con tilde («Administración»)
  se codificaba en UTF-8 y Previred lo releía como Latin-1, mostrando
  «AdministraciÃ³n» y rechazando la línea con «Error de formato en el campo
  Centro de Costos, Sucursal, Agencia, Obra, Region». Ahora se translitera a
  ASCII con `previred.strip_accents` antes de truncar a 20 caracteres, igual
  que el resto de los campos alfanuméricos del formato. Corrige RUT
  20681876-K (Los Lingues) y los tres RUT reportados por Megafrut
  (09800422-K, 07016555-4, 14692801-3).
* **Pendiente, no incluido en este corte** (RUT 14250811-7, Marcelo Soto,
  licencia médica de 30 días): la Cotización SIS (campo 29), la Cotización
  Expectativa de Vida (campo 94) y la Renta Imponible / Cotización Accidente
  del Trabajo Mutual (campos 97-98) dependen de una renta imponible especial
  para licencias (RIMA, campo 92) y de reglas de negocio (tope de 30 días de
  licencia para el aporte Mutual) que hoy calcula el motor de nómina del
  proveedor (`l10n_cl_hr`), no `step_hr_previred`. Ver
  `docs/PREVIRED_TICKET_LOS_LINGUES_MEGAFRUT_2026-09.md` para el análisis
  numérico y lo que falta confirmar antes de tocar ese cálculo.

## 18.0.3.4.0

Correcciones 2 (documento funcional 2026-08-29). Elimina las dos causas de los
11 errores que impedían generar el TXT PreviRed en Demo-SyS.

* **Campo 13 «Días Trabajados» desde la línea de asistencia.** El valor se toma
  de la línea de días trabajados cuyo tipo de entrada es «Asistencia» (código
  técnico estable `WORK100`; respaldo por rótulo si Tipo y Descripción son
  ambos «Asistencia», normalizados). Se suman **sólo** esas líneas: «Fuera de
  contrato», licencias, permisos, ausencias y vacaciones quedan excluidos
  siempre. Se **elimina** el respaldo genérico que sumaba toda línea no marcada
  como ausencia (contaba «Fuera de contrato» y producía p. ej. 18 en vez de 6).
* **Formato entero y tope de 30.** `6.00` se exporta como `6`. Una fracción no
  representable se informa como error, sin truncar en silencio. La suma se
  acota a 30 (mes previsional Previred) con una advertencia auditable.
* **Sin fuente válida ⇒ error preciso.** Si la liquidación no tiene una línea
  de asistencia no se inventa un valor (ni días calendario, ni el rango de la
  liquidación, ni «30 − ausencias»): se bloquea con un hallazgo que identifica
  la liquidación de forma segura.
* **Campo 13 en todas las filas.** El valor se escribe también en las líneas
  anexas. Era la causa real de «Falta el campo obligatorio 13»: 10 de los 11
  errores estaban en líneas anexas, no en la principal.
* **Multiplicidad de líneas principales por contrato.** El registro canónico
  gana `contract_id` como metadata interna: no se exporta ni desplaza ningún
  campo del TXT. La unicidad admite tantas líneas principales (código `00`)
  como contratos elegibles tenga el trabajador en la compañía y período; dos
  líneas del mismo contrato siguen siendo error. N líneas para menos de N
  contratos elegibles bloquea la generación (`too_many_principal_lines`).
* **Correlación línea ↔ contrato determinística.** El bridge SimpleDigital
  entrega al núcleo el contrato de cada línea principal replicando la selección
  del generador del proveedor. Sin esa metadata y con ambigüedad real, se
  bloquea con `ambiguous_contract_correlation` en vez de asignar por posición.
* Contratos y liquidaciones en borrador o cancelados no amplían el cupo de
  líneas principales.
* Documentación: la matriz SimpleDigital anota que el núcleo recalcula el
  campo 13 y no usa `_get_real_worked_days_from_payslip` del proveedor.

## 18.0.1.0.0

Primera versión.

* Dataset canónico único (`step.previred.extractor`) del que derivan todas las
  salidas por partición.
* Adaptadores de motor para `l10n_cl_hr` y `l10n_cl_simpledigital_payroll`:
  reutilizan el generador vigente, no lo reimplementan.
* TXT consolidado, TXT por departamento y ZIP con manifiesto de control
  (archivo, departamento, conteos y SHA-256, sin datos personales).
* Excel de revisión: consolidado con hoja `Resumen`, hoja por departamento y
  fila técnica con el número oficial de cada campo.
* Perfiles de formato versionados con fuente y vigencia (largo variable v84,
  julio 2025).
* Validación campo por campo de los 105 campos antes de permitir la descarga,
  con botón «Validar» separado de «Generar».
* Política explícita y auditable para trabajadores sin departamento.
* Cuatro grupos de permisos y reglas de registro multiempresa.
* Lote de auditoría con perfil, versión, fuente, conteos y hashes.

## 18.0.2.0.0

Rearquitectura: el core deja de conocer los motores y el flujo Previred pasa a
ser único dentro de Nómina.

* **Separación core / bridges.** `step_hr_previred` depende sólo de
  `hr_payroll`. Los motores viven en `step_hr_previred_blueminds` y
  `step_hr_previred_simpledigital`, cada uno con dependencia explícita de su
  proveedor. Una prueba impide que el core vuelva a nombrar un addon de motor.
* **Un solo flujo visible.** Se retira el submenú paralelo «Previred Steps» que
  publicaba la 1.0.0 (migración idempotente) y cada bridge repunta el menú que
  su motor ya tenía hacia el asistente unificado.
* **Filtro de elegibilidad.** El lote selecciona sus propias liquidaciones por
  compañía y estado y descarta las filas que el generador emite de más.
  `draft` y `cancel` nunca se exportan.
* **Estados por motor**, declarados y justificados en el perfil, no una lista
  global: Blueminds `done,paid`; SimpleDigital `verify,done,paid`.
* **Matriz de los 105 campos** por motor, generada desde el código del
  generador y visible en el perfil.
* **Validación de condicionales de las líneas anexas**: fechas obligatorias
  según el código de movimiento y datos del afiliado voluntario en las 03.
* **Cierre de la ruta insegura** de SimpleDigital por herencia del controlador,
  sin tocar el addon del proveedor.
* Los perfiles sembrados por la 1.0.0 son **adoptados** por su bridge; los
  lotes ya generados conservan su perfil.

## 18.0.3.2.0

Actualización normativa y endurecimiento del flujo para agosto de 2026.

* Perfil oficial largo variable **v98** con selección automática por período;
  el perfil v84 queda acotado hasta julio de 2026.
* Campos 93, 94 y 95 implementados y validados para la reforma previsional:
  tipo de jornada, expectativa de vida y rentabilidad protegida.
* La expectativa de vida conserva primero el valor calculado por el motor
  (incluido RIMA/licencias) y sólo usa la tasa legal como respaldo.
* Tipo de línea principal normalizado a `00` y líneas anexas conservadas junto
  a su liquidación principal.
* Selección exacta y determinística de liquidaciones por empresa, período y
  estado; duplicidades o filas ambiguas bloquean la descarga.
* Departamentos particionados por identificador, por lo que nombres repetidos
  no mezclan archivos.
* Bloqueo de exportaciones con visibilidad multiempresa incompleta.
* Auditoría bloqueada persistente cuando la validación falla.
* Administradores existentes reciben explícitamente los cuatro permisos
  Previred mediante migración idempotente.
