# T197 · Listado de recepciones de fruta a proceso

El menú Packing → Recepciones → Fruta a proceso muestra producto, embalaje,
cantidad de envases, kilos netos y kilos por envase. Las columnas de envases
y kilos totalizan las filas visibles. Una recepción puede mostrar varios
productos y embalajes.

Las columnas toman los datos de las tarjas y recurren a las operaciones
cuando falta el dato. En recepciones abiertas, la cantidad prevista se usa
si todavía no se registra una cantidad en la operación. El promedio se
calcula con el peso neto de la recepción dividido por sus envases.

Se preparó `step_packing_ticket_revision` 18.0.1.2.1 desde el commit
`52d136bbc340787592f0347e668a39c80c3b1caa`, con SHA-256
`ab7815d5432abb4ea9186aa436ff48c785996c86013c5b04b41e04e8e7ce0c00`.

Las copias de Desarrollo, Cerro y QA-Cerro pasaron ocho pruebas cada una.
Se verificaron el menú, las cinco columnas, los dos totales, la importación
existente y las recepciones con varios productos o embalajes, con operaciones
sin tarjas y sin datos de peso. El listado de Packing San Javier mostró
385 envases, 861 kg netos y 2,24 kg por envase en la recepción del caso,
tanto en la copia como en Cerro El Plomo.

El mismo paquete quedó publicado y verificado en Desarrollo, Cerro El
Plomo y QA-Cerro El Plomo. La versión y el código efectivo coinciden en
los dos ambientes de Cerro. Se verificó de nuevo Desarrollo después de
publicar la versión final de la corrección de producto del T196.
