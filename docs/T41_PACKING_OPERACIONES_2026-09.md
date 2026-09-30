# T41 — Operación de Packing, primera etapa

Fuente: ticket de Helpdesk #41, «Módulo de Packing», adjuntos `ERP Steps Odoo- Packing.docx` y `Anexo1 Módulo de Packing.xlsx` (recibidos el 30-09-2026). Al leer Helpdesk no existía T42; este es el único ticket nuevo de Packing. El trabajo parte de `codex/t40-inventory-packing` porque T40 ya aporta las tarjas C/E/N y sus paquetes de stock.

## Arquitectura

`step_packing_operations` amplía los módulos existentes. La OT es `mrp.production` de Odoo; la tarja es `stock.quant.package`; la reserva se incorpora al modelo `step.export.stock.reservation` y usa movimientos de stock reservados. No se duplica ninguno de esos registros.

## Primera etapa implementada

- OP semanal con líneas de producto, especie, variedad, embalaje, cajas, kilos, instructivo y restricciones de productor/variedad. Se crean OT desde sus líneas.
- Cálculo consolidado de materiales desde las listas de fabricación, comparado con cantidad libre de stock. La OP se valida y se cierra solo cuando sus OT están cerradas.
- Cuadratura de la OT: tarjas C consumidas; E de exportación y N de comercial, precalibre o desecho; merma calculada. Valida un productor y una variedad, restricciones de la OP y conservación de kilos. Para cerrar exige fabricación nativa terminada, las tarjas presentes en los movimientos reales y producto dentro de los paquetes resultantes.
- Repaletizado completo de paquetes C, E o N con conservación de cajas, kilos, productor y atributos. Ejecuta un traslado de Inventario entre paquetes en la misma ubicación. Permite una tarja de salida mixta, manteniendo detalle por productor. Las fuentes pasan a «Repaletizada» y las nuevas a «Validada».
- Reserva de tarjas para una OP mediante la reserva nativa de movimientos. Se libera antes de consumir las mismas existencias en una OT.
- Informe PDF de proceso con cuadratura y detalle de tarjas. El acceso móvil permite escanear QR o código de barras, registrar C/E/N, capturar sin conexión y sincronizar después; el PDF de tarja existente permite imprimirla con QR. La sincronización repite de forma segura un registro si se reenvía el mismo número de tarja.

Las recepciones de fruta, envases, Packing List, instructivo de embarque y despachos ya están en T40 o Exportaciones y se muestran desde la app Packing existente.

## Límites de esta entrega

- La conexión de una impresora específica queda para homologación con su modelo. El navegador imprime el PDF mediante el diálogo de impresión.
- El escáner por cámara usa `BarcodeDetector` cuando el navegador lo ofrece; siempre se puede ingresar el código manualmente.
- El coste del proceso y el estado «Contabilizada» son etapa 2 del documento. La compra mensual al productor y la valorización contractual requieren tarifas, diarios y revisión contable; este módulo no publica asientos ni presume precios.
- Inspecciones nuevas figuran como «pendiente» en el documento. Se conservan las inspecciones de la app existente.

## Verificación

- QA aislada `T40_QA_20260929T203507Z`: instalación y actualización, 7 pruebas de Packing, 0 fallos y 0 errores al 30-09-2026 11:06 UTC. Incluye fabricación real, repaletizado simple/mixto y reserva/liberación.
- Copia actual de Desarrollo `T41_QA_20260930_CURRENT`: instalación de T40 y Packing; 14 pruebas combinadas, 0 fallos y 0 errores al 30-09-2026 11:12 UTC. La actualización posterior del acceso móvil pasó 8 pruebas de Packing, 0 fallos y 0 errores al 30-09-2026 11:25 UTC.
- Tras ajustar el informe a la plantilla global de Desarrollo, la prueba de impresión y las otras 7 pruebas de Packing pasaron nuevamente: 0 fallos y 0 errores al 30-09-2026 11:34 UTC.

T22 y T27 ya estaban presentes en Desarrollo con archivos idénticos a sus ramas revisadas. La respuesta más reciente de T27 indica que Desarrollo es el ambiente donde el cliente desea probar; SyS se usa para Nómina.
