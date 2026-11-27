# CRM de Steps en Odoo Community

Se restauró el respaldo de `karo_consultorias` en dos bases privadas. La
referencia nativa tenía 310 módulos instalados, entre ellos 123 Enterprise.
En la candidata se habilitaron 157 módulos de licencia libre. Para cada uno
se comprobó la versión registrada en Steps, la licencia, las dependencias
de la base y del manifiesto, la ruta que resolvió Odoo y la ruta del código
que cargó Python. Los 157 manifiestos efectivos coincidieron con el
inventario seleccionado.

Ambas copias recibieron los 1.744 archivos referenciados por los adjuntos
del respaldo. El vendedor original abrió CRM desde el menú 340. Su acción
de servidor 488 devolvió la acción 505 y el formulario 1484. El ensayo usó
su cuenta habitual y su compañía original.

| Comprobación del vendedor | Nativa | Community |
| --- | ---: | ---: |
| Oportunidades que puede consultar, incluidas archivadas | 1.640 | 1.640 |
| Oportunidades asignadas a su cuenta | 9 | 9 |
| Contactos que puede consultar, incluidos archivados | 1.586 | 1.586 |
| Nombres de campos del formulario de oportunidad | 71 | 71 |
| Propiedades leídas por oportunidad, incluida su identidad | 72 | 72 |

Las identidades de las oportunidades y los contactos coincidieron. En los
nueve negocios asignados se compararon los valores devueltos por la lectura
web del formulario, campo por campo. Coincidieron las 72 propiedades, los
valores de sus relaciones y el orden de los registros.

En cada copia el vendedor creó una oportunidad desde el formulario original,
eligió un contacto existente, avanzó a la etapa 2 y usó el botón para marcarla
como ganada. Ambas terminaron en la etapa 4 con probabilidad del 100 %.
Se revirtió la prueba y se comprobó que la oportunidad de ensayo había
desaparecido. El alta consumió un valor en dos de los 804 contadores de cada
copia, el de oportunidades y el de disparadores del planificador. Se
conservaron esos avances y se contrastaron las filas de CRM y permisos
antes y después del ensayo.

El vendedor consultó también los cuatro documentos históricos de ventas
(tres pedidos confirmados y un presupuesto en borrador). Coincidieron sus
cuatro líneas, clientes, productos, impuestos, tarifas, cantidades e importes.
Dos oportunidades daban acceso a los tres pedidos vinculados. Desde una
oportunidad propia, la acción 526 abrió el formulario 1384 de presupuesto
con los mismos valores iniciales y los mismos 120 nombres de campo.

De los 447 adjuntos con archivo y modelo de oportunidad, 238 apuntaban a
209 oportunidades existentes. El vendedor podía consultar los 238, el usuario
público tenía denegados los 238 y doce archivos leídos por el vendedor
coincidieron en tamaño y contenido. Los otros 209 adjuntos ya carecían de
una oportunidad asignada en el original y se conservaron en la copia.

La primera prueba de alta de un presupuesto vinculó el cliente, producto,
tarifa e impuestos en la referencia nativa. Al inicializar el formulario de
alta, la candidata de 157 módulos conservaba una vista original con dos
campos sin proveedor activo, `spreadsheet_template_id` y `spreadsheet_id`.
La vista de oportunidad y la lectura de pedidos históricos funcionaron en
esta misma candidata. Steps tenía una plantilla de cotización, cero hojas
de venta guardadas y cero plantillas con hoja asignada.

Una segunda instalación de la selección de 157 módulos sobre el SQL
original conservó las 163.133 filas de 1.112 tablas y los valores de los
804 contadores antes de abrir Odoo. La comparación de cada fila encontró
únicamente el cambio esperado de estado en los 153 módulos excluidos. Se
conservaron 5.650 restricciones, 11.939 columnas, propietarios y permisos
de 1.916 tablas y secuencias. Los 1.744 objetos referenciados por los
adjuntos se recuperaron con su tamaño y contenido originales.

El inventario del producto conserva 153 módulos instalados en la referencia
nativa que este perfil deja fuera. Entre ellos se encuentran proveedores
de soporte, aplicaciones propias y módulos Enterprise. El seguimiento de
los flujos de transporte y del resto de Steps continúa por separado.

El recibo privado de la pareja U42C y las pruebas de lectura se guardan en
`~/.codex/local-artifacts/community-resume-20261125/U40/`. La huella SHA-256
de los manifiestos admitidos es
`0146e9a78d75ed0b33c943505cc3c1a3026f7fd15d2a5ec0c6198087465cd210`.
