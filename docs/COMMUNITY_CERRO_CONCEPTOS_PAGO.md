# Conceptos de pago de exportación de Cerro El Plomo

La lista Studio 4845, el menú 987 y la acción 1378 volvieron a funcionar en una copia de Cerro con 189 módulos libres. Se instalaron los cinco archivos de `step_cerro_export_payment_concepts` 18.0.1.0.1 sobre una restauración verificada del perfil de 188 módulos. El ensayo incluyó instalación, actualización y un nuevo arranque con el mismo paquete.

| Verificación con la referencia nativa | Resultado en Community |
|---|---|
| Usuario de inventario 6 en ocho empresas individuales y el conjunto de las ocho | Los seis conceptos conservan exactamente los mismos valores en los nueve contextos |
| Seguridad efectiva de 15 usuarios internos originales | Coincidieron lectura, creación, escritura y eliminación. El usuario público recibió el rechazo original |
| Relaciones de productos | Se conservaron los dos productos vinculados y ambos identificadores de campo de producto. La asignación a un concepto nuevo pasó por el ORM |
| Costo estándar por kg, caja y pallet | Un programa en borrador permitió editar. Un programa valorizado visible rechazó las tres ediciones. El registro en otra empresa siguió la regla nativa del programa |
| Integridad tras el ensayo | La transacción de edición se revirtió y se restableció la única secuencia utilizada por el alta |
| Base y seguridad después de actualizar | Los catálogos SQL y de permisos coinciden con la semilla de 188 módulos en todas las propiedades cotejadas. Se conservaron 62.030 identidades externas, los 24 disparadores activos de protección y las 23 filas completas de vistas Studio |

El proveedor conserva las quince identidades de campo del concepto, las tres ACL de sus propietarios originales y las vistas y menús históricos. El control de costo consulta el programa y su empresa mediante las relaciones existentes. Cuando la aplicación de embalajes está fuera del registro de esta copia, la consulta de protección comprueba los permisos efectivos del operador y el dominio original aplicado. Los ensayos utilizaron un programa y un costo temporales, ya que el respaldo contenía diez programas de venta y cero programas de embalajes.

La matriz del usuario de inventario alcanza **21 rutas originales, 20 lecturas exactas de los campos Studio y 16 fichas completas de 23**. Siguen pendientes siete lecturas completas. Dos requieren los controles de Calidad de las transferencias y dos las órdenes de Packing. Las otras tres dependen del estado de las tarjas, del envío SII de la guía y del seguimiento de cobros de Contactos.

## Paquete y referencias

El paquete reproducible contiene cinco archivos y su SHA-256 es `cdba41119f13f2d01457b5e92c2d8ad92b7aa10bab9e5544d658822d351b6d1c`. Se reconstruye con `python tools/community/build_cerro_verified_172.py --source . --profile concepts --output <tar-nuevo>`. La referencia de Odoo nativo `native-concept-user.json` tiene SHA-256 `49fa2ff286f841f0bd25a38700befa33b4f963c83af0b52b32ed0b246fdfa9fc`. La vuelta completa de Community `accepted-concepts.json` tiene SHA-256 `50849918f3750c2dc7891d7e1b964f351c2526750f238d3249159f60614a253e`.

El servidor de ensayo estaba por debajo de la reserva de espacio para crear la siguiente copia. Se ejecutó el paquete sobre la misma semilla restaurada en un PostgreSQL 12.22 privado del equipo local. Se verificaron el núcleo, los 188 proveedores originales, Python y el ejecutable oficial de Odoo. De esos 188, 129 coincidieron byte por byte con fuentes ya disponibles en la máquina y 59 necesitaron una copia específica. Las bases del servidor se conservaron.

## Verificación de restauración

Los archivos y sus inventarios permanecen en el almacenamiento privado. Cada base restituyó 1.521 tablas, 1.247 secuencias con su valor y 677 objetos físicos. Se contrastaron todas las filas por tabla, las definiciones y los permisos. En los tres casos PostgreSQL volvió a representar de forma distinta el mismo array de constantes de cuatro CHECK de contabilidad. La verificación cotejó cada expresión completa, sus propiedades y el resultado de comparar las dos constantes dentro del propio motor.

| Copia recuperada | Filas verificadas | SHA-256 del recibo de recuperación |
|---|---:|---|
| Piloto U44K | 249.640 | `33d8b9dc1553c8d079d96de682d796ef4bbfa04685596c5adf9e2504f0ba5541` |
| Piloto U42P | 249.605 | `a365200289bd6a0d76d95d10d3f795967f568fbf199f81d88034e14aa9a305ec` |
| Semilla U44M | 249.641 | `f884bbe8bccdd490d242a3095923f8f5526563f08a98a9ca384f7de3dd57c990` |

Los respaldos de las tres bases contienen exactamente los mismos bytes de filestore. Su SHA-256 es `28a92a607b8e53d4ee2ec166392508b332f545f9609bf10701ffd258f3ddcd57`. La copia operativa tiene su propio directorio y sus propios archivos. El conjunto de fuentes de U44M suma 136 módulos oficiales y 52 adicionales, con SHA-256 `f7d04b1ee1e832c6840fbb346d1829ad64416c1fc213cd43a50347c84c242864`.
