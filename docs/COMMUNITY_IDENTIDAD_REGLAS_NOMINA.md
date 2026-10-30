# Nombres originales y propiedad de reglas de nómina — 29-10-2026

Continuación vigente: [COMMUNITY_ARRANQUE_ORIGINAL.md](COMMUNITY_ARRANQUE_ORIGINAL.md).

Aceptación Schema B y upgrade de nombres completada; resumen privado reproducible verificado.
Base canónica `78e5cde8`; paquete congelado en `e08ee7f4`.
351 archivos, huella común
`7f1e6fd96172723db7e02631ca90f91451a6a60a9366664bfdee5af1868fe97a`.
Tar Git SHA256 `fb28afffba55f27a34abe394edeb1d0c4b518eb2e0037c5b148764b596c75909`.
Conserva la aceptación de [Período C](COMMUNITY_PERIODO_NOMINA.md).
La integración conserva además la canónica concurrente `69780cd2` de Packing;
sus herramientas de corrección de fecha no modifican el paquete de Nómina probado.

## Implementación API 18.0.1.12.0

El nombre original de `hr.payslip.input.type` es un literal VARCHAR no
traducible. El adaptador anterior lo convertía a JSONB traducible; el ORM
oficial, al quitar ese atributo, puede proyectar sólo `en_US` y perder idiomas.
La nueva migración admite el cambio antes de la inicialización del campo:
conserva texto, espacios, Unicode, vacío, SQL NULL, ID y NOT NULL. Un literal
con apariencia JSON sigue siendo texto y nunca se interpreta como un objeto.

Un JSON existente sólo se convierte si tiene exactamente `en_US` con un
valor string. Cualquier otra clave, incluso con el mismo texto, base ausente,
JSON null, array, número o Boolean bloquea la migración. Un default SQL
requiere una política explícita. No se elige un idioma ni se borran idiomas
para completar la actualización. Una base con traducciones reales conserva
su estado y queda bloqueada para resolver ese contrato.

El helper usa bloqueo de tabla y savepoints, compara hash de ID/literal y
verifica el contrato físico. No elimina vistas, índices ni defaults para
forzar el DDL. Pre-init y pre-migración comparten la admisión real; conservan
las guardas de motor OCA, cero Enterprise y tablas esperadas.
La API privada `_step_original_name_literal` devuelve un plan escalar sin
escribir el maestro. El alias anterior `_step_original_name_translations`
devuelve ahora ese mismo literal, no un mapa; no tiene consumidores productivos
inventariados. Ambos verifican ACL/campo con actor normal, caché caliente y
sudo entrante. Las notas de reglas conservan su JSON multilingüe; las notas
históricas de líneas siguen siendo texto almacenado.

## Propiedad de reglas y namespace histórico

La herencia clásica OCA propaga métodos de `hr.salary.rule` a
`hr.payslip.line`. Los hooks de propietario ahora distinguen exactamente los
dos modelos: crear o editar una línea no intenta enlazar su ID numérico como
si fuera el ID de una regla ni modifica maestros durante un cálculo/asiento.
Las guardas históricas de las líneas permanecen en su cadena real.

Crear reglas, cambiar su propietario/compañía y modificar `structure.rule_ids`
autorizan las referencias físicas completas: propietario FK, pares M2M, reglas archivadas,
IDs ocultos y permisos de campo. El cambio FK, el retiro del enlace anterior
y el enlace nuevo comparten savepoint. Una denegación real en el segundo paso,
aunque el llamador la capture, revierte el conjunto. Las estructuras verifican
primarios por SQL completo, sin depender de un search filtrado por permisos.

Se mantienen NULL, copia, padres, compartición M2M y relaciones adicionales
existentes. **No se cambia `rule_ids` a One2many ni se asignan propietarios
inferidos.** La identidad nativa O2M y los cinco required siguen pendientes.
La referencia CE tiene tres estructuras sin tipo y diez reglas sin propietario;
OCA permite esos casos. Hacer los campos obligatorios ahora rompería el motor.

## Aceptación y preservación

**448 casos Community y 294 nativos**, cero fallos/errores, dos omisiones CE
y cinco nativas documentadas (las mismas de Período C). Son nueve
casos CE adicionales: tres de almacenamiento literal y seis de propiedad;
se conserva el paquete completo de cinco consumidores HR, Tesorería y CAF.
Las pruebas de propiedad usan motor, líneas y asiento OCA reales, actor normal,
denegaciones y comparación SQL de la historia cerrada.

El upgrade `name-scalar` parte exclusivamente de Período C aceptado:
API1.11→1.12; Base1.5 permanece igual. Incluye un tipo de entrada privado
persistido con el formato anterior y una nota con dos idiomas distintos. Antes
del upgrade intenta la migración real del candidato con un idioma adicional:
debe rechazarlo, conservar filas/esquema/contadores y retirar solamente el
fixture de idioma mediante rollback. Después prueba la conversión literal
admitida, IDs, relaciones, propiedades JSON y lectura histórica sin recálculo.

Schema A queda como diagnóstico: 1 fallo/0 errores de 448 casos, por un
fixture que esperaba retirar una regla archivada con el contexto por defecto.
El ORM conserva esa pareja; B pide `active_test=False` para ejercitar la
eliminación real. El producto y las guardas no cambiaron con esa corrección.
La rama nativa de A no se ejecutó.

El upgrade B compara **674 filas de veinte tablas**: conserva **671 literalmente**,
transforma exactamente un nombre privado JSON de una clave en su mismo literal y
audita los dos `write_date` XML existentes. No se cuentan esas tres filas como
byte-idénticas. Conserva **529 IDs de modelo y 10.265 de campo**, las tres
relaciones no vacías, JSON de notas/propiedades y contadores, sin campos nuevos.
El origen Período C y su filestore permanecen intactos; respaldo decodificado.

El origen Community aceptado tenía cero tipos de entrada persistidos. La
conversión positiva usa uno privado creado por el motor/API1.11 antes del
upgrade; no acredita importación de los seis tipos originales de Cerro ni
recálculo de liquidaciones comerciales. La nota privada lleva dos idiomas
distintos antes del cierre; su JSON completo y la historia se preservan.

La Community instala **96 módulos y cero Enterprise**. La copia fresca nativa
instala **391 y conserva sus 140 EE**; esa referencia no es una conversión.
Se preservan **921 tablas/proyecciones y 140 contadores comerciales** (1.061
contratos), **59.079 XML IDs originales con noupdate**, maestros, ACL,
relaciones, saldos e históricos en esa copia. Los 88 aliases originales y
los tres nuevos de referencia están clasificados sin deriva inesperada.
Las comprobaciones pasivas conservan 615 contratos de registro CE y 1.602 nativos.
Los dos PDFs nuevos, cuatro páginas renderizadas e inspeccionadas, mantienen
cero, negativos, NULL, visibilidad BASIC y bloque de firma.

El resumen offline reproduce el paquete exacto de 351 archivos contra Git,
las derivaciones, el upgrade, la negativa multilingüe y el contrato de beneficios.
No ejecuta el código de evidencias exportadas. Las 26 pruebas puras de las
herramientas (16 del upgrade, cinco del verificador y cinco del auditor) son
adicionales; no se presentan como cálculos comerciales ni pruebas de un motor
de beneficios. Las observaciones nativas de reembolsos/etiquetas previas siguen
vigentes y no acreditan paridad monetaria OCA.

## Estado acumulado y pendientes

Inventario fresco y repetido con el auditor del candidato: Cerro **381/140/100**,
Steps **310/123/19**, SyS **332/142/17** (instalados/EE/propios), sin cambios
respecto del final de Período C. Repo **126 módulos propios**, **30 fuera de
Cerro**, **54 apps instaladas con caminos Enterprise**. Las fuentes privadas
quedan incluidas; `steps_transport` conserva fuente recuperada e inactiva.

Se cierra un contrato de campo adicional: **27 acumulados**. Quedan **siete
brechas de campos y cinco físicas**, tres observaciones de selecciones y la
adopción de identidad/configuración. El nombre coincide en sus diez atributos
de campo y es VARCHAR NOT NULL; su ID de campo entre los motores aún es
distinto. La coincidencia de contrato no acredita adopción de IDs.
Se conservan los 12 bloqueos de seguridad, 24 IDs ocupados, 60 colisiones
XML ID y la acción 462. No se han ampliado permisos para atravesar esas puertas.

[Beneficios](COMMUNITY_BENEFICIOS_NOMINA.md) tiene ahora auditoría original
Cerro/SyS y alternativa OCA LGPL real, pero ninguna equivalencia declarada:
son diez modelos, catorce tablas y 58 registros relacionados que preservar,
aunque los beneficios configurados sean cero. No hay modelo vacío sustituto.

Continuar con identidad original sin demo/colisiones, propietarios y estructuras,
ACL, 120 maestros/71 reglas y valores originales de entradas. Los lotes siguen
bloqueando descriptores/tipos de entrada configurados mientras falta admitir
sus valores; siguen abiertos períodos parciales, redondeo/YTD, reembolsos,
contabilización, Previred y libro. Mantener DTE/CAF/folios/firma/transporte y
respuestas SII, Tesorería restante, Calidad, Studio/Documentos/Firma y todos
los productos hasta la conversión integral restaurable con cero Enterprise.

**El 31 sigue en riesgo alto.** Las pruebas sintéticas y extracciones parciales
no certifican liquidaciones de clientes ni resuelven el vencimiento. Sin escrituras
en producción, refresco de QA-Cerro, recálculo de pagadas, cambios de vencimientos
ni emisión real. Calendar, Boolean bancario y 210233 siguen protegidos.

Evidencia privada: `/opt/steps-validation/community-payroll-schema-20261029B`,
`community-schema-upgrade-20261029B`, `community-schema-preflight-20261029B`.
Copia local y resumen en
`C:/Users/tito4/.codex/local-artifacts/community-payroll-schema-20261029/acceptance-B`.
El recibo `accepted-evidence-B-final.receipt.json` queda en la carpeta padre.

> Continúa desde la canónica actualizada en worktree propio. Lee AGENTS,
> registro, operación, workflow, autonomía, continuidad, COMMUNITY_IDENTIDAD_REGLAS_NOMINA.md
> y COMMUNITY_BENEFICIOS_NOMINA.md. Conserva Schema B, Período C y sus guardas.
> Prioriza identidad original sin demo y propiedad O2M/maestros/ACL antes de
> dependencias; no asignes propietarios ni valores inferidos. Evalúa el motor
> OCA real de ventajas sin sustituir el catálogo nativo. Usa SyS como referencia
> real para reglas/entradas y certificación financiera; no recalcules pagadas.
> Cierra los restantes campos/períodos y valores originales de entradas, asientos,
> Previred/libro, DTE/firma/folios/respuestas y conversión integral cero EE.
> Respeta todas las restricciones, conserva traducciones bloqueadas y prueba el
> paquete exacto en ambos motores y upgrade. Guarda evidencia, commits/push,
> integra sólo lo validado y ejecuta python tools/git/verify_handoff.py --require-pushed.
