T35 revisión adicional de tarjas y reclamos
==========================================

Solicitud
---------

Después de confirmar los cambios anteriores con «OK los cambios» (mensaje
9228), el cliente envió dos revisiones el 07-10-2026: consulta de tarjas en
Packing List (mensaje 9229, adjunto 3298) y reclamos por tarja (mensaje 9230,
adjunto 3299). El ticket fue reabierto por el cliente. Destino: Desarrollo,
LAB_TAREAS, https://desarrollo.stepsapp.cl; no se solicita producción.

Tarjas
------

Consultar Tarjas aparece inmediatamente después de Reserva de Stock en
Exportaciones / Embarque. Utiliza stock.quant.package, sin duplicar inventario.
Expone clasificación, productor, fundo, especie, variedad, cajas, kilos,
ubicación y relaciones de embarque. Los campos de estado, producción,
composición y salida se incorporan si los módulos agrícolas que los poseen
están instalados; no se crea una dependencia circular con Inventario Packing.
La búsqueda permite filtrar tarja, embarque y atributos; ofrece filtros con y
sin embarque. Campos adicionales son seleccionables en las columnas.

El número de embarque proviene de la relación many2many existente con el
instructivo. Se asigna seleccionando la tarja en Tarjas y despachos del
instructivo, no digitando otro número en la tarja. La ficha y la consulta
muestran esa relación y sus números, conservando todos los vínculos previos.

Packing List usa la misma consulta para seleccionar tarjas, filtrada por las
tarjas del embarque. La ventana de selección se amplía al ancho disponible y
permite desplazamiento horizontal para las columnas. El estilo se limita a
los diálogos que muestran el campo específico de números de embarque.

Reclamos
--------

El formulario filtra tarjas por los embarques reclamados y el servidor rechaza
tarjas ajenas desde el guardado, incluida entrada directa por API. El botón
Cargar tarjas del embarque presenta su lista para ingresar los montos. Se
pueden añadir directamente tarjas del mismo conjunto. Cada tarja aparece una
sola vez por reclamo; el detalle muestra productor, variedad, categoría,
calibre, producto, unidad, embalaje, lotes, cajas y kilos.

Cada fila permite reclamar y aceptar importes USD. Los totales se actualizan
al cambiar el detalle. El ejemplo del cliente se comprueba con 2000 USD
reclamados y 1100 USD aceptados (500 y 600 aceptados por tarja). Solo las
tarjas con importes se vinculan como reclamadas. No se permiten negativos ni
aceptar más de lo reclamado por tarja. Aceptar conserva el flujo existente
hacia liquidaciones, atribuyendo el importe aceptado al embarque de cada
tarja en lugar de repartirlo por kilos. Un reclamo resuelto bloquea creación, edición y borrado
de su detalle, además del bloqueo del encabezado existente.

Se añade detalle transaccional, no un maestro paralelo. Los reclamos previos
sin detalle mantienen sus montos y pueden seguir el flujo anterior. No se
reparten importes históricos ni se generan reclamos de cliente automáticamente.

Estado
------

Publicado y comprobado: step_export 18.0.2.9.8 en Desarrollo.

* Commit del código: 890f4e570d85ccd077c29057e701ab652aa99093.
* SHA256: c18e0817463079f25966b5e7c974b7f9dffb2f9701f8d22d55a2625e2a0c3e15.
* Copia fresca: MANAGEMENT_QA_DEVELOPMENT_t35tagsclaims07c.
* 34 pruebas: cero fallos, cero errores.
* Perfil Ventas/Inventario: consulta de tarjas, asociación bidireccional,
  carga del reclamo, guardado de detalle 2000/1100 USD, aceptación y relación
  con embarque; incluye el flujo previo de nota/proforma y Packing List.
* Comprobación funcional repetida en destino, con muestras revertidas.
* Preservación de registros comerciales e importes comprobada en copia
  y durante la publicación; no se generaron reclamos de cliente reales.
* Respaldo: /opt/steps_backups/management_development_20261007T155611Z.
* Overlay: /opt/steps-managed/releases/development/890f4e570d85ccd077c29057e701ab652aa99093.
* No se modifica producción ni se publican addons en raíces compartidas.

Dos ensayos previos se descartaron para promoción: el primero detectó un
atributo class no admitido en search; el segundo, fixtures de tarja sin tipo
E cuando Inventario Packing está instalado. Ambos se corrigieron en Git y se
repitió la instalación desde una copia fresca. El ensayo final incluye la
atribución exacta de importes por tarja a las liquidaciones de sus embarques.
