# Custodia CAF, agrupación de pagos y configuración original — 29-10-2026

Estado acumulado posterior: [COMMUNITY_PROPIEDADES_NOMINA.md](COMMUNITY_PROPIEDADES_NOMINA.md),
pareja F y upgrade I. Esta hoja conserva la aceptación histórica de custodia y lotes.

Continuación de la canónica `6e3c8298`, rama propia
`codex/community-original-config-20261029`. Tres agentes autorizados prepararon
frentes independientes; las restauraciones, actualizaciones y verificaciones
del registro usan una sola cola bajo `/run/lock/steps-environments.lock`.

**G aceptado.** Código probado `ccdae62e`, paquete exacto cotejado con Git y
verificador local sin errores. La aceptación anterior sigue
en [COMMUNITY_PAYROLL_ADOPCION.md](COMMUNITY_PAYROLL_ADOPCION.md).

## Implementación

### Configuración de nómina

API OCA **18.0.1.8.0** admite estructuras globales con compañía NULL y país
original opcional, conservando el default normal de compañía para nuevas
creaciones. Reglas y categorías pueden conservar su propiedad global; no se
les inventa un país. Las políticas de país intersectan las políticas de empresa
y no agregan ACL. La selección de padres, reglas y entradas comprueba todos los
vínculos originales sin sudo, incluyendo permisos y almacenamiento PostgreSQL.

Se cubre la diferencia entre una regla OCA sin estructura primaria y una regla
con estructura primaria de otro país: el dominio incluye explícitamente
`struct_id=False`. Un dominio sólo por `struct_id.country_id` excluía el primer
caso, aunque el país final fuese NULL. La regresión usa reglas reales propias y
globales, pertenencia M2M, herencia y un actor de otra compañía/país.
No cambia la prioridad `(sequence,id)`, el guard financiero ni las fórmulas.

La cápsula privada conserva **120 maestros**, las **71 reglas**, cuatro
estructuras, cinco tipos, seis entradas, 34 categorías y **91 XML IDs**.
Conserva JSON por compañía, NULL físicos, referencias y filas originales;
no ejecuta reglas ni lee liquidaciones. Está sellada con permiso 0600.
SHA256: `14b18ced97032ec27c306ed4c71c46f0c3d56e324d0eace4f0c8f2c86544e140`.
Ver [COMMUNITY_PAYROLL_CONFIG_ORIGINAL.md](COMMUNITY_PAYROLL_CONFIG_ORIGINAL.md).

**La configuración original todavía no está adoptada en OCA.** Faltan diez
campos: tres relaciones de regla, dos flags contables y cinco campos de
estructura, incluidos archivo, reporte y diario por compañía. Las cuatro
estructuras apuntan al reporte nativo 462; tres guardan diarios por compañía.
Cinco reglas de la estructura archivada usan separación de asientos. No se
aplanan esas propiedades ni se activa la estructura archivada. También faltan
cerrar traducciones y la diferencia de permisos usuario/administrador entre
ambos motores. Ninguna regla demo completa la configuración original.

### Pagos existentes

`step_batch_payment_grouping` es un servicio abstracto sin tabla de negocio.
Crea grupos, reemplaza pertenencia y elimina borradores sobre el proveedor real.
Comprueba permisos antes y después de locks, todos los pagos originales,
empresa, diario, moneda, dirección, método y línea del diario. Rechaza pagos
ocultos, enviados, conciliados y de otro grupo. Las operaciones tienen savepoint
propio y revalidan cachés después de bloquear; un fallo tardío no deja cambios
parciales aunque el llamador capture el error. Descarta defaults ajenos al
seleccionar un proveedor y exige referencia explícita, sin consumir numeración.

`step_batch_payment_core` añade un proveedor CE real para
`account.batch.payment` / `account_batch_payment`, su FK original desde pagos,
formulario, menú y ACL de lector contable/facturación. Selecciona pagos existentes
y protege también la escritura directa de su FK y los defaults por RPC. No
crea pagos, asientos ni maestros para aparentar una agrupación. Los importes y
residuales salen de pagos y líneas contables reales, sin convertir con la tasa
actual ni modificar sus valores al leer.

La observación privada del proveedor nativo confirmó pagos en borrador y
publicados, importes firmados y residuales en moneda de compañía, con 1.061
contratos de tablas/proyecciones/correlativos exactos. La regresión CE exige
esos resultados y preserva pagos, asientos y líneas. Falta certificar divisas,
conciliaciones parciales y concurrencia entre procesos. En la copia nativa se
instala sólo el servicio; su clase original permanece intacta.

La admisión prueba instalación CE limpia, rechazo de tabla fría y de ambos
proveedores nativos instalados o en cola. No certifica posteriores cambios de
proveedor ni adopción histórica. Validación, envío, rechazo, congelación,
conciliación, wizards y sus IDs/M2M siguen pendientes; las operaciones fiscales
o financieras que no están implementadas fallan explícitamente. No se retiran
dependencias Enterprise de Tesorería ni se simula `bank.rec.widget`.

### CAF privado

Tres addons: `step_l10n_cl_caf_custody_core`, proveedor CE
`step_l10n_cl_caf_storage` y puente `step_l10n_cl_caf_native_reference`.
El proveedor usa el modelo/tabla originales y catorce campos, Binary con
`attachment=True`, sus relaciones, estados, dos ACL y regla de compañía.
Guarda y recupera bytes originales privados mediante roles reales, sin tabla
paralela ni contador fiscal. El puente nativo conserva los cuatro métodos
originales; no instala el proveedor CE sobre Enterprise.

La carga verifica formato/RSA, RUT de la empresa y tipo/rango/fecha. Protege
también la creación directa del adjunto, público/token, reemplazo, reasignación
y duplicados. La descarga revalida rol/empresa sobre el usuario real incluso
con un recordset cacheado o sudo, y prueba el stream/filestore con un Request
real. Una lectura histórica no repara ni normaliza el archivo o su metadata.
El mixin Python usa `__slots__=()` para conservar el layout del registro nativo.

Una carga nueva queda sin estado fiscal, no como CAF habilitado. Habilitación,
agotamiento y reserva de folios siguen bloqueados. No se afirma confianza SII
por una clave aportada por el propio archivo. Falta confianza oficial,
concurrencia con procesos separados, CAF real autorizado para pruebas,
asignación/consumo atómicos, firma, respuestas y reintentos. La referencia usa
fixtures sintéticos en las tablas reales; no emite al SII ni consume folios.
Ver [COMMUNITY_CAF_CUSTODY.md](COMMUNITY_CAF_CUSTODY.md).

## Aceptación y evidencia

| Entorno privado | Casos registrados | Correctos | Omisiones por API/política | Fallos/errores | Instalados / EE |
| --- | ---: | ---: | ---: | ---: | ---: |
| Community oficial + OCA | 313 | 311 | 2 | 0 / 0 | 95 / 0 |
| Copia fresca Cerro, referencia nativa | 244 | 242 | 2 | 0 / 0 | 389 / 140 |

Las omisiones son explícitas: política de aprobación nativa y observación del
proveedor nativo en CE; refresco teórico de días e inexistencia del flag propio
de historial en el motor nativo. No son resultados financieros certificados.
El perfil incluye 63 casos API CE, 34 casos de lotes CE/20 nativos y 20 de
custodia CE/9 nativos, junto a los contratos y consumidores del bloque previo.
No se suman suites históricas de perfiles distintos.

Mismos **288 archivos**, SHA256 de `source-files.json`:
`54ad8235a56a95cee272ee4ea615acd3ae41cc596f9c0d9790c2062a95a932f0`.
Community oficial `4b4efe68291d6def5bb7d2e1f2b829e0cda577d4` y OCA
`4c71cd42e46a09a7512d92f5c63c0a9f7c26ad3e`; fuente/derivaciones AGPL
y consumidores cotejados byte a byte. El exportador sólo cambió para incluir
los inspectores ejecutados en el paquete de evidencia, sin cambiar addons.

Preservados **921 tablas/proyecciones y 140 correlativos**, antes/después del
upgrade y pruebas; **59.048 XML IDs**, 1.218 modelos, 27.045 campos, 5.076
selecciones, 2.324 ACL, 610 reglas, 1.330 menús, 463 relaciones y 529
restricciones originales. Sólo continúa la excepción previamente aceptada de
presentación de tres campos de Corrección; no se añadió ninguna excepción.
Se conservan los 15 aliases bancarios y 37 multimoneda. BASIC positivo de SyS
coincide en amount/quantity/rate/total en ambos motores y sus fixtures hacen
rollback; continúa sin certificación de nómina completa o línea temporal.

También pasó la inspección pasiva de ambos registros: **613 contratos** de
tablas/correlativos exactos CE y **1.602 nativos**, sin leer registros de negocio,
payloads, cuerpos del proveedor ni ejecutar computes. Confirma ambos proveedores
reales en CE, Binary CAF attachment=True y ausencia de un `bank.rec.widget`
ficticio; la referencia conserva sus clases originales.

Resumen privado verificado:
`C:/Users/tito4/.codex/local-artifacts/community-original-config-20261029/acceptance-G-complete/summary.json`.
Incluye comparaciones de preservación, origen completo de SyS, cápsula original,
inventario, metadatos cargados y huellas del paquete/validadores.

Raíz privada: `/opt/steps-validation/community-operational-custody-20261029G`.
Bases nuevas `COMMUNITY_PAYROLL_API_CUSTODY_20261029G` y
`MANAGEMENT_QA_CERRO_PAYROLL_API_CUSTODY_20261029G`. La segunda restaura un dump
fresco de Cerro y copia su filestore; conserva el motor nativo como referencia.
No se interpreta como conversión histórica ni ensayo de recuperación integral.

La evidencia se exporta con `collect_payroll_acceptance.py`, limitada a informes,
logs, fuente AGPL fijada y referencias privadas aprobadas. No exporta dumps,
filestore, configuración ni fuentes OEEL. `summarize_payroll_api.py` coteja el
paquete y sus derivaciones con Git, los snapshots, metadatos, pruebas, cápsula,
inventario de los tres productos y referencia documental de SyS.

El inventario completo se repitió en sólo lectura antes de implementar:

| Producción | Instalados | Enterprise | Propios |
| --- | ---: | ---: | ---: |
| Cerro | 380 | 140 | 99 |
| Steps | 310 | 123 | 19 |
| SyS | 331 | 142 | 16 |

Siguen **53 apps propias instaladas con caminos Enterprise**. Hay 124 manifiestos
propios en el repositorio y 29 fuera del inventario instalado de Cerro, incluidos
los cinco nuevos de este bloque y herramientas de referencia nativa que no son
productos para instalar en el perfil CE. `steps_transport` tiene fuente encontrada pero inactiva,
sin origen/licencia operativa acreditados; no se activó. No hay publicaciones
en producción ni QA-Cerro, cambios de vencimiento o recálculo de originales.

Retención revisada sin borrar: siete ensayos rechazados e inactivos de este
bloque liberarían 671 MiB. Hay 49,9 GiB en PostgreSQL y 34,9 GiB en artefactos,
por encima de las reservas 5/2 GiB; no se ejecutó cleanup. El plan privado
`community-operational-custody-20261029-retention-plan/cleanup-plan-after-G.json`
protege G, ADOPTION A/B, SyS C y todos los archivos/respaldos. Su eventual uso
requiere aceptación de G, justificación y nueva comprobación bajo bloqueo.

## Pendientes y valoración del 31 de octubre

1. Cerrar los diez campos, reporte Community real, diarios/contabilidad,
   traducciones, ACL e identidad para adoptar los 120 maestros y 91 XML IDs
   originales en una referencia sin demo. Mantener el bloqueo ante brechas.
2. Adoptar identidad y almacenamiento histórico del motor; certificar nómina
   completa contra SyS: 71 reglas, estructuras/entradas, días reales,
   cantidades/redondeo/YTD, asientos, Previred y libro. BASIC positivo sigue
   siendo un único concepto reproducido, no una liquidación certificada.
3. Completar lotes/conciliación y DTE/CAF/folios/firma/respuestas SII, con
   concurrencia e históricos; adoptar sus consumidores antes de dependencias.
4. Calidad, Studio, Documentos/Firma, interfaz y restantes productos/fuentes.
5. Copia integral restaurable con cero Enterprise, comparación de identidad,
   permisos, históricos, saldos y correlativos, flujos por rol y aceptación en
   Desarrollo. El corte productivo queda fuera de la automatización.

**El 31 sigue en riesgo alto.** La evidencia actual no permite asegurar llegar
con todo migrado. Producción conserva 140 Enterprise y no existe todavía una
conversión integral aceptada. Estos proveedores reales y sus pruebas reducen
trabajo pendiente, pero no resuelven el vencimiento. La programación horaria
continúa hasta cumplir todas las puertas de COMMUNITY_AUTONOMIA.md.

## Siguiente prompt

```text
Continúa desde origin/codex/ambientes-canonicos-reparacion actualizada, en un
worktree propio. Lee AGENTS.md, el registro de ambientes, operación/workflow,
COMMUNITY_AUTONOMIA.md, COMMUNITY_CUSTODIA_LOTES.md,
COMMUNITY_PAYROLL_CONFIG_ORIGINAL.md y sus referencias. Fetch e inventario
completo antes de implementar; recupera avances útiles pendientes del hilo.

Prioriza los diez campos y relaciones de configuración original, reporte real
Community conservando acción/IDs, diario y cuentas company_dependent sin
aplanar JSON, active/NULL y flags contables. Cierra traducciones y permisos
antes de importar los 120 maestros/71 reglas/91 XML IDs en referencia sin demo.
No uses BASIC/GROSS/NET demo ni inventes dueños, diarios o cuentas. Continúa
después identidad histórica Simple Digital–OCA y certificación completa con SyS.
No simules hr.payslip ni recalcules originales pagados/validados.

Con hasta tres agentes ya autorizados, avanza lotes/rechazos/conciliación y
CAF/folios/firma/respuestas SII en frentes independientes, manteniendo una sola
cola de upgrades y pruebas. No confundas custodia o agrupación de borrador con
conversión histórica o emisión. Conserva visibles Calidad/Studio/Documentos/
Firma y productos fuera de Cerro, y la puerta integral restaurable cero EE.

Preserva IDs/maestros/ACL/relaciones/históricos/saldos/correlativos. Respeta
Calendar, Boolean bancario y 210233. No escribas en producción, retires allí
Enterprise, cambies vencimientos, uses step_expire_database, refresques QA-Cerro,
emitas al SII real, envíes mensajes, imprimas credenciales o copies OEEL.
Usa overlays/bases nuevas, respaldo y bloqueo compartido; prueba paquete exacto
en Community oficial y copia fresca Cerro. Guarda evidencia privada, commits,
push, integra sólo lo validado y verifica handoff --require-pushed. Actualiza
estado/evidencia/pendientes; ninguna extracción parcial resuelve el 31.
```
