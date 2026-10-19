# T94 · Trazabilidad de exportaciones por pallet

Publicado y verificado el 19-10-2026 (Chile), para revisión humana en Desarrollo.
Alcance exclusivo: Desarrollo para revisión humana, sin promoción a producción.
Ticket 94 en etapa 4 con nota interna 9517, sin destinatarios ni notificaciones.

## Paquete final

- Módulo `step_export_traceability`, versión `18.0.1.0.1`.
- Commit: `32b884ede0e87503f7ce3f1883ca1876e5e4b87e`.
- SHA-256: `fb51dcf721dfc13334724490d102bfe7f4ba6ac852ecea1e66f3a9f4c6283ba6`.
- Destino: <https://desarrollo.stepsapp.cl/odoo/action-2180>, base `LAB_TAREAS`.
- Ruta: Exportaciones / Recibidor / Trazabilidad.
- Copia fresca: `MANAGEMENT_QA_DEVELOPMENT_t94final`.
- Evidencia de copia: `/opt/steps-validation/management_development_t94final/qa_passed.json`.
- Respaldo: `/opt/steps_backups/management_development_20261019T220903Z`.
- Overlay privado: `/opt/steps-managed/releases/development/32b884ede0e87503f7ce3f1883ca1876e5e4b87e/`.

El mismo paquete pasó tres pruebas sin fallos ni errores en la copia fresca,
y tres comprobaciones funcionales con transacciones descartadas en el registro
instalado. La publicación utilizó bloqueo compartido, respaldo y rechazo de
downgrade/cambios concurrentes; conservó los valores de negocio del destino.

## Comportamiento y conservación

La acción existente pasa de un resumen de embarques a una lista de tarjas E con
las siete etapas del documento: productor, recepción, embalado, calidad,
despacho, exportación y recibidor. Los detalles de cada etapa se pueden exportar
con la herramienta estándar de Odoo. Cada folio abre el panel de siete columnas,
con enlaces nativos a los procesos, maestros y documentos originales.

La genealogía recorre OT, detalle de contenido y repaletizajes validados hacia
sus tarjas de origen, con control de ciclos. Se muestran cajas y kilos de la
tarja consultada; no se atribuyen cantidades de una recepción completa a cada
pallet. La selección de calidad de llegada agrega únicamente una relación
opcional al catálogo de calidad existente, en el embarque. No se duplican
maestros ni se crean documentos operativos o resultados de inspección.

Las guías directamente asignadas al pallet y las guías de su embarque sin
asignación individual aparecen diferenciadas. La fecha de guía no se presenta
como prueba de salida física. Los controles de recepción conservan ese alcance;
no certifican individualmente todas las tarjas de la recepción. Las inspecciones
y orígenes del panel son el historial vinculado, no una autorización de despacho.
Las fechas de arribo son las registradas en el embarque, no confirmaciones AIS.

Los datos sin evidencia vinculada disponible se muestran como «Sin registro».
El cuartel histórico procede del dato ya registrado en la recepción, sin
inventar una relación a un maestro. No se resuelven enlaces por coincidencias
de nombre. Las tablas, campos y documentos anteriores se conservan.

La consulta no usa sudo. Respeta ACL y reglas nativas y acota los documentos a
las empresas activas, incluidas las líneas antiguas de repaletizado sin regla
propia. Un paquete vaciado puede quedar compartido en Odoo; eso no permite
mostrar sus procesos o inspecciones de otra empresa.

## Validación

Casos de prueba: recorrido desde una OT cerrada y una recepción vinculada,
siete etapas, contenidos y enlaces, textos escapados, listado y vistas reales;
ausencia de evidencia y actualización de la consulta; repaletizado con stock
real y permisos entre empresas. Se verifican también guías históricas del
embarque y su asignación directa al pallet como relaciones diferentes.

La prueba inicial detectó la particularidad de los paquetes vaciados y se
corrigió el alcance de empresa. Se emplea la ruta nativa `/odoo/modelo/id`:
el visor HTML de Odoo abre las referencias en una pestaña adicional y se comprobó
la OT original en esa pestaña, sin guardar modificaciones. Las copias intermedias y la entrega inicial
18.0.1.0.0 no se usan como prueba del paquete final 18.0.1.0.1.

Evidencias privadas en `~/.codex/local-artifacts/t94-20261019/`: adjunto original,
inventario previo, pruebas, manifiestos, logs de publicación, capturas y
`visual-review.json` con sus hashes. No se guarda información del cliente ni
credenciales en el repositorio público. Los registros de pruebas se descartan.

En navegador se verificaron el menú existente, los ocho pallets visibles en la
empresa activa, la búsqueda por folio que devuelve un registro, las siete etapas,
las guías históricas, el embarque y la apertura efectiva de la OT desde el panel.
No se guardaron cambios sobre los documentos de negocio revisados.
Se comprobó también la presencia del selector de calidad de llegada en el
formulario nativo de embarque. La evidencia visual tiene hashes de seis capturas.
