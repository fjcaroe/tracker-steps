# Propiedades, traducciones y actores de nómina — borrador del 29-10-2026

**BORRADOR: NO ACEPTADO.** Revisión del candidato `5489141b`, desde la canónica
`205b1311`. La aceptación vigente continúa en
[COMMUNITY_CONFIGURACION_NOMINA.md](COMMUNITY_CONFIGURACION_NOMINA.md), pareja D.
Esta hoja no reemplaza sus pointers ni autoriza integración, importación o corte.

El ensayo E terminó funcionalmente verde, con **375 casos Community y 252 en
referencia nativa** informados por el coordinador. La comprobación posterior
detectó **52 banderas `noupdate` originales que cambiaron de False a True** por
hooks financieros. E no cumple preservación y no constituye una aceptación.
La corrección y una nueva pareja fresca permanecen pendientes; no se añade una
excepción al comparador para admitir esas modificaciones.

## Implementación candidata

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
del calendario sobre el fallback real del tipo de work entry.

Los casos de seguridad usan actores normales sin asignar gerente para obtener
un resultado verde. La instalación OCA genérica conserva al oficial como
lector de reglas; la referencia nativa comprueba el CRUD original, acceso a
campos, globales, país y denegación de compañías ajenas, incluida caché caliente.
**Comparar ambos comportamientos no adopta los ACL ni iguala los permisos.**
La diferencia de rol continúa bloqueando la adopción mientras no exista un
plan explícito que conserve las membresías, grupos, ACL y dominios originales.

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

## Puertas de aceptación abiertas

1. Corregir las 52 modificaciones de `noupdate` sin ignorarlas, restaurarlas
   artificialmente al final ni añadir una excepción al comparador. Capturar la
   bandera y PK originales antes y después de la actualización real.
2. Repetir el paquete corregido exacto en Community oficial y copia fresca
   aislada de Cerro, con preservación y herramientas de evidencia completas.
   Las dos referencias deben usar el mismo paquete Git; cada derivación debe
   estar declarada y cotejada con los bytes probados.
3. Completar el ensayo de actualización desde la referencia D en otra copia
   nueva. El seed/replay de upgrade E tiene un bloqueo pendiente. No basta una
   instalación limpia para declarar preservación al cambiar el almacenamiento.
   Verificar estado/pagada, importes, notas y analítica de líneas, modelos,
   campos, relaciones y contadores; no reconstruir valores con sueldo actual.
4. Resolver los marcadores inferiores y revisar el resumen independiente antes
   de marcar aceptación, integrar o actualizar pointers. Ningún resultado de
   E se promueve automáticamente por haber pasado las pruebas funcionales.

| Evidencia de cierre | Estado en este borrador |
| --- | --- |
| Commit del paquete final corregido | `PENDIENTE_COMMIT_FINAL` |
| Conteos finales CE/nativo, correctos y omisiones | `PENDIENTE_CONTEOS_FINALES` |
| Archivos exactos y SHA256 de `source-files.json` | `PENDIENTE_FINGERPRINT_PAQUETE` |
| Preservación final, incluidos PK/`noupdate` | `PENDIENTE_PRESERVACION_FINAL` |
| Upgrade D → API 1.10/Base 1.3 y replay almacenado | `PENDIENTE_UPGRADE_PROPIEDADES` |
| Preflight repetido de las 12 diferencias/7 columnas | `PENDIENTE_PREFLIGHT_FINAL` |
| Ruta del resumen independiente revisado | `PENDIENTE_EVIDENCIA_REVISADA` |
| Push, integración y `verify_handoff --require-pushed` | `PENDIENTE_HANDOFF_ACEPTACION` |

La raíz privada del ensayo observado es
`/opt/steps-validation/community-payroll-properties-20261029E/`; sus resultados
no son la raíz aceptada definitiva. Los pins de referencia son Community
`4b4efe68291d6def5bb7d2e1f2b829e0cda577d4` y OCA
`4c71cd42e46a09a7512d92f5c63c0a9f7c26ad3e`. El cotejo del paquete final,
derivaciones, fuentes y evidencia sigue pendiente. No publicar dumps,
filestore, fórmulas, datos personales, credenciales ni fuentes OEEL.

## Estado acumulado y próximo bloque

Inventario vigente de la última aceptación: Cerro **380 instalados / 140
Enterprise / 99 propios**; **53 apps propias instaladas** mantienen caminos
Enterprise. Repositorio: 124 manifiestos propios y 29 fuera de Cerro; Steps
310/123/19 y SyS 331/142/16 (instalados/EE/propios). Debe repetirse el inventario
al retomar; no convertir esos números en un porcentaje funcional de migración.

Tras cerrar la aceptación local, priorizar la copia de adopción con espacio de
identidad original y los 12 contratos restantes, sin importar sobre demo.
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

## Prompt de continuación provisional

Continúa desde la canónica actualizada en worktree propio. Lee AGENTS, registro
de ambientes, operación, workflow, continuidad, la última aceptación vigente,
este borrador y COMMUNITY_AUTONOMIA.md. Primero cierra las modificaciones de
noupdate y el ensayo de upgrade, repite la pareja exacta y resuelve los marcadores
de aceptación antes de promover este documento. Después adopta identidad y
referencias originales sin sobrescribir los 120 maestros/71 reglas/88 filas
originales de aliases ni los tres aliases del adaptador. Mantén visibles los
12 campos/7 columnas y los selectores no admitidos. Certifica con la referencia
real SyS sin recalcular históricos. Conserva DTE/CAF/SII y todos los productos,
las restricciones operativas, bloqueo/respaldo/overlays y la puerta integral
restaurable cero EE. Guarda commits, push e integra sólo lo validado; verifica
handoff. No declares resuelto el 31 por cerrar una extracción parcial.
