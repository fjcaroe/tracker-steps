T87 Packing cambio de productor comercial
========================================

Ticket ID 87, mensaje humano 9455 y adjunto 3352. Se amplía el Repaletizado
nativo, sin nueva aplicación ni modelos de documentos paralelos. Productor
comercial relaciona el maestro res.partner con is_productor y aparece en
Tarjas que entran, Distribución y trazabilidad y formulario de tarja. En la
impresión ocupa el campo Productor; la procedencia y sus líneas se conservan.

El tipo existente Cambio Productor / Cambio de productor queda marcado por
una migración versionada. La marca también está disponible en el maestro de
tipos, dentro de la categoría Corrección. La validación exige productor
comercial por tarja de destino, del maestro compartido o de la misma empresa.
Las tarjas validadas bloquean la modificación. El repaletizado normal hereda
la selección anterior y rechaza mezclas o cambios comerciales implícitos.

El traslado nativo conserva cantidades, cajas, kilos, lotes y propietarios de
stock y líneas de origen. La clasificación comercial no transfiere propiedad
jurídica ni genera facturación o liquidaciones. No se cambian los históricos.

Pruebas de aceptación
--------------------

Se comprueban un traslado real origen-destino, productor impreso, trazabilidad,
obligatoriedad, inmutabilidad al validar, repetición de repaletizado ordinario,
restricción al maestro de productores, empresa y vistas/menú efectivos. Se
ensayan tarjas de exportación y nacionales con reversión de las pruebas.

Publicación y cierre verificados
-------------------------------

Publicado el 15 de octubre de 2026 en Desarrollo y Cerro El Plomo:
step_packing_producer_change 18.0.1.0.0, paquete del commit
c9b976f9821d8d2f69fe989b481336dc7cf0f2ce, SHA-256
779abe3515b38b4f90e79f84bce31cdba10c460c9a289bc074f9b2cab1565f2c.
El mismo paquete pasó tres pruebas funcionales en cada copia, seis en total,
sin fallos ni errores. Incluye escritura por ambas pestañas, stock trasladado,
trazabilidad y lectura del productor comercial en la impresión QWeb.

Copias: MANAGEMENT_QA_DEVELOPMENT_t87_g_dev y
MANAGEMENT_QA_CERRO_t87_g_cerro. Comparación de preservación aprobada en ambas.
Sondas posteriores en cada instalación repitieron los casos funcionales con
reversión de los documentos de prueba. Los dos logs contienen
MANAGEMENT_DEPLOY_OK, MANAGEMENT_REGISTRY_OK y MANAGEMENT_VERIFY_OK.

Respaldos: /opt/steps_backups/management_development_20261015T184559Z y
/opt/steps_backups/management_cerro_20261015T184658Z. Exclusión compartida y
overlays privados, sin reemplazar raíces de addons ni bajar versiones.

Revisión visual por HTTPS: menú Packing, formulario nativo de Repaletizado,
columna Productor comercial en Tarjas que entran y Distribución y trazabilidad
en ambos destinos. En Cerro se revisó el RP/2026/00003 del adjunto, sin editar
sus datos. Se renderizaron y revisaron PDF reales de ambas copias: productor
comercial correcto y QR incrustado mediante el motor nativo de Odoo, evitando
la dependencia de una petición HTTP adicional para el código.

Evidencia privada en ~/.codex/local-artifacts/t87-packing-20261015: capturas,
PDF de ambas copias, certificados QA, logs y visual-review.json con huellas.
Ticket ID 87 cerrado como resuelto, nota interna 9458 sin notificaciones ni
destinatarios externos, tras comprobar que no había respuestas humanas nuevas.
