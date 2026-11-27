# Contratos de la copia Community de Cerro El Plomo

## U43Z con 187 módulos

El usuario de inventario 6 perdió acceso a tres categorías de fruta al trabajar por separado en cada una de las empresas 29, 30 y 31. Perdió acceso a seis clases de fruta en la empresa 29. La consulta conjunta de las ocho empresas ocultó el problema. La lectura de los dos catálogos de calibres devolvió los registros originales en las nueve configuraciones. El perfil de 187 módulos queda limitado a los circuitos ya probados de Presupuestos, Fletes y Contactos.

La prueba ejecutó las reglas de registro de Odoo sobre cada uno de los cuatro modelos con los permisos reales del usuario. Las cuatro reglas 446–449 usaban la empresa única de la ficha en la semilla libre U41L y en U43Z. El control nativo usa las empresas asignadas a cada registro mediante los cuatro Many2many. Las 36 particiones de IDs dieron SHA-256 `8dc954c8279223ce3585dce59a38abf10f97c7ad6b8cdb5397de5296c64df689` en el control nativo y `fd8a8944164f482ccfad0288df1aec6a39adb15d4cd52a89ad7c2120224f5013` en la candidata.

### Estructura y permisos

La comparación abarca la copia nativa bajo custodia U40Q (414 módulos instalados y 140 Enterprise), la semilla libre U41L (148), la etapa U42H (172) y la final U43Z (187). Las tres copias libres tienen cero módulos Enterprise instalados. El control funcional de referencia fue U42N, que ejecuta los cuatro dominios de U40Q.

| Objeto original de U40Q | Presentes en U43Z | Diferencia observada |
|---|---:|---|
| Columnas | 17.619/17.619 | 29 obligatorias relajadas, una opcional pasó a obligatoria y una cambió de tipo |
| Restricciones SQL | 8.320/8.320 | Tres acciones ante borrado distintas y cuatro expresiones CHECK equivalentes |
| Índices | 3.301/3.301 | Definiciones conservadas |
| Vistas SQL | 29/29 | Definiciones idénticas |
| Secuencias | 1.242/1.242 | Definiciones idénticas |
| ACL de Odoo | 2.372/2.372 | Cinco altas y cero modificaciones a las originales |
| Reglas de Odoo | 654/654 | Cuatro dominios distintos y dos altas |
| Asignaciones usuario/grupo, herencias y grupos de vistas | 1.959, 284 y 36 | Todas presentes e iguales |

El propietario físico de 2.785 relaciones, 3.301 índices y 4.328 tipos pasó del rol nativo de Cerro al rol de la copia. El rol se sustituyó también en sus concesiones y se usó el espacio de almacenamiento privado del ensayo. La comparación no encontró otra diferencia de privilegios SQL. Las relaciones originales entre grupos y menús subsisten y U43Z incorporó doce asociaciones adicionales.

Ninguna de las 31 columnas que habían perdido obligatoriedad en U41L contenía valores NULL en ninguna de las cuatro copias. U43Z ya restituyó la obligatoriedad de `res_company.harvest_hours_per_day` y `step_management_budget_import.target_budget_type`. La obligación añadida en `product_pricelist_item.uom_id` difiere de U40Q.

| Relación | Borrado en U40Q | Borrado en U43Z | Filas con referencia / padres usados |
|---|---|---|---:|
| `account_move_line.account_id` | CASCADE | RESTRICT | 2.012 / 109 |
| `purchase_order_line.product_uom` | SET NULL | RESTRICT | 29 / 2 |
| `product_pricelist_item.uom_id` | SET NULL | RESTRICT | 4 / 1 |

Las tres diferencias también aparecen en los atributos originales del ORM. Cuatro CHECK contables difieren sólo en la colocación del cast de dos constantes de texto. PostgreSQL comparó ambos arrays con IS NOT DISTINCT FROM y se cotejó el resto de cada predicado completo. Las seis fichas de tipo de paquete conservan sus valores de peso, incluidas dos taras informadas. El almacenamiento `numeric` nativo cambió a `double precision` en U42H.

Desde U41L hasta U43Z se conservaron las 17.726 columnas, 8.374 restricciones, 3.316 índices, 29 vistas y 1.247 secuencias de la semilla. En seis columnas de la tabla añadida de permisos de la biblioteca cambió la posición física tras la restauración lógica. U43Z añadió la tabla privada de resguardo, una PK y dos índices. Los 23 disparadores originales de la semilla se conservaron.

### Reproducción privada

`tools/community/audit_cerro_original_schema.py` captura el catálogo en transacciones repetibles de lectura y conserva diferencias por objeto y atributo. `check_cerro_schema_counterexamples.py` ejecuta los controles SQL y llama a `probe_cerro_fruit_schema.py` bajo ambos motores. Los resultados detallados se guardan fuera de Git. La auditoría `schema-v2.json` tiene SHA-256 `5591e7ba4330db5dec7e1349f72f53e9e012f94ac88840d2b7901cc0248504df` y el resultado de acceso y predicados `schema-counterexamples.json` tiene SHA-256 `6ef1b1cd7f5c489c7571dfe288aad9619207e0ae911050d360d0724c68792efa`.
