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

Registro de fletes: error al guardar
----------------------------------

Se reprodujo en el navegador de Desarrollo la creación de una orden con una
línea de detalle. Al guardar, ``web_save`` crea el registro y luego solicita
los campos de las líneas de Costeo, incluso si esa pestaña está vacía.
El widget estándar de distribución analítica solicita ``analytic_precision``;
el modelo de costeo no lo definía y ``web_read`` lanzaba un ``KeyError``.
La transacción completa se revertía y la orden no quedaba guardada.

18.0.2.6.1 incorpora ``analytic.mixin`` al mismo modelo de costeo y expone su
empresa desde la orden. La cuenta de cargo se recalcula también si cambia la
empresa. No sustituye el maestro analítico ni crea una tabla paralela.

Las regresiones ejercitan ``web_save`` y ``web_read`` con Costeo vacío,
creación/edición/reapertura, el formulario efectivo con detalles, costeo y
contabilización, y la distribución guardada hasta el apunte analítico.
El sondeo operativo prueba además el formulario y el guardado con un usuario
interno sin permisos de Contabilidad, y revierte todos los datos de prueba.

En el primer ejercicio del navegador también se detectó que el importe
calculado era un campo de solo lectura y no se enviaba al guardar una orden
nueva. Además, la vista previa multiplicaba por cantidad las tarifas por viaje.
18.0.2.6.2 incluye el importe en el guardado del formulario y aplica la misma
modalidad y conversión de moneda que Calcular costeo. Se cubre con una prueba
del formulario que crea, guarda y edita la cantidad de un flete por viaje, y
comprueba que el importe se conserve y coincida con su costeo.

Paquete final de esta corrección: ``b23b2636eac165ca3eb0469c82727442f0e77278``;
SHA-256 ``b62b57f4f3d9cafc489a7f3946bf331c0ca78a6731ff93d82b2472262196e520``.
Fletes 18.0.2.6.2 y Guías de despacho 18.0.2.0.2 pasaron 54 pruebas, sin fallos
ni errores, en la copia nueva ``FREIGHT_QA_register_1006c``. La comparación de
columnas, filas e importes originales pasó en la copia y en el destino.
Publicado bajo el bloqueo compartido y con respaldo
``/opt/steps_backups/freight_development_20261006T145718Z``. Las pruebas,
huellas, sondeos y registros de publicación están en
``/opt/steps-validation/freight_development_register_1006c``.

Verificación en el navegador de Desarrollo: se creó una orden nueva, se
guardó con Costeo vacío, se cambió su cantidad de 3 a 4, se volvió a guardar,
se calculó su costeo y se reabrió desde el listado. Una tarifa por viaje de
55.000 conservó ese importe antes y después del guardado, de la edición y del
costeo. La captura final es ``registro-fletes-verificado.jpg`` en el directorio
local de evidencias mencionado arriba. Las órdenes marcadas QA quedan como
ejercicios en Desarrollo; no se contabilizaron allí. La contabilización y sus
apuntes analíticos se verificaron en las pruebas de la copia aislada.

Se dejó el aviso breve de revisión en T27 (mensaje 9182), sin cerrar el ticket.
El código de los dos módulos de la entrega sigue siendo exactamente el del
paquete probado; los commits posteriores de documentación no cambian sus bytes.

Terminación del flujo y menú estándar
-----------------------------------

Se leyó el error enlazado en el comentario 8950 de T27 y el documento V2 con
las respuestas del cliente. El error adjunto era ``analytic_precision``;
también se abrió en pantalla el flete del ejercicio de ese documento, con su
costeo y asiento existentes, sin modificarlo ni reproducir el fallo.

Fletes utiliza ahora la barra y las vistas internas estándar de Odoo, como
Packing. En el navegador ambas barras coincidieron en fondo blanco, colores
de texto, menús y altura de 46 px. Se retiraron los estilos de Fletes sobre
la navegación; la portada conserva su contenido propio.

Elegir la tarifa después de introducir los detalles actualiza precio,
servicio y unidad. Los cambios de frío, fecha o empresa actualizan las líneas
sin recalcular documentos contabilizados. Una única modalidad aplicable de
la tarifa se completa automáticamente. El precio manual positivo de Detalles
se conserva durante el costeo; las líneas sin precio importadas usan la tarifa.
Las tarifas genéricas sin servicio admiten el servicio elegido en el detalle.

La numeración se ejecuta en ``create()`` nativo. La migración adopta el mismo
contador y sus rangos, sin reiniciarlo; desactiva únicamente la automatización
histórica reconocida por su código exacto. Se conservan los folios importados,
editar no renumera y duplicar genera otro folio. La comparación incorpora las
filas y columnas del contador y sus rangos.

Crear guía desde Fletes toma el tramo, camión y chofer de Detalles. Los despachos
con varios tramos o vehículos requieren separarse y reciben una validación
clara. El ensayo en copia crea y confirma la guía vinculada.

La comprobación del navegador descubrió otra causa de bloqueo: Tab desde la
última columna podía agregar y guardar una fila vacía. Se descartan únicamente
las creaciones de filas sin información y con sus valores predeterminados.
Las filas existentes se conservan; las vacías no impiden el costeo. Una fila
con datos ingresados permanece y exige completar sus campos.

Paquete final: ``4b248373783b859b5b056a7b3cf607a1d7ec3b4e``; SHA-256
``f88f38f111c88758201821b170c7119bb5c20b79c7e3feb65609bc3a58810d99``.
Fletes 18.0.2.7.1 y Guías 18.0.2.0.3 pasaron 66 pruebas sin fallos ni errores
en ``FREIGHT_QA_completion_1006b``, con preservación de registros e importes.
Publicado y sondeado en Desarrollo bajo el bloqueo compartido; respaldo
``/opt/steps_backups/freight_development_20261006T153001Z`` y evidencias en
``/opt/steps-validation/freight_development_completion_1006b``.
Los assets se renovaron primero en la copia y luego en el destino, comprobando
la URL nueva y la apariencia del menú en el navegador.

En Desarrollo se verificó la carga de tarifa después del tramo, el guardado
con precio manual, folio generado en código y reapertura desde el listado.
El flete QA con una fila vacía existente costeó 57.000 sin borrarla. El ejercicio
final usando Tab guardó una sola línea y conservó 56.500 al costear y reabrir.
La guía se abrió con las direcciones, tramo, camión y chofer del flete; se
descartó ese borrador de prueba. Las órdenes QA se conservan sin contabilizar.
La captura final es ``fletes-completo-menu-limpio.jpg`` en el directorio local
de evidencias de T27. La contabilización se verificó en la copia de pruebas.

El cliente confirmó en el comentario 9183: registro, costeo, contabilización
y enlace con guía de despacho OK. El comentario propio 9184 se actualizó para
reconocer esa respuesta y el menú corregido, sin repetir la petición de validar
los mismos pasos. No se cambió la etapa del ticket ni se publicaron estos módulos
en otros ambientes.
