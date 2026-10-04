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

## Despliegue en Desarrollo

- PR draft: https://github.com/fjcaroe/tracker-steps/pull/12, apilado sobre T40.
- Base `LAB_TAREAS`, servidor `odoo-new`. Respaldo PostgreSQL verificado en `/opt/steps_backups/t41_packing_dev_20260930T113739Z/LAB_TAREAS.dump` (SHA-256 `1a1e35038329ee13c7858070b5c2ca9b60eb6c2593d457c519ae7530631f2caf`).
- Instalados `step_inventory_packing` y `step_packing_operations` versión `18.0.1.0.0`; servicio `odoo18-dev.service` activo. `https://desarrollo.stepsapp.cl/packing/mobile` llega al inicio de sesión de Odoo (HTTP 200 después de redirecciones).
- Helpdesk T41 pasó de «New» a «In Progress» para que el cliente pruebe la primera etapa. T22 permanece «Solved»; T27 continúa «In Progress» y su código ya estaba desplegado en Desarrollo.

## Retoma del 01-10-2026 tras resolver T40

[T40](https://soporte.stepsapp.cl/helpdesk/ticket/40) figura **Resuelto**. Las recepciones y tarjas que T41 reutiliza están instaladas en Desarrollo mediante `step_inventory_packing` versión `18.0.1.0.0`; `step_packing_operations` también figura instalado en versión `18.0.1.0.0`. `odoo18-dev.service` está activo y `/packing/mobile` llega a la pantalla de inicio de sesión con HTTP 200. La homologación de balanza y el piloto físico de recepción se siguen en [T45](https://soporte.stepsapp.cl/helpdesk/ticket/45) y no bloquean el uso manual de las tarjas en Packing.

La base de Desarrollo aún registra **cero órdenes de proceso de Packing**. Por tanto, las ocho pruebas automatizadas de la primera etapa no sustituyen la revisión funcional con una OP y fruta representativas del cliente. Para comprobarla, en Desarrollo se debe crear una OP semanal con programa, instructivo, producto, embalaje, lista de materiales y restricciones pertinentes; calcular materiales; generar una OT; asociar tarjas C recibidas y tarjas E/N resultantes; terminar la fabricación; validar la cuadratura, el repaletizaje y la reserva; y contrastar el PDF y la captura móvil con los datos esperados. Registrar el resultado y los ajustes en T41 antes de cerrar esta primera etapa.

El documento funcional ubica el costeo de procesos en **etapa 2** y deja el detalle de nuevas inspecciones como «pendiente». La valorización contractual y la compra mensual al productor requieren reglas y datos contables verificables. T38 Productores sigue **En progreso**, aunque `step_producers` ya figura instalado en Desarrollo. T41 permanece **En progreso**: el cierre de T40 quitó la dependencia de recepciones y tarjas, pero no acredita el piloto de Packing ni completa la segunda etapa.
