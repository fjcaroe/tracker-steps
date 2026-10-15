Packing List y documentos comerciales de exportación
==================================================

T85 corresponde al registro Helpdesk 84 y T86 al 85. El alcance se implementa
en ``step_export_document_revision``, sobre las aplicaciones existentes de
Exportaciones, ventas, contactos, tarjas y órdenes de trabajo de Packing.

Packing List
------------

El documento conserva el embarque, guía, contenedor, sello y tarjas registrados.
La impresión incorpora producto, contenedor, folio comercial, nave, fechas,
booking, exportador, recibidor, puertos y totales del embarque. El detalle muestra
CSP, pallet, variedad, fecha de proceso, CSG, cajas, kilos netos/brutos, termos y
calibre; sus totales corresponden a las tarjas seleccionadas.

Se reutilizan el CSG del productor y la fecha/planta de la OT. CSP se añade al
contacto existente del packing; peso bruto y termos se registran en la tarja.
Las tarjas mixtas muestran los CSG de sus productores, sin elegir uno por nombre.
La versión anterior instalada de Packing recibe la misma referencia relacionada
a planta desde su OT, sin duplicar ese vínculo ni actualizar módulos ajenos.

El formulario usa los kilos reales del detalle por productor cuando existe;
el cálculo histórico por quants se conserva como alternativa para tarjas sin
ese detalle. PDF y Excel comparten las mismas fuentes. El archivo Excel conserva
los códigos como texto y no ejecuta como fórmulas ni enlaces el contenido de
los campos. Sus adjuntos conservan los permisos del documento de origen.

El texto de T85 pide expresamente POD para salida y POL para arribo. Se adapta
solo la presentación de este documento, preservando las relaciones y significado
de origen/destino en el ERP.

Nota de venta y documentos comerciales
-------------------------------------

Las notas nuevas permiten ingresar cajas y el embalaje del producto; kilos es
cajas por kg del embalaje. Precio kg comienza desmarcado. El neto se calcula
con cajas por precio, o kilos por precio cuando se activa ese criterio,
conservando los impuestos y descuentos nativos.

Los kg por caja se guardan al seleccionar el embalaje. Cambiar posteriormente
el maestro no modifica el peso acordado en la nota. Los documentos anteriores
conservan cantidades e importes. Una nota antigua sin confirmar puede adoptar
el cálculo por cajas mediante una acción explícita que conserva el precio.
El criterio de precio no se cambia en notas confirmadas.

Proforma e Invoice comercial tienen botones de impresión propios, rótulos en
inglés y el mismo formato y folio de la nota. Imprimirlos no genera asientos ni
facturas. La factura contable sigue el ciclo estándar: si la venta usa precio
por kg, se convierte ese precio a precio por caja al preparar sus líneas,
conservando las cantidades físicas y los importes pendientes de facturar.

Preservación y validación
------------------------

La carga inicial del nuevo campo almacenado de kg por caja causa escrituras
del ORM sobre líneas históricas. Los hooks versionados conservan en una tabla
temporal transaccional los cuatro valores afectados: autor/fecha de edición y
los indicadores internos is_service/is_downpayment. Tras llenar exclusivamente
el campo nuevo se restablecen esos valores y se invalida la caché. No se omiten
esos campos de la comprobación de preservación.

Las pruebas cubren precios por caja/kg, descuentos e impuestos, preparación de
la factura estándar, peso acordado, adopción explícita de notas anteriores,
bloqueo de confirmadas, validación del embalaje, idioma, ausencia de efectos
contables al imprimir, coherencia PDF/Excel, protección de celdas, formularios
y permisos por empresa. El publicador compara íntegramente las filas anteriores,
verifica versiones y origen de código, y ejecuta el flujo y el conversor PDF
nativo con reversión de los registros de prueba.

Los documentos de muestra se renderizan e inspeccionan como imágenes. Los
archivos de clientes, respaldos y evidencia visual se conservan fuera del
repositorio público. La publicación exige el mismo paquete probado en copia
aislada, respaldo, bloqueo compartido y overlay privado, sin downgrade ni
cambios concurrentes.

Entrega comprobada
------------------

Versión publicada: ``18.0.1.0.1``.
Paquete: ``5b112acc4be6bd0a1b5ef7a5c61866bbe61c01d6``.
SHA-256: ``a9724e0128b241ff5bc60a084d1fec67299321c7d26a2e3751f82c6e6015d887``.

Seis pruebas sin fallos en cada copia nueva, con comparación íntegra de las
filas anteriores y generación PDF nativa. Las muestras finales y los Excel
fueron renderizados e inspeccionados; se comprobaron límites del texto y tamaño
carta. También se imprimieron documentos existentes con la empresa seleccionada
explícitamente, sin elegir otra por el usuario técnico de la sesión.

Desarrollo: copia ``t8586_j_dev``. Respaldo previo a la entrega final:
``/opt/steps_backups/management_development_20261015T051029Z``.
Cerro El Plomo: copia ``t8586_j_cerro``. Respaldo:
``/opt/steps_backups/management_cerro_20261015T051327Z``.
Ambos sirven exactamente el mismo paquete probado desde sus overlays privados;
se verificaron versión, fuente, formulario, menú, flujo, PDF y Excel después
de publicar, además del acceso HTTPS.

La revisión en navegador confirmó las columnas y Precio kg inicialmente falso
en las notas nuevas de ambos ambientes, y los botones PDF/Excel de Packing List.
En Desarrollo se descargaron realmente ambos formatos y se comprobó que el
formulario del Packing List existente muestra los kilos de su tarja. Las notas
sin guardar usadas para revisar formularios se descartaron.
Cerro no tenía Packing Lists anteriores: el flujo completo se ensayó con
registros de prueba y reversión, sin guardar un embarque ficticio en producción.

Los demás pendientes siguen sujetos a sus requisitos humanos vigentes:
T45 necesita equipo y prueba en terreno; T46 mantiene validación nativa y la
decisión de arquitectura de pasajeros; T48 espera activar Meta y probar el canal
real. No se encontraron respuestas humanas nuevas que destrabaran esos hitos.

T85 y T86 se marcaron resueltos tras las verificaciones, con notas internas
9441 y 9442 respectivamente y seguimiento/notificaciones suprimidos. Se leyó
la configuración y el código de seguimiento de Helpdesk antes de cerrar:
la plantilla automática de cierre depende del seguimiento de MailThread,
deshabilitado en esa escritura. No se enviaron correos al cliente.
