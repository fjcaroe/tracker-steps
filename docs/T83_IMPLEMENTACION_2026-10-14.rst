T83 Modificaciones al formato de instructivo de embarque
======================================================

Alcance
-------

Se revisaron descripción, comentario humano y Word adjunto del T83, incluyendo
sus cuatro imágenes y el formato original del T81 para identificar los campos
rojos. Los destinos solicitados son Desarrollo y Cerro El Plomo.

Cambios de formato y operación
-----------------------------

* Formas de pago Collect y Prepaid, conservando las claves almacenadas
  ``collect`` y ``prepaid`` y todos los pagos existentes.
* Producto y carga usa la distribución de la referencia: producto y variedad,
  envase y cajas/sacos, pallets y contenedores, marcas y calibres, kg netos y
  brutos del embarque, y calidad. Una carga adicional imprime su bloque completo.
* Se restituyeron los rótulos rojos de la referencia: cantidad de contenedores,
  flete, cláusula de venta, puertos, booking, temperatura, ventilación, atmósfera,
  thermos, fecha/hora de carga e instrucciones SWB.
* La documentación impresa contiene los cinco requisitos fijos. No incluye
  Estado ni fechas del seguimiento. Los estados, cantidades, instrucciones y
  responsables del seguimiento operativo se conservan en el formulario.
* El desglose siempre imprime los trece conceptos de la referencia y su forma
  de pago. La lista fija aparece también en instructivos antiguos sin líneas.
  Los conceptos adicionales históricos y observaciones existentes siguen
  visibles; no se eliminan ni se fusionan pagos distintos silenciosamente.
* Los nuevos instructivos completan el listado usando relaciones al maestro
  nativo de conceptos de gastos en exterior. Se reutilizan las referencias
  existentes de su empresa; solo se crean las que falten en ese mismo maestro.
  Las equivalencias ambiguas se rechazan. Un bloqueo por empresa evita altas
  concurrentes duplicadas. No se crearon tablas paralelas ni campos de texto
  para reemplazar relaciones.
* Completar listado de fletes permite incorporar las filas faltantes a un
  instructivo anterior, sin modificar pagos u observaciones ya registrados.
  En Fletes solo se editan pago y observación; los conceptos permanecen fijos.
* La paginación mantiene juntos encabezado y contenido de cada bloque. No hay
  salto de página fijo ni reducción del tamaño de papel. Producto y carga,
  transporte, coordinación, observaciones, fletes y documentación se prueban
  con datos normales y con varias cargas y observaciones extensas.

Preservación y paquete
----------------------

La actualización no reescribe los instructivos, líneas, pagos, seguimiento,
maestros ni documentos contables anteriores. Los listados impresos se calculan
sin crear registros al imprimir. Se conserva el folio comercial del T81 y sus
relaciones con nota de venta e invoice. No se modificó Studio.

``step_export_shipping_design``: ``18.0.1.0.1``.
Commit del paquete: ``80f886910032da5128e2c55b7279ce64a5f1b279``.
SHA-256: ``bfe1b624f24876c78088ce4bde2b1e15e8b536313b58a2ed32caf59ee774cc09``.

Validación
----------

Siete pruebas cubren folios, facturación, permisos por empresa, formulario,
estructura impresa, conservación del seguimiento, copia e idempotencia del
listado, y pagos existentes. Se comprueban menú y flujo con un operador de
ventas, la generación PDF nativa de Odoo y las vistas efectivas del destino.

Las muestras PDF normal y extendida se renderizan como imágenes y se inspeccionan
página a página. Una comprobación adicional verifica formato carta vertical,
límites del texto, presencia de rojo y coincidencia de página para el principio
y final de cada sección. También se imprime un instructivo existente de cada
base en modo de solo lectura. Los adjuntos, PDFs, imágenes y pruebas quedan
fuera del repositorio público.

La promoción exige el mismo paquete probado en cada copia de destino,
comparación íntegra de registros anteriores, respaldo de base/configuración/
filestore, bloqueo compartido y overlay privado sin downgrade.

Desarrollo: siete pruebas aprobadas, revisión visual de los casos normal y
extendido y verificación posterior del formulario, menú, folios y flujo.
Respaldo: ``/opt/steps_backups/management_development_20261015T011754Z``.
La impresión de un instructivo existente se comprobó también desde el servicio
publicado, con su logo y datos reales y sin grabar cambios en el documento.

Cerro El Plomo: siete pruebas aprobadas en su copia, revisión visual de los
casos normal y extendido y del instructivo existente con logo y datos del
cliente. Respaldo: ``/opt/steps_backups/management_cerro_20261015T012218Z``.
Se verificaron después de publicar la versión y fuente efectivas, el formulario,
menú, permisos, folios y flujo; se volvió a imprimir el instructivo existente
desde Cerro y se inspeccionaron todas sus páginas. Ambos destinos sirven el
mismo paquete probado y mantienen su acceso HTTPS.
