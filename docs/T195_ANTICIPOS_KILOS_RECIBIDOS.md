# T195 Anticipos por kilos recibidos

En **Productores → Anticipos → Preparar anticipos**, el campo **Calcular por**
ofrece kilos procesados y kilos recibidos. La segunda opción toma los kilos
netos de las tarjas C y E de recepciones validadas, según el período de
recepción y la lista seleccionada. El corte de proceso aplica a los kilos
procesados. El cálculo queda identificado en la proforma y su PDF.

La preparación reserva las fuentes para evitar el doble uso entre modalidades,
incluidas las tarjas C divididas que originan tarjas E. Un segundo borrador
que comparte una tarja E con una proforma validada queda impedido de validar.
Las compras mensuales comprueban también las reservas por kilos recibidos.

El paquete `producer-advances` contiene `step_producer_advances` 18.0.1.2.0
y `step_packing_fruit_proforma` 18.0.1.2.2. Su commit es
`14820baf7d30b9601e1fb16a789c7fd7e402f226` y su SHA-256 es
`89835f668dbbb000a05a12e43505ea00c60cbff0877c91a8dde80fbf9106dd2c`.

Las copias frescas de Desarrollo, Cerro y QA-Cerro pasaron 70 pruebas cada
una. Se revisaron las proformas de ambas modalidades, el anexo de mil filas,
el ciclo de compra y los borradores 33 y 46. En la copia de Cerro, las cuatro
recepciones del caso totalizaron 20 tarjas y 8.425,10 kg netos. La preparación
se ensayó con una tarifa de prueba y una cuenta de la matriz configurada
temporalmente para la sucursal dentro de la misma transacción de prueba.

Por decisión del solicitante, Contabilidad define los precios de los
productos recibidos. En Packing San Javier se requiere además asignar
la cuenta de compra del producto base o su categoría. El diario de compra
de fruta de la sucursal se requiere al generar la factura en borrador.

Se publicó y verificó el mismo paquete en Desarrollo, Cerro El Plomo y
QA-Cerro El Plomo. Los controles de versión y código efectivo confirmaron
paridad entre los dos ambientes de Cerro. La consulta posterior en Cerro
confirmó los kilos del caso y el aviso por falta de tarifa.
