# Ventajas contractuales OCA: candidato funcional y límites

Candidato desde la canónica `ce24087d`, 30-10-2026. Conserva la pareja H de
[Multifrente](COMMUNITY_MULTIFRENTE.md). El inventario fresco del coordinador
permanece igual: Cerro 381/140/100, Steps 310/123/19, SyS 332/142/17
(instalados/Enterprise/propios); SHA256
`2cd3cfb9a85b88c5ddd65657228df3468d87dec65a50e54a89da808da64ca9ba`.
Esta hoja describe implementación y pruebas preparadas, **sin aceptación de
bases todavía**. El coordinador ejecuta las copias nuevas y el paquete exacto.

## Proveedor real y adaptación

`payroll_contract_advantages` `18.0.1.0.0`, LGPL-3, se usa desde el pin OCA
`4c71cd42e46a09a7512d92f5c63c0a9f7c26ad3e`. No se modifica su fuente. Aporta
dos modelos reales: `hr.contract.advantage.template` y
`hr.contract.advantage`, relacionados con el contrato por `advantages_ids`.
Su API `hr.payslip.get_current_contract_dict` proporciona el objeto real
`current_contract.advantages` al evaluador OCA. Los importes siguen siendo
Float del proveedor; no se certifica aritmética Decimal ni una conversión de
históricos NUMERIC por este bloque.

El nuevo `step_payroll_advantages_oca` `18.0.1.0.0` depende de ese proveedor y
de la frontera Simple Digital Community existente. No declara campos, tablas
de beneficios nativos ni aliases equivalentes. Mantiene los ACL originales
OCA y añade una regla global de compañía a los valores por contrato. No
asigna roles, sustituye contratos ni fabrica beneficios.

La admisión privada `_step_check_contract_advantages` comprueba el actor
normal y los contratos seleccionados por la API real. Antes de calcular o
contabilizar recoge todas las filas físicas de esos contratos, comprueba
acceso a cada fila/plantilla/campo y lee el almacén SQL autorizado. Rechaza
tipos o cantidades ausentes, NULL físicos, valores no finitos, límites
invertidos o incumplidos y códigos ambiguos por contrato. Un código duplicado
no puede convertirse silenciosamente en el último valor de un diccionario.
No rellena faltantes con cero ni modifica los valores durante la admisión.

El cero explícito conserva la excepción existente de límites del proveedor
OCA; no se confunde con NULL. Los importes negativos se admiten sólo dentro
de sus límites reales. Crear o cambiar valor/plantilla comprueba referencias y
límites dentro de una transacción; cambiar límites después del cálculo se
vuelve a comprobar antes del asiento. Las cantidades y tasas se aplican por
la **regla salarial OCA real**, no mediante un campo de cantidad inventado
en ventajas. En reglas Python se usan `result_qty` y `result_rate`, tal como
requiere el proveedor; el campo `quantity` no sustituye ese resultado de la
regla de código. No se añade un redondeo ajeno al cálculo vigente del motor.

Los métodos de lectura, copia y mutación de los valores y plantillas conservan
el UID normal aun con sudo entrante. Los valores de otra compañía no se
pueden leer o copiar por caché caliente. Una referencia contractual o de
plantilla vacía queda bloqueada para crear/mutar valores en este puente;
sus columnas OCA no se convierten globalmente a required ni se rellenan datos
anteriores para imponer otro esquema.

## Histórico y referencia nativa

Un recibo cerrado no proporciona un contexto calculable de ventajas actuales.
La API de cálculo/contabilización y `get_current_contract_dict` lo rechazan,
también con sudo. La lectura histórica de líneas y asientos usa sus importes
almacenados. Cambiar las ventajas o su código para períodos futuros no debe
reescribir esas líneas ni reconstruirlas a partir de un contrato vigente.
No se crea un snapshot paralelo que se haga pasar por procedencia histórica.

`step_payroll_benefits_native_reference` `18.0.1.0.0` es una referencia separada,
dependiente del proveedor nativo ya instalado. No se instala en Community.
Sus casos usan el catálogo y los valores nativos reales, formulario y roles
originales; no leen ni copian cuerpos OEEL ni calculan liquidaciones pagadas.
Comprueban la relación One2many original por su inverso y la conservación de
las catorce tablas anteriores al ensayo privado. No declaran que el valor
configurable del catálogo equivalga al importe OCA por contrato.

## Pruebas preparadas

Diez casos Community sobre modelos, motor y asientos reales:

- Cálculo mediante `current_contract.advantages`, cantidad 3, tasa 80 y asiento
  balanceado; formularios originales de contrato y plantilla.
- Onchange real, límites, cero explícito y negativos autorizados.
- Filas físicas o plantillas ocultas, lotes y caché/sudo sin mutaciones parciales.
- ACL de campo de importe/límite y usuario interno sin permisos de Nómina.
- Códigos duplicados y SQL NULL que no se convierten en último valor/cero.
- Límites cambiados entre cálculo y contabilización.
- Rechazo de reconstrucción de historia cerrada tras cambiar valores actuales.
- Compañía ajena, lectura/copia/edición/eliminación y referencias normales.
- No finitos, límites invertidos y cambio de plantilla fuera de límites.
- Error real de una segunda regla que revierte ambos borradores.

Tres casos de referencia nativa comprueban catálogo/valor e inverso reales,
formulario/roles y conservación sin instalar OCA. Son contextos diferentes;
no acreditan trece cálculos comerciales equivalentes ni certificación chilena.
No se han ejecutado estas pruebas de base por el agente implementador.

## Puertas que siguen abiertas

La familia nativa continúa siendo **diez modelos, catorce tablas y 58 maestros**,
con 46 campos de beneficio, Firma, documentos, ofertas y otras relaciones.
Sus dos modelos OCA no son un reemplazo nominal. Sigue abierta la identidad/API
de `hr.payroll.structure.type.salary_benefits_ids`; no se añade un alias vacío,
se cambia el comodelo ni se importa su catálogo original en estas tablas OCA.
Véase [auditoría nativa](COMMUNITY_BENEFICIOS_NOMINA.md).

La etapa siguiente debe definir un puente con las identidades originales,
funciones y referencias que efectivamente usan Cerro/SyS, conservando los 58
maestros y permisos. Las funciones no demostradas deben seguir bloqueadas.
Este candidato quita la falta de un motor libre probado como siguiente puerta,
si su aceptación pasa; no cierra por sí solo la coadopción original.

Continúan las 71 reglas/120 maestros, referencias externas/acción 462, roles,
certificación SyS, Previred/libro y la conversión integral restaurable con cero
Enterprise. Se mantienen las restricciones de producción, QA-Cerro, históricos,
vencimientos, SII, comunicaciones, Calendar, Boolean bancario y cuenta 210233.
La fecha del 31 sigue en riesgo alto; no se deduce resuelta por este candidato.
