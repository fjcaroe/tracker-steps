# Recuperación del CRM de Steps

Se tomó una copia de la selección Community de 157 módulos de Steps una vez
comprobada su conservación contra el respaldo original de `karo_consultorias`.
Se sellaron el SQL, el árbol físico del filestore, el motor Community y los
proveedores que realmente usaba Odoo. Los 157 proveedores tienen licencia
LGPL-3. Sus versiones coinciden con la base y con sus manifiestos.

| Comprobación al restaurar | Resultado |
| --- | ---: |
| Tablas y filas | 1.112 tablas y 163.133 filas |
| Secuencias, incluidos valor actual e indicador de primer uso | 804 |
| Columnas y restricciones | 11.939 columnas y 5.650 restricciones |
| Objetos de filestore referenciados | 1.744 |
| Archivos del motor y proveedores efectivos | 20.688 |
| Arranques independientes desde el paquete | 2 |

El proceso de arranque solo accedió al código y a los archivos restaurados.
Las dos veces el vendedor original abrió la acción CRM del menú 340 y tuvo
acceso a las mismas 1.640 oportunidades. Coincidieron las 72 propiedades de
los nueve negocios asignados. El vendedor leyó doce adjuntos de oportunidades
y doce adjuntos de menús y vistas. El usuario público recibió la denegación
de los doce archivos de oportunidades.

Se contrastaron todas las filas, contadores, propietarios, permisos y
definiciones antes y después de los dos arranques. Se cotejó también el
esquema del archivo SQL con el de las dos bases. La captura, la restauración
y el cotejo físico del filestore usaron el mismo bloqueo operativo.

La estación de trabajo recibió los trece archivos del respaldo y comprobó
cada uno contra el manifiesto del servidor. Volvió a verificar los 20.688
archivos dentro del paquete de código y los 1.744 objetos del filestore.
El esquema tenía 22 vistas y 2.409 índices. El manifiesto de custodia
tiene SHA-256 `0b1555ee825bbff3263bbd557a78c6cc6944051fa26cb9a4e3648cf83acc08d2`.
El recibo privado quedó en
`~/.codex/local-artifacts/community-resume-20261125/U40/steps-crm-cold/offline-verification.json`.

El SQL recuperado tiene SHA-256
`9353826752eaacc7e01f3ec437a5fd9ea6c5ed4ce99e1852eb2b33d56149d41f`.
El paquete del motor tiene SHA-256
`bdd4240638ec6770800474d53d3315929e6fa9742a48e5c70c9c8181cb7c94bb`.
Este respaldo corresponde al perfil de CRM. La fuente nativa de Steps
tenía 310 módulos activos. Los demás flujos conservan sus propias pruebas
de aceptación.

## Presupuestos en el mismo respaldo

Una segunda captura incorporó la configuración de ventas probada sobre la
base original. Conservó las 163.133 filas y los 804 contadores antes de que
se usara la copia. En los dos arranques desde el nuevo paquete, el mismo
vendedor abrió la acción 526 desde una oportunidad y el formulario inicializó
el cliente y la oportunidad correctos. Pudo consultar los cuatro documentos
de venta históricos. La prueba del alta y reapertura con importes está en
[CRM y ventas de Steps](COMMUNITY_STEPS_CRM.md).

El SHA-256 del SQL de esta versión fue
`0d36901de7be4bf0c20e9b5311c101bb564dc445cb0b8d9bce90ccff8cc7f12d`.
La estación comprobó los 13 componentes incluidos en el manifiesto
`5de21f357e0c270d33cdbb23268c343ba2643a2be5ca44992210831132b22f79`.
El recibo quedó en `U40/steps-crm-quote-cold/offline-verification.json`.
