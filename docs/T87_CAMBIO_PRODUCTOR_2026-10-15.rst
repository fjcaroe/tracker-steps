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

Estado: pruebas del paquete final y publicación pendientes.
