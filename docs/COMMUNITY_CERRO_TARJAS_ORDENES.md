# Tarjas y órdenes de trabajo de Cerro El Plomo

La consulta de tarjas 5193 y las listas de órdenes de trabajo 5189 y 5194 devuelven los mismos registros y valores que la referencia nativa. En la copia combinada hay 191 módulos libres instalados. Coinciden 23 de 23 rutas, 23 de 23 lecturas de los campos Studio y 21 de 23 lecturas completas de las fichas. El formulario de traslado 5245 y Seguimiento de cobros 5192 aún requieren proveedores adicionales.

| Prueba de usuario | Resultado de la copia fría |
|---|---|
| 15 operadores y 64 combinaciones de usuario y empresas | Coincidieron registro por registro los datos visibles de 10 órdenes y 238 tarjas, incluidos sus permisos de lectura, empresas, productores, variedades, embalajes y plantas. |
| Inventario de fruta | Las 241 líneas de detalle, los 30 vínculos de entrada y los 40 de salida conservan sus valores físicos. Al aumentar temporalmente en siete los kilos de un detalle, la consulta aumentó en siete los kilos de su tarja. |
| Horas y rendimiento | Un turno de cuatro horas con una hora de detención, dos trabajadores, 180 kg de entrada y 90 kg exportados produjo tres horas efectivas, 60 kg/h, 30 kg/h por trabajador y 50 % de exportación en ambos sistemas. Los cuatro indicadores volvieron a cero en el control sin término, trabajadores ni kilos de entrada. |
| Paquetes | Se conservó el rechazo al modificar el número de cajas de una tarja validada. El operador también creó y renombró un paquete ordinario en ambos sistemas. Se revirtió la transacción y se restauró su única secuencia consumida. |
| Identidad y estructura | Coincidieron las filas completas de cinco modelos, 329 campos y 48 opciones de selección. Todas las columnas, restricciones, vistas, índices, reglas y permisos de la semilla se conservaron tras instalar y actualizar. Las once tablas de inventario y Packing comparadas coinciden en cada fila. |

La pantalla nativa de tarjas permite consulta. El proveedor de las órdenes abre sus listas históricas y restringe las altas, ediciones y bajas. Los importes almacenados de las órdenes conservan el balance de sus proveedores originales, incluido el consumo parcial de tarjas. Los porcentajes y rendimientos se calculan con sus datos reales. Las reglas originales siguen decidiendo qué registros puede leer cada operador. Validar o cerrar una orden, revisar sus materiales, generar consumos y emitir una guía necesitan el flujo operativo completo.

Un primer ensayo perdió el atributo obligatorio de seis columnas al registrar modelos parcialmente. Se conservaron el ensayo y el respaldo anterior. El paquete final incorpora la causa real de detención, ambas fechas y el estado de la orden de proceso, la unidad de medida y la inspección obligatoria de la OT. La instalación fría posterior conservó los seis requisitos sin DDL correctivo y sin relajar las protecciones del esquema.

## Restauración y entrega

Se restauró el volcado de 189 módulos `fec1b4afc757c170f2ae5ea5048a87a818f58b997266cb5ebec0c52053726ddb` con PostgreSQL 12.22. La copia tiene 677 objetos de filestore propios. Primero se instalaron y actualizaron los cuatro archivos finales de la consulta de recepciones. Inmediatamente después se instalaron y actualizaron los cuatro archivos finales de Tarjas y OT. El operador repitió las dos listas de traslados, los filtros combinados de Calidad, las dos listas de OT y las tarjas con la combinación final. El usuario de inventario pudo consultar las OT y recibió los tres rechazos previstos al intentar crear, escribir y eliminar una orden por el proveedor histórico.

| Comprobante SHA-256 | Valor |
|---|---|
| TAR de recepciones, perfil `picking` | `e759f3b69e50631e3fc153009a951b3f7cc4cb3c0224a731ed3bcc3d8a8c1968` |
| Aceptación fría de 190 | `1d386881a264a0d1da5197ef172deb313814f00c8ba2e1cf4f56976eca3d0ff4` |
| TAR de Tarjas y OT, perfil `pack_reports` | `e533b1a0113e5ef7627bc4504a4e936b76c306eedd22f6c8245d37dcd4f79d52` |
| Lectura nativa de las órdenes y tarjas por operador | `eb3f396575eea81656c1c21bc55b18d35faaf30b35127dbc29ee728572ff1ec7` |
| Contrapruebas operativas de referencia nativa | `4bad66f2d093e0fc7faddfb6602d113d61041d8479d6e1361e5861b0cfcc40e6` |
| Catálogo íntegro tras instalar y tras actualizar 191 | `4ed97d6a5ebd1b9b4bb193ed81176494a59d028d2edbe6cf6699a0aaed7febc4` |
| Aceptación combinada fría de 191 | `c353991a99ad5f668dd376820d0350172573e27e9b6c8ee19068e7f6be6daf0b` |

`build_cerro_verified_172.py` reconstruye ambos TAR desde el repositorio. `run_cerro_pack_reports.py --cold-chain` compara la restauración 189, el control 190 y la instalación y actualización de 191 en el entorno privado. Los recibos de usuario detallados y la base se mantienen fuera del repositorio.
