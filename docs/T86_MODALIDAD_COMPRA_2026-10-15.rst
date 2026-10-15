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

Publicación y cierre verificados
-------------------------------

Publicado en Desarrollo y Cerro El Plomo el 15 de octubre de 2026:
step_producer_purchase_mode 18.0.1.0.0. Paquete del commit
ed9a1d61a574a92c74eed045af3fb8172d78e831, SHA-256
655699173aad5f93e97c5849213cf1d279c1e1d143060120b569df919b26fcac.
El mismo archivo pasó cuatro pruebas en cada copia (ocho en total), sin
fallos ni errores, además de comparación de preservación y sonda funcional
posterior en cada destino con reversión de los registros de prueba.

Copias de validación: MANAGEMENT_QA_DEVELOPMENT_t86mode_a_dev y
MANAGEMENT_QA_CERRO_t86mode_a_cerro. Respaldos previos:
/opt/steps_backups/management_development_20261015T153745Z y
/opt/steps_backups/management_cerro_20261015T153942Z. Los dos registros de
publicación contienen MANAGEMENT_DEPLOY_OK y MANAGEMENT_VERIFY_OK.

Revisión visual por HTTPS en los dos destinos: menú Productores,
encabezados nativos de contrato y estimación, opciones y explicación de
modalidad, filtros y agrupación de informes. Los formularios nuevos se
descartaron sin guardar documentos ficticios. Los históricos aparecen
sin definir y conservan cantidades, importes y auditoría.

Evidencia privada en ~/.codex/local-artifacts/t86-contract-20261015:
seis capturas, visual-review.json con sus huellas, certificados QA y logs
de publicación vinculados al paquete. Ticket ID 86 cerrado como resuelto
tras comprobar ausencia de respuestas humanas posteriores al requisito;
nota interna 9453, sin notificaciones ni destinatarios externos.
