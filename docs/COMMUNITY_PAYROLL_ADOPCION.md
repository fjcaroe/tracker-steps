# Jerarquías reales, permisos y FK históricos — 29-10-2026

Continuación de la canónica 5d827f9e. Worktree propio y rama
codex/community-payroll-adoption-20261029. Tres agentes autorizados preparan
frentes independientes; respaldos, restauraciones, upgrades y comprobaciones de
registro usan una sola cola bajo /run/lock/steps-environments.lock.
No hay publicación en servicios, refresco de QA-Cerro, recálculo de originales
ni cambios de vencimiento.

## Implementación de nómina

API OCA 18.0.1.7.0 resuelve estructuras y reglas heredadas mediante las APIs
reales get_structure_with_parents/get_all_rules, conservando sus registros.
Comprueba primero todos los vínculos originales, acceso normal a cada estructura
y regla, empresa y ciclos; detecta reglas ocultadas por reglas de registros,
sin sudo ni exposición de fórmulas. Los SQL de integridad usan flush de los
campos consultados para contrastar el estado actual de la transacción.

El cálculo continúa la cadena super existente. Se conserva la prioridad
(sequence,id) ya implementada para reglas con igual secuencia, incluso cuando
la regla más antigua pertenece al hijo y otra al padre. No se reemplaza esa
prioridad por el orden de inserción M2M o por el orden de los padres.

También se cierra la selección cuando struct_id está vacío. Usa los contratos
originales elegidos por OCA, coteja el dominio público completo del empleado/
período/estado/active_test, y verifica ACL y compañía. No admite una selección
parcial de contratos o reglas ocultas. No asigna maestros ni estructura al leer.

Contratos 18.0.1.11.0 e integración de seguridad Simple Digital 18.0.1.6.0 usan
ese alcance efectivo en el diagnóstico y guard financiero. Un perfil Chile
implícito o heredado no puede eludir el guard dejando vacíos estructura/contrato;
se diagnostican sus reglas originales y se requiere contexto explícito para
procesar. Las liquidaciones cerradas, pagadas o históricas conservan su bloqueo.
No cambian dependencias, reglas originales, sus fórmulas ni membresías existentes.

## Los tres conceptos ausentes no son una configuración de producción

La auditoría fijada del proveedor AGPL-3 y OCA confirma:

| Fuente | BASIC/GROSS/NET suministrados |
| --- | ---: |
| Datos productivos del proveedor Simple Digital | 0 |
| Datos productivos OCA Payroll | 0 |
| Datos de demostración OCA Payroll | 3 |

El default OCA fijado apunta al namespace legado hr_payroll.structure_base.
No se sustituye por payroll.structure_base de demostración para aparentar una
configuración chilena completa. El default del puente es padre no asignado;
los padres existentes o escogidos explícitamente, incluido default_parent_id,
se conservan. No se crean ni enlazan BASIC/GROSS/NET de muestra al perfil real.

hr_rule_source_audit.py verifica los 52 archivos AGPL y el pin/árbol OCA,
registra procedencia y hashes sin cuerpos de fórmulas ni lecturas DB. Falta
adoptar la configuración original, las 71 reglas y estructuras con identidad
histórica; GROSS de Cerro sigue requiriendo resolución con la referencia SyS.
Este bloque no certifica remuneraciones ni el período completo de un trabajador.

## Dos relaciones de contrato físicamente protegidas

validate_payroll_relation_storage.py ahora admite una referencia Community
real instalada, sin Enterprise. Verifica atributos de los cuatro campos y
las FK reales del motor. Sobre una copia NUEVA de SyS prepara las cuatro
columnas ya documentadas y dos FK validadas ON DELETE RESTRICT:

- hr_payslip_worked_days.contract_id → hr_contract.id.
- hr_payslip_input.contract_id → hr_contract.id.

No reemplaza ni renombra restricciones existentes. Un nombre, destino, tipo o
política inesperados bloquean toda la transacción. La repetición conserva los
OID/definiciones de las FK y la proyección original; no restaura secuencias.
Las pruebas OCA usan filas nuevas reales y comprueban que PostgreSQL rechaza
contratos inexistentes mediante esas FK, con savepoint y sin tocar históricos.

Preparación SyS C aceptada: 812 días y dos entradas; ocho FK originales intactas
y dos nuevas, 1.986 contratos de tablas/secuencias originales exactos antes/
después y tras repetir. Conserva los dos nombres NULL originales. Respaldo
totalmente decodificado, hash y reservas 5 GiB PostgreSQL/WAL y 2 GiB artefactos.
Servidor /opt/steps-validation/community-payroll-related-storage-20261029C,
base MANAGEMENT_QA_SYS_PAYROLL_STORAGE_20261029C.

Es preparación SQL: no carga Odoo, no calcula importes ni cambia metadata,
ACL, IDs, fechas o maestros originales. Las cuatro declaraciones nativas siguen
related/nonstore y no se aplica NOT NULL a sus columnas nuevas. La adopción
ORM/store, propiedad de metadata y conversión del motor siguen abiertas.
Su referencia inicial es Community A 1.7.0; la comprobación pasiva posterior
contrasta las mismas cuatro declaraciones con el paquete Community final.

## CAF y lotes: límites comprobados antes de crear reemplazos

CAF: [COMMUNITY_CAF_STORAGE.md](COMMUNITY_CAF_STORAGE.md) y
[COMMUNITY_CAF_REGISTRY.md](COMMUNITY_CAF_REGISTRY.md). SQL conserva 22 secciones
de metadata/almacén; el modelo original tiene 14 campos, 25 XML IDs, dos ACL,
una regla y cuatro FK. Las copias Cerro/SyS auditadas tienen cero CAF/adjuntos.
No existe contador ni reserva fiscal en la tabla CAF; no se inventa uno paralelo.
El contrato pasivo de registro inspecciona Binary.attachment y firmas/MRO sin
registros, payloads, defaults, cuerpos ni ejecución del proveedor. Siguen
asignación/concurrencia de folios, historia binaria, permisos y CAF/ancla reales.

Lotes: [COMMUNITY_BATCH_ADOPTION.md](COMMUNITY_BATCH_ADOPTION.md). Contrato de
11 modelos, 116 campos, 274 XML IDs, 16 ACL, tres reglas, tres propietarios M2M
y cuatro contadores. La copia Cerro sólo aporta un lote draft sin pagos ni
archivos: no prueba historia de lotes cerrados. bank.rec.widget y sus líneas
son consumidores reales pendientes. La alternativa OCA AGPL usa order/lot y
crea pagos; no es sustituto directo de account.batch.payment agrupando pagos
existentes. No se cambia la dependencia ni se registran modelos vacíos.

validate_adoption_registry.py inspecciona únicamente atributos de modelos y
campos ya cargados en registros privados aceptados, bajo READ ONLY, sin upgrade
ni servicio HTTP. Contrasta todas las tablas públicas y correlativos de negocio
antes/después; los contadores de caché/serial de infraestructura no son números
de documentos y los IDs originales quedan cubiertos por los hashes de tablas.
La captura de atributos no certifica un motor compatible ni autoriza retiro.

## Aceptación y evidencia

El candidato A pasó 252/215 casos sin fallos y preservó la copia. La revisión
posterior detectó el cambio de prioridad en empates y el camino de estructura
vacía; no se integró. El candidato final B añade las regresiones de ambos casos
y mantiene intacto el criterio de preservación.

**B aceptado, código 694bf2dc.** Community oficial/OCA: 254 casos registrados,
253 correctos y una omisión de política de lotes nativa; 78 módulos/0 Enterprise.
Copia fresca Cerro: 215 registrados, 213 correctos y dos omisiones de API
exclusiva Community; 386 módulos/140 Enterprise. Cero fallos y errores.
Se conserva la referencia nativa, no se convierte su motor a OCA.

Mismos 247 archivos fuente; SHA256 de source-files.json
4c3f3bdbe16e27d04b7e7b4303577813d61459d315667e307e52f6dd828e34f8.
Pins oficiales: Community 4b4efe68291d6def5bb7d2e1f2b829e0cda577d4 y
OCA 4c71cd42e46a09a7512d92f5c63c0a9f7c26ad3e. Las transformaciones privadas
del proveedor y consumidores HR se reproducen byte a byte desde Git.

Preservados 921 tablas/proyecciones y 140 correlativos después del upgrade y
de las pruebas, 59.048 XML IDs, 1.218 modelos, 27.045 campos, 5.076 selecciones,
2.324 ACL, 610 reglas, 1.330 menús, 463 relaciones y 529 restricciones originales.
La excepción de presentación sigue limitada a ayudas de tres campos y título
de uno de ellos en Corrección; demás propiedades e idiomas permanecen exactos.
Continúan intactos los 15 aliases bancarios y 37 multimoneda. BASIC positivo de
SyS coincide en amount/quantity/rate/total en ambos motores con rollback
comprobado; no se recalculó el original ni se certificó la nómina completa.

Las capturas pasivas B también pasaron en ambos registros: 496 contratos de
tablas/correlativos exactos en Community y 1.602 en la copia nativa. Confirman
CAF nativo con Binary.attachment=True, store=True y required=False; sin columna
caf_file en su tabla. Se obtienen _auto, currency_field, attachment y firmas
reales de lotes/consumidores. Community confirma ausencia de ambos proveedores,
sin rellenarlos con modelos ficticios. Los payloads de inspección no accedieron
a registros de negocio ni binarios y no ejecutaron computes/métodos del
proveedor; la preservación SQL obtiene únicamente conteos y huellas, sin
materializar importes en Python. La referencia de las cuatro
columnas/FK de SyS C coincide con las declaraciones del Community B final.

La configuración observada conserva 48 reglas activas distintas en Community,
39 en Chile. Hay 58 apariciones por herencia, que no son 58 maestros nuevos;
49 filas SQL incluyendo la inactiva, igual que en M y sin reglas de fixtures.
Continúan los tres conceptos esenciales ausentes del perfil Chile y el GROSS
desconectado en la referencia nativa de 71 reglas. No hay falsa certificación.

Reproducción sin DB sobre evidencia consolidada:

```powershell
python tools/community/summarize_payroll_api.py C:/Users/tito4/.codex/local-artifacts/community-payroll-adoption-20261029/acceptance-B --output C:/Users/tito4/.codex/local-artifacts/community-payroll-adoption-20261029/acceptance-B/summary.json
```

El verificador pasó: paquete exacto contra Git, snapshots originales, herramientas,
procedencia de reglas, FK SyS, registros pasivos e inventario de tres productos.
full_cerro_conversion, simpledigital_certified y deadline_resolved siguen false.
Bases COMMUNITY_PAYROLL_API_ADOPTION_20261029B y
MANAGEMENT_QA_CERRO_PAYROLL_API_ADOPTION_20261029B; servidor
/opt/steps-validation/community-payroll-adoption-20261029B. Capturas pasivas en
/opt/steps-validation/community-adoption-registry-20261029B.

Evidencia privada: ~/.codex/local-artifacts/community-payroll-adoption-20261029/,
subcarpetas sys-storage-C y acceptance-B. Los dumps, fórmulas, PDF y resultados
privados no se publican en Git. Los tests de perfiles anteriores se conservan
y no se suman como una única conversión integral.

## Pendientes y siguiente prompt

Inventario repetido de las tres producciones: Cerro 380/140 módulos/Enterprise,
Steps 310/123 y SyS 331/142. Permanecen 119 manifiestos propios, 24 fuera del
inventario Cerro y 53 apps propias instaladas con caminos Enterprise genéricos.
Las fuentes localizadas de Transport no están activas ni tienen procedencia/
licencia resueltas; ver COMMUNITY_TRANSPORT_SOURCE.md. No confundir este
inventario o un registro Community de pruebas con todos los productos migrados.

Sigue siendo crítico adoptar los modelos/metadata/IDs/FK/M2M e histórico completo
del motor; incorporar y certificar las 71 reglas/estructuras/entradas originales,
días, redondeos/YTD, asientos y Previred/libro no vacíos. Continúan DTE/CAF/folios/
firma/respuestas SII, lotes/conciliación, Calidad, Studio/Documentos/Firma y demás
productos. Falta copia integral restaurable con cero Enterprise y aceptación.
El riesgo del 31 sigue alto; este bloque no resuelve el vencimiento ni autoriza
corte o desinstalación Enterprise en producción.

Continúa desde origin/codex/ambientes-canonicos-reparacion actualizada en un
worktree propio. Lee AGENTS, registro de ambientes, operación, workflow,
COMMUNITY_AUTONOMIA.md, COMMUNITY_CONTINUACION.md, esta aceptación y referencias.
Reutiliza lo comprobado y revisa inventario vigente antes de implementar.
Prioriza la adopción real de reglas/estructuras e identidad histórica usando
la referencia SyS y la copia C: no asignes los tres maestros demo como solución.
Conserva la prioridad (sequence,id), el alcance completo también en fallback y
los contratos/horas originales; prueba cálculo real sobre casos aprobados nuevos,
sin recalcular originales pagados. Cierra metadata/store/propiedad sin confundir
las dos FK validadas con conversión ORM.

Se permiten hasta tres agentes adicionales. Avanza también con el motor real
de lotes y el asignador/almacén CAF, conservando sus bloqueos concretos. Bases y
upgrades en serie con respaldo y bloqueo compartido. No cambies dependencias
antes de cerrar modelos/relaciones/vistas/IDs/ACL. Preserva maestros, históricos,
saldos y correlativos; respeta Calendar, Boolean bancario y 210233. No escribas
en producción, retires allí EE, alteres vencimientos, uses step_expire_database,
refresques QA-Cerro, emitas al SII o envíes mensajes externos. No copies OEEL ni
simules hr.payslip. Prueba paquete exacto Community y copia fresca Cerro, y SyS
si cambia histórico. Evidencia privada, commits/push, integra sólo lo validado y
python tools/git/verify_handoff.py --require-pushed. El corte queda fuera de la
automatización y el 31 sigue pendiente hasta todas las puertas integrales.
