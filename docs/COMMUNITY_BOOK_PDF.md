# Libro: PDF binario y alcance de acceso — 28-10-2026

Continuación desde c0eb74a. Candidato step_hr_remuneration_book 18.0.3.5.2.
La dependencia genérica canónica permanece; el candidato específico deriva solo
el prerequisito por el puente real Simple Digital. Sin cambios de modelos, campos,
XML IDs, relaciones ni ACL. No se instala OCA sobre el motor de una producción.

## Cambio y aceptación

El formato del PDF confundía cero numérico con False y lo dejaba vacío. Ahora
conserva explícitamente cero y negativos; None/False siguen vacíos. La ficha ya
mostraba cero por su fallback, pero el consolidado no. Los importes almacenados
no se escriben ni recalculan. El informe exige un solo asistente y comprueba su
acceso de lectura antes de construir el dataset; no ignora IDs adicionales.
Se respetan propiedad del transitorio, reglas salariales, rol y compañía. La
propiedad se comprueba explícitamente; check_access por sí solo no la rechazó en
el ensayo nativo. El superusuario conserva la semántica de administración.

La ruta estándar de informes se republica con readonly calculado: solo los dos
nombres exactos del Libro usan una transacción normal para su auditoría, con
Cache-Control: no-store. Los demás informes conservan la ruta de lectura.
No se abren transacciones separadas ni se fuerza commit. Los artículos de estos
dos informes usan la fuente local DejaVu Sans; se comprueba su embedding en los
PDF. Cambia el estilo QWeb de sus vistas existentes, conservando sus IDs.

Se añade comprobación real de ambos PDF por la ruta estándar autenticada de Odoo,
forzando wkhtmltopdf: test_enable sin force_report_rendering devolvería HTML.
El renderer usa un servidor estático local de prueba con bytes exactos de los
assets obtenidos previamente del runtime por HTTP autenticado; sus hashes quedan
en la prueba y cualquier recurso desconocido bloquea la aceptación. Esto evita
callbacks al cursor de test de Odoo, sin sustituir HTML, fuentes, CSS ni renderer.
No usa rutas ni recursos del servicio de producción. El CSS nativo contiene
referencias a fuentes CDN y recursos legados no usados: se registran, pero los
PDF deben embeber solo DejaVu Sans local. Un 404 prefetched no bloquea por sí
solo si no se usa; cualquier recurso pedido por el renderer que falte sí bloquea.
Se obtienen además las URLs con prefijo Website del HTML real, sin quitar el
prefijo ni sustituir contenidos. Los bytes servidos son los del runtime. Se comprueban
cabecera PDF, MIME, páginas y tamaño Legal horizontal/A4 vertical, auditoría única
del actor normal y lectura histórica estable. No hay mocks del renderer ni del
motor. Se añaden rechazo de asistentes vacíos/múltiples/ajenos y líneas ocultas,
y comprobación de ceros en celdas HTML reales. Los fixtures hacen rollback.

Paquete **D aceptado**, código de exportación de53d8d: **167 pruebas Community y
107 en copia fresca nativa, cero fallos/errores**. Community instala el Libro real
sobre OCA: 71 módulos, cero Enterprise; la referencia nativa conserva 380/140.
No es conversión histórica ni certificación financiera.

196 archivos de addons idénticos entre modos, mapa SHA-256
`fd26799b1ac963d6028ae7c19005bb1dcbadb3243c95d93bb0b9f061e6344182`.
El verificador reconstruye el paquete desde Git, la única transformación del
prerequisito del Libro y la derivación reproducible de los 52 archivos AGPL.

Se preservan 919 tablas/proyecciones y 140 contadores (1.059 controles), 59.039 XML
IDs originales, 1.614 vínculos usuario-grupo y 283 implicaciones. Históricos e
identidades comparados antes/después de upgrade y fixtures. El mapa mantiene
934 campos ausentes, una diferencia de tipo, cero de relación, 12 de almacén,
17 de obligatoriedad y cinco de selección: adopción histórica aún no aceptada.

Cuatro PDF finales comprobados: una página cada uno, texto/importe/ceros/rótulos,
Legal horizontal y A4 vertical, fuentes DejaVu Sans y Bold locales embebidas.
Se renderizaron todas las páginas. Los PNG finales de Community fueron revisados
visualmente; los nativos coinciden byte a byte con los del probe nativo ya visto.
No se observaron recortes en ese fixture. Esto no sustituye la aceptación humana,
el navegador ni la paginación de un volumen real.

Evidencia local: evidence-D/, summary-D.json, verification-D.log,
pdf-verification-D.json y visual-review-D.json en la ruta privada indicada.
JSON/logs de A/B y probes C conservados; sus fallos no se cuentan como aceptación.

A se rechazó: faltó el rechazo del asistente ajeno, la ruta readonly intentó
insertar la auditoría y el renderer quedó bloqueado al pedir assets al test de
Odoo. Se conservan logs y dump. Se cancelaron únicamente su runtime propio y
wkhtmltopdf y el validador Community que aún esperaba el bloqueo (sin crear base).
No se terminaron sesiones de producción ni procesos ajenos. B usó bases y paquete nuevos: 1 fallo de 167 pruebas en Community y 1 de 107 en
referencia, por la prelectura estricta de referencias CDN. También se rechazó.
C fue solo prototipo focalizado sobre la referencia B ya descartada: el primer
arranque no seleccionó tests (cero casos, no aceptado); después se corrigieron
referencias legadas no usadas y URLs Website. El último probe pasó un test real
que genera los dos PDF, con extracción de texto, dimensiones, fuentes y páginas
revisadas. No sustituye las dos bases frescas del paquete D final. El preflight HTML adicional tiene su propia auditoría;
cada descarga PDF debe incrementar exactamente en uno la auditoría de su formato.

tools/community/verify_book_pdf_outputs.py verifica hashes, páginas, tamaño,
texto del empleado sintético, importe, ceros y rótulos de cada formato, y renderiza
todas las páginas para revisión visual. Esto no constituye aceptación del navegador
ni certificación financiera o regulatoria. Las fichas no son liquidaciones. El fixture de software tiene una línea y produce
una página por formato; no certifica volúmenes reales ni paginación múltiple.

## Evidencia privada y espacio

Local: ~/.codex/local-artifacts/community-book-pdf-20261028/.
Servidor aceptado D: /opt/steps-validation/community-payroll-book-pdf-20261028D.
Las bases D terminan en BOOK_PDF_20261028D. El paquete exacto se prueba en Community
oficial/OCA y copia fresca nativa; la referencia mantiene Enterprise, no es una
conversión de Cerro. Se verifica la derivación AGPL de 52 archivos sin copiar OEEL.

Se retiró solo la pareja fallida BOOK_HTTP_20261028A, inactiva y propia:
228.501.214 bytes. Después de los diagnósticos se retiraron otros tres ensayos
PDF A/B propios inactivos: 397.527.629 bytes. Total de este bloque: cinco bases,
626.028.843 bytes; cero dumps eliminados. Dos planes nuevos revisados y aplicados
bajo el bloqueo compartido;
no repetirlo. Conserva logs y dump de A, última pareja aceptada HTTP B, caso dorado
de históricos y núcleo sin motor. Cada plan decodificó completamente tres respaldos y verificó sus hashes antes
de retirar bases: cuatro archivos distintos conservados entre ambos planes.
Se mantienen también logs y dumps de los ensayos rechazados. Evidencia A/retention y C/retention: cleanup-plan-resume.json, cleanup.py y resultado.

## Estado y siguiente bloque

Auditoría nueva de solo lectura y matriz regenerada sin cambios: 377 instalados,
96 propios/140 Enterprise en producción; 114 manifiestos propios, 22 fuera de
Cerro y 52 apps con caminos genéricos Enterprise. Las fuentes privadas y el perfil
original siguen inventariados: 71 reglas, cuatro estructuras, seis entradas;
Cerro no tiene contratos/liquidaciones/entradas laborales para certificar un caso
financiero histórico. Sigue pendiente la referencia humana BASIC/IMP/GROSS.

No se cierra identidad/almacenamiento del motor por probar un PDF. Permanecen
reglas/configuración original y casos chilenos, estructuras/entradas/días reales,
redondeos/YTD/asientos, Previred/CSV oficiales no vacíos y rutas del proveedor.
Faltan aceptación visual del navegador, DTE/CAF/folios/firma/respuestas SII,
Tesorería, Calidad, Studio/Documentos/Firma y demás productos; conversión integral
restaurable cero Enterprise, conciliación, recuperación y aceptación. El 31 sigue
en riesgo alto. No se escribe en producción ni se refresca QA-Cerro; no se alteran
vencimientos ni se recalculan pagadas. Calendar, Boolean bancario y 210233 vigentes.

Siguiente prompt: continúa desde la canónica actualizada en worktree propio.
Lee AGENTS, ambientes, operación, workflow, plan, continuidad, autonomía, matriz,
COMMUNITY_PAYROLL_CONFIGURATION.md, COMMUNITY_PAYROLL_YTD.md,
COMMUNITY_BOOK_HTTP.md y COMMUNITY_BOOK_PDF.md. Haz fetch y revisa inventario
completo, fuentes privadas y apps fuera de Cerro. Incorpora la referencia aprobada
si llegó; no inventes reglas para superar BASIC/IMP/GROSS. Prioriza identidad y
almacenamiento del motor y las 71 reglas sin perder FK, M2M, XML IDs ni permisos.
Conserva instalación real, HTTP y PDF del Libro y bloqueo del CSV no certificado.
No repitas esas suites sin un cambio o fallo nuevo que lo justifique.
Si falta el caso financiero, avanza DTE/CAF/SII o una frontera verificable de HR:
audita licencia/API, históricos, folios, firma y respuestas, sin emisión real.
No declares conversión ni certificación por pruebas sintéticas. Mantén pendientes
explícitos Previred/CSV y conversión integral restaurable cero Enterprise. No
retires dependencias antes de cerrar modelos, relaciones, vistas, IDs y permisos.
Verifica espacio y no repitas planes consumidos. Usa respaldo, overlays privados
y bloqueo; prueba paquete exacto en Community oficial y copia fresca aislada.
No escribas en producción, recalcules pagadas, alteres vencimientos, refresques
QA-Cerro ni emitas SII real. Respeta Calendar, Boolean bancario y 210233. Guarda
evidencia, commits y push, integra solo lo validado y verifica handoff.


Continuidad posterior: el usuario aportó SyS como referencia real. Ver
[COMMUNITY_SYS_REFERENCE.md](COMMUNITY_SYS_REFERENCE.md) para aceptación del
lector histórico, evidencia privada y siguiente bloque. No repetir la pregunta
sobre qué base usar; certificación financiera e identidad siguen pendientes.
