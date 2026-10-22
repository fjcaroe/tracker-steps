# T103: conversión de documentos agrícolas

Estado: convertido, publicado y verificado en Desarrollo; T103 cerrado con
nota interna silenciosa 9597. El usuario eligió convertir también los registros y formularios
históricos. El destino de esta migración es **Desarrollo**; no habilita una
promoción a Cerro El Plomo ni a las otras producciones.

## Alcance comprobado

El inventario de los trece botones y de sus relaciones alcanzó 33 modelos.
Incluye pronósticos, registros y tarjas de cosecha, inspecciones, asesorías,
sus líneas, BPA, fertirriego, válvulas y maestros asociados. Los maestros
existentes se renombran sobre sus propias tablas, conservando los IDs.
No se copian documentos a tablas paralelas ni se resuelven relaciones por
coincidencias de nombres.

`step_agriculture_records` declara los modelos, campos, formularios, listas,
búsquedas y analíticas en archivos estáticos versionados. Sus generadores
son herramientas de desarrollo: el addon no crea modelos desde metadatos de
Studio en tiempo de ejecución. Los permisos se adoptan por sus referencias
originales y se conservan sus grupos. Los folios usan las secuencias existentes
desde métodos Python, retirando las automatizaciones Studio de esos documentos.

La migración cambia tablas, columnas, referencias de modelos, campos relacionados,
reglas y filtros dentro de una transacción previa a cargar el registro. El
publicador exige el mismo paquete probado, respaldo, bloqueo y ausencia de
cambios concurrentes. La comparación de preservación normaliza exclusivamente
los nombres migrados y comprueba IDs, valores anteriores, relaciones, mensajes
y adjuntos. Los campos relacionados que ya no existían en el registro original
se conservan como declaraciones inactivas de cálculo, sin inventar valores ni
exponerlos en los nuevos formularios.

Los valores históricos ausentes permanecen ausentes. En particular, el consumo
por hora conserva su obligatoriedad en el formulario sin forzar valores sobre
los documentos anteriores. La clasificación de grupo de labor sigue siendo
obligatoria en el formulario de labores; los productos que no son labores
pueden conservar su clasificación vacía, igual que antes de la conversión.

Se incorporó al repositorio el puente `step_bpa_inventory` encontrado instalado
en Desarrollo, incluyendo sus pruebas; sus movimientos, cantidades y distribución
por hectáreas se conservan al actualizar las referencias. No se reemplazan las
raíces compartidas de addons. Los accesos de T100, T101 y T102 deben seguir
funcionando después de actualizar Cosecha y sus dependencias.

## Equivalencia de estados autorizada

El usuario confirmó «Vigente» → «Validada» y aceptó «Despachada» → «Desp/Emb»,
conservando Repaletizada, Procesada y Nula. La relación operativa
`packing_tag_state_id` reutiliza los registros existentes de `step.packing.tag.state`:
V → 02, D → 05, R → 04, P → 03 y N → 10. La migración resuelve los códigos
dentro de la empresa del centro de costo; rechaza estados ausentes o ambiguos.
No crea un segundo maestro operativo ni copia registros de estados.

Los estados originales conservan sus códigos V, R, D, P y N, sus filas, sus IDs
y las relaciones de cada registro en la columna original `tag_state_id`.
La tabla preexistente `step.agriculture.harvest.tag.state` queda como histórico
de solo lectura, protegido también por métodos ORM. Los formularios presentan
el estado del maestro actual y permiten consultar la referencia original.
La relación operativa se inicializa una sola vez al agregar la columna; las
actualizaciones posteriores no reinterpretan los cambios operativos del usuario.
La publicación exige las pruebas funcionales completas del paquete final en
una copia fresca y la comparación de los datos originales.

Adjuntos, inventarios, código original recuperado, respaldos y resultados se
guardan en los artefactos privados de T103, fuera de Git. No se publican datos
de documentos ni credenciales.

## Paquete y validación

Conversión inicial: `c66f89938d8dac6d7c2acbdcf78418929d1fc1e1`.
SHA-256: `0b2a6f440350191de169af0c65c587b1177200fbae9910fd1fb978e02b16c175`.
La copia fresca `MANAGEMENT_QA_DEVELOPMENT_t103qa3` pasó 54 pruebas, sin
fallos ni errores. Se compararon los datos originales, relaciones, tablas
intermedias e históricos; la comparación resultó idéntica normalizando
solamente los nombres convertidos. La verificación efectiva comprobó los
33 modelos nativos, sus cinco vistas y los trece botones de centros de costo.
La auditoría de precisión confirmó que los dos costos relacionados con
`standard_price` conservan `Product Price` por herencia.

Las pruebas incluyen creación y reapertura de formularios, filtrado entre dos
centros de costo, permisos de un administrador agrícola, folios y cálculo de
aplicaciones, consumo de inventario y la generación de una restricción
fitosanitaria desde una aplicación real que impide aprobar la cosecha.
Se ejecutaron también las pruebas de Cosecha, BPA y presupuestos del paquete.

La revisión del navegador detectó que el despachador de botones de Odoo mezcla
nuevamente el contexto del directorio después de recibir la acción Python.
Por eso la acción declara explícitamente las banderas de creación, edición y
borrado según los ACL del modelo de destino; omitir las claves no basta para
eliminar el bloqueo del directorio. No se amplían grupos ni permisos.
Las actualizaciones posteriores reutilizan las referencias ya adoptadas y
comprueban su existencia, sin depender de los XMLID antiguos de Studio.

Paquete final con la equivalencia autorizada:
`9f7935209ff1eecd0ac44bd968cd6aa88e13975f`.
SHA-256: `a78a43f4bcaf73cc22a1212f014d0a682bfe2bfbdad17879348446da4e9e958e`.
La copia fresca `MANAGEMENT_QA_DEVELOPMENT_t103qa6` pasó **55 pruebas**, sin
fallos ni errores de pruebas. La comparación de preservación volvió a ser
idéntica. Se enlazaron las siete tarjas históricas al maestro existente,
conservando sus referencias originales y sin crear estados nuevos. Las pruebas
recorren los cinco códigos autorizados, comprueban el cambio posterior del
estado operativo conservando el original, la inmutabilidad del histórico y el
rechazo de un estado que pertenece a otra empresa.

La prueba de menús de Presupuestos se ejecuta después de cargar el registro
completo, porque consulta otras aplicaciones instaladas. Conserva todas sus
comprobaciones; no se ignoran errores de modelos ausentes ni se reduce la suite.

## Entrega comprobada

Se publicó el mismo paquete final probado en Desarrollo, usando el bloqueo
compartido y un overlay privado. Respaldo final:
`/opt/steps_backups/management_development_20261022T021446Z`.
La conversión inicial conserva además el respaldo
`/opt/steps_backups/management_development_20261022T014916Z`.
La comparación de preservación en el destino real fue idéntica y el sondeo
comprobó las versiones y rutas efectivas de los ocho addons del paquete.

En el navegador autenticado se verificaron el acceso desde Gestión y Costos,
los trece botones y sus contadores, los pronósticos filtrados y el formulario
nuevo con el centro de costo correcto. Ese formulario se descartó. Se abrieron
cosechas históricas con sus líneas, cantidades, maestros e historial; las
tarjas muestran «Validada» y la columna histórica permite consultar «Vigente».
Se restauró la preferencia inicial de columnas. También se recorrió una línea
de maquinaria de aplicación hasta su documento padre con productos e historial.
Los documentos existentes permiten edición conforme a sus permisos.

El registro de entrega comprobó que no hubiera respuestas humanas nuevas sin
leer, SLA ni automatizaciones de Helpdesk activas. La nota 9597 y el cierre en
estado Solved no generaron registros de `mail.notification` ni `mail.mail`.
