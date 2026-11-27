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

El propietario físico de 2.785 relaciones, 3.301 índices y 4.328 tipos pasó del rol nativo de Cerro al rol de la copia. El rol se sustituyó también en sus concesiones y se usó el espacio de almacenamiento privado del ensayo. Los demás privilegios SQL coinciden con el origen. Las relaciones originales entre grupos y menús subsisten y U43Z incorporó doce asociaciones adicionales.

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

## Corrección en una copia nueva con 188 módulos

El proveedor `step_cerro_catalog_contracts` recupera las empresas de las cuatro fichas de fruta mediante sus tablas Many2many originales y vuelve a usar las reglas 446–449. La edición comprueba los documentos que usan estas asignaciones mediante los campos y claves foráneas originales, incluso si el proveedor del documento todavía queda fuera del registro de esta copia.

El mismo proveedor restituye la precisión decimal de la tara y los tres atributos de borrado de los campos Odoo. Al instalarlo, el propio ORM crea los FK correspondientes. Una transacción posterior restituye los 29 NOT NULL a partir del catálogo nativo. Cada columna debe tener el tipo y valor por defecto SQL de origen y cero NULL existentes. La operación sólo cambia metadatos. Durante la actualización conjunta de los catálogos y la biblioteca documental, el cargador comprueba por columna el tipo, ID del campo y alias originales antes de conservar la restricción. Los campos de aplicaciones excluidas siguen sujetos a su contrato de almacenamiento. El alta de empresas, cuentas, usuarios y otros documentos que requieren inicialización propia de esas aplicaciones queda fuera de los circuitos ensayados.

El paquete `18.0.1.0.2` contiene nueve archivos y se reconstruye con `tools/community/build_cerro_verified_172.py --source . --profile contracts --output <archivo-nuevo>`. Su SHA-256 es `c29cb57fd3555b1e482522077eba2bed54e4a1bce727b4e7667ba923757c5d00`. Los programas `check_cerro_catalog_contracts.py`, `verify_cerro_catalog_contracts.py` y `check_cerro_catalog_forms.py` requieren el perfil privado y los recibos de U43Z.

En U44M se instaló ese mismo archivo desde una copia nueva de U43Z, se actualizaron el proveedor y la biblioteca, y se volvió a iniciar Odoo. La comparación posterior encontró las 17.619 columnas originales con tipo, obligatoriedad y valor por defecto idénticos. Las 8.320 restricciones originales conservaron su semántica, incluidas sus acciones de borrado. Las 29 vistas SQL, los 3.301 índices y las 1.242 secuencias originales conservaron sus definiciones. Las 654 reglas, 2.372 ACL y las asociaciones originales de grupos, usuarios, vistas y menús conservaron su contenido. El emparejamiento de propietarios entre la base nativa y la copia privada sigue siendo el documentado para U43Z.

La actualización oficial intentó relajar los 29 campos y comprobó las 29 identidades antes de conservarlos. Los cuatro catálogos mantienen sus 33 fichas y 48 asignaciones originales. Se compararon las filas completas y las seis fichas de tipo de paquete. En los nueve contextos del usuario 6 coincidieron las 36 lecturas. También coincidieron 48 intentos de retirar asignaciones. Hubo ocho retiros autorizados, 34 rechazos por consistencia y seis por permisos. El usuario creó y compartió categoría, clase, grupo y calibre en una transacción de prueba. Los nueve contextos de Contactos y los controles de guardado y rechazo coincidieron con Cerro.

El resultado funcional y de estructura `accepted-contracts.json` tiene SHA-256 `8cf384f8a096ad78dbb547147cd911d72d8ebbca9d9f0d7940fb3cc6a76121de`. El catálogo de diferencias `schema-final.json` tiene SHA-256 `3c8bcada390809d25cf577411d748692e7aaeeab8a5c156f3a79987bad17ef57`.

Se volvieron a abrir las 23 vistas originales tras el segundo arranque. Se conservaron las 23 filas históricas completas, las 20 rutas de menú de U43Z, las 19 lecturas exactas de los campos originales de Studio y las 15 fichas con lectura completa idéntica. El recibo `accepted-views.json` tiene SHA-256 `f477a8b34f8a3f5db09c12ffc8d553fe3b3517412f2975a3fe9716cff44055ec`.
