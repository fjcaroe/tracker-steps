# Traslados y recepciones de Cerro El Plomo

Las listas originales de traslados 5187 y recepciones externas 5244 recuperaron la lectura completa en la copia Community de 190 módulos. El módulo se instaló desde la semilla de 189 en PostgreSQL 12.22 con las 677 piezas del filestore en un directorio independiente. La versión final incorpora la combinación de empresas y usuario en la caché de lectura. Sus cuatro archivos pasaron la actualización y el nuevo arranque en la misma restauración.

| Prueba | Resultado |
|---|---|
| 110 traslados, 184 líneas de tarja y 49 referencias externas presentes en la fuente | Coincidieron todos los registros visibles y los valores de las nueve columnas restauradas para 15 usuarios originales en 64 combinaciones de usuario y empresas. Se conservaron los tres rechazos de lectura y los 21 resultados vacíos de la referencia. |
| Productos, embalajes, envases, kilos netos y promedio | Las relaciones apuntan a los productos y embalajes originales. La lectura usa las líneas de tarja autorizadas, los movimientos activos y la conversión de unidad del producto. El recuento físico anterior de un movimiento se conserva cuando corresponde usarlo para el resumen. |
| Número de guía y estado SII | Los 110 traslados históricos tenían ambos campos vacíos. Se introdujeron temporalmente un número y un estado aceptado en los tres estados de traslado existentes y se reprodujo la respuesta nativa. El envío fiscal y la modificación de sus estados requieren el proveedor de despacho. |
| Calidad por usuario | Para traslados en borrador, asignados y hechos se compararon controles pendientes, aprobados, fallidos, de empresa ajena y de empresa ajena con un punto de control de la empresa visible. La base original contiene cero controles y cero puntos. Las contrapruebas usaron las dos tablas reales y terminaron con reversión. |
| Filtros de calidad | Pasaron nueve configuraciones de controles, con todas las empresas y una empresa individual. En el sistema original un traslado sin controles queda fuera de ambos filtros. Un traslado con un control pendiente y otro terminado visibles aparece en ambos. |
| Catálogo después de instalación y actualización | Sin pérdida ni modificación en las 17.731 columnas, 8.375 restricciones, 3.318 índices, 29 vistas SQL y 656 reglas de la semilla combinada. Se conservaron los nueve registros completos de campos restaurados, siete opciones de estado SII, 62.030 identificadores originales, 24 protecciones y 23 vistas Studio. |
| Pantallas de Cerro | 21 de 23 rutas originales, 20 de 23 con idénticos valores Studio y 18 de 23 con lectura completa idéntica para el operador de inventario. |

La prueba se ejecutó en una restauración privada de un volcado nuevo de la base de 189 módulos. El registro final contiene 190 módulos instalados con licencia libre. El clúster de la contraprueba en RAM usa un socket Unix aislado y no escucha por TCP. Las 1.247 secuencias volvieron al punto previo a los ejercicios. El recibo final es `501aa3df9576c73c74b29c417d1912035079fb9f7961bb0ef98e808fd02b5bd7`. Los catálogos tras instalar y actualizar tienen el mismo SHA-256, `f6b6e6492f885d4482e7e6942bb5d53b980fe2fdb2f1eae38f2a7f8599a77200`.

## Reproducción

Se puede reconstruir el archivo con `python tools/community/build_cerro_verified_172.py --profile picking --source . --output <tar-nuevo>`. El SHA-256 del archivo es `e759f3b69e50631e3fc153009a951b3f7cc4cb3c0224a731ed3bcc3d8a8c1968`. El árbol del módulo es `6beaabe1774dfbc179949fe7aa67be4c8d65dc48036b516975e7fed5d89e6794`.

`run_cerro_wsl_picking.py --cold` recibe el ejecutor Focal y la carpeta privada de evidencias. Construye el mismo TAR, comprueba los perfiles de origen y destino y compara las pruebas nativas de usuario (`35c8b598ffe9ee8582991468b2ecaabacc671672707fdf3fefdedde51fd00962`) y filtros (`8c138bcfadb1d9b8b12b37bb15c8aa4fc31599af9e9ae12d9602f396b1443fa5`).

La referencia para el trabajo siguiente ya comprende las diez OT y las 238 tarjas, con valores por usuario y empresa. Su SHA-256 es `eb3f396575eea81656c1c21bc55b18d35faaf30b35127dbc29ee728572ff1ec7`. Las fichas 5189, 5193, 5194 y 5245 y el seguimiento de cobros 5192 continúan pendientes tras el corte de 190. La validación o cierre de una OT, la emisión fiscal y el ciclo de un control de calidad requieren pruebas de operación adicionales.
