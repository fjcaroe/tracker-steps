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
