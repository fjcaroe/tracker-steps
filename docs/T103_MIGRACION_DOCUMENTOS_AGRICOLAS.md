# T103: conversión de documentos agrícolas

Estado: implementación y validación en curso; sin publicación ni cierre del
ticket. El usuario eligió convertir también los registros y formularios
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

Paquete inmutable: `c66f89938d8dac6d7c2acbdcf78418929d1fc1e1`.
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
