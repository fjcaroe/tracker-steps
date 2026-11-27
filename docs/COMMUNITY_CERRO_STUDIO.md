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
