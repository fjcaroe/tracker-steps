# Recepción de fruta a proceso en Cerro

La copia privada de Cerro con 192 módulos libres permitió al usuario original de bodega de la empresa 31 registrar y validar una recepción a proceso. Se utilizaron los maestros y las operaciones de la recepción histórica 228. El formulario devolvió primero un error cuando los kilos distribuidos todavía no figuraban como recibidos en Operaciones. La recepción siguió en borrador y conservó la tarja sin asignar.

Tras registrar los 612 kg, la validación dejó una tarja C validada, una existencia de 612 kg vinculada al lote, al productor y a la ubicación correctos, y un borrador de devolución de los 180 envases de cosecha al mismo productor y bodega. En el control original y en Community coinciden todos los valores de la prueba. Las operaciones se revirtieron y las 1.247 secuencias recuperaron su estado.

## Paquete y referencias

El perfil `receipt_flow` de `tools/community/build_cerro_verified_172.py` reconstruye los 29 archivos que se probaron sobre la copia restaurada. Su SHA-256 es `afe9a37e9f68e260cefb81a7269058c0af5f721f81d9a5d9bc8d0bc8f4c9c35a`. El módulo de recepción usa AGPL-3. El archivo `SOURCE.txt` identifica la fuente y la licencia de cada pieza. El módulo de consulta de Packing conserva LGPL-3. La derivación mantiene reproducibles los paquetes anteriores de 190 y 191 módulos.

| Control | Resultado de la copia | SHA-256 |
| --- | --- | --- |
| Recepción con devolución de envases | Igual a la operación nativa realizada en privado | `c455217d3098ed9daba73fa16bc0f1f8d4de602ab7db70ec3177124186a8324b` |
| Trazabilidad de inventario | 58 recepciones, 56 movimientos, 184 líneas detalladas con su lote y propietario en 64 contextos | `4c418eba0f20faff2aea1b4cbafd3ac80a2d02ee204d0af4a36bfd14f53b35fe` |
| Permisos de recepción | 900 resultados idénticos en 15 modelos, cuatro operaciones y 15 usuarios | `21a571ee5e41a3b4c0ef56dae8a87e322ec06837eaaadbb03651e5666b9458e9` |
| Lectura y permisos del asistente de importación | Se reprodujeron la búsqueda, la apertura y los permisos sobre la ficha de otro usuario. Doce operadores podían abrirla. El usuario 34 podía editarla y tenía prohibido eliminarla | `7cb775f078a2fbf832f3adacf4b88bc7a82b82d845fc63ada0ca9793d0ce6a44` |
| Comparación posterior a la operación | Se conservaron 17.731 columnas, 8.375 restricciones, 3.318 índices y 29 vistas SQL. Coinciden los 21 modelos afectados, sus 2.252 campos y sus 469 opciones. También coinciden los permisos, reglas y tablas de negocio comparados | `1a7d401b98139d7401a1731e6c8c27b9f5b050280ac89da52522e9c5366e2b7a` |

El control de permisos detectó que el primer candidato permitía a un operador eliminar el asistente. La derivación aprobada aplica los niveles de los grupos originales de Packing a los modelos que intervienen en la recepción. La prueba repitió cinco rechazos independientes, entre ellos el acceso a la recepción de otra empresa y los intentos de cambiar una tarja o crear un movimiento de envases fuera de la recepción. Las órdenes históricas de Packing conservaron la consulta y los tres rechazos de edición.

## Formulario y alcance

El formulario 5245 conserva la ruta y los campos Studio originales. El registro pasó de 127 a 188 de los 211 campos de la arquitectura original, y de 16 a 19 de sus 34 botones. Se comprobó la creación y la validación mediante `web_save` y `button_validate`, con sus mismas operaciones de inventario. Continúan pendientes la lectura completa de esa pantalla y la del seguimiento de cobros de Contactos. La matriz conserva 23 rutas, 23 lecturas de campos Studio y 21 lecturas completas.

La aceptación cubre el ingreso manual por unidad de traslado y la preparación de la devolución. La balanza física, las recepciones interplanta, los controles de Calidad al validar, la corrección o reversión del ingreso, la emisión fiscal y la validación del movimiento de envases tienen alcances separados. El candidato rechaza la validación de un traslado con una guía interplanta y de una recepción que requiera controles de Calidad. La referencia nativa de esta prueba incluye un borrador de devolución.

El comprobante agregado del ensayo sobre la copia actualizada es `89ad30807b3e986536ba5f375d2aebc0ca101293b75cbff24b8932afde251825`. Las filas, nombres y valores individuales se conservan en el archivo privado de QA.


## Segunda restauración

El ejecutor `tools/community/run_cerro_receipt_flow.py` reconstruyó una copia nueva desde la base de 189 módulos, verificó sus 677 archivos y cargó sucesivamente los paquetes de 190, 191 y 192. La instalación inicial del perfil final, su actualización y el control tras las pruebas devolvieron las mismas huellas de catálogo que la primera copia. Los ocho cotejos funcionales, los cinco intentos denegados y las tres comprobaciones sobre las órdenes históricas pasaron en este segundo arranque. El recibo completo de la restauración es `f84eb7d6dc2ae5708642815f123113fc259c2e6c63ddde468f1bc9e785df00a7`.
