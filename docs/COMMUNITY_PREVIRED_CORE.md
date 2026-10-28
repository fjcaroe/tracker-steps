# Núcleo Previred sin motor Enterprise — 28-10-2026

## Alcance

Base canónica ccf6985; rama propia codex/community-payroll-exports-20261028.
Código 9044539. El inventario de solo lectura continúa en 374 módulos instalados,
93 propios y 140 Enterprise; Cerro tiene 71 reglas y ninguna liquidación/contrato.
La fuente efectiva de step_hr_previred es 18.0.3.8.4, mientras la canónica ya tenía
18.0.3.8.7. La copia fresca ensaya su actualización a 18.0.3.8.8; no hay downgrade
ni escritura en producción. No se confunde ese upgrade nativo con conversión.

Se comprobó la frontera de modelos: el núcleo define perfiles, lotes/archivos y
un asistente con relaciones a compañía, usuario, departamento y sus propios
modelos. Su extensión de resource.calendar es Community. No hereda hr.payslip
ni define relaciones a un modelo de Nómina. Por eso puede instalarse sin motor;
la extracción real sigue a cargo de los puentes y proveedores explícitos.

## Implementación

step_hr_previred 18.0.3.8.8 depende de step_payroll_contracts 18.0.1.2.0. El núcleo
conserva modelos, IDs, campos, relaciones, perfiles, acciones, vistas, grupos y ACL.
Se elimina de su XML el ref obligatorio al grupo Enterprise. El hook conserva las
implicaciones existentes y enlaza los roles al grupo real del motor disponible;
el registro también lo resuelve cuando el motor aparece después del núcleo.
No se crean grupos ni aliases de motores inexistentes, ni un modelo hr.payslip.

El contrato de acceso resuelve los IDs reales de los grupos de Nómina, deduplicando
aliases de una misma identidad y rechazando identidades en conflicto. Comprueba
pertenencia al registro de grupo, no has_group de un alias que Odoo puede no tomar
como XML ID principal. La generación exige además su permiso propio y acceso
real al modelo. Sin motor se informa la falta de motor/puente, sin presentar un
archivo vacío o una simulación como exportación válida.

## Aceptación y evidencia

Paquete A, 130 archivos idénticos entre ambos paquetes completos y coincidentes
con Git, SHA256 3ff38732da4f55b12dcf43660d4f41c86ff0d963de54ed9a20676f4750146e43.
Community oficial con OCA y proveedor real: 113 pruebas, 69 módulos/cero EE.
Copia fresca nativa: 53 pruebas, 377 módulos/140 EE. El tercer escenario instala
solo el núcleo y sus dependencias Community: siete pruebas, 46 módulos/cero EE,
sin payroll/hr_payroll instalados y sin modelo hr.payslip registrado. El paquete
standalone coincide con el subconjunto exacto de archivos del paquete completo.
No se suman suites previas ni se presentan estas pruebas como certificación del TXT.

Los siete contratos del núcleo revisan aislamiento y dependencia, registro abierto,
error explicativo sin puente, ausencia de rutas de proveedor, formulario real con
usuario de resumen sin permiso de exportación y generación con usuario normal
contra el grupo real o explicación de ausencia. La consulta de roles no crea grupos.
El resto de contratos OCA/proveedor/almacenamiento/YTD se mantiene en los dos motores.

En la copia nativa se conservan 918 tablas/proyecciones, 140 contadores, 58.956 XML
IDs y los modelos/campos, ACL, reglas, relaciones, restricciones, históricos y
saldos originales, antes/después del upgrade y las pruebas. Fuente activa intacta;
los 52 archivos AGPL derivados se reproducen byte a byte. Los campos ausentes del
mapa parcial bajan de 1.076 a 984 por los modelos reales del núcleo; se mantienen
una diferencia de tipo, 12 de almacenamiento, 17 de obligatoriedad y seis de
selección. Cero diferencias en atributos comparados del proveedor. No se ha hecho
adopción de esos IDs ni conversión integral de Cerro.

Se contrasta además el respaldo original contra la copia ya probada: las 1.614
relaciones usuario-grupo y 283 implicaciones entre grupos son exactamente iguales,
con hashes y conteos completos. El verificador es versionado, solo lee el respaldo
y la copia privada y no exporta identidades individuales.

La matriz completa regenerada baja de 53 a 52 apps propias instaladas con caminos
EE pendientes; producción conserva 374 instalados, 93 propios y 140 EE. Continúan
111 manifiestos propios en repo y el inventario de productos fuera de Cerro.
El puente Blueminds fuera de Cerro pierde el camino EE del núcleo, pero conserva
una dependencia sin fuente inventariada; su cero de caminos conocidos no acredita
que ese producto esté migrado.

Evidencia privada: ~/.codex/local-artifacts/community-previred-core-20261028/
evidence-A, summary-A.json y verification-A.log. Servidor: /opt/steps-validation/
community-previred-core-20261028A y A-standalone; auditoría en community-previred-
core-20261028-audit. El resumidor verifica paquete/Git, conservación, configuración,
reproducción y prueba standalone sin motor. Los respaldos quedan en el servidor
privado; no se publican datos ni credenciales.

## Estado y límites

La prueba de formulario/permisos del núcleo no certifica los 105 campos Previred
ni la salida oficial de Simple Digital. Su puente, controles HTTP, generador,
normalización, perfiles y lotes deben probarse con datos/reglas originales sobre
OCA. Libro de Remuneraciones y su tablero aún conservan referencias Enterprise;
no se cambian esas dependencias sin cerrar modelos, vistas, acciones y permisos.
Los perfiles e históricos reales se conservan en la copia nativa.

Continúan bloqueados BASIC/GROSS y la adopción de las 71 reglas, estructuras,
entradas e identidad/almacenamiento del motor. YTD calendario está acotado, no es
certificación completa de YTD ni de políticas chilenas. DTE/CAF/folios/firma/
respuestas SII, Tesorería, Calidad, Studio/Documentos/Firma y los demás productos,
conversión integral restaurable con cero Enterprise y aceptación siguen pendientes.
La producción conserva Enterprise. El 31 de octubre mantiene riesgo alto y no está
resuelto por esta extracción. Producción, QA-Cerro, pagadas, vencimientos, Calendar,
Boolean bancario y 210233 no se modifican.

Siguiente prompt: continúa desde la canónica actualizada en worktree propio. Lee
AGENTS, ambientes, operación, workflow, plan, continuidad, autonomía, matriz completa,
COMMUNITY_PAYROLL_CONFIGURATION.md, COMMUNITY_PAYROLL_YTD.md y
COMMUNITY_PREVIRED_CORE.md. Revisa inventario completo y conserva lo probado. El
núcleo Previred puede instalarse sin motor y resuelve permisos contra el motor
real; eso no certifica sus archivos. Prioriza configuración original Simple Digital,
identidad y almacenamiento, 71 reglas/estructuras/entradas y la desconexión BASIC/GROSS.
Si sigue bloqueado, avanza el puente Simple Digital de Previred y Libro: modelos,
relaciones, formularios, menús/acciones, controladores y permisos antes de cambiar
dependencias. No simules generadores ni hr.payslip, no fabriques maestros o importes
para pasar la validación. Prueba paquete exacto en Community oficial y copia fresca,
conservando IDs, ACL, relaciones, maestros, históricos, saldos y correlativos. No
recalcules pagadas ni modifiques producción, vencimientos o QA-Cerro; respeta
Calendar, Boolean bancario y 210233. No emitas SII real. Guarda evidencia privada,
commits, push, integra solo lo validado y verifica handoff. Mantén visibles DTE/CAF/
SII, Previred/libro y conversión integral cero Enterprise.
