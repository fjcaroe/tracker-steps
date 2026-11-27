# Vistas y lista de materiales de Cerro El Plomo

El respaldo de noviembre de Cerro tiene 23 vistas activas distintas con ID de
Studio. En dos restauraciones privadas de ese control se ensayaron la relación
de empresa de la lista de materiales y las dos vistas contables de producto,
con el proveedor original y con Odoo 18 Community oficial. En ambos casos el
usuario interno 6 pudo crear una lista de materiales, cambiar el campo de
empresa adicional, copiar el registro y borrar ese valor. El usuario público
recibió una denegación. Las operaciones se revirtieron y conservaron las siete
listas originales, su llave foránea a empresa y los permisos.

La empresa nativa tiene valor en una de las siete listas y el campo adicional
está vacío en las siete. El addon conserva ambos campos independientes, el
identificador original del campo adicional y su política `ON DELETE SET NULL`.
El inventario no encontró ninguna vista que empleara ese campo.

## Vistas verificadas en el proveedor original

Las 23 vistas están en módulos propios. Cada módulo comprueba las identidades,
los padres, el orden de aplicación y el contenido original de sus vistas
antes de asociar el ID del paquete al registro existente. El ID de Studio
sigue resolviendo al mismo registro. La instalación no añade grupos.

| Área del paquete | Pantallas | Cantidad |
| --- | --- | ---: |
| Contabilidad de producto | Categorías de gasto y plantillas de producto | 2 |
| Empresas | Directorio, RUT y comuna | 1 |
| Agricultura | Centros analíticos, fundos y formulario de centro | 3 |
| Especies | Códigos y composición de pallets | 1 |
| Productores | Productos agrícolas y estimaciones de exportación | 2 |
| Exportación | Costos de pago y contactos | 2 |
| Presupuestos | Categorías contables, presupuesto de temporada, costos reales y resumen | 4 |
| Traslados | Variedad, lote y guía en los traslados de fruta | 1 |
| Packing | Tipos de proceso, resultados y órdenes de packing, etiquetas, recepciones y despachos | 7 |

La prueba se ejecutó con el mismo usuario interno 6 en las dos lecturas del
control nativo. Para cada una de las 23 vistas, Odoo aplicó la herencia al
renderizar la pantalla, el operador tuvo un menú del modelo y leyó un registro
existente. El recibo incluye los 23 IDs de vista y de Studio, sus padres,
grupos, prioridades, contenidos, menús y el hash de cada pantalla. Antes y
después de instalar los módulos, el recibo completo tiene el mismo SHA-256
`21808b141b7b77808b7567035c7ce10fa5be058dc2e6093cd9f5a29b4d95aadd`.

La copia de control deriva del par U40Q y conserva 1.261 filas de adjuntos.
Sus 1.009 referencias a archivos corresponden a 676 objetos distintos, con
98.438.007 bytes. Se verificaron el SHA-256 del archivo de custodia y el SHA-1
de cada objeto extraído. El nuevo respaldo de SQL usado para las dos
restauraciones privadas tiene SHA-256
`954c632423424cc31923e9ec5b8f01f5944435491cec4da11b69e8e02f1654b7`.

El cliente de Odoo cargó además las 23 listas y formularios y leyó un registro
visible desde cada pantalla, con el mismo operador. Se comprobaron los 57 usos
de campos añadidos por 19 de las vistas, incluido el campo de un movimiento
dentro de una recepción. Las otras cuatro vistas modifican atributos de campos
o de la pantalla. El recibo de lecturas conserva solo identificadores y
huellas de los valores y tiene SHA-256
`a635dbae9cbab84fa5d199a029b3e7ff7052c3905739784dfa81a04393d79038`.

## Prueba inicial en Community

Se instaló el código de 13 vistas sobre Odoo 18 Community oficial y los
proveedores libres disponibles. En 12 el operador abrió una pantalla con la
herencia original activa, un menú autorizado y registros existentes. El
resultado antes y después de adoptar las 13 conserva SHA-256
`58c963371d11b2fcfa129cc5e60931e0565861bc2840188ebbdce4ad6ddb5b0a`.
En Fundos, la regla de empresas que protege los datos necesitaba
`step.fundo.company_ids`, aportado por la aplicación agrícola multiempresa.

Los paquetes de Exportación, Especies y Packing declaran proveedores de
informes contables, exportación electrónica de Chile y Gantt. Los embarques
usan dos relaciones con borrado restringido al catálogo de puertos aduaneros
para el puerto de origen y de destino. El informe de programa de ventas
abre el Gantt de las semanas del programa. El grafo por vista distingue las
dos primeras dependencias de los modelos que también necesitan el Gantt.

## Fundos compartidos

El paquete `step_agriculture_shared_farms` contiene la relación de empresas del
fundo y los grupos de productores usados por las reglas originales. La
aplicación multiempresa depende de este paquete. En la copia Community y en
el control original quedaron idénticos 53 fundos, sus 95 asignaciones de
empresa, los 19 contactos agrupados, cuatro reglas y 15 permisos. La prueba
verificó seis identificadores históricos del modelo, sus campos y la herencia.

Con las ocho empresas autorizadas, el usuario 6 leyó los mismos 53 fundos en
los dos runtimes. Al elegir cada empresa por separado leyó 3, 41, 0, 1, 7,
12, 31 y 0 registros en las empresas 1, 2, 3, 4, 29, 30, 31 y 41. Se
denegaron la lectura directa de fundos ajenos, la eliminación de la empresa
propietaria y el ciclo de contacto productor. Las asignaciones y los grupos
permanecieron iguales después de las escrituras revertidas.

Las 13 vistas adoptadas en Community ya leen los campos de la personalización
con el usuario 6. Dos vistas adicionales de recepciones de stock conservan la
lectura de sus campos a través de su definición de origen. Para las 15, los
valores leídos fueron idénticos a los del mismo registro en el control original.

## Especies, tipos de proceso y alcance de las copias

En las dos copias las siete especies conservan sus códigos SAG y las dos
cantidades históricas de cajas por pallet. Los campos 28723 y 28724 y la
restricción 6836 mantienen sus identidades. Se rechazó un valor negativo al
escribir como usuario 6. En Tipos de proceso se conservan las seis filas, el
campo 28229 y los tres registros de selección 6034–6036. El usuario 6 cambió
y revirtió una categoría y se rechazó una opción ajena a la selección.

El control de noviembre U40Q tiene 414 módulos instalados, incluidos 140 con
licencia OEEL-1 y el paquete OPL-1 de Studio. U40B usa exclusivamente fuentes
libres para iniciar el motor oficial de Community pero conserva declaraciones
históricas. Tras instalar las primeras vistas y catálogos se observaron 432
módulos marcados como instalados, 138 OEEL-1 y uno OPL-1. Estos recuentos
describen el estado de la base en esa etapa. U40D HANDOVER y U41L Biblioteca
tenían respectivamente 144 y 145 módulos instalados, todos libres, antes de
incorporar Fundos a la biblioteca.

En el control nativo, cada una de las 23 herencias se aplica al seleccionar
una acción de menú visible para el usuario 6. Todos los campos de las 23
pantallas se describen en la respuesta del cliente. En U40B, antes de incorporar
los proveedores de los campos hermanos de especies y productos agrícolas,
se alcanzaron 19 herencias por menú, 17 lecturas de los campos añadidos por
Studio idénticas al control y 12 pantallas con todos sus campos registrados.
Las recepciones de stock permiten leer el campo original de Studio y todavía
requieren campos de sus proveedores de recepción, DTE y Calidad para abrir el
formulario completo.

La actualización de las vistas de U40B Community mantuvo iguales 61.896
identificadores que existían en esa copia antes de actualizar. La guarda
verificó la fila, el módulo, el nombre, el modelo y el registro de destino.

Se habilitaron después los proveedores ya declarados de datos BPA de producto
y código arancelario de especie, con las mismas versiones del respaldo. Con
ellos el cliente leyó todos los campos de un registro existente en 14 pantallas
del U40B híbrido. En Traslados faltan los dos campos almacenados de
`l10n_cl_edi_stock` y el indicador calculado `quality_check_todo` de
`quality_control`. En Tarjas, el proveedor de origen también protege las
fechas de cosecha de las tarjas validadas; en Costos de exportación impide
cambiar una tarifa usada en un programa valorizado.

En la actualización nativa completa la guarda detectó que el cargador iba a
retirar el ID de modelo de Tipos de proceso de su antiguo módulo. El código de
cada antiguo dueño sigue registrando su modelo al actualizar. Al repetir la
actualización se conservaron los 60.749 identificadores de la copia nativa y
se verificaron de nuevo sus 23 vistas y rutas.

## Directorio en una copia con registro íntegramente libre

U41L instaló el núcleo agrícola, el directorio y Fundos compartidos sobre la
restauración Community de Cerro. Conservó los 53 fundos, 95 vínculos con
empresas, 19 contactos agrupados, cuatro reglas y quince permisos. La relación
original del productor con sus fundos conserva los campos 26219 y 26726, el
inverso `step.fundo.partner_id` y la regla de empresa 543. La consulta de
contactos de la biblioteca funcionó con los 15 usuarios originales en 65
contextos bajo este registro.

U42C deriva de U41L y comenzó con 148 módulos instalados, todos registrados
con licencia libre, y cero transiciones pendientes. La copia física verificó
677 objetos y 98.447.031 bytes para 1.010 referencias en 1.262 filas de
adjuntos. U42C utiliza la misma biblioteca 18.0.1.0.4 que recibió de U41L al
clonarse. El ensayo independiente U42E recibió la biblioteca 18.0.1.0.5,
publicada después del primer clon.

Un primer ensayo que incluía Packing y Costos intentó cambiar la categoría
histórica de una línea de recepción al maestro retirado. También retiró la
restricción de estimación por centro y cuartel. Se restituyó en U41L la
restricción original de tres columnas. La comparación posterior con U40D
confirmó las 8.370 restricciones con iguales definiciones y validación, y
las 14 líneas de estimación con idénticos valores. U41L añadió cuatro
restricciones para sus nuevos proveedores.

La restauración nativa U42N resolvió la validación de la vista 4637 en el
formulario de Temporadas 4159. El núcleo agrícola 18.0.1.1.4 extiende los
18 maestros ya registrados por el proveedor original de personal y el
catálogo 18.0.1.1.1 se carga después de ambos. La instalación y la
actualización ordinarias finalizaron en la copia restaurada desde U40Q.

El operador 6 obtuvo las 23 rutas originales y las 23 lecturas completas del
control. Las filas de las 23 vistas, incluidos los seis historiales sensibles,
coincidieron en todas sus columnas con el origen. Se protegieron 60.691
identificadores externos. La acción 1082 conservó las vinculaciones 836 y
837. Las cuatro relaciones de categoría y las 14 estimaciones conservaron
sus datos. Para Temporadas se comprobó el campo 27057, las relaciones de
las tres temporadas y el acceso bajo las ocho empresas. En la regla 553
cambió la fecha de escritura durante la actualización. El resto de sus
columnas coincidió con el origen.

El registro **nativo** tenía 433 módulos instalados, 140 Enterprise y
uno OPL, con cero transiciones pendientes. El recibo privado
`U42N/verified-histories.json` tiene SHA-256
`54ef89dba13ea308b8beb55e706f40ef3cde1c79391ec8b9ea55552b42446cd7`.

En U42C el usuario 6 obtuvo los mismos 53 fundos y los mismos registros al
abrir cada empresa. También coincidieron el inverso de productores y todas
las lecturas de contactos en los ocho contextos. La acción original 1254
permanece accesible por los menús 849, 890, 918, 945, 1082 y 1148. La
regresión de identificadores conservó el nombre transferido, limpió una
referencia de prueba obsoleta y rechazó dos nombres que pretendían señalar
registros distintos. Los menús homónimos de Especies de las dos aplicaciones
mantienen sus registros independientes.

## Pantallas, listas de materiales y estimaciones en Community estricto

| Copia | Módulos instalados | OEEL / no libres / pendientes | Operación comprobada |
| --- | ---: | --- | --- |
| U42C | 160 | 0 / 0 / 0 | Fundos, productos, empresas, tipos de proceso y especies |
| U42B | 161 | 0 / 0 / 0 | Empresa principal y empresa adicional de la lista de materiales |
| U42E, estimador | 152 | 0 / 0 / 0 | Lectura por cuartel y centros de costo |
| U42E, Packing y Productores | 171 | 0 / 0 / 0 | Categorías históricas, traslados, productores y centros analíticos |

En U42C se recorrieron las 23 vistas originales con el usuario 6. Se llegó
a 15 desde un menú y acción originales. En ocho coincidieron el registro,
los campos de Studio y los valores leídos. Seis devolvieron idéntico registro
completo, incluidos los valores relacionales del cliente web: las dos listas
de Productos, Empresas, Fundos, Tipos de proceso y Especies. El usuario
también abrió los seis tipos de proceso y comprobó que el selector rechaza
una categoría inválida. El recibo privado
`U42C/strict-with-species-comparison.json` tiene SHA-256
`3113114534d540bbfd3f8f8e286923213fae1386c2f8ec243fe5944f099c4f42`.

U42B se restauró lógicamente desde U42C. Antes de crear por primera vez la
guarda de fila de campos, se adoptó `mrp.bom.x_studio_compaia` conservando su
ID 30516 y la FK original a empresas. La única variación en las 27.963 filas
de campos fue el paso de su estado manual a base. Los 62.099 identificadores
previos y las siete listas permanecieron iguales. Se creó un identificador
adicional del nuevo proveedor. Se verificaron los 23 triggers del ancla y
la prohibición de revertir el estado. El usuario 6 creó una lista, copió la
empresa adicional y la vació conservando la principal. Se rechazó la
escritura del usuario público y se revirtió el ensayo. Los recibos privados
son `U42B/adopted-receipt.json` y `U42B/qualified-bom.json`.

U42E incorporó la declaración original de cuartel y la unicidad de
estimación, centro y cuartel desde el primer registro del proveedor de
costos. Reutilizó las dos vinculaciones existentes de la acción 1082: la
lista 836 apunta a la vista 4174 y el formulario 837 a la vista 4173.
El usuario 6 leyó las 14 líneas de estimación y sus 11 cuarteles. Coincidieron
con el origen las 14 filas completas, el campo 31444, el índice parcial y
la restricción validada. Los recibos privados son
`U42E/estimate-result.json` y `U42E/estimate-user.log`.


En U42E los proveedores completos de Packing y Productores registraron desde
su primera carga el mismo catálogo de categorías de fruta que conserva el
origen. Las cuatro claves foráneas y sus registros de campo coincidieron
con Cerro después de cada instalación. El usuario de inventario leyó las
184 líneas de tarja y las 55 recepciones vinculadas a una categoría. El campo
de clase en las recepciones conservó sus valores vacíos. La integración con
el centro analítico cargó su puente original de costos y productores.

Con 171 módulos, el usuario 6 alcanzó 17 de las 23 vistas desde sus menús y
acciones originales. En 14 coincidieron sus campos de Studio, el registro y
el valor leído. En diez coincidió la fila completa del cliente web. Se
preservaron las 14 estimaciones, sus 11 cuarteles y su unicidad. El recibo
privado `U42E/packing-reference-comparison.json` tiene SHA-256
`3b969a2d6c3d2f5d91d52c5dfae3608f5f6ca4f66e5ebbd29d964c10637fc764`.
Se reproduce con `tools/community/compare_cerro_studio_receipts.py` usando
las dos referencias nativas y la lectura real `U42E/packing-studio.log`.


La matriz de fallos identifica el primer dato que interrumpe la lectura
integral de cada pantalla del usuario. Sus nombres de módulo se obtuvieron
de los registros originales de U40Q.

| Vistas | Primer proveedor necesario |
| --- | --- |
| 5293 | Registros agrícolas, campo `agriculture_can_cost` |
| 5312, 5317, 5318 | Diseño presupuestario, versión y dos informes |
| 5193 | Inventario de Packing, estado de la tarja |
| 5189, 5194 | Operaciones de Packing, modelo de producción |
| 5267 | Directorio de tipos de despacho, su alcance por empresa y su destinatario |
| 4845, 5192 | Exportaciones, concepto de pago y receptor |
| 5187, 5244 | Calidad, `stock.picking.quality_check_todo` |
| 5245 | Localización chilena de stock, `stock.picking.l10n_cl_sii_send_file` |

El archivo privado `U42E/packing-view-owners.json` tiene SHA-256
`2a374b6dbb921e88fa22d1e4ed94edcc43235b3db48fa0a57bf319d00d591c69`.


## Instalación fría, actualización y presupuestos

U42H se creó por restauración lógica desde la biblioteca U41L. En ese
origen, las 23 vistas tienen exactamente las mismas filas que la copia de
custodia nativa U40Q. Se registró el propietario de la lista de materiales
antes de crear la primera guarda de campos. Se instalaron la adopción de
Studio y los proveedores de Packing, estimación, Fundos, Especies, empresas,
productos y procesos, y se actualizaron todos de nuevo.

Las 23 filas, con todas sus columnas y sus arquitecturas anteriores, quedaron
idénticas al origen en cada fase. La huella conjunta fue
`a0e0ae80a5c095ae1ca7beb27ea16e1d3670ccba563309dc5287f4e0a34c2431`.
Se conservaron 62.030 identificadores externos y las 23 guardas. El
resultado de la base integrada fue 172 módulos libres, cero pendientes,
17 rutas, 14 lecturas de Studio y diez filas web completas de 23.
El recibo `U42H/qualified-combined.json` tiene SHA-256
`adddcf0dde7d30462b88e2caa85bae622253a8298d32c780234c607b7d8d7656`.
En U42B se ejercitó además la creación y copia de una lista de materiales
con sus dos empresas y el rechazo al usuario público. El recibo compuesto
`U42B/combined-packing-verified.json` tiene SHA-256
`b45c1483a169adf2fd58f9dd729c57f0597bd89da941163cdf7f18d76e146f00`.

En U42E los paquetes de Operaciones, Tarjas, Cosecha y Formatos conservaron
la identidad y la bandera de actualización de los metadatos originales.
Se instaló Diseño Presupuestario con los registros agrícolas y los
proveedores reales de cosecha, maquinaria y movilización. Las 14
estimaciones y los cuatro enlaces de categoría siguieron coincidiendo con
el control. La misma prueba del usuario 6 encontró 19 rutas coincidentes,
17 lecturas de Studio y 14 filas completas. El registro terminó con 184
módulos, cero licencias no libres y cero transiciones pendientes.
`U42E/budget-reference-comparison.json` tiene SHA-256
`e48b6ce80ea45194bb0615e6957ab2dd0739ba2f4e443f213f68f16e5642ab56`.
