T30 y T38 revisión del cliente
=============================

Alcance y destino
-----------------

Se incorporan los adjuntos humanos del 06-10-2026: revisión 3 de Contratos
de compra en T30, ordenamiento del menú de Productores y la respuesta posterior
de T38 sobre la revisión 3 de Estimación. Desarrollo
es el único destino de QA. Demo-SYS y las producciones no reciben este paquete.
Los documentos, capturas y evidencia con datos del cliente permanecen fuera
del repositorio público, en el directorio privado ``t30-t38-client-revision``.

Contrato de compra
------------------

* El selector de fruta utiliza el indicador existente ``step_export_enabled``.
  Su definición pasa al núcleo independiente de Productores, manteniendo
  la columna y los valores usados por Exportaciones.
* Se retira el widget de distribución analítica y la edición de cuentas de
  cargo por fruta. Se conservan los campos históricos, sin utilizarlos en
  nuevas provisiones ni alterar apuntes ya publicados.
* Las referencias a líneas de contrato muestran el producto y sus variantes,
  en lugar de ``modelo,id``. El calendario muestra ``Anticipo contrato``
  seguido del folio, junto con la fruta de referencia que mantiene el cálculo.
* Ajustes contables permite seleccionar un producto existente como concepto
  de anticipo y una cuenta de activo de la empresa. No se crean maestros
  duplicados ni se sustituye ninguna relación por texto.
* El acceso a Ajustes contables abre la empresa activa existente. No inicia
  una empresa vacía. La acción anterior conserva el listado de empresas
  autorizadas con selección de formulario explícita; la vista especializada
  tiene prioridad 99 para no sustituir formularios generales por defecto.
* Contabilizar genera un par de apuntes por cuota activa, con fecha de
  vencimiento, moneda y referencia a la cuota. El debe corresponde a la
  cuenta configurada de anticipo y el haber a la provisión del contrato.
  Se respeta la lista de cuentas permitidas del diario y se impide repetir
  la contabilización o falsificar los vínculos generados mediante escritura.

El nuevo puente ``step_producers_integrations`` integra las cuotas publicadas
con la hoja de proveedores de Tesorería. Respeta la empresa, moneda, saldo
reconciliado y reversas vinculadas. Las cuotas pagadas no se vuelven a
proyectar. Una provisión de diario se identifica como contrato y conserva el
enlace a ese documento; no se presenta como una factura al asistente de lotes.

Menú de Productores
------------------

Se preservan identificadores y acciones, distribuidos en Inicio,
Planificación, Control Contratos, Control fruta, Liquidación, Maestros y
Configuraciones. La repetición de Estimaciones en la imagen no crea un
segundo acceso al mismo proceso. Los consolidados existentes permanecen
en Liquidación. Los accesos a materiales y listas de materiales utilizan
productos componentes y BOM existentes. Procesos de packing abre las OT
de Packing, mediante un puente explícito a la aplicación instalada.

Estimación de cosecha
---------------------

La respuesta humana más reciente de T38 se incorpora antes de publicar:

* Encabezado en dos columnas: identificación, productor y packing a la
  izquierda; fecha, período, fundo y temporada a la derecha. Fundo queda
  junto a Productor. Los maestros mantienen sus relaciones existentes.
* Se muestran únicamente Fecha, Fecha desde y Fecha hasta. Se retiran del
  formulario fechas duplicadas, total de kilos del encabezado y la sección
  de clasificación, etiquetas, autorización y rendimiento que el cliente
  marcó como ajena al proceso. Se preservan campos y valores históricos.
* La distribución semanal muestra total y diferencia frente a los kilos de
  la línea. Validar rechaza faltantes y excesos por cada línea de fruta;
  cantidades compensadas entre líneas no permiten aprobar una estimación.
  Una versión vigente sigue inmutable y requiere una nueva versión.

Paquete y validación
-------------------

Fuente inmutable: ``924ac1f825933c5cba9e740e1231f83d5f8d15ec``.
SHA-256: ``1112a4f36095934989c6fc15c53e9a5ca21bacb406411fb4ad26dedd127b6244``.

Versiones:

* ``step_producers``: 18.0.1.8.2.
* ``step_producer_fruit_flow``: 18.0.1.2.2.
* ``step_export``: 18.0.2.9.2.
* ``step_producers_integrations``: 18.0.1.0.0.

La copia fresca ``MANAGEMENT_QA_DEVELOPMENT_producers_1006e`` pasó 50 pruebas
con cero fallos y errores, incluyendo el acceso a la empresa activa y el cambio
de empresa. Se comprobaron 20 acciones efectivas del menú,
dominios y formularios compilados. Se ensayó también un contrato existente
del cliente: dos cuotas en USD, cuatro apuntes equilibrados y dos líneas
de Tesorería con sus vencimientos. Ese ensayo siempre termina en rollback.

El cargador informa la ausencia preexistente de ``steps_api`` y advertencias
de vistas Studio ajenas al alcance. La certificación permite únicamente ese
addon faltante ya auditado y rechaza errores nuevos.

La preservación compara todas las filas de las tablas step/account y los
maestros afectados. Para nuevas columnas nulas, normaliza únicamente los
valores JSON nulos; cualquier valor no nulo o modificación de un registro
existente sigue participando del hash. No se omiten importes ni fechas de
escritura. En la copia aislada se excluye únicamente ``web.base.url``.

El ensayo anterior 1006c detectó una diferencia de ``res_company``: el
snapshot del servicio vivo se había tomado antes de configurar el anticipo,
pero el dump se capturó después. La restauración independiente del dump
original comprobó igualdad exacta de las 563 tablas con la copia probada;
la actualización no cambió esos registros. La herramienta toma ahora la
referencia de la copia recién restaurada y compara todas las tablas en una
única sentencia SQL con una instantánea MVCC consistente. Se conserva la
evidencia anterior y se ensaya nuevamente en una copia fresca, sin omitir
campos ni sustituir los controles por resultados de pruebas unitarias.

Configuración del ejercicio
--------------------------

El cliente ya había definido la cuenta de cargo de anticipos. Se reutiliza
el producto de anticipo existente y se incorpora exclusivamente esa cuenta
a la lista no vacía de cuentas permitidas. El diario dedicado a contratos
estaba definido como compras con documentos fiscales. El ensayo demostró
que la provisión financiera requiere un diario general. La herramienta
``configure_producer_contract_advance.py`` permite reclasificar el mismo
diario únicamente si no contiene movimientos y no es un valor predeterminado
de otra función de la empresa. Conserva identificador, nombre, código,
moneda y lista de cuentas. No modifica documentos fiscales ni históricos.

Publicación
-----------

La promoción usa el mismo paquete certificado, overlay privado y bloqueo
``/run/lock/steps-environments.lock``. Comprueba las versiones y hashes de
todos los addons Steps instalados para rechazar modificaciones concurrentes.
El respaldo de base y configuración es
``/opt/steps_backups/management_development_20261006T180551Z``.
La primera entrega de Contratos conserva adicionalmente el respaldo
``/opt/steps_backups/management_development_20261006T173450Z``, con el inventario
previo a la configuración autorizada del anticipo y el diario vacío.

Se verificaron después de publicar las cuatro versiones y su origen efectivo,
el servicio activo y el acceso HTTPS. La navegación real de Productores
comprobó los siete grupos, el calendario del contrato con referencias
legibles y el acceso de procesos de packing a las OT existentes. Ajustes
contables abre la empresa activa con producto y cuenta de anticipo ya
configurados, sin iniciar otra empresa. El formulario de la estimación
existente muestra dos columnas, fechas únicas, Fundo y Temporada. Su detalle
muestra la diferencia semanal y la advertencia al no cuadrar los kilos.
Se capturó evidencia privada de los formularios, sin guardar cambios en
documentos del cliente ni contabilizar contratos en el servicio vivo.

Se publicaron mensajes breves de revisión en T30 y T38 después de comprobar
los resultados. Ambos permanecen en progreso, pendientes de aceptación del
cliente. En la estimación debe completar los maestros y distribución semanal
antes de Validar; no se inventan esos datos para aprobarla.
