# Paquete ampliado HR, bancos y CAF — 29-10-2026 UTC

Continuación y aceptación posteriores:
[COMMUNITY_PAYROLL_ADOPCION.md](COMMUNITY_PAYROLL_ADOPCION.md). Este documento
conserva la evidencia histórica de M; no reemplaza el estado/prompt vigente.

Continuación de f56e221d. El usuario pidió ampliar los bloques y autorizó hasta
tres agentes adicionales. Se usaron cuatro worktrees propios; los upgrades y
respaldos siguieron en serie bajo `/run/lock/steps-environments.lock`. No se
publicó en servicios ni se refrescó QA-Cerro. La programación horaria continúa.

## Implementación

**Días y entradas históricos.** API OCA 18.0.1.6.0 conserva el nombre NULL de
entradas originales; no lo sustituye por el nombre actual del maestro. Al crear
filas tipadas abiertas toma únicamente el contrato real de su liquidación, y
rechaza otro contrato/trabajador/empresa. Crear, mover, modificar o eliminar
días/entradas de liquidaciones cerradas queda bloqueado. Las filas sin tipo no
reciben un maestro inventado al leer.

`validate_payroll_relation_storage.py` prepara cuatro columnas físicas en una
copia nueva de SyS: code y contract_id de días/entradas. Copia los valores que el
motor nativo mostraba por sus relaciones originales; rechaza maestros ausentes,
contratos incoherentes, conflictos y nulos almacenados preexistentes. No carga
Odoo ni calcula importes, no cambia descripciones, metadata, write_date o
secuencias. Es preparación SQL para la adopción: el registro nativo sigue
declarando esos campos relacionados no almacenados. No equivale a cambiar motor,
adoptar sus FK/metadata OCA ni certificar toda la nómina.

**Cuatro consumidores HR reales.** Lifecycle/finiquitos, adaptador Simple
Digital, transición y Corrección se instalan sobre el proveedor Simple Digital
AGPL-3 y el motor OCA real mediante un overlay reproducible. Ver la fuente fijada
en [COMMUNITY_SIMPLEDIGITAL_OCA.md](COMMUNITY_SIMPLEDIGITAL_OCA.md).
El overlay sustituye únicamente prerrequisitos y referencias externas de
vistas/menús/grupos; se conservan modelos, campos, XML IDs y ACL propios.
Los manifiestos genéricos siguen nativos hasta aceptar la conversión de identidad.

Corrección deja de cancelar y recalcular `done`: valida nuevamente estados y
banderas pagadas/históricas, bloquea todo el lote antes de mutar, comprueba grupo
RPC, empresa, contratos y visibilidad completa de asistencias, toma bloqueo de
filas y usa savepoint. Las entradas que cruzan el corte requieren revisión de
horas. OCA debe usar entradas reales; no se admiten días teóricos como sustituto.
Se conservan finiquitos aprobados/pagados y sus vínculos con trabajador/compañía.

Se cierran seis consumidores de horas semanales. El calendario nativo mantiene
su valor del proveedor; Community usa las APIs oficiales de asistencias globales
y duración, incluyendo ciclo de dos semanas y excluyendo colación. Fechas,
asignaciones individuales, semanas ambiguas y flexibilidad sin referencia se
rechazan para revisión. No se crean jornadas ni se usa una constante de ocho
horas. La adecuación se invalida al cambiar tramos reales.

**Flujo bancario Community.** `step_bank_export_core` 18.0.1.2.1 usa pagos,
beneficiarios y cuentas originales. Produce XLSX BancoEstado de siete columnas
y BIFF8 Security de nueve columnas. Verifica RUT, CLP entero positivo, dirección,
empresa, titularidad, código bancario y autorización original de la cuenta.
El asistente normal de Contabilidad permite seleccionar pagos, generar y
descargar el archivo privado con ACL de responsable, reglas globales de dueño y
empresa y controles de `ir.binary`. No crea, contabiliza ni transmite pagos.
Mantiene las políticas de aprobación nativas cuando existen.
La selección se comprueba por todos los IDs relacionados, sin leer datos con
sudo ni exportar un subconjunto oculto por reglas. Una revocación de lectura
bloquea también el binario ya generado y la lectura RPC. El asistente no acepta
comandos de crear/modificar/eliminar pagos, incluidos defaults de contexto.
Los adaptadores nativos BE/Security y CSV interno usan igualmente la relación
completa; sus versiones son Tesorería 18.0.1.5.1 y Security 18.0.1.1.1.

Los dos campos bancarios, siete valores de selección, dos vistas, dos aliases
del modelo bancario y dos campos relacionados del asistente original conservan
sus IDs y ambos namespaces. El único cambio de XML IDs admitido es noupdate false→true
para esos quince registros; arquitectura y permisos originales de vistas permanecen
exactos, con procedencia de archivo nueva controlada. Los adaptadores de lotes
nativos conservan aprobación, adjuntos y contadores. El motor completo de lotes
y conciliación todavía depende de Enterprise.

Balance Analítico 18.0.1.1.0 depende del núcleo multicurrency ya extraído, cerrando
su camino Enterprise innecesario. No cambia datos ni fórmulas monetarias.
La referencia debe actualizar también el puente multimoneda canónico 18.0.2.1.0:
el 18.0.2.0.1 instalado aún define el método antiguo de account.move y puede
sobrescribir la extensión analítica por orden de carga. Ese puente se incluye
en el fingerprint común y solo se carga en la referencia nativa; se prueban
además los once contratos monetarios del núcleo en ambos entornos.

El núcleo multimoneda 18.0.1.1.0 adopta 37 XML IDs legados: 26 campos,
seis aliases de modelo y cinco vistas. Incluye los cinco campos delegados
reales de account.bank.statement.line mediante move_id. El alias de
account.report permanece en el puente Enterprise; no se inventa ese modelo
en Community. La adopción protege las filas originales antes de limpiar el
namespace del puente y también soporta actualizar una instalación previa del
núcleo.

**CAF verificable.** `step_l10n_cl_edi_core` aporta parser XML estricto, FRMA RSA
con ancla/fingerprint/IDK explícitos, comprobación de claves y selección de folio
sin consumo. Conserva bytes originales, incluido RSASK sin exponerlo en errores
ni representaciones; original_bytes() devuelve deliberadamente el documento
sensible y exige la misma custodia que el CAF original. Ver
[COMMUNITY_CAF_CORE.md](COMMUNITY_CAF_CORE.md). No crea modelos ni secuencias.
Cerro tiene cero CAF: las pruebas criptográficas son sintéticas, no certifican
CAF real ni emisión, firma completa, persistencia, reservas de folio o respuestas
SII. No se copiaron fuentes OEEL ni se emitió al SII.

## Evidencia y aceptación

**Pareja final M aceptada, código caa8bc94.** Perfil simpledigital con
--accelerated, sin despliegue. Community oficial/OCA: 242 casos registrados,
241 ejecutados correctamente y una omisión nativa explícita; 78 módulos,
cero Enterprise. Copia fresca Cerro: 214 casos registrados, 212 ejecutados
correctamente y dos omisiones específicas de API, cero fallos/errores,
386 módulos y los 140 Enterprise conservados como referencia. No sumar estas
suites a perfiles agrícolas, Libro/Previred/HTTP/PDF anteriores sin cambios.

Mismos 246 archivos fuente, incluyendo el proveedor AGPL derivado de 52 archivos
y la transformación HR reproducida separadamente byte a byte. SHA256 de
source-files.json: 8c661555b1ba4608b893b12f800756ade6a83406466f18f8f6e40e3405ded3a1.
Community oficial mantiene revisión 4b4efe68291d6def5bb7d2e1f2b829e0cda577d4;
OCA Payroll, 4c71cd42e46a09a7512d92f5c63c0a9f7c26ad3e.

Preservación exacta después del upgrade y después de tests: 921 tablas/
proyecciones y 140 contadores, 1.061 contratos de negocio en total. Permanecen
los 59.048 XML IDs, 1.218 modelos, 27.045 campos, 5.076 selecciones, 2.324 ACL,
610 reglas, 1.330 menús, 417 vínculos acción-vista, 463 relaciones y 529
restricciones originales. También se conservan las relaciones originales de
grupos, reglas y menús. Los únicos cambios de presentación de campos admitidos
son las ayudas de tres campos y el título de uno de ellos en el asistente
Corrección, contrastados exactamente con su AST;
las demás propiedades e idiomas originales permanecen intactos.

Los 15 aliases bancarios y 37 multimoneda están verificados en los registros y
formularios reales; los dos transitorios nuevos quedan vacíos. BASIC positivo
SyS vuelve a coincidir en amount/quantity/rate/total con la referencia SQL y PDF,
con TransactionCase, rollback comprobado y cero empresas/usuarios de ese fixture
restantes. No se recalculó la liquidación original ni se certificó el período
completo.

La inspección de configuración sigue bloqueando el uso salarial real:
Community tiene 48 reglas totales/39 chilenas y faltan BASIC/GROSS/NET en el
alcance de Nómina Chile. Cerro conserva 71 totales/47 chilenas y su advertencia
GROSS_DISCONNECTED_FROM_BASIC. El replay aislado BASIC no subsana la estructura
original ni demuestra GROSS/NET. Resolver esas relaciones con configuración
original y referencia SyS, preservando maestros e identidad, es camino crítico.

Evidencia privada consolidada:
`~/.codex/local-artifacts/community-accelerated-20261029/acceptance-M/summary.json`.
Servidor: `/opt/steps-validation/community-accelerated-20261029M`, bases
COMMUNITY_PAYROLL_API_ACCELERATED_20261029M y
MANAGEMENT_QA_CERRO_PAYROLL_API_ACCELERATED_20261029M. El resumen se verificó con:

```powershell
python tools/community/summarize_payroll_api.py C:/Users/tito4/.codex/local-artifacts/community-accelerated-20261029/acceptance-M --output C:/Users/tito4/.codex/local-artifacts/community-accelerated-20261029/acceptance-M/summary.json
```

El verificador reproduce el paquete desde Git, el overlay HR y los hashes de
herramientas; contrasta también inventario de los tres productos y preparación
SQL SyS. full_cerro_conversion, simpledigital_certified y deadline_resolved
permanecen false. La copia nativa conserva Enterprise y no equivale a una
conversión histórica OCA. La integración conserva el avance concurrente T131
d96a9783 sin editar su checkout.

La preparación SyS B pasó sobre una copia fresca: 812 días y dos entradas,
conservando exactamente 1.986 contratos de tablas/secuencias de toda la base,
incluidos importes, fechas, IDs, relaciones, metadatos, ACL y nulos originales.
Segunda ejecución idempotente comprobada. Dump decodificado y hash privado;
preflight y reservas posteriores 5 GiB PostgreSQL/WAL y 2 GiB artefactos.
No usa filestore ni acredita recuperación integral del producto.

Evidencia privada: `~/.codex/local-artifacts/community-accelerated-20261029/`,
subcarpeta `sys-storage-B`; servidor
`/opt/steps-validation/community-payroll-related-storage-20261029B`.

La primera pareja A es diagnóstico rechazado. Community detectó horas semanales
ausentes, fixtures que editaban cuentas ya autorizadas, copia de campos fuera del
rol y una suposición falsa de tabla para M2M compute no-store. Los controles
nativos se mantuvieron; no se relajaron para hacer pasar pruebas. El loader no
seleccionaba 17 métodos CAF heredados: se hicieron explícitos. No sumar A como
aceptación ni confundir conteo declarado con casos realmente ejecutados.

Los candidatos B–F tampoco acreditan aceptación final: detectaron fixtures y
controles de selección/binario bancario, además de propiedad incompleta de IDs
multimoneda. E bloqueó el ensayo nativo antes de crear su base. F pasó 242 casos
Community pero falló un caso HR y un assert de fixture bancario nativo. Los
diagnósticos G–K usaron exclusivamente la copia F y no cuentan como nuevas
copias frescas. K pasó el caso HR tras identificar que el motor nativo regenera
la jornada desde el calendario: el caso usa ahora generate_work_entries en
ambos motores, deriva horas de las entradas reales y exige conservar todos los
IDs/datos/estados anteriores al corte y los inputs originales. No fuerza ocho
horas ni adapta importes para obtener verde. El código de producto no necesitó
relajar sus controles para corregir esos fixtures.

L pasó los 242/214 casos sin fallos, pero fue rechazado por la comparación final:
los fixtures habían consumido tres secuencias originales en la copia nativa
(Payment, adecuación de jornada y lote de pagos saliente). Las secuencias
PostgreSQL no se revierten con el rollback de TransactionCase. No se restauran
con setval ni se excluyen del comparador; los fixtures deben seleccionar sus
contadores privados y probar esa selección antes de repetir la pareja fresca.
El probe M pasó 79 casos reales y los 140 contadores originales quedaron
exactos, sin restauración. Finanzas usa secuencias no_gap nuevas por compañía
y verifica el ID seleccionado sin consumirlo. Adecuación usa compañía,
calendario de 45 horas, contrato y aprobador privados; exige el error específico
de distribución sin sudo y ya no omite el caso por falta de contratos de muestra.
Ese probe reutiliza L sólo para diagnóstico y no reemplaza la pareja fresca.

El conteo Community incluye una omisión explícita: el caso de aprobación de
lotes Enterprise se ejecuta en la referencia nativa, donde existen sus campos;
no se fabrica ese modelo/política en el Community limpio. No presentar esa
omisión como un flujo Enterprise convertido.
La referencia nativa omite dos contratos exclusivos del adaptador Community:
rechazo de días teóricos OCA y step_history_locked, campo ausente en el motor
nativo instalado. No se añade un campo ficticio para hacer correr ese caso;
los bloqueos de estados cerrados/pagados se ejecutan con las APIs reales.

## Estado acumulado y pendientes

Inventario regenerado en lectura: Cerro 380 módulos instalados, 99 propios,
140 Enterprise. Código versionado: 119 manifiestos propios, 24 fuera de este
inventario y 53 apps instaladas todavía con caminos Enterprise genéricos.
Ver [matriz vigente](COMMUNITY_INVENTARIO_ENTERPRISE_20261029.md). Estos números
no equivalen a porcentaje funcional de migración; los overlays HR se identifican
por separado y no rebajan artificialmente la matriz genérica.

La auditoría nueva `audit_product_frontier.py` consulta las tres producciones
con default_transaction_read_only=on, sin ORM ni datos de negocio/fórmulas.
Inventaría dependencias, versiones, licencias, fuentes privadas y sus hashes;
los caminos y registros completos quedan privados.

| Producto | Instalados | Enterprise | Propios prefix-step |
| --- | ---: | ---: | ---: |
| Cerro | 380 | 140 | 99 |
| Steps | 310 | 123 | 19 |
| SyS | 331 | 142 | 16 |

No sumar módulos repetidos como productos diferentes ni extender una aceptación
de Cerro a SyS/Steps. `steps_transport` 18.0.1.5 sigue instalado en Steps fuera de
sus rutas activas. La búsqueda adicional encontró su fuente en una carpeta
custom_addons ya documentada en ENTREGA_ORDENAMIENTO_AMBIENTES_2026-10-06.md.
No se activó ni se copiaron clases vacías. Conserva dos modelos, 33 campos,
dos ACL, una restricción, dos selecciones y una secuencia por XML IDs; imported
es NULL. Su API antigua y su aislamiento por empresa requieren revisión antes
de recuperar/convertir el flujo. La auditoría distingue fuentes encontradas de
fuentes efectivamente declaradas en el ambiente.

Ver [COMMUNITY_TRANSPORT_SOURCE.md](COMMUNITY_TRANSPORT_SOURCE.md): el manifiesto
recuperado no declara licencia/autor y no tiene procedencia Git. Los defaults
del registro no prueban autoría. Sus 21 rutas (ocho públicas) y 32 llamadas sudo
requieren revisión de seguridad y procedencia antes de copiar/activar el código.

Se mantienen las extracciones agrícolas/operacionales, Tesorería, calendarios,
API OCA, proveedor original, pruebas de Libro/Previred/HTTP/PDF y componentes/BASIC
de entregas previas. Las suites de perfiles diferentes no se suman ni se vuelven
a presentar como una única conversión integral.

Camino crítico: adoptar todos los campos/almacén, IDs, ACL, FK/M2M y estados del
motor conservando el histórico; configurar y certificar las 71 reglas, estructuras
y entradas originales con casos reales, GROSS imponible/NET ambiguo, días,
redondeos/YTD/asientos y salidas Previred/libro no vacías. Seguir con consumidores
HR restantes, lotes/conciliación, persistencia CAF/folios/firma/DTE/guías/exportación
y respuestas/reintentos SII, Calidad, Studio/Documentos/Firma y otros productos,
incluidas fuentes privadas o ausentes del inventario instalado.

Falta una copia integral restaurable que arranque y opere exclusivamente sobre
Community, con cero Enterprise, conservación y aceptación por empresa/perfil.
**El riesgo del 31 sigue alto; no hay evidencia para asegurar terminar todo antes
del vencimiento.** Ni la preparación SQL ni los núcleos nuevos resuelven esa fecha.
El corte de producción sigue fuera de la automatización.

Los siguientes bloques deben cerrar puertas verificables, manteniendo tres
frentes de implementación y una sola cola de aceptación de bases:

| Frente | Próxima entrega exigible |
| --- | --- |
| Nómina | Adopción ORM/metadata/FK de días y entradas sobre la preparación SyS B, conservando filas e importes; después replay completo aprobado de reglas/estructuras y salidas no vacías. |
| DTE | Almacén CAF y reservas de folio con identidad/histórico original, permisos y concurrencia; el parser sintético no sustituye CAF/ancla real ni firma/respuesta SII. |
| Tesorería y productos | Modelo y ciclo real de lotes/conciliación sin borrar sus registros; inventario y conversión funcional de Calidad/Studio/Documentos/Firma y fuentes propias externas. |
| Convergencia | Integrar todos los bloques aceptados en una copia restaurable con cero Enterprise y probar por perfil/empresa. Esta puerta sigue abierta. |

## Siguiente prompt

Continúa desde origin/codex/ambientes-canonicos-reparacion actualizada, en worktree
propio. Lee AGENTS.md, ~/.odoo/environments.json, operación, workflow,
COMMUNITY_CONTINUACION.md, COMMUNITY_AUTONOMIA.md, COMMUNITY_PAQUETE_ACELERADO.md,
la matriz 20261029 y sus referencias. Conserva las comprobaciones anteriores.
El usuario autorizó hasta tres agentes adicionales para bloques independientes;
las bases, respaldos y upgrades siguen en serie bajo el bloqueo compartido.

Prioriza la adopción real de identidad y almacén Simple Digital–OCA: usa la copia
privada SyS B con 812 días/dos entradas y las cuatro proyecciones preservadas,
sin confundir columnas preparadas con metadata/FK/ORM convertido. Cierra contexto,
estructuras, reglas/entradas originales y consumidores HR antes de dependencias.
Reproduce casos aprobados completos sin recalcular originales; conserva NULL,
factores y totales históricos y las reglas NET distintas. Avanza en paralelo
adopción CAF/folios y lotes/conciliación real, manteniendo explícitos los bloqueos.

Preserva IDs, maestros, relaciones, ACL, históricos, saldos y correlativos.
Respeta Calendar, Boolean bancario y 210233. No escribas en producción, retires
allí EE, alteres vencimientos, uses step_expire_database, recalcules pagadas ni
refresques QA-Cerro; no emitas al SII ni envíes mensajes externos ni copies OEEL.
Paquete exacto en Community oficial y copia fresca Cerro, además de la copia SyS
si cambia histórico. Evidencia privada, commits/push, integra solamente lo validado
y ejecuta python tools/git/verify_handoff.py --require-pushed. Actualiza estado,
evidencia y siguiente bloque; no declares resuelto el 31 sin todas las puertas.
