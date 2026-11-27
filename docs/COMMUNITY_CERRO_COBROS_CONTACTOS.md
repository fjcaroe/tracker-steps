# Seguimiento de cobros en la ficha de Contactos de Cerro

La ficha original 5192 recupera los saldos por cobrar, los vencidos, el estado, la etapa, el próximo recordatorio, su modalidad y su responsable. El usuario puede consultar los saldos, filtrar los contactos por estado o etapa y guardar los ajustes de la ficha. En la copia de 193 módulos libres se abren las 23 rutas originales, se leen las 23 personalizaciones y coinciden los registros completos de 22 pantallas. La ficha restante es la recepción 5245, cuyo ingreso manual y devolución de envases se verificaron en el perfil de 192 módulos.

## Pruebas con el registro original

El control proviene de una copia privada de Cerro del 27 de noviembre de 2026. Los 15 usuarios internos se probaron en 64 combinaciones de usuario y empresas. En 57 combinaciones se compararon las siete columnas de todos los contactos visibles, para un total de 12.487 lecturas y 75 observaciones con saldo distinto de cero. Las otras siete combinaciones devolvieron la misma denegación que el original. Los importes, los contactos y las filas contables individuales permanecen en la evidencia privada.

| Operación | Comprobación |
| --- | --- |
| Importes y vencimientos | Los resultados coincidieron con el registro original y con un cálculo independiente sobre sus apuntes publicados sin conciliar. Se contrastaron vencimiento, fecha contable cuando falta el vencimiento, pagos, abonos y saldo agregado. |
| Cambio de etapa | En 18 casos de fecha, 16 de saldos combinados y 14 de cambios o ámbitos de empresa se reprodujeron los mismos resultados. Se comprobaron los umbrales originales de 15 y 30 días y el efecto de subir, bajar y limpiar la etapa sobre apuntes contables balanceados. |
| Búsquedas | Se compararon 12 filtros en cuatro solicitudes independientes, una por ámbito de empresa. Coincidieron las capacidades de búsqueda y los 48 conjuntos completos de identificadores. |
| Ajustes del contacto | Se creó una ficha, se guardaron responsable, modalidad y próxima fecha mediante el formulario y se cambiaron fechas por separado en dos empresas. Se verificaron la lectura de los 15 operadores, la limpieza de la primera fecha y la conservación de la segunda. |
| Recepciones y existencias | La copia volvió a reproducir el ingreso de 612 kg, su lote y propietario, sus 180 envases y el traslado de devolución en borrador. El inventario de las 58 recepciones y sus movimientos coincidió en los contextos originales. |

El paquete agrega un proveedor LGPL que usa las identidades y las tablas originales de Odoo. En particular, conserva la relación de cada apunte con su etapa, el responsable por empresa y el grupo contable exigido para leer los saldos. Las dos etapas existentes se consultan desde la ficha. La creación o edición del catálogo de etapas y el envío de recordatorios por correo, SMS o actividades quedan fuera de este perfil.

## Conservación y reproducción

La instalación se ensayó en dos copias independientes. La segunda se comprobó contra el perfil 192 antes de instalar. La primera instalación, la actualización y la comparación tras revertir las operaciones devolvieron la misma huella de catálogo. Se verificaron los 677 archivos, las 1.247 secuencias, las 17.731 columnas, las 8.375 restricciones, los 3.318 índices, las 29 vistas SQL, los 2.377 permisos y las 656 reglas. Coincidieron los 26 modelos afectados con sus 3.009 campos y sus 1.353 opciones. Se compararon íntegramente 790 movimientos contables, 2.012 apuntes, las conciliaciones y las demás tablas de negocio alcanzadas.

| Evidencia | SHA-256 |
| --- | --- |
| Paquete de cuatro archivos, perfil `contact_followup` de `tools/community/build_cerro_verified_172.py` | `dad06f9ee868d78aeea53dc572492b278ac0f55ff36bc9f40a61b9b1a5a5e8c6` |
| Lectura de los contactos y permisos en el original | `3085ddbf2ce5e12e47a25d2f9f50bb3a9d3245330630bcce82e2df7626f8c711` |
| Búsquedas nativas por empresa | `0879d1ab33232cefefc547426b4217f4202aa95ee183e94179f4346b4fe3f900` |
| Ajustes guardados por empresa en el original | `8421dddd45f182e381e1475bbb3da72bcb39b21b268776a096fdc19f9c92899b` |
| Catálogo después de instalación, actualización y reversión de las pruebas | `48585970cb08c4bb841429649c00c641883ac3fee5d5cc54296317df436ddb3a` |
| Resultado de la segunda instalación, con matriz de pantallas y referencias | `fd3ad217938e4c6e540d972ff31378b95e2728b89b3db7030411015c95ef6a90` |

`tools/community/run_cerro_contact_followup.py` admite la copia privada desde el recibo firmado de 192 y las referencias originales de usuarios. Si el catálogo, los permisos, las relaciones o los resultados divergen, el ejecutor se detiene sin emitir la aceptación.
