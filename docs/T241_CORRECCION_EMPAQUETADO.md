# T241: corregir empaquetado de recepciones

La solicitud identifica catorce folios de una sucursal productiva. El inventario
privado distingue los documentos existentes de los no encontrados; no infiere
equivalencias ni crea recepciones para completar la numeración.

La distribución de las tarjas ya puede tener el embalaje correcto, después de
una corrección nativa de producto, mientras la operación original y la tarja
conservan el anterior. `tools/ops/correct_reception_packaging.py` corrige únicamente
las relaciones explícitas al maestro de embalajes. Conserva el producto y lote
históricos de los movimientos; acredita el producto actual con sus movimientos
nativos de corrección. No vuelve a validar documentos ni genera movimientos.

También armoniza la relación y etiqueta de embalaje en las fuentes de anticipos
que siguen en borrador, conservando cantidades, precios, impuestos, tipo de cambio
e importes. Las líneas de otros embalajes y las proformas canceladas permanecen.
Un documento aprobado, facturado, ambiguo o con fuentes mezcladas exige revisión.

El plan privado guarda IDs, nombres, referencias faltantes y huellas de los
documentos, operaciones, tarjas y anticipos. No guardar estos datos en Git.
`guarded_cerro_data_repair.py` exige:

1. `rehearse <plan> /opt/steps-validation/t241-<etapa-nueva>`: respaldo totalmente
   decodificado, restauración fresca y copia sin correo ni tareas programadas.
2. Flujo nativo con un usuario existente de la sucursal, menús, formulario y
   `web_read`, más comparación completa de stock, lotes, cajas, contabilidad,
   maestros, envases y notificaciones. Solo se permiten los campos de embalaje
   enumerados y la auditoría de escritura de los registros autorizados.
3. Segunda ejecución sin escrituras y con el mismo resultado. Certificado del
   plan, herramientas y fuentes efectivas. No reutilizar pruebas fallidas.
4. `apply` con los mismos archivos y certificado, bloqueo compartido, ausencia de
   upgrades concurrentes, respaldo nuevo y configuración privada. La transacción
   compara el resultado con la copia antes de confirmar.
5. Revisión de solo lectura con `t241_browser_session.py` y
   `check_reception_packaging_ui.cjs`: cada recepción, una tarja por recepción y
   los anticipos. Retirar la sesión al terminar y conservar capturas privadas.

La intervención no instala addons, no cambia credenciales/permisos y no copia
datos a otros ambientes. Si quedan folios sin identificar, mantener T241 abierto
y registrar el resultado parcial; no afirmar que los catorce fueron corregidos.
