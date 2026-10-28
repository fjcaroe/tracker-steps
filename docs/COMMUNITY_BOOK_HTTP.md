# Libro: descargas firmadas y tablero por HTTP — 28-10-2026

Continuación desde 4d030b3. step_hr_remuneration_book 18.0.3.5.1 mantiene el
candidato Simple Digital–OCA real del bloque anterior. No se cambian modelos,
relaciones, vistas, IDs ni grupos/ACL; la dependencia genérica sigue intacta y
el candidato privado deriva solamente el prerequisito real del manifiesto.

## Bloque implementado

Una línea salarial oculta bloquea Excel con HTTP 404, sin archivo parcial ni error
500. La auditoría guarda solo salary_access, usuario, período y compañía, sin
importes ni datos del trabajador. La ruta oficial también maneja ese
rechazo y el extractor prevalida la visibilidad salarial completa antes de
cualquier delegación en un proveedor que pueda elevar permisos internamente.
El CSV oficial OCA del Libro propio continúa deshabilitado hasta certificarlo.

El tablero respeta el permiso independiente de perfiles Previred: su ausencia
produce sección no disponible, sin elevar permisos ni registrar un error del
servidor. No llama al generador Previred si no hay liquidaciones elegibles del
período completo y no presenta como disponibles datos con errores. El resumen
del Libro también rechaza datasets con errores. No se recalculan pagadas ni se
reconstruyen importes; las cifras financieras siguen viniendo de snapshots SQL.

Se añaden seis contratos con sesiones y rutas HTTP reales, sin reemplazar motores,
generadores ni respuestas. Se descarga un Excel firmado, se inspeccionan sus celdas
XML y el trabajador sintético, y se comprueba una sola auditoría del actor real.
Se rechazan firma, vencimiento del enlace, compañía o período manipulados; otro
administrador no puede reutilizar el asistente del titular. Una línea oculta no
produce reporte ni error del servidor. El CSV rechaza enlaces inválidos y en OCA
rechaza además un enlace válido por la certificación pendiente. El tablero se
consulta por JSON-RPC real, con acciones del motor, totales del perfil, lote y
Previred no disponible sin el permiso específico de perfiles. El fixture tampoco
abarca el mes completo; no demuestra un resumen Previred no vacío. No se usan contraseñas reales ni
se imprimen las claves efímeras de los usuarios de prueba.

## Aceptación y evidencia

Aceptado el paquete B, código 562624c: **164 pruebas Community y 104 pruebas en
copia fresca nativa, cero fallos/errores**. Community instala realmente el Libro
sobre OCA: 71 módulos y cero Enterprise; la referencia conserva 380 módulos/140
Enterprise. No es una conversión histórica ni certificación financiera.

196 archivos de addons idénticos entre ambos modos, mapa SHA-256
`dc3cda1e6765d18da2fa0f8d9990439f5dafc4a4af46b175617d930f3107b176`.
El verificador reconstruye el paquete desde Git, incluida la única modificación
privada del prerequisito del Libro y los 52 archivos AGPL del proveedor.

La referencia preserva 919 tablas/proyecciones y 140 contadores (1.059 controles),
59.039 XML IDs originales, 1.614 vínculos usuario-grupo y 283 implicaciones.
Los históricos e identidades conservan su comparación antes/después del upgrade
y de los fixtures. El mapa permanece en 934 campos ausentes, una diferencia de
tipo, ninguna de relación, 12 de almacenamiento, 17 de obligatoriedad y cinco de
selección. La adopción de identidad/almacenamiento sigue pendiente.

Evidencia local: `evidence-B/`, `summary-B.json` y `verification-B.log` bajo la ruta
privada indicada abajo; el verificador debe volver a pasar tras integrar. Las
bases privadas terminan en `BOOK_HTTP_20261028B`. El código ensayado queda separado
de las actualizaciones documentales de aceptación.

El candidato A se rechazó: 1/104 fallos en referencia y 2/164 en Community.
La respuesta HTTPException descartaba la auditoría; se reemplaza solamente ese
rechazo por una respuesta HTTP 404 normal, sin commits manuales. Se corrige además
la expectativa del test CSV: la política existente devuelve 409, no 400. El acceso
Previred denegado queda explícitamente tratado sin ampliar ACL. Los registros de
A se conservan como diagnóstico; no son evidencia de aceptación.

El paquete se prueba en Community oficial/OCA con la aplicación real instalada
y en una copia fresca nativa, conservando la distinción: esta última no convierte
Cerro ni retira Enterprise. Los fixtures usan ORM y motores reales y hacen
rollback. Su perfil de software no es el caso financiero aprobado pendiente.
No se prueba emisión real al SII ni se certifica el archivo regulatorio.

Evidencia privada: ~/.codex/local-artifacts/community-book-http-20261028/.
Servidor aceptado: /opt/steps-validation/community-payroll-book-http-20261028B.
Se verifica paquete/Git, derivación de prerequisitos, proveedor AGPL de 52 archivos,
configuración, conservación, grupos y retención. No se copian fuentes OEEL.

Para reservar espacio se retiraron cuatro ensayos propios inactivos con un plan
nuevo revisado, bajo /run/lock/steps-environments.lock: 455.953.852 bytes. Se
conservaron caso dorado, ensayo sin motor, última pareja validada y cuatro
respaldos completamente decodificados antes de retirar nada. No se borraron dumps,
producción, QA-Cerro ni copias de otros productos. Plan/resultado/ejecutor en
A/retention. No repetir un plan consumido.

## Pendientes y siguiente prompt

El inventario mantiene 377 instalados, 96 propios y 140 Enterprise; 114 manifiestos
propios, 22 fuera de Cerro y 52 apps con caminos Enterprise genéricos. Siguen la
configuración original BASIC/IMP/GROSS y el caso aprobado solicitado, identidad y
almacenamiento del motor, 71 reglas/cuatro estructuras/seis entradas, días reales,
YTD/asientos, Previred no vacío y Libro/CSV oficial completo. El PDF binario,
la aceptación visual del navegador y las fuentes históricas/rutas directas del
proveedor siguen pendientes. La instalación y HTTP internos no certifican esas
puertas. Continúan DTE/CAF/folios/firma/respuestas SII, Tesorería, Calidad,
Studio/Documentos/Firma y demás productos. Falta conversión integral restaurable
cero Enterprise, conciliación, recuperación y aceptación. El 31 sigue en riesgo alto.

No hubo escritura en producción, retiro de Enterprise allí, cambios de vencimiento
ni refresco QA-Cerro. Se respetan Calendar, Boolean bancario y 210233. No se
recalculan pagadas, inventan maestros ni envían mensajes externos.

Siguiente prompt: continúa desde la canónica actualizada en worktree propio.
Lee AGENTS, ambientes, operación, workflow, plan, continuidad, autonomía, matriz,
COMMUNITY_PAYROLL_CONFIGURATION.md, COMMUNITY_PAYROLL_YTD.md,
COMMUNITY_BOOK_INSTALL.md y COMMUNITY_BOOK_HTTP.md. Haz fetch y revisa inventario
completo, apps fuera de Cerro y fuentes privadas. Incorpora la referencia humana
aprobada si llegó; no inventes reglas para superar BASIC/IMP/GROSS. Conserva la
instalación real del Libro y las rutas firmadas; no vuelvas al ensayo de biblioteca.
Prioriza identidad/almacenamiento y certificación original de nómina; si siguen
bloqueados, avanza PDF binario/navegador o DTE/CAF/SII con auditoría real de licencia,
API, folios, firma y respuestas, sin emisión real. Mantén pendientes explícitos
CSV/Previred no vacíos y conversión integral restaurable cero Enterprise. No
retires la dependencia genérica antes de cerrar otros proveedores y sus modelos,
relaciones, vistas, IDs y permisos. Verifica espacio real y no repitas planes
consumidos. Usa respaldo, overlays privados y bloqueo; prueba paquete exacto en
Community oficial y copia fresca aislada. No escribas en producción, recalcules
pagadas, alteres vencimientos, refresques QA-Cerro ni emitas SII real. Respeta
Calendar, Boolean bancario y 210233. Guarda evidencia, commits y push, integra
solo lo validado y ejecuta verify_handoff.py --require-pushed.


Continuación validada: [COMMUNITY_BOOK_PDF.md](COMMUNITY_BOOK_PDF.md), con PDF binario,
ceros visibles, alcance/propiedad y recursos/fuentes reales. Conserva pendientes
financieros y de conversión integral.
