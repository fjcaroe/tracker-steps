# Changelog

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
