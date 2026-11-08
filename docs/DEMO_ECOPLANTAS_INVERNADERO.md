# Demo de invernadero ECOPLANTAS

Ingresar a [Invernadero en Desarrollo](https://desarrollo.stepsapp.cl/odoo/invernadero?cids=527)
con la cuenta habitual de Desarrollo y seleccionar **EcoPlantas** como empresa
activa. La portada de Steps enlaza a los registros de Odoo identificados con
`[DEMO]` y muestra los estados del lote.

Las pantallas del recorrido tienen una guía con pasos, acceso al panel e
indicadores actualizables. En Despacho se puede consultar la disponibilidad
en la ubicación de plantines. El reparto enlaza a centros, drivers y carga
semanal desde la misma pantalla.

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

En **Costos compartidos → Repartos semanales**, abrir *Servicios compartidos
del vivero [DEMO]*. El borrador conserva los cargos y la semana de la demo
original. Muestra $110.000 para Propagación Norte y $90.000 para Propagación Sur.
La opción **Carga semanal** reúne las cantidades de superficie y horas que
explican los importes.

## Comprobación de publicación

`tools/ops/move_ecoplantas_to_development.py` traslada los registros de la base
separada a la empresa existente. Certifica una copia fresca de Desarrollo y
compara el paquete y los datos exportados antes de aplicar el traslado con
respaldo. El recorrido completo se prueba en la copia y se conservan los
borradores para la presentación. La cuenta interna usa sus credenciales de
Desarrollo. `tools/ops/verify_ecoplantas_development_https.py` verifica la entrega
con el perfil de Desarrollo.
