# T240: corrección de kilos de tarjas recibidas

El requerimiento autoriza corregir siete tarjas C de un destino productivo.
La distribución de la recepción ya puede contener el peso aprobado mientras
el detalle inmutable de la tarja y las existencias conservan el peso anterior.
No basta con modificar el dato visible de la recepción.

`tools/ops/correct_reception_weights.py` usa un plan privado fuera del repositorio
que identifica compañía, usuario existente, tarjas, detalles, recepción, lote,
propietario, producto, ubicación, cajas y pesos anteriores/aprobados. Los totales,
las identidades y las huellas de concurrencia de los borradores son privados.

La confirmación humana recibida durante la atención de T240 amplía expresamente
la corrección a dos anticipos en borrador, sin facturas. Sus cantidades e importes
se actualizan conservando precios unitarios, precios de origen, tipo de cambio,
impuestos, referencias, otras fuentes y estado. No aprobar ni facturar documentos.

El procedimiento requiere stock íntegro de tercero, sin reservas, procesos,
divisiones, repaletizados ni despachos posteriores. Conserva todos los movimientos
anteriores y agrega un movimiento de inventario nativo por diferencia, manteniendo
producto, lote, propietario y ubicación. Actualiza únicamente kilos y cantidad del
detalle nativo mediante mantenimiento versionado y restricciones ORM conservadas.
Las cajas, maestros, recepciones originales y las instantáneas del Excel permanecen.

## Ejecución en el servidor canónico

1. Crear un directorio privado de herramientas revisadas, copiar la herramienta y
   `native_business_profile.py`, y proteger el plan JSON con modo `0600`.
2. Ejecutar `rehearse <plan> /opt/steps-validation/t240-<etapa-nueva>` como root.
   Obtiene el bloqueo compartido, inventaría las fuentes efectivas de stock y
   Packing, respalda/restaura una copia fresca y neutraliza correo y tareas.
3. La copia ejecuta y confirma el flujo completo; una segunda ejecución exige
   idempotencia, sin crear otro ajuste. El certificado registra las huellas del
   plan, herramienta, perfil y fuentes, junto con ambos resultados.
4. Ejecutar `apply` con exactamente el mismo plan, herramienta y etapa certificada.
   Rechaza cambios de código, configuración, datos objetivo o borradores. Guarda
   un respaldo nuevo verificable y la configuración antes de la transacción.
5. Verificar los formularios efectivos, los menús, `web_read`, las existencias,
   cantidades y totales de ambos borradores. Los originales ajenos al alcance,
   asientos, valoración y colas de notificación deben conservar sus huellas.
6. Para aceptación visual de solo lectura, usar `t240_browser_session.py` con el
   mismo usuario/compañía y `check_reception_weights_ui.cjs`. Guardar pruebas y
   capturas fuera del checkout y retirar la sesión temporal al terminar.

No instala módulos, no cambia permisos/credenciales ni publica datos en otros
ambientes. Las versiones de Cerro y QA-Cerro se conservan; los ejercicios del
cliente no se refrescan. Esta corrección de datos no introduce una nueva función
general de edición de tarjas validadas.
