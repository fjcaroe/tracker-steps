# Configuración original y lectura histórica de nómina — 29-10-2026

Estado vigente y siguiente prompt: [COMMUNITY_PAGOS_CERTIFICADOS.md](COMMUNITY_PAGOS_CERTIFICADOS.md).
R3 valida 33 addons propios/508 archivos: aplicación contable de pagos nuevos,
admisión HR normal y cadena/CRL DTE offline, con Q4/D/H conservados. Pasaron
665 casos Community/457 referencia nativa, cero fallos/errores; 120/397
instalados y 0/140 EE. Se preservan 921 tablas/proyecciones, 140 contadores y
59.079 XML IDs, con 1.060 snapshots literales y testigo numérico tipado R3.
La clausura readonly de Calendar/Activity/Rating reduce guardas 116→113 CE y
27→24 nativas; no importa los 120 maestros/71 reglas ni reserva 462 ocupado.
Continúan 54 apps instaladas con caminos EE, coadopción/certificación SyS,
DTE completo, Calidad nativa y conversión integral cero EE pendientes.
La impresión técnica pasó seis páginas; aceptación productiva/legal abierta.
Producción conserva 140 EE. El 31 sigue en riesgo alto. Ver detalle y prompt.
El contenido inferior conserva su alcance histórico.

Bloque desde la canónica `db398fba`, worktree propio y rama
`codex/community-payroll-configuration-20261029`. Addons congelados en
`e097560b`; las herramientas posteriores sólo verifican/exportan evidencia.
Complementa [COMMUNITY_CUSTODIA_LOTES.md](COMMUNITY_CUSTODIA_LOTES.md),
[COMMUNITY_PAYROLL_CONFIG_ORIGINAL.md](COMMUNITY_PAYROLL_CONFIG_ORIGINAL.md) y
[COMMUNITY_CONFIG_ADOPTION_PREFLIGHT.md](COMMUNITY_CONFIG_ADOPTION_PREFLIGHT.md).

## Implementación

API OCA **18.0.1.9.0** añade los diez campos originales pendientes de regla y
estructura y los cuatro del tipo: `default_schedule_pay`,
`default_work_entry_type_id`, `sequence` y `wage_type`. Conserva relaciones
reales, propiedades JSON por compañía, NULL y archivo; no asigna propietarios,
padres, entradas o cuentas para completar originales. Las nuevas altas normales
conservan los defaults documentados; una adopción debe escribir los originales
explícitamente y no reutilizar defaults como dato de migración.

Cálculo y contabilización verifican toda la jerarquía efectiva, campos,
relaciones y permisos normales antes de cambiar líneas, estados o numeración.
Los modos o flags no implementados se almacenan y rechazan al procesar; no se
habilitan las cinco reglas con separación contable de la estructura archivada.
Una lectura histórica no ejecuta estas guardas ni repara configuración.

La contabilización usa el asiento real de OCA. Exige contexto de compañía y
diario general originales; comprueba la relación almacenada del contrato y
cada slot JSON original. Un JSON incompleto no puede tomar un diario desde
`ir.default`; sólo la propiedad totalmente NULL permite el fallback contractual
probado. Un savepoint propio protege también el fallo tardío del proveedor,
aunque el llamador capture el error. El caso de cuenta descontinuada usa un
fixture privado distinto de 210233; esa cuenta original no se reactiva.

Los onchanges reales del contrato aplican sólo políticas compatibles, antes de
mutar. La generación oficial de work entries conserva la prioridad explícita
del calendario; el tipo original interviene en el fallback real, sin caché
obsoleto. Horario o salario no certificados se conservan pero no se procesan.
Los formularios heredan vistas reales; las opciones no implementadas aparecen
sólo como lectura para el gerente. No se agregan ACL ni se retiran dependencias.

Base Simple Digital **18.0.1.2.0** imprime mediante la acción OCA real y la
plantilla AGPL derivada, con actor normal. Encabezado, referencia y valores
salen de la liquidación almacenada. Consulta completa de hijos autorizados,
ACL de registro y campo, NULL, cero, negativos, NET repetido de la misma regla
y rechazo de NET ambiguo están comprobados. No usa sueldo actual, reglas,
computes de total ni horas extra actuales. Ocultar BASIC cambia presentación,
no NET ni importes almacenados. Categorías relacionadas siguen siendo metadata
actual; esto no certifica clasificación histórica inmutable.

El empleado imprime su propio documento sin recibir permisos de configuración.
SQL sólo recupera importes físicos después de la admisión normal y metadata de
presentación acotada con ACL de campo. Sudo, caché, datos o contextos aportados
al reporte no conceden acceso a otras liquidaciones. Si un hijo queda oculto,
se rechaza el documento completo. El reporte original 462 sigue sin adoptar:
en Community está ocupado por otra clase de acción. No se sobrescribe ni se
crea un alias falso para aparentar identidad conservada. El bloque completo de
certificación/firma/identidad se mantiene unido al paginar con wkhtmltopdf; la
comprobación independiente del PDF distingue el signo menos con U+200B del
widget oficial y exige que un NULL quede vacío.

## Preparación física independiente

`prepare_payroll_configuration_storage.py` restauró un dump fresco totalmente
decodificado en `MANAGEMENT_QA_CERRO_CONFIG_STORAGE_20261029A`. Sin ORM ni cambio
de motor, añadió cinco columnas nullable de empresa/padre con las FK reales de
OCA y creó su relación original `hr_structure_salary_rule_rel` con exactamente
los **71 pares** derivados del `struct_id` original. No es una tabla paralela
de maestros. Conserva relaciones primarias, todos los valores/contadores
originales y todas las restricciones anteriores; dos repeticiones prueban
idempotencia, incluida una nueva transacción. Cero propietarios/padres asignados.

Evidencia privada en
`/opt/steps-validation/community-configuration-storage-20261029A/`.
Este ensayo SQL no adopta metadata, permisos o motor y no acredita recuperación
integral Community. Su contrato de cinco FK y M2M se coteja con el Community
actual, sin reutilizar números internos de campos.

## Aceptación

**D aceptado.** Paquete exacto de **299 archivos**, SHA256 de
`source-files.json`:
`3b98e6fa785c325aab62874a26fbbc5d13d469b87ec08140466a2b195ae41bbe`.
Community oficial `4b4efe68291d6def5bb7d2e1f2b829e0cda577d4` y OCA
`4c71cd42e46a09a7512d92f5c63c0a9f7c26ad3e`; mismos bytes en ambos ensayos,
con derivaciones AGPL y herramientas ejecutadas cotejadas con Git.

| Entorno privado | Registrados | Correctos | Omisiones explícitas | Fallos / errores | Instalados / EE |
| --- | ---: | ---: | ---: | ---: | ---: |
| Community oficial + OCA | 343 | 341 | 2 | 0 / 0 | 95 / 0 |
| Copia fresca Cerro, referencia nativa | 244 | 242 | 2 | 0 / 0 | 389 / 140 |

No se suman perfiles históricos. Los treinta casos adicionales CE son diecisiete
de configuración/contabilización, cuatro de tipos y nueve de impresión. El
perfil entero conserva las dos omisiones documentadas por API/política de la
aceptación G. Las herramientas de preflight tienen 19 y 7 pruebas locales
correctas, separadas del conteo Odoo.

Antes/después del upgrade y de las pruebas se preservan **921 tablas/proyecciones
y 140 correlativos**, **59.048 XML IDs**, 1.218 modelos, 27.045 campos, 5.076
selecciones, 2.324 ACL, 610 reglas, 1.330 menús, 463 relaciones y 529 restricciones.
Sólo continúa la excepción de presentación de tres campos de Corrección ya
aceptada; no se añade una excepción. Siguen intactos los 15 aliases bancarios y
37 multimoneda. La referencia mensual BASIC real aprobada de SyS coincide en
amount/quantity/rate/total con rollback de fixtures; no es replay de nómina
completa ni prueba de sueldo histórico inmutable.

Las inspecciones pasivas posteriores conservan exactamente **613 contratos CE**
y **1.602 nativos** de tablas/contadores, sin leer registros ORM de negocio ni
ejecutar computes. La preparación SQL independiente conserva **2.614 contratos**
de tablas y secuencias, incluidos contadores técnicos, y los 71 pares originales;
su contrato de cinco FK/M2M coincide con el registro Community 1.9.0 aceptado.
Estos conteos corresponden a auditorías distintas y no se suman.

Los dos PDF reales usan ruta autenticada y wkhtmltopdf. Se cotejaron bytes,
texto, geometría, NET 75, cero, negativo y NULL vacío; sus cuatro páginas fueron
inspeccionadas visualmente. BASIC aparece sólo en el primer caso; el segundo
usa estructura archivada. Firma/certificación/identidad quedan en la misma
página. No se certifica paridad visual nativa, branding ni snapshots inmutables
de los maestros relacionados del empleado/empresa.

El preflight readonly confirma **14/14 contratos físicos** originales, atributos,
columnas y las dos selecciones exactas. Quedan veinte diferencias de campo,
nueve físicas y tres de catálogo de selección fuera de ese cierre. Dos capturas
idénticas revalidan el origen sellado y el destino; no se importan maestros.
Las seis tablas de la cápsula B coinciden también en hashes/conteos con la
referencia nativa fresca D: 120 maestros, 71 reglas y M2M de entradas vacía.

**Procedencia XML ID:** los 91 nombres/model/res_id/noupdate de la cápsula
coinciden entre B y D. Son **88 filas del origen y tres aliases del adaptador de
referencia**, ausentes en el snapshot previo al upgrade. Las 88 filas conservan
sus PK; los tres aliases nuevos tienen otros PK de ir_model_data entre copias.
No se afirma que existan 91 PK originales idénticos. El snapshot de identidad
previo no incluye noupdate; la comparación B/D de esa bandera sí está capturada
en el preflight. Esa limitación debe cerrarse para la adopción integral.

Raíz privada aceptada:
`/opt/steps-validation/community-original-configuration-20261029D`.
Bases nuevas `COMMUNITY_PAYROLL_API_CONFIGURATION_20261029D` y
`MANAGEMENT_QA_CERRO_PAYROLL_API_CONFIGURATION_20261029D`. La segunda restaura
dump fresco totalmente decodificado y filestore de Cerro; conserva Enterprise
como referencia, sin servicio público, emisión SII ni cambios en producción.
Ambas operaciones y las inspecciones ORM se serializan con el bloqueo compartido.

Resumen completo privado, verificado sin errores:
`C:/Users/tito4/.codex/local-artifacts/community-payroll-configuration-20261029/acceptance-D/summary.json`.
Incluye `pdf-reviewed/`, `configuration-storage/`, `configuration-preflight/`,
`adoption-registry/`, inventario y cápsula. Preflight remoto en
`/opt/steps-validation/community-config-adoption-preflight-20261029D/`.
El exportador usa una lista permitida; no copia dumps, filestore, configuración,
credenciales o fuentes OEEL al repositorio. Los intentos A/B conservan sus
fallos de fixture/QWeb; C pasó Odoo pero la revisión del PDF exigió corregir el
paginado. Sólo D constituye esta aceptación; no modificar sus addons congelados.

## Pendientes y valoración del 31

La configuración original de **120 maestros / 71 reglas** y su cápsula de
**91 aliases** todavía
no está adoptada en OCA. La referencia limpia contiene demo y colisiones de
identidad; no se borran maestros ni se importan sobre ellos por coincidencia
numérica. Quedan el destino de conversión real, permisos originales por rol,
traducciones y las API no físicas, identidad de reporte, empresas/diarios y
políticas contables. `analytic_account_id` original es JSON por compañía y el
destino es entero: sus 71 NULL no autorizan ignorar esa incompatibilidad.
También faltan los selectores originales `input` de condición/importe, aunque
ninguna de las 71 reglas los usa. No se añaden declaraciones sin semántica. Los campos y el PDF cierran una parte verificable; no
certifican las 71 reglas, contabilización completa, Previred o libro de nómina
real con la configuración original. La referencia humana sigue siendo SyS;
no se pide otra vez ni se recalculan sus pagadas.

Inventario vigente: Cerro **380 instalados / 140 Enterprise / 99 propios**;
**53 apps propias instaladas** aún alcanzan Enterprise. Repositorio: 124
manifiestos propios, 29 fuera de Cerro. Steps tiene 310/123/19 y SyS 331/142/16
(instalados/EE/propios). `steps_transport` tiene fuente hallada, pero falta
acreditar procedencia/licencia y prueba funcional. Estos números no equivalen
a un porcentaje funcional de migración.

Siguen críticos DTE/CAF/folios/firma/respuestas/reintentos SII, pagos y
conciliaciones de Tesorería, Calidad, Studio/Documentos/Firma y los demás
productos. Hay núcleos y puentes probados, pero falta el paquete integral con
cero Enterprise, preservación completa, restauración ensayada y aceptación en
Desarrollo. Producción y QA-Cerro permanecen intactos. Se respetan Calendar,
el Boolean bancario legado y 210233. La automatización continúa; el corte de
producción queda fuera.

**Riesgo alto para el 31-10-2026.** No hay evidencia para asegurar que todas
las puertas puedan cerrarse antes de esa fecha. Ninguna extracción parcial
resuelve el vencimiento; no se alteran sus parámetros.

## Siguiente prompt

Continúa desde la canónica actualizada y este documento en worktree propio.
Lee AGENTS, registro de ambientes, operación, workflow, continuidad, autonomía,
configuración original y preflight; incorpora las respuestas humanas de SyS.
Prioriza una copia real de conversión que conserve identidad de maestros,
acciones, ACL, relaciones y almacenamiento. Cierra traducciones y las API no
físicas antes de adoptar las 71 reglas; nunca importes originales sobre demo
por coincidencia numérica ni reasignes el reporte 462. Certifica reglas/días/
entradas/redondeos/YTD/asientos/Previred/libro con referencias reales. Mantén
DTE/CAF/SII y el resto de productos visibles. Paquete exacto, Community oficial
más copia fresca de Cerro, evidencia privada, bloqueo, commit/push/integración
y verify_handoff. Mantén todas las restricciones operativas y no declares
resuelto el 31 con una aceptación parcial.
