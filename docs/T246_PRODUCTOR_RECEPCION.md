# T246 — Productor recibido y tarjas C

El ticket 246 del 27-11-2026 autoriza esta funcionalidad en Desarrollo,
Cerro El Plomo y QA-Cerro El Plomo. No requiere modificar ninguna recepción
real durante la instalación.

`step_packing_producer_change` 18.0.1.1.0 agrega **Cambiar productor** a la
recepción de fruta a proceso realizada y a sus tarjas C. El asistente muestra
la recepción, el productor actual y todas las tarjas afectadas. Corrige
`stock.picking.partner_id`, el productor del paquete y su detalle, y el
propietario de las existencias nativas. El cambio abarca la recepción
completa para mantener consistente su campo único «Recibido de».

Cada existencia genera dos movimientos nativos de ajuste de propietario,
referidos a recepción y tarja, con motivo, usuario y fecha. Los movimientos
originales conservan al productor anterior. Se mantienen productos, lotes,
ubicaciones, fecha de entrada, kilos, cajas y fundo original; no se modifica
el productor del maestro de fundos. Las reservas existentes se conservan
con su propietario corregido. Un traslado interno no impide el cambio.

No se admiten fruta consumida o despachada, tarjas procesadas o stock
incompleto. Se comprueban nuevamente stock y estado bajo bloqueo al aplicar.
Los permisos de modificación de Packing, Inventario y empresa siguen
vigentes. Las escrituras directas y contextos RPC no eluden la corrección.
Las compras, anticipos y comprobantes históricos no se reescriben.

Antes de publicar: copia fresca de cada destino, pruebas nativas y revisión
del formulario y flujo con un usuario operativo, paquete inmutable idéntico,
respaldo, bloqueo compartido, comparación de datos conservados y Desarrollo
publicado primero. QA-Cerro conserva sus datos e inhabilitación de salidas.
El cierre exige comprobar ambas entradas en los tres destinos.
