T77-T79: presupuesto, planificación diaria y provisión de embarques
=================================================================

Alcance autorizado
------------------

* T77: Desarrollo, para pruebas y revisión conforme a los ocho anexos.
* T78: Desarrollo y Cerro El Plomo, confirmado por Fernando en este chat.
* T79: Desarrollo y Cerro El Plomo, según la solicitud y sus capturas.
* T76 está cancelado y no se reactiva.

Los documentos originales y sus imágenes se conservan fuera del repositorio.
No se copian adjuntos ni datos de clientes al repositorio público.

Implementación
--------------

``step_budget_design`` amplía los documentos presupuestarios existentes.
Relaciona temporada, versión, especie, variedad, actividad y origen; conserva
los textos históricos. La distribución usa fechas año-mes de la temporada,
ordenadas cronológicamente. Las hojas de cantidades y valores muestran
matrices con columnas ``YYYY-MM``; las cantidades se editan en la lista
mensual de la misma hoja. Los valores se presentan en moneda del presupuesto
y USD, separando ingresos, costos y margen. Un mes sin tasa no se presenta
como un total USD completo. Las plantillas calculan cantidad de producto,
valor total y precio por unidad; para poda, 3.000 plantas / 200 = 15 jornadas,
3.000 × 150 = 450.000 y 450.000 / 15 = 30.000 por jornada. Aplicar a cuatro
hectáreas produce 60 jornadas y 1.800.000. La aprobación exige distribución
completa y mantiene el flujo de revisiones y las protecciones del core.

El importador normalizado conserva el staging, la validación y el control de
archivos duplicados. Añade la relación al maestro de temporada, el año-mes
explícito y los montos directos sin cantidad. El importador de plantillas usa
la estructura de ``datos`` y ``distribución cantidad`` del Anexo 1.6.2.2;
resuelve nombres o códigos exactos y rechaza ambigüedades. Solo interpreta
referencias de celdas y aritmética: no ejecuta macros, vínculos ni código.
Los totales se calculan en Odoo. Las categorías de fruta se seleccionan del
maestro existente, sin inferirlas por textos parecidos.

Maquinaria tiene horas y componentes mensuales, consumo por hora, tarifa y
valores directos. La tarifa aprobada de la temporada se puede aplicar a una
labor de una plantilla. No modifica las tarifas reales del vehículo. Los
informes Data, Resumen, Jornadas, CCosto y Labor leen los mismos documentos;
el Resumen evita sumar hectáreas repetidas por cada labor. La comparación
con gastos reales mantiene la fuente contable publicada del core y usa las
fechas del maestro de temporada.

``step_producer_daily_estimate`` usa el maestro único de mercados compartido
entre Productores, Packing y Exportaciones. Mantiene Responsable como relación
a usuarios, rotulada Agrónomo, y Autoriza como relación a empleados. Tipo
fruta no se rellena por suposiciones en registros históricos. Mercado se
selecciona en la línea y las tres dimensiones están en el informe semanal.

La distribución diaria se vincula a la semana y versión originales. Reparte
las próximas tres semanas desde el lunes elegido entre cinco, seis o siete
días, con el resto de redondeo en el último día. No sobrescribe distribuciones
manuales. Los kilos por día pueden ajustarse sin exceder el total semanal.
Al reemplazar una versión, se conserva la planificación anterior. El informe
permite agrupar por día, semana, mes, bloques de seis semanas, trimestre y
año; el filtro Próximas seis semanas es móvil. Los bloques de agrupación
tienen un ancla explícita de lunes y no se confunden con ese filtro.

``step_export_shipment_provision`` registra gastos usando los maestros de
ítem productor, productos, proveedores, documentos y monedas del ERP. Su
flujo es Creado → Validado → Costeado → Contabilizado. El programa y embarque
deben coincidir en empresa, temporada, especie y recibidor. Costear guarda
los importes CLP, USD y moneda de empresa con las tasas diarias de esa fecha,
la cuenta de gasto y la cuenta de provisión configurada en el diario general.

Contabilizar genera un asiento balanceado en ``account.move``, con débito
al producto o categoría y crédito a la cuenta del diario. Se usan las
cuentas analíticas existentes de temporada y especie; la cuenta del embarque
se selecciona del maestro analítico existente en su formulario. Deben ser
tres planes distintos. No se crea ni adivina un maestro analítico por nombre.
El control transaccional y las restricciones únicas impiden duplicar el
asiento; los importes costeados no se recalculan al cambiar posteriormente
las tasas. No se crean facturas de proveedores ni se contabilizan documentos
reales de clientes durante las comprobaciones.

Validación y publicación
-----------------------

Cada módulo se empaqueta desde blobs Git con versión y SHA por archivo. Los
tipos de entrega ``budget-design``, ``daily-estimate`` y ``shipment-provision``
usan el publicador canónico con copias privadas, pruebas funcionales,
comparación de filas originales, bloqueo compartido, respaldo y overlay
privado. T77 rechaza cualquier destino distinto de Desarrollo.

El cierre requiere pruebas aprobadas, fuente y versión instaladas, menús y
formularios efectivos, y flujo con el perfil previsto en los destinos
autorizados. El resultado de cada publicación y las rutas de sus evidencias
se registrarán aquí una vez verificados. No se cierra por commit o HTTP 200.

T78 publicado y verificado
-------------------------

``step_producer_daily_estimate`` 18.0.1.0.1, commit
``4aae93ecd5d17f66719b275968afe9ef14269a69``, SHA-256 del paquete
``56346746f4e231dec6b5439b7c6836fd3239998976696ea5f6aa44013206ac0b``.
Seis pruebas aprobadas por destino y comprobación adicional del flujo con
el perfil de planificación, incluidos menús, formulario, generación diaria,
ajustes manuales y activación de una versión sucesora.

* Desarrollo: evidencia ``management_development_t78_4aae93e_dev``;
  respaldo ``/opt/steps_backups/management_development_20261013T180139Z``.
* Cerro: evidencia ``management_cerro_t78_4aae93e_cerro``;
  respaldo ``/opt/steps_backups/management_cerro_20261013T180738Z``.

Los overlays de ambos destinos usan ese mismo commit bajo
``/opt/steps-managed/releases/<ambiente>/``. Se comprobaron servicios y
dominios HTTPS después de las verificaciones funcionales.

T79 publicado y verificado
-------------------------

``step_export_shipment_provision`` 18.0.1.0.0, commit
``d495b23fb5a00af060895b0c5df76b95376d0e74``, SHA-256 del paquete
``dbd01d26a795ee66403ee0d6695d5c8da818fbb0a219e627df97dc0ca5045add``.
Seis pruebas aprobadas por destino, preservación de filas y comprobación
adicional con un usuario de Contabilidad. El ejemplo temporal de 100 USD
a 900 CLP/USD genera un asiento de 90.000 CLP balanceado. Las tres cuentas
analíticas se conservan en sus columnas nativas dentro de un solo apunte,
sin triplicar el gasto. Se verificaron el bloqueo de cambios, la tasa
conservada y la prevención de un segundo asiento.

* Desarrollo: evidencia ``management_development_t79_current_f``;
  respaldo ``/opt/steps_backups/management_development_20261013T185246Z``.
* Cerro: evidencia ``management_cerro_t79_current_cerro_f``;
  respaldo ``/opt/steps_backups/management_cerro_20261013T185921Z``.

La compañía del ejemplo se revierte al finalizar. Su creación evita la
carga automática de una localización contable; las acciones de validación,
costeo y contabilización se ejecutan con el contexto y permisos normales.

T77 publicado y verificado
-------------------------

``step_budget_design`` 18.0.1.0.0, commit
``1c5635bb68f4f2bfa51034b5b189779a83ea74f1``, SHA-256 del paquete
``0e30b7688b0a0f792c366ba61d2999b3e818f6fbc2c671b33cc1d90e47094539``.
Once pruebas aprobadas en la copia de Desarrollo, incluida la matriz de
meses reales, las fórmulas de poda/cosecha, la aplicación por hectáreas,
distribución completa, duplicación, aprobación y nueva versión. También
se probaron monto directo, carga normalizada de dos meses sin cantidad,
carga de plantilla equivalente al anexo, maquinaria, reportes y perfiles.

La comprobación instalada repitió el flujo de generación, aprobación y
creación de una nueva revisión con un usuario de Gestión y Costos. Se
verificaron los formularios, los siete menús de entrega y las columnas
año-mes de las matrices, sin alterar los registros anteriores.

* Desarrollo: evidencia ``management_development_t77_final_j``;
  respaldo ``/opt/steps_backups/management_development_20261013T190726Z``.

El código permanece en un overlay privado del mismo commit. No se publicó
este módulo en Cerro ni en otro destino fuera del alcance del ticket.
