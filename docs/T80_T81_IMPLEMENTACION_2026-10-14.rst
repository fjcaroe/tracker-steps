T80 y T81 — Gastos e instructivos de embarque
==========================================

Alcance y destinos
-----------------

Se revisaron descripción, comentarios y adjuntos de los tickets nuevos T80 y
T81. Los pendientes anteriores T45, T46 y T48 siguen en espera sin respuestas
nuevas. T80 corrige la apertura de Provisión gastos embarques, entregada por
T79; T81 solicita mejoras y formato del instructivo y configuración de folios.
Ambos se atienden en Desarrollo y Cerro El Plomo, con overlays privados.

T80 — corrección comprobada
--------------------------

El log del servidor de Cerro muestra ``KeyError: analytic_precision`` durante
el ``onchange`` inicial. El componente nativo ``analytic_distribution`` agrega
ese campo a su petición incluso cuando la distribución está en solo lectura.
Se incorporó la precisión no almacenada del maestro nativo Percentage Analytic.
La distribución conserva su condición de snapshot protegido del costeo.

``step_export_shipment_provision``: versión ``18.0.1.0.1``.
Paquete probado y publicado: commit
``8be9d7be6c18bfdd3c73cdf6590c94e698b2a87d``; SHA-256
``96ff7d13942ad13f7c254d5463efb4add34d760626fbadc6da7525cc1d02803a``.

Pasaron siete pruebas en cada copia de destino, incluyendo la petición de
Nuevo, permisos/menú/formulario, validación, costeo, congelación de importes,
contabilización balanceada, tres planes analíticos y prevención de duplicados.
Las pruebas de menús se ejecutan post_install para consultar el registro completo
también al actualizar un módulo ya instalado. No se ignoraron modelos faltantes.

Respaldos recuperables:

* Desarrollo: ``/opt/steps_backups/management_development_20261014T033830Z``.
* Cerro: ``/opt/steps_backups/management_cerro_20261014T034309Z``.

Se verificaron después código/versión efectivos, formulario, Nuevo, menú y
flujo con perfil de operación/contabilidad en ambas bases reales, descartando
las muestras. Las pruebas no contabilizaron gastos del cliente.

T81 — implementación y criterios de entrega
------------------------------------------

El addon ``step_export_shipping_design`` amplía el instructivo existente
``step.export.export`` y sus líneas; no usa el instructivo Studio histórico.

* Booking se ubica debajo del tipo; Pago flete permite Collete y Prepago.
* Variedad, Marca, Calibre y Calidad quedan visibles entre Embalaje y Pallets.
  Variedad y Calibre reutilizan sus relaciones existentes; Marca conserva el
  campo existente ``label`` y Calidad relaciona el maestro nativo instalado.
* Notas incorpora temperatura, ventilación, atmósfera, filtros y thermos;
  transporte, packing, consolidación, staking, operador, carga, contacto,
  teléfono, contenedor, cantidad, kg brutos y agencia de aduana.
  Los participantes se seleccionan de contactos existentes.
* Seguimiento contiene los cinco documentos del adjunto, originales, copias,
  instrucciones, estado, fecha y responsable. Las cantidades de referencia
  son valores iniciales para documentos nuevos y pueden ajustarse.
* Fletes usa el maestro existente de conceptos de gasto en exterior y registra
  forma de pago y observación por línea. Las reglas limitan ambas tablas de
  detalle a las empresas permitidas.
* Imprimir incorpora el instructivo con los datos de la empresa y contactos
  reales, carga, transporte, observaciones, fletes y documentación, tamaño carta.
  El título distingue transporte marítimo, aéreo y terrestre. Los datos del
  ejemplo del adjunto no se incorporan al código ni a maestros del cliente.

La configuración está en Exportaciones / Configuraciones / Folios de exportación
y se guarda por empresa. Folios por documento mantiene el circuito existente.
Folio comercial único permite un número inicial positivo: el operador ingresa
manualmente el folio en la nota de venta y la selecciona al crear el instructivo.
La nota de venta, Proforma/Invoice comercial, instructivo y embarque usan el mismo
número. El documento contable conserva su número y muestra el folio comercial.
No se renumeran documentos anteriores ni se cambia automáticamente el modo
de las empresas existentes.

Un índice parcial hace únicos los folios positivos por empresa sin restringir
las ventas ordinarias con folio vacío. Se conservan los folios vinculados y
confirmados y se comprueba empresa, recibidor y vínculo al embarque. Los
documentos comerciales seleccionan la nota fuente, sin coincidencias por nombre.

Antes de publicar se exige prueba funcional en una copia fresca de cada destino,
comparación de todos los datos originales, revisión visual del PDF y verificación
de la versión, formulario, menú y flujo real después de publicar el mismo paquete.
La instalación preserva todas las columnas originales de embarques, líneas,
ventas, documentos contables y empresas, incluida su auditoría.

Comprobación y publicación T81
-----------------------------

``step_export_shipping_design``: versión ``18.0.1.0.0``.
Paquete probado y publicado en ambos destinos: commit
``21a829f2140203ac61f70ec9186283683d39c877``; SHA-256
``2cde3ac5ce7125562886370fb0df89a01fba9c0c8836197a2603b644e62e664c``.

Pasaron cuatro pruebas en cada copia fresca de destino, sin fallos ni errores:
folio común y documentos comerciales, numeración independiente y ventas
ordinarias, unicidad/conservación del folio, y formulario/permisos/aislamiento
por empresa. La factura borrador mantiene su estado y numeración nativos;
el vínculo comercial se propaga desde la nota de venta.

La verificación posterior comprobó versiones y archivos efectivos, menú,
formulario con perfil de ventas, seguimiento, fletes, validación del instructivo,
origen del folio para Invoice y generación PDF con el convertidor de Odoo en
ambas bases reales. Se descartaron las muestras. Los snapshots completos de
columnas originales coincidieron antes/después de instalar en cada destino.

El PDF final se renderizó con Poppler y se inspeccionó visualmente: carta vertical,
612 × 792 puntos, una página para la muestra completa, sin superposiciones ni
cortes. Las secciones continúan en la misma hoja cuando hay espacio; tablas
largas pueden continuar sin una segunda página obligatoria. La herramienta de
control de navegador no inició; la comprobación de formulario usa su vista
efectiva y las peticiones/métodos reales de Odoo, sin afirmar inspección del
navegador.

Respaldos recuperables:

* Desarrollo: ``/opt/steps_backups/management_development_20261014T041020Z``.
* Cerro: ``/opt/steps_backups/management_cerro_20261014T041450Z``.

Evidencia privada
-----------------

Adjuntos, capturas, paquetes, logs y pruebas quedan fuera del checkout en
``~/.codex/local-artifacts/ticket-80`` y ``ticket-81``. Los paquetes se construyen
desde blobs Git comprometidos. El publicador exige SHA, respaldo, baseline
sin cambios concurrentes, bloqueo compartido y ausencia de downgrade.

Cierre y coexistencia
--------------------

Después de instalar T81 se repitió la verificación completa de T80 en las dos
bases reales: Nuevo, formulario, menú, validación, costeo, asiento balanceado,
tres planes y prevención de duplicados siguieron pasando. Ambas versiones
conviven en overlays privados sin sustituir raíces compartidas.

T80 y T81 quedaron en Solved, con notas internas 9416 y 9417 respectivamente,
sin destinatarios ni notificaciones. El cierre exigió evidencia del paquete
exacto, QA, publicación y flujo en cada destino; T81 exigió también la revisión
visual del PDF. Se revisaron respuestas recientes de tickets abiertos y cerrados
antes del cierre. No había más tickets nuevos después del 81.
