# Propiedades, traducciones y actores de nómina — aceptación del 29-10-2026

Aceptación posterior vigente: [COMMUNITY_ADMISION_NOMINA.md](COMMUNITY_ADMISION_NOMINA.md),
pareja y upgrade C. Esta hoja conserva la evidencia histórica F/I.

Aceptación histórica desde la canónica `205b1311`. La pareja **F**, paquete
de addons `4705aa85`, pasa **375 casos en Community y 252 en copia fresca de
Cerro**, sin fallos ni errores y con dos omisiones por entorno según proveedor.
Añade ocho contratos originales a los catorce del bloque anterior: **22 en total**.
La configuración original de 120 maestros/71 reglas y la conversión integral
siguen abiertas.

Se cierra también la pérdida de `noupdate` detectada en E: los 52 aliases
financieros conservan ahora su bandera original y la protección al actualizar
el bridge. El testigo compara los **59.048 XML IDs originales** completos.
E y los intentos anteriores conservan sus diagnósticos; F es la pareja aceptada.
El ensayo de actualización de almacenamiento aceptado es **I**, en otra base
Community privada nueva; su alcance se detalla abajo.

## Implementación validada

### Almacenamiento y traducciones

API OCA **18.0.1.10.0** conserva HTML traducible en `hr.salary.rule.note`.
La proyección explícita de un escalar original es `{"en_US": literal}`:
`en_US` es la base técnica de fallback de Odoo, no una afirmación de que el
texto fue traducido al inglés. NULL permanece SQL NULL, el texto vacío conserva
su diferencia respecto de NULL y un texto con apariencia JSON sigue siendo
literal. No se generan traducciones de otros idiomas.

Los objetos JSON existentes conservan todas sus lenguas y valores. La
preparación de un payload comprueba acceso normal al registro/campo y su
preimagen; rechaza un conflicto con la base u otra traducción existente, o un
NULL original que borraría valores actuales. Devuelve un plan, sin escribir
los maestros ni evaluar reglas. No resuelve colisiones de identidad.

`hr.payslip.input.type.name` **ya era traducible y JSON en Community**; en el
origen es escalar y `translate=False`. Se mantiene el contrato Community y se
implementa la política sin pérdida para una adopción posterior. La diferencia
de metadata/columna permanece visible: no se presenta como equivalencia estricta.
Los seis nombres originales todavía no se han importado.

El HTML sanitizado traducible de Odoo 18 usa un traductor de términos. Las
pruebas añaden traducciones autorizadas con `update_field_translations` y
`source_lang='en_US'`, conservando el HTML base; una escritura ordinaria del HTML
edita la fuente y no sustituye esa API. Se comprueban la lectura multilingüe y
el fallback sin crear una traducción ausente.

La herencia clásica de OCA requiere un límite explícito:
`hr.payslip.line.note` conserva **TEXT / `translate=False`**. La migración no
convierte notas de líneas históricas por herencia del campo del maestro. Su
eventual equivalencia nativa requiere una aceptación independiente.

### Analítica por compañía

Base Simple Digital **18.0.1.3.0** conserva la propiedad original
`hr.salary.rule.analytic_account_id` como JSON por compañía, con referencias
reales a cuentas analíticas. No infiere compañía desde la cuenta, estructura,
creador o contexto para convertir un escalar sin dueño explícito.

La admisión verifica el objeto físico y su clave exacta de compañía, existencia,
permisos normales y cuenta propia o compartida. Un `ir.default` no completa una
propiedad ausente o incompatible. SQL NULL, objeto vacío y slot NULL conservan
su representación; la admisión al procesar es un contrato separado. Se
rechazan booleanos físicos usados como IDs, extremos inválidos y permisos
ocultos incluso con caché o un recordset elevado.

La preparación de asientos sigue el proveedor OCA real: **prioridad de la cuenta
del contrato y, cuando falta, la propiedad original de la regla**. No se afirma
que esa prioridad certifique equivalencia con el motor nativo. Débitos y
créditos comprueban la distribución efectiva antes de publicar y no aceptan una
distribución distinta aportada al proveedor. Se revisan también todas las
líneas y reglas originales cuando se confirma un borrador ya calculado.

`hr.payslip.line.analytic_account_id` mantiene su columna escalar independiente;
no se transforma el historial pagado en una propiedad por compañía. Se
conservan la guarda de contexto de compañía, el diario general compatible y el
savepoint de la confirmación ya implementados en el bloque anterior.

**Sí hay DDL y proyección de representación de maestros en destinos privados:**
nota de regla TEXT a JSON y analítica de regla escalar a JSON cuando su dueño
ya está acreditado. Esto no crea ni reasigna maestros/IDs, ni reconstruye
importes históricos. La preparación del nombre de entradas puede convertir un
almacén escalar admitido, pero el Community de partida ya utiliza JSON. No se
reescriben las dos columnas independientes de líneas históricas.

Los helpers internos admiten una Community legítima independientemente del
nombre de su base y conservan las barreras estructurales/OCA/cero Enterprise.
Rechazan nativo o Enterprise también en `to install`, `to upgrade` y `to remove`.
El wrapper de ensayos mantiene el prefijo privado; los runners siguen exigiendo
respaldo, overlays, reservas y `/run/lock/steps-environments.lock`. No hay una
opción para omitir las guardas del motor.

En instalación inicial, la ausencia de `hr_payslip_input_type` sólo se admite
cuando el módulo real está en `to install`. El helper declara el estado
pendiente sin crear tablas o datos; lo hace el ORM real. En actualización una
tabla ausente aborta. La nota de regla de OCA debe existir y se prepara antes
del registro. Las conversiones son atómicas y no hacen commit propio.

### Relaciones, tipos y actores

Se conserva `RESTRICT` para las propiedades de cuentas débito/crédito y
`SET NULL` para `default_struct_id`, usando las políticas reales del ORM/FK.
No se elimina un mapa de cuentas de otra compañía al retirar su extremo.

El tipo expone la relación inversa real `struct_ids` y un contador que respeta
el actor, compañías permitidas y `active_test`, sin sudo ni relación paralela.
`structure.schedule_pay` lee la política de su tipo, sin escribirla al consultar.
Continúan las guardas de modalidades no certificadas y la prioridad explícita
del calendario sobre el fallback real del tipo de work entry. Se observaron
`monthly` y `weekly` en ambos motores. Los catálogos SQL de `schedule_pay`
están vacíos en ambos: la API relacionada está probada, pero el catálogo
completo de opciones en ejecución sigue explícitamente sin certificar.

Los casos de seguridad usan actores normales sin asignar gerente para obtener
un resultado verde. La instalación OCA genérica conserva al oficial como
lector de reglas; la referencia nativa comprueba el CRUD original, acceso a
campos, globales, país y denegación de compañías ajenas, incluida caché caliente.
**Comparar ambos comportamientos no adopta los ACL ni iguala los permisos.**
La diferencia de rol continúa bloqueando la adopción mientras no exista un
plan explícito que conserve las membresías, grupos, ACL y dominios originales.

## Identificadores financieros durante futuras actualizaciones

`step_bank_export_core 18.0.1.2.2` y
`step_accounting_multicurrency_core 18.0.1.1.1` conservan los 15 aliases bancarios
y 37 multimoneda, incluidos PK y `noupdate`. Los hooks validan el propietario
real y usan `_load_xmlid`; la protección acotada de `_process_end` cubre también
actualizaciones posteriores sólo del bridge. No se restaura ni infiere una
bandera al final del ensayo. Hay pruebas con flags mixtos, dos limpiezas reales
consecutivas y retiro de un namespace privado con otro propietario real.
Detalle: [COMMUNITY_FINANCE_XMLID_LIFECYCLE.md](COMMUNITY_FINANCE_XMLID_LIFECYCLE.md).

## Vacíos que el preflight mantiene visibles

El cierre anterior de catorce campos físicos y estos ocho contratos adicionales
no convierten todo el modelo nativo. Permanecen **12 diferencias de campo**:

| Modelo / campo | Diferencia pendiente |
| --- | --- |
| Estructura: `rule_ids` | One2many nativo frente a Many2many OCA; falta adopción de identidad/metadata de la relación. |
| Estructura: `type_id` | Obligatoriedad nativa frente a campo opcional Community. |
| Estructura: `unpaid_work_entry_type_ids` | API inversa original ausente; auditar su relación y uso real antes de declararla. |
| Tipo: `name` | Obligatoriedad diferente. |
| Tipo: `salary_benefits_ids` | Modelo/relación/API original pendiente; no sustituir por un campo vacío. |
| Entrada: `name` | Origen escalar no traducible frente a JSON traducible; política explícita implementada, adopción no ejecutada. |
| Regla: `category_id` | Diferencias de obligatoriedad y política de eliminación. |
| Regla: `code` | Obligatoriedad diferente. |
| Regla: `credit_tag_ids` | Relación y semántica original ausentes. |
| Regla: `debit_tag_ids` | Relación y semántica original ausentes. |
| Regla: `struct_id` | Obligatoriedad diferente. |
| Categoría: `code` | Obligatoriedad diferente. |

Persisten **7 diferencias físicas de columna**: nulabilidad de
`structure.type_id`, `type.name`, `rule.struct_id`, `rule.category_id`,
`rule.code` y `category.code`; además, el tipo escalar/JSON de `input.type.name`.
No son siete columnas ausentes. Los selectores originales `input` de condición
e importe siguen sin semántica admitida, aunque ninguna de las 71 reglas los
utiliza. Se mantienen los bloqueos al procesar; no se amplía una selección para
aparentar soporte.

## Identidad original y alcance todavía pendiente

La cápsula conserva **120 maestros y 71 reglas**: cuatro estructuras, cinco
tipos, seis tipos de entrada y 34 categorías. Sus **91 aliases** corresponden a
88 filas del origen y tres aliases del adaptador de referencia. No se afirma
que los 91 sean PK originales de `ir_model_data`; los tres nuevos tienen PK
distintos entre copias. No se importa la configuración en este bloque.

La referencia Community contiene demo: quedan 24 IDs originales ocupados y
60 XML IDs del proveedor ligados a otra identidad. No se borran maestros,
renumeran originales ni retargetean aliases para superponer la cápsula. Una
coincidencia numérica no acredita identidad. La preparación SQL separada de
los 71 pares estructura/regla conserva el origen y sigue sin cambiar su motor.

Faltan las compañías/diarios y demás referencias externas con identidad
acreditada, JSON completos, el reporte original 462 y el contrato de roles.
La acción 462 de la referencia CE sigue ocupada por otra clase de acción; el
renderer Community probado no autoriza sobrescribirla. Tampoco se certifican
las 71 reglas, liquidación completa, temporalidad de sueldo, asientos,
Previred/libro o históricos mediante esta extracción. La referencia humana es
SyS; no se recalculan sus pagadas ni se vuelve a pedir la referencia ya dada.

## Aceptación y evidencia

| Comprobación | Resultado |
| --- | --- |
| Paquete de addons F | `4705aa85`; 322 archivos iguales en ambos entornos y cotejados con Git |
| SHA256 de `source-files.json` | `2d9a7b209b385d56d0cfc8df918658dfeb32794e1a78c480793e49f884dafe8c` |
| Community oficial + OCA real | 375 casos, cero fallos/errores, dos omisiones; 95 módulos y cero Enterprise |
| Copia fresca de Cerro | 252 casos, cero fallos/errores, dos omisiones; 389 módulos, conserva 140 Enterprise como referencia nativa |
| Datos/correlativos originales de Cerro | 921 tablas/proyecciones y 140 contadores, 1.061 contratos iguales antes/después |
| Identidad/permisos originales | 59.048 XML IDs con PK/destino/`noupdate` exactos; 1.218 modelos, 27.045 campos, 5.076 selecciones, 2.324 ACL, 610 reglas, 1.330 menús y 463 relaciones preservados según los contratos versionados |
| Inspección posterior de registros cargados | 613 contratos CE y 1.602 nativos sin cambios; sólo metadata, sin conversión funcional implícita |
| Impresión real | Dos PDF desde valores almacenados, cuatro páginas revisadas, NULL/cero/negativos y firma conservados |
| Preflight de configuración | Dos lecturas idénticas; campos 20→12 y columnas 9→7; 22 contratos cerrados, tres observaciones de selecciones aún visibles |
| Roles originales | Plan de admisión con un ACL y una regla originales; mantiene 13 clases de bloqueo y no concede derechos nuevos |

Las dos omisiones CE son contratos que requieren el proveedor nativo de
aprobación/importe de lotes; las dos nativas corresponden a guardas específicas
de días e historial Community. No son excepciones de preservación.

Bases de la pareja: `COMMUNITY_PAYROLL_API_PROPERTIES_20261029F` y
`MANAGEMENT_QA_CERRO_PAYROLL_API_PROPERTIES_20261029F`. Respaldo fresco de Cerro
decodificado y filestore aislado, sin servicio público ni cambios en producción.
Pins: Community `4b4efe68291d6def5bb7d2e1f2b829e0cda577d4`, OCA
`4c71cd42e46a09a7512d92f5c63c0a9f7c26ad3e`. Se ejecutó el mismo paquete, con
las derivaciones Community del proveedor y consumidores registradas por hash.

### Actualización real de las dos propiedades

`COMMUNITY_PAYROLL_API_PROPERTIES_UPGRADE_20261029I` restaura la referencia
Community D aceptada en otra base nueva. Actualiza realmente API **1.9→1.10** y
Base **1.2→1.3**, manteniendo los demás addons de D. Es un ensayo de esos dos
componentes; no es un upgrade integral del paquete ni una conversión de Cerro.

Se calculó y cerró un fixture privado con actor normal y motor OCA real, con
asiento balanceado publicado, antes de cambiar su sueldo contractual vigente.
La comparación posterior cubre **877 filas de 20 tablas, tres relaciones M2M,
ocho modelos y 257 campos originales**, importes y contadores. Las notas HTML
TEXT y cuentas analíticas escalares de reglas cambian sólo a su representación
JSON explícita; NULL y las columnas independientes de líneas permanecen intactos.
La lectura histórica no reconstruye importes con el contrato actual.

El cargador vuelve a escribir los dos maestros XML `structure_chile` y
`structure_type_chile` con los mismos datos. Sus dos `write_date` se admiten
únicamente con PK/modelo/destino/`noupdate=False` exactos, fuente AGPL original,
derivación aprobada de 52 archivos, log real y ventana UTC tomada de PostgreSQL.
No se ignoran `write_uid`, fechas de liquidaciones/asientos u otros maestros.
El resultado distingue 875 filas preservadas bajo las proyecciones declaradas y
dos fechas auditadas, y declara **`all_original_raw_fields_exact=False`**.
No se simula igualdad binaria de las representaciones convertidas.

El marcador de pagado es **sintético**, sobre ese fixture recién cerrado, tras
comprobar sus IDs/estado/bloqueo. El valor SQL previo NULL queda sellado. No
certifica el flujo real de pago ni una nómina de cliente. La referencia D y
su filestore quedan idénticos; respaldo totalmente decodificado y cero
reescrituras manuales de estados de módulos. Trece pruebas puras del verificador pasan
también en Python 3.10 del servidor.

### Evidencia privada reproducible

Resumen independiente final, sin errores:
`C:/Users/tito4/.codex/local-artifacts/community-payroll-properties-20261029/acceptance-F-final/summary.json`.
Incluye fuentes/procedencia, PDF revisados, preflight/seguridad, contrato SQL
anterior, inspecciones de registros e `properties-upgrade/`. La prueba SQL
anterior de cinco FK/M2M sigue siendo una preparación separada de identidad;
no se presenta como adopción del motor.

Raíces remotas: `/opt/steps-validation/community-payroll-properties-20261029F/`,
`/opt/steps-validation/community-properties-preflight-20261029F/` y
`/opt/steps-validation/community-properties-upgrade-20261029I/`.
El export completo permitido tiene SHA256
`20935c3a0205ffe2798c30108c8028cf7f18f593e291a461a58a97187f6b50e2`.
El recibo privado de cierre registra commit/ramas y resultado de
`python tools/git/verify_handoff.py --require-pushed` tras publicación e integración.
No se publican dumps, filestore, fórmulas, datos personales, credenciales o
fuentes OEEL. Los ensayos de actualización D–H conservan sus diagnósticos;
I es el aceptado. Se respetó el bloqueo compartido y las reservas de espacio.

## Estado acumulado y próximo bloque

Inventario repetido en este bloque: Cerro **380 instalados / 140
Enterprise / 99 propios**; **53 apps propias instaladas** mantienen caminos
Enterprise. Repositorio: 124 manifiestos propios y 29 fuera de Cerro; Steps
310/123/19 y SyS 331/142/16 (instalados/EE/propios). Debe repetirse el inventario
al retomar; no convertir esos números en un porcentaje funcional de migración.

Priorizar la copia de adopción con espacio de identidad original y los 12
contratos restantes, sin importar sobre demo.
Continuar identidad/almacén del motor y certificación con SyS. Siguen críticos
DTE/CAF/folios/firma/respuestas/reintentos SII, pagos/conciliación de Tesorería,
Calidad, Studio/Documentos/Firma y los demás productos/fuentes.

No existe una conversión integral restaurable aceptada con cero Enterprise.
Producción conserva Enterprise; el corte sigue fuera de la automatización.
Mantener Calendar, Boolean bancario legado y 210233 descontinuada; no refrescar
QA-Cerro, recalcular pagadas/validadas, escribir producción, alterar vencimientos,
usar `step_expire_database`, emitir al SII real ni enviar mensajes.

**El 31-10-2026 sigue en riesgo alto.** Esta implementación y sus pruebas
funcionales parciales no permiten asegurar que todas las puertas estén
cerradas antes de esa fecha, ni resuelven el vencimiento.

## Siguiente prompt

Continúa desde origin/codex/ambientes-canonicos-reparacion actualizada en worktree
propio. Lee AGENTS, registro de ambientes, operación, workflow, continuidad,
COMMUNITY_PROPIEDADES_NOMINA.md, COMMUNITY_AUTONOMIA.md y sus referencias. La
pareja F pasó 375/252 casos, preservó 921 tablas/proyecciones, 140 contadores y
59.048 XML IDs con noupdate. El upgrade privado I pasó API 1.9→1.10/Base1.2→1.3
con historial protegido; sus dos fechas XML están auditadas, no ignoradas.

Cierra los 12 campos/7 columnas restantes y las relaciones reales de días no
pagados, beneficios y etiquetas contables antes de cambiar dependencias.
Prepara una copia de conversión que conserve identidad de modelos, 120 maestros,
71 reglas, relaciones, acciones, grupos/ACL y referencias externas. No importes
sobre demo, retargetees IDs ocupados ni reasignes el reporte 462; distingue los
88 aliases originales de los tres nuevos del adaptador. Conserva el plan de
seguridad bloqueado hasta una adopción real por rol, sin permisos de conveniencia.
Certifica reglas/días/entradas/redondeos/YTD/asientos/Previred/libro con SyS,
sin recalcular sus pagadas ni inferir su sueldo histórico desde el maestro actual.

Aprovecha hasta tres agentes autorizados para frentes independientes, con un
único coordinador de upgrades y un paquete coherente. Avanza en paralelo en
DTE/CAF/folios/firma/respuestas/reintentos SII offline y los demás productos;
la conversión integral restaurable con cero Enterprise sigue pendiente.
Conserva Calendar, Boolean bancario y 210233; producción y QA-Cerro intactos,
sin alterar vencimientos ni emitir al SII real. Prueba el paquete exacto en
Community oficial y copia fresca de Cerro, distingue referencia de conversión,
respaldo/bloqueo/overlays, evidencia privada, commits/push/integración validada
y verify_handoff --require-pushed. No declares resuelto el 31 con una extracción
parcial; el corte de producción permanece fuera de la automatización.
