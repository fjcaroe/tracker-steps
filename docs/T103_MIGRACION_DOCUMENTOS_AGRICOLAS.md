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

## Estados originales

Los estados de tarja de cosecha conservan sus códigos V, R, D, P y N, sus filas,
sus IDs y las relaciones de cada registro. Su tabla preexistente se convierte
en `step.agriculture.harvest.tag.state`, sin copiarla ni crear otro maestro.
El ciclo de Packing usa códigos diferentes y no se reinterpreta el significado
de «Vigente» al convertir los documentos. La equivalencia consultada al usuario
queda como una posible unificación posterior, ajena a la entrega de conversión.
La publicación exige las pruebas funcionales completas del paquete final en
una copia fresca y la comparación de los datos originales.

Adjuntos, inventarios, código original recuperado, respaldos y resultados se
guardan en los artefactos privados de T103, fuera de Git. No se publican datos
de documentos ni credenciales.
