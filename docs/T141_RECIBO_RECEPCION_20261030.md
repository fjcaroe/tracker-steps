# T141 Recibo de recepción

## Alcance

Mensaje 9863 y adjunto 3446 revisados: capturas de cabecera y operaciones,
formas de texto y dos tablas EMF con detalle de pallets y transporte. Los EMF
se convirtieron a PNG con GDI para revisar todas sus columnas. Recepciones de
fruta entrantes en Desarrollo, Cerro y QA-Cerro; se conserva la acción nativa
Recibo de entrega y los otros documentos de stock.

## Implementación preparada

Addon `step_packing_reception_report`: QWeb versionado y helpers de lectura,
sin campos, maestros o registros paralelos. Cabecera, guía, tipo/clase y lote;
operaciones con envases físicos independientes del peso; detalle de pallets,
kg brutos/tara/netos, promedio ponderado por cajas y transporte/chofer.
Los totales de operaciones separan unidades de medida diferentes. No se
validan ni alteran recepciones al imprimir.

## Estado

Pendiente certificación del paquete exacto, PDF nativo, inspección visual y
publicación. No cerrar por este documento. Datos, capturas y PDFs fuera de Git.
