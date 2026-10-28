# Contratos del Libro propio sobre motores reales — 28-10-2026

## Alcance

Continuación desde da0b56e. step_payroll_contracts 18.0.1.5.0 ofrece un mapa
por liquidación y código original almacenado. Mantiene las comprobaciones de
padres, modelo/campos, líneas completas e inclusión de archivadas OCA. Conserva
cero y códigos originales sin leer fórmulas ni reconstruir amount*quantity*rate.
La API de suma filtrada anterior delega en el mismo mapa y conserva su contrato.

step_hr_remuneration_book 18.0.3.4.1 usa esa captura en el extractor y en los
adaptadores que terminan sumando reglas. La extracción de reglas obtiene el mapa
una vez por lote y lo pasa a la resolución por liquidación. Los adaptadores siguen
agrupados por clave/parámetro y lote; no se añade una consulta financiera por fila. Continúan las comprobaciones de acceso y consultas de
configuración adicionales. Se preserva la suma por código del Libro anterior,
además de int(round(total)) del adaptador: no se interpreta como certificación de
códigos duplicados, una nueva política chilena o la semántica del motor de cálculo.

El adaptador vuelve a aplicar el entorno del actor a los registros recibidos,
incluso si un llamador entrega una liquidación elevada. El sudo existente queda
limitado al catálogo de tipos y códigos de regla; no alcanza las líneas salariales.
No cambia identidades de modelos, campos, tablas, relaciones, vistas, XML IDs
ni grupos/ACL.
Mantiene hr_payroll; solo declara explícitamente step_payroll_contracts, que ya
llegaba transitivamente por el núcleo Previred candidato. No se retira una
frontera Enterprise antes de cerrar su instalación completa.

## Pruebas y límite de la aceptación

Paquete C, addons 151c585: **153 pruebas en Community oficial** (70 módulos,
cero Enterprise) y **94 en copia fresca nativa** (380 módulos, 140 Enterprise),
sin fallos. Se conservan los 150/90 contratos anteriores y se añaden tres casos
compartidos y uno del extractor nativo registrado.

Se preservan exactamente **919 tablas/proyecciones, 140 contadores y 59.039
XML IDs**, maestros, relaciones, ACL, metadatos, históricos, adjuntos de negocio,
saldos y vencimientos. El contraste contra el respaldo conserva las 1.614
relaciones usuario-grupo y 283 implicaciones sin ninguna diferencia.
Ambos modos usan los mismos 195 archivos de addons. SHA256 de su mapa:
bec4a21568efd72cb87aaf532bc9ba327ccdc2ec5ade8ef731c1a0529aa9e20d.
La evidencia local evidence-C/, summary-C.json y verification-C.log verifica los
bytes contra Git, los ámbitos instalados y la preservación. El mapa parcial
sigue con 984 campos ausentes, una diferencia de tipo, 12 de almacenamiento,
17 de obligatoriedad y cinco de selección. No se declara adoptada la identidad
del motor ni certificado Simple Digital completo.

En Community se ejecuta el archivo Python real del registro de adaptadores del
Libro, que contiene clases ordinarias y no registra modelos ORM. El módulo entero
NO se instala allí: siguen pendientes su herencia hr.payslip, menús, acciones,
vistas, grupos y puentes. Los modelos salariales y el proveedor sí son los reales
OCA/Simple Digital. La evidencia comprueba por SQL que el Libro está sin instalar;
no hay hr.payslip simulado ni un módulo Enterprise vacío.

La copia nativa actualiza el módulo propio instalado 3.4.0->3.4.1, comprobando
primero la versión de origen de solo lectura, y ejecuta además su extractor
registrado con un mapeo salarial real de fixture. Los casos nuevos cubren dos
liquidaciones por lote con cero y negativo almacenados, el adaptador de movimientos
real y el rechazo de líneas ocultas aunque se entregue un padre sudo. El caso
nativo adicional comprueba el código 2101 sin reconstruir un total original cero.
No se activa ese perfil sintético ni se certifica el archivo oficial con él.
Todos los fixtures hacen rollback; no son contratos/liquidaciones de producción.

El modo book-consumers distingue own_book_library_only/own_book_installed y
verifica el alcance en la base. Las pruebas no declaran instalado u operativo en
Community el Libro completo. Sus columnas de días, movimientos/contrato/indicadores,
adaptadores externos, tablero y archivo oficial siguen pendientes.

## Evidencia y capacidad

Evidencia privada: ~/.codex/local-artifacts/community-own-book-contracts-20261028/.
Servidor: /opt/steps-validation/community-payroll-own-book-20261028C.
El proveedor conserva sus 52 archivos runtime AGPL y se deriva de forma reproducible.
No se copian fuentes OEEL. El resumidor contrasta paquete y validador con Git,
conservación, inspector, proveedor, grupos y plan de retención.

Para mantener la reserva de PostgreSQL se aplicó un plan nuevo a cuatro copias
propias obsoletas, sin sesiones y bajo /run/lock/steps-environments.lock. Se liberan
454.094.268 bytes; quedan 6.032.310.272 bytes antes de los ensayos. No se eliminan
dumps. Se decodifican completamente cuatro respaldos retenidos antes de retirar
nada; se conservan el caso dorado de upgrade, la prueba sin motor y la última
pareja validada E del Libro del proveedor. Plan/resultado/ejecutor en la carpeta
community-payroll-own-book-20261028A/retention. No repetir un plan consumido.

A preparó el paquete. B queda rechazado por el dato obligatorio earn_type ausente
en el fixture de tipo de movimiento; no se alteraron maestros originales para
solucionarlo. C repite el paquete corregido en bases frescas. Se conservan logs,
JSON, respaldo y código del diagnóstico fuera del checkout.

## Estado acumulado y siguiente bloque

El inventario de solo lectura mantiene 377 módulos instalados, 96 propios y
140 Enterprise. Hay 114 manifiestos propios en repo, 22 fuera de Cerro y 52 apps
instaladas con caminos Enterprise. Las fuentes privadas/desconocidas mantienen
sus puertas aunque no se conozca una dependencia Enterprise directa.

BASIC/IMP/GROSS sigue bloqueado y la referencia aprobada solicitada continúa
pendiente. No se importan las dos NET activas de SyS ni se inventa una política
salarial. Quedan configuración original/71 reglas/cuatro estructuras/seis entradas,
identidad y almacenamiento del motor, casos chilenos, YTD restante, contabilización,
Previred no vacío, Libro completo y consumidores HR. Siguen DTE/CAF/folios/firma/
respuestas SII, Tesorería, Calidad, Studio/Documentos/Firma y demás productos.
Falta una copia integral restaurable con cero Enterprise, conciliación, recuperación
y aceptación funcional. El 31 de octubre continúa en riesgo alto.

No se escribe en producción, retira allí Enterprise, recalculan pagadas, alteran
vencimientos ni refresca QA-Cerro. Se respetan Calendar, Boolean bancario y 210233.
No se emite al SII real ni se envían mensajes externos.

## Siguiente prompt

Continúa desde la canónica actualizada en worktree propio. Lee AGENTS, ambientes,
operación, workflow, plan, continuidad, autonomía, matriz vigente y
COMMUNITY_PAYROLL_CONFIGURATION.md, COMMUNITY_PAYROLL_YTD.md,
COMMUNITY_PAYROLL_BOOK_LINES.md y COMMUNITY_OWN_BOOK_CONTRACTS.md. Haz fetch y
revisa inventario completo, apps fuera de Cerro y fuentes privadas. Conserva las
pruebas aceptadas e incorpora la referencia humana aprobada si ya llegó. Prioriza
configuración original e identidad/almacenamiento del motor. Cierra ahora los
modelos, herencia hr.payslip, menús, vistas, acciones y permisos del Libro completo
antes de retirar hr_payroll: la biblioteca probada en OCA no equivale a instalar
la aplicación. Reutiliza el mapa SQL por lote sin recuperar totales por lectura
ORM ni reconstruir ceros; conserva los límites de adaptadores externos, tablero
y archivo oficial aún pendientes. Mantén visibles DTE/CAF/SII y la conversión
integral restaurable cero Enterprise. Comprueba espacio real, no repitas planes
de retención consumidos y conserva caso dorado, referencia reciente y respaldos.
Prueba el paquete exacto en Community oficial y copia fresca aislada de Cerro,
con respaldo, overlay privado y bloqueo. No escribas en producción, recalcules
pagadas, cambies vencimientos, refresques QA-Cerro ni emitas SII real. Respeta
Calendar, Boolean bancario y 210233. Guarda evidencia, commits y push, integra
solo lo validado sin pisar cambios concurrentes y verifica handoff.


Continuación aceptada y siguiente prompt vigentes: [COMMUNITY_BOOK_INSTALL.md](COMMUNITY_BOOK_INSTALL.md).
El candidato específico ya instala la aplicación completa en Community, con
CSV oficial OCA aún bloqueado y conversión integral pendiente.
