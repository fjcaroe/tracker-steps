# Demo de invernadero ECOPLANTAS

Ingresar a [Invernadero](https://ecoplantas.stepsapp.cl/odoo/invernadero) con el
usuario interno habilitado para la revisión. La portada de Steps enlaza a los
registros de Odoo identificados con `[DEMO]` y muestra los estados del lote.

1. En Inventario, abrir la recepción en borrador con origen `[DEMO] Semillas
   y sustrato`. Registrar un lote para las semillas y recibir los insumos en
   la ubicación de invernadero.
2. En Manufactura, abrir la orden con origen `[DEMO] Lote de 100 plantines`. La lista de
   materiales vincula semillas y sustrato; las operaciones son siembra y
   trasplante. Confirmar la orden, asignar los insumos y nombrar el lote final.
3. En Calidad, completar la revisión visual del lote vinculada a fabricación.
   Después de terminar las operaciones, registrar los plantines producidos.
   Consultar el lote final y sus movimientos en Inventario.
4. En el despacho con origen `[DEMO] Despacho de plantines`, seleccionar el
   lote producido y preparar la salida de 60 plantines. Consultar el saldo y
   los movimientos del lote desde Trazabilidad de plantines.
5. En Proyecto, abrir `Labores del invernadero [DEMO]` para revisar riego,
   sanidad, trasplante y despacho. En Mantenimiento, abrir `Bomba de riego
   [DEMO]` y su solicitud preventiva de revisión de bomba y goteros.

Las cantidades, operaciones y controles ilustran el flujo. Ajustar los
productos, lotes y labores al proceso del invernadero al preparar su operación.

## Comprobación de publicación

`tools/ops/manage_ecoplantas_greenhouse.py` prueba la instalación y el ciclo
completo en una copia privada nueva antes de publicar el mismo origen nativo.
Conserva un respaldo previo, datos existentes y credenciales.

Si la instalación y configuración terminaron y solo falla la respuesta HTTPS
inmediatamente después del arranque, no repetir la instalación. Ejecutar
`tools/ops/verify_ecoplantas_greenhouse_delivery.py RUN_ID RUTA_RESPALDO` bajo
el bloqueo compartido que adquiere el propio verificador. Este comprueba el
origen probado, versiones, formularios y respuesta HTTPS; restaura el respaldo
en una base privada temporal para cotejar los registros originales, contraseñas
cifradas y ausencia de nuevas notificaciones, sin modificar los datos de la demo.
