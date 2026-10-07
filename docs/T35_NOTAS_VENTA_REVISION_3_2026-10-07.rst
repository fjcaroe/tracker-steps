T35 notas de venta, embarques y Packing List
==========================================

Solicitud y ambiente
--------------------

Se incorpora el adjunto de revisión 3 recibido el 07-10-2026. Pide ocultar los
campos APR del encabezado cuando su configuración esté vacía y seleccionar
productos con el atributo existente Es exportación de la ficha agrícola.
Destino: Desarrollo, LAB_TAREAS, https://desarrollo.stepsapp.cl.
La base agrícola canónica integra las decisiones contables y navegación previas.

Corrección
----------

* APR se determina con los productos de cargo fijo y consumo variable que ya
  guarda cada empresa. Si ambos están vacíos, se ocultan medidor, sector, tipo
  de carga, periodos, lecturas y consumo. Cuando existe configuración, se
  mantienen los campos APR. No se modifica la configuración ni los datos
  históricos de lectura. La fecha de emisión, tarifa, pago y datos comerciales
  permanecen en el formulario.
* La adaptación usa código de step_export y tolera instalaciones sin APR;
  no instala ni requiere ese módulo y no modifica vistas Studio manualmente.
  Una nota comercial sin APR recibe sus valores numéricos predeterminados para
  evitar que el create antiguo de APR exija una lectura invisible.
* Notas nuevas desde Exportaciones quedan identificadas como comerciales de
  exportación, incluso antes de vincular programa o embarque. Las notas previas
  conservan sus relaciones y se reconocen por ellas, sin reemplazar registros.
* Selector de producto, variante y catálogo incorporan Es exportación a los
  filtros existentes de venta/empresa. Las ventas generales conservan su
  selección habitual. Se reutiliza product.template.step_export_enabled.

Embarques recibidos durante la revisión
--------------------------------------

Se incorpora también el adjunto de revisión de Embarques del 07-10-2026,
recibido mientras se verificaban las notas. Naviera/aerolínea, consignatario,
notify y agentes de carga/aduana seleccionan contactos con la marca original
Exportación? (res.partner.step_export). No se crean otras marcas ni contactos.

POL/AOL y POD/AOD son relaciones a l10n_cl.customs_port, el maestro existente
de Contabilidad / Puertos Aduanas. La dependencia l10n_cl_edi_exports ya está
instalada en Desarrollo. Los textos anteriores permanecen de solo lectura;
la migración vincula solo un código o nombre exacto normalizado con una única
coincidencia. Si hay ambigüedad o ausencia de coincidencia, conserva el texto
visible para su revisión. Packing List imprime el puerto seleccionado o el
texto histórico si aún no existe relación. El instructivo queda primero en
Embarque, antes de Exportación, usando el mismo documento operacional.
Los usuarios internos de Exportaciones pueden consultar Puertos Aduanas; la
nueva autorización es solo de lectura y no habilita edición, creación ni
borrado de este maestro.

Packing List recibido durante la revisión
-----------------------------------------

Se incorpora el mensaje 9223 y adjunto 3297, recibidos el 07-10-2026 a las
14:22:44 UTC. El error de pertenencia impedía guardar, por lo que el nombre
Nuevo de las capturas correspondía a un documento sin persistir. No había
Packing Lists guardados en el destino al revisar el problema.

El encabezado de la guía de despacho ahora selecciona Embarque. El selector
es una proyección con inversa de la relación many2many existente, no una
segunda relación almacenada. Mantiene vínculos históricos incluso si hay
varios; en ese caso no adivina un embarque único. Cambiar el selector conserva
la pertenencia en ambos formularios, valida empresa y respeta el bloqueo de
embarques cerrados. Una guía con Packing List no puede cambiar de embarque.
No se modifica el módulo de emisión DTE ni sus folios.

El Packing List hereda el número de embarque; contenedor y sello aparecen
antes del selector, con nombres que los distinguen. El número de sello no
se reemplaza por el número de embarque. Las guías se filtran por pertenencia;
cambiar el embarque limpia una guía incompatible. El guardado acepta nombre
vacío/Nuevo y asigna el correlativo PL/ de la empresa del embarque; si falta
configuración, avisa en lugar de guardar un documento denominado Nuevo.
La versión 18.0.2.9.7 agrega vistas y campos calculados sin cambiar datos
ni columnas comerciales existentes.

Pruebas y publicación
---------------------

Se prueban configuración APR vacía y activa, creación sin lecturas, selector
producto/variante, catálogo de exportación/general y relaciones históricas.
La comprobación funcional con perfil de Ventas crea una nota, verifica que
aparezca en el menú, comprueba su catálogo, genera el HTML de proforma y
confirma el pedido. La transacción se revierte: no se envían proformas ni se
conservan documentos de prueba en Desarrollo.

El gestor de publicaciones compara todas las tablas comerciales Steps,
contables, inventario y productos, además de empresas, contactos y pedidos de
venta con sus líneas. Solo se excluyen las columnas nuevas de cada migración (indicador de nota o
relaciones de puerto, según la versión de origen);
IDs, campos previos, lecturas, cantidades e importes se comparan íntegramente.
El paquete debe superar una copia privada fresca de Desarrollo y se publica
con respaldo, overlay privado, control de versión y bloqueo compartido.

Resultado: publicado y verificado en Desarrollo el 07-10-2026.

* Código probado/publicado: 1ecf400a02687b85aa4ee13e10a7420b442e5e24.
* Versión step_export: 18.0.2.9.7.
* SHA256: 2f3c9c42cf9720562f6ef974aa715517b6e69e937975b175f66ae757befd567f.
* Copia privada: MANAGEMENT_QA_DEVELOPMENT_t35packing07f.
* Resultado: 28 pruebas, cero fallos y cero errores.
* Flujo con perfil de Ventas/Inventario: nota comercial, catálogo, proforma,
  confirmación, puertos, participantes, guía con embarque y Packing List
  guardado con correlativo e informe. Repetido correctamente en el destino;
  todas las muestras transaccionales se revierten.
* Respaldo: /opt/steps_backups/management_development_20261007T143147Z.
* Overlay privado: /opt/steps-managed/releases/development/1ecf400a02687b85aa4ee13e10a7420b442e5e24.
* Preservación comercial, servicio y comprobación HTTPS correctos.
* La migración de puertos conserva Philadelphia como texto histórico por
  no existir una coincidencia en el maestro. Valparaíso sí se vincula con
  su único puerto aduanero nativo. No se crean ni adivinan puertos.

Para retomar la captura del cliente, seleccionar el embarque en el encabezado
de la guía, guardar y después elegir esa guía al crear el Packing List.
Las relaciones del cliente no se adivinan por el texto del folio.
