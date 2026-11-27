# T246 — Productor recibido y tarjas C

El ticket 246 del 27-11-2026 autoriza esta funcionalidad en Desarrollo,
Cerro El Plomo y QA-Cerro El Plomo. No requiere modificar ninguna recepción
real durante la instalación.

`step_packing_producer_change` 18.0.1.1.2 agrega **Cambiar productor** a la
recepción de fruta a proceso realizada y a sus tarjas C. El asistente muestra
la recepción, el productor actual y todas las tarjas afectadas. Corrige
`stock.picking.partner_id`, el productor del paquete y su detalle, y el
propietario de las existencias nativas. El cambio abarca la recepción
completa para mantener consistente su campo único «Recibido de».
Las tarjas antiguas recuperan su recepción desde la línea nativa existente
cuando todavía no tienen el enlace explícito de origen del paquete.

Cada existencia genera dos movimientos nativos de ajuste de propietario,
referidos a recepción y tarja, con motivo, usuario y fecha. Los movimientos
originales conservan al productor anterior. Se mantienen productos, lotes,
ubicaciones, fecha de entrada, kilos, cajas y fundo original; no se modifica
el productor del maestro de fundos. Las reservas existentes se conservan
con su propietario corregido. Un traslado interno no impide el cambio.
Las transferencias pendientes conservan el nuevo propietario al completarse,
incluidas las que agrupan fruta de otras recepciones con distintos dueños.

No se admiten fruta consumida o despachada, tarjas procesadas o stock
incompleto. Se comprueban nuevamente stock y estado bajo bloqueo al aplicar.
Los permisos de modificación de Packing, Inventario y empresa siguen
vigentes. Las escrituras directas y contextos RPC no eluden la corrección.
Las compras, anticipos y comprobantes históricos no se reescriben.
Entre propietarios terceros no se genera valoración. Si el cambio involucra
fruta propia de la compañía, se conserva el comportamiento nativo de
valoración de Inventario y sus asientos según la configuración contable.

Antes de publicar: copia fresca de cada destino, pruebas nativas y revisión
del formulario y flujo con un usuario operativo, paquete inmutable idéntico,
respaldo, bloqueo compartido, comparación de datos conservados y Desarrollo
publicado primero. QA-Cerro conserva sus datos e inhabilitación de salidas.
El cierre exige comprobar ambas entradas en los tres destinos.

## Entrega verificada — 27-11-2026

Publicado y comprobado en Desarrollo, Cerro y QA-Cerro: versión 18.0.1.1.2,
paquete del commit `c63dfe962dcf49fdd3783303817d23f26d0151e7`, SHA-256
`d356c1feb64d9ce1a462fad8abf86f8fa1c97ee768db33d984b2179e1032b041`.
Las tres copias frescas aprobaron 16 pruebas nativas cada una. También se
completó la corrección con un usuario existente sin superusuario en la
empresa receptora, revirtiendo los registros de ensayo. Se comprobaron las
dos entradas reales en navegador sin aplicar cambios a recepciones reales.

Se preservaron los registros originales y se publicaron los mismos bytes
probados, con bloqueo compartido, comparación de versiones y respaldo.
Los respaldos finales son `management_development_20261127T195228Z`,
`management_qa-cerro_20261127T195744Z` y `management_cerro_20261127T200314Z`
en `/opt/steps_backups/`. Se verificó la igualdad de código de Cerro y
QA-Cerro, su aislamiento de red y base de origen, y la neutralización de
salidas de QA. Las sesiones de revisión se eliminaron.

El ticket 246 quedó en Solved después de revisar el mensaje 10706 y las
evidencias de los tres destinos, sin comentarios, correos ni notificaciones
adicionales. Los artefactos privados están en
`~/.codex/local-artifacts/tickets-pendientes-20261127-revision2/delivery/`.
