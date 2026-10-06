Fletes: nombres técnicos propios y selectores
============================================

Decisión del usuario: retirar los nombres técnicos ``x_`` de Fletes en
Desarrollo y corregir selección/creación de Tramo y Modalidad de frío.
Se renombra el conjunto operativo de doce modelos a ``step.freight.*`` y sus
campos a nombres descriptivos (``name``, ``code``, ``route_id``, ``cold_mode_id``,
``km_from``, ``km_to``, etc.). No se crean maestros paralelos. La migración
18.0.2.6.0 renombra tablas y columnas existentes, conserva IDs/FK y adapta
metadatos, acciones, filtros, mensajes, adjuntos y referencias.

La modalidad admite creación por nombre desde el selector. Tramos usa
``Crear y editar`` y abre su formulario propio con nombre, origen y destino;
se impide la creación rápida incompleta que solo envía el nombre. Los campos
Many2one apuntan a los maestros correctos y los formularios se fijan de forma
explícita. Las vistas Studio de los modelos operativos se archivan y sus
reportes anteriores se desvinculan de los botones de impresión.

Guías de despacho extiende Fletes. Se reconcilió primero su código efectivo
18.0.2.0.1: todos sus archivos coincidían con ``7c626f1``. Su puente se adapta
a los modelos/campos nuevos y pasa a 18.0.2.0.2. Se entrega junto con Fletes;
no se permite un upgrade que deje cargando el puente anterior.

Pruebas del mismo paquete en copia nueva de Desarrollo: nombres y búsqueda
desde Many2one, creación rápida de frío, creación/edición de tramo por formulario,
tarifas, costeo, contabilización, reportes y guía con flete. El publicador compara
las columnas originales después de traducir exclusivamente sus nombres y las
referencias de modelo; conserva importes, documentos y sus relaciones.

Paquete definitivo: ``287b447c8de7723e0d51f007cfa45bb3f2b25c39``; SHA-256
``55823dbc5d6c904b8f2d0d48050d1455826fd93240135c03009201b09cd74761``.
Pasó 50 pruebas sin fallos ni errores en la copia nueva
``FREIGHT_QA_native_1006e`` y conservó las columnas/filas originales, incluyendo
asientos, detalles, guías, mensajes y adjuntos. Se comprobaron también referencias
almacenadas de automatización para mantener la numeración de los fletes.
Publicado y verificado en Desarrollo / LAB_TAREAS, con respaldo
``/opt/steps_backups/freight_development_20261006T140812Z`` y evidencias en
``/opt/steps-validation/freight_development_native_1006e``.

La comprobación del navegador detectó JavaScript antiguo en caché. Los paquetes
construidos desde Git tenían mtime de época y Odoo reutilizaba la URL anterior.
``tools/ops/refresh_freight_assets.py`` comprueba el paquete aprobado, usa el
bloqueo compartido y regenera exclusivamente los assets compilados de Odoo.
Actualiza la fecha de los estáticos privados sin cambiar su contenido y señala
la invalidación de caché. Se probó en la copia y en Desarrollo; la URL de
``web.assets_web.min.js`` cambió y la portada volvió a mostrar sus registros.
Este paso forma parte de la verificación de la entrega, sin borrar documentos.

En el navegador se creó un tramo desde Crear y editar con origen/destino y
kilómetros, y una modalidad de frío mediante creación rápida por nombre.
Ambos se seleccionaron y se guardó la tarifa de prueba, comprobando sus FK en
la base. No apareció error y los campos mostraron sus nombres. La tarifa
``QA selectores nativos 06-10`` queda en Desarrollo para reproducir el ejercicio;
no se contabilizó. Las capturas están fuera de Git, en
``~/.codex/local-artifacts/ambientes-canonicos/t27-current/``.

La retirada completa de Studio en las otras aplicaciones y de las automatizaciones
históricas sigue el inventario global. Esta entrega no instala Fletes ni Guías
en Demo-SYS o SyS. Demo-SYS conserva únicamente el alcance permitido de SyS.
