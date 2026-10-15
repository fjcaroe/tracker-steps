T86 Contrato de productores y modalidad de compra
================================================

Alcance
-------

Ticket Helpdesk ID 86, cuyo título vigente es «T86 Contrato de productores,
modalidad de compra». No confundir con el antiguo título T86 de la nota de
venta, ID 85, ahora renumerado T85 y ya resuelto. Requerimiento humano 9452
y adjunto 3351, revisados el 15 de octubre de 2026.

La selección Modalidad de compra ofrece A firme y Consignación en el
encabezado de los contratos y estimaciones existentes. El campo incluye
la definición del adjunto y una explicación visible de la opción elegida:
A firme tiene precio final sin liquidación; Consignación tiene precio
referencial y determina el final según la venta en Liquidación de productor.

El campo no crea liquidaciones, asientos ni precios automáticamente. El
ciclo existente de liquidación de productor se conserva; el adjunto pide
clasificar documentos y agregar la dimensión a informes, sin especificar
una nueva asociación de contratos con tarjas o una nueva fórmula de retorno.

Los informes existentes de estimaciones de cosecha y contratos productores
muestran la modalidad, permiten buscar, filtrar las dos opciones o Sin
modalidad y agrupar, incluso en la tabla dinámica. Las proyecciones SQL
reutilizan la consulta nativa, conservando IDs, cantidades y valorizaciones.
No se crean tablas de documentos ni maestros paralelos ni objetos Studio.

Preservación
------------

No se supone una modalidad para registros anteriores ni para documentos
nuevos. El operador la elige explícitamente. Se permite completar la modalidad
vacía de un histórico sin recalcularlo; para cambiar una elección ya registrada
en un contrato confirmado o estimación vigente se usa la revisión nativa.
Las versiones nuevas heredan la modalidad y pueden cambiarla en borrador.

El publicador conserva todas las columnas anteriores, incluidos importes,
filas y auditoría; solo normaliza nulos al comparar las dos tablas que reciben
el campo nuevo. Se usa overlay privado, copia nueva por destino, respaldo,
exclusión compartida y el mismo paquete probado. Desarrollo es el único QA
público; la copia de Cerro valida compatibilidad con su producción.

Verificación
------------

El módulo incorpora cuatro pruebas funcionales: selección y agrupación en
contratos, selección y agrupación en estimaciones, versiones, vistas/menús
efectivos, permisos por empresa y clasificación histórica sin revalorizar.
La sonda posterior ejecuta el mismo flujo en el destino con reversión.

Estado de publicación: pendiente de completar pruebas y revisión visual.
