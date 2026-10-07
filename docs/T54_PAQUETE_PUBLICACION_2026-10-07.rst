T54 paquete de actualización de Cerro El Plomo
=============================================

Autorización y alcance
----------------------

Fernando confirmó en este chat: «Sí, incluye todos los cambios que hemos
hecho, súbelos a Cerro El Plomo». Se incorporan las aplicaciones nuevas de
las áreas del ticket, además de los componentes instalados atrasados. No se
copian bases entre clientes ni se replica toda aplicación incidental de QA.

La lista versionada está en tools/ops/stack_scope.py. Incluye 26 módulos:
Tesorería batch, portada, Guías, Fletes, Exportaciones, Productores, Inventario
Packing, Operación de Packing, traslado de lotes, control de fruta, integración
con Tesorería/Packing, Costos Tracker, clasificación de tareas, trazabilidad
fitosanitaria, puente agrícola de Gestión, dependencias Tracker/Gastos y los
ocho complementos de política/nómina existentes.

Las versiones instaladas de Base, Contactos, Mail, Proyectos, Ventas, Compras,
Inventario, Contabilidad, localización chilena, exportación DTE, Flota,
Manufactura, RRHH, contratos, work entries, Payroll y Simple Digital son iguales
entre Desarrollo y Cerro. El motor Simple Digital es 18.0.1.0.0 en ambos. Las
áreas cuyo código ya coincide se conservan y se verifican, sin sustituir fuentes
con una carpeta de otro checkout ni recalcular documentos pagados.

Dependencias de Tracker
----------------------

step_tracker_usage, step_tracker_portal y step_expense_tracker provienen de
origin/codex/steps-movil, su fuente canónica, y se incorporan sin los cambios
del frontend ni sus archivos de entorno. Sus archivos de ejecución coinciden
con Desarrollo. step_expense_tracker solo difiere en una prueba de presencia
de botones, añadida después de e09d4d7e12f8e91984cf61c2c2e9f85167be22bf.
No se copian datos de Tracker ni claves. step_expense_report, ya instalado en
ambos ambientes, se conserva con su fuente existente.

Compatibilidad descubierta al probar el conjunto
-----------------------------------------------

Las pruebas de Costos Tracker ahora crean un diario general propio. No usan
un diario de cliente con restricciones de cuentas, ni modifican ese diario.
El ensayo completo anterior tuvo 17 errores de fixtures en 542 pruebas y no
se promovió. No se ocultaron los errores ni se relajaron controles contables.

Las cuentas analíticas son el maestro nativo compartido. Los campos agrícolas
fundo_id, type_costo, etapa_costo y tipo_fruta conservan sus relaciones,
selecciones y datos, pero se vuelven opcionales para permitir actividades
no agrícolas sin inventar un fundo o tipo de fruta. La adaptación vive en
step_management_costs_agriculture 18.0.2.1.1, que depende de step_hr y carga
después del dueño de esos campos. No se modifica la carpeta externa step_hr
ni se crea otro maestro. Costos Tracker 18.0.1.1.1 incluye los controles de
compatibilidad y el fixture contable independiente.

Protocolo
---------

manage_stack.py usa solo el registro de Desarrollo/Cerro. Su paquete viene de
Git e incluye manifestación SHA256 de cada archivo. Se rechazan otros módulos,
traversal, archivos agregados o alterados y downgrades. El ensayo de Desarrollo
permite una revisión ascendente de un componente; el resto del código debe
coincidir con lo ya revisado, normalizando únicamente finales de línea de
texto. Las pruebas pueden mejorar sin alterar el código instalado.

Las copias son privadas, con correo y cron deshabilitados y HTTP local con
dbfilter exacto. La compatibilidad de producción exige una copia fresca;
no reutiliza una copia con migración fallida. El modo retry-tests queda
limitado a Desarrollo, migración previa cargada, mismo código de ejecución y
misma línea de base; no permite eludir una migración fallida de producción.

Antes y después se comparan IDs, cantidades, importes y columnas originales
de tablas Steps, cuentas/movimientos, inventario, productos, nómina, flota,
ventas, compras, proyectos, fabricación, empresas y contactos. Se siguen solo
los renombres declarados de Fletes. Las columnas nuevas no reemplazan datos
antiguos. Se permiten únicamente las nuevas filas de contacto de la migración
de choferes y los flags de participante que esa migración define; los demás
valores de contactos previos se comparan. write_date/write_uid se consideran
metadatos de actualización, no cantidades comerciales.

El publicador exige certificados del paquete exacto en Desarrollo y copia
de Cerro, aplicación previa en Desarrollo y línea de base de código/config
sin cambios. Adquiere /run/lock/steps-environments.lock y rechaza otros upgrades.
Guarda dump/configuración, usa overlays privados y verifica versiones,
fuentes, formularios y flujos transaccionales. No restaura descartando datos
nuevos silenciosamente si algo falla; conserva el respaldo recuperable.

Migración acumulativa de Fletes
------------------------------

La primera copia fresca de Cerro detectó que el post-migrate 18.0.2.3.0
consultaba x_tarifa_de_fletes después de que el pre-migrate 18.0.2.6.0 ya
había renombrado las tablas. No se reutilizó esa copia para promoción.
step_operations_ui 18.0.2.7.3 incorpora un helper versionado que reconoce
tablas/campos antiguos y nativos reales; marca como transportistas solo los
contactos ya referidos por documentos. No crea contactos de fletes ni busca
coincidencias por texto. Dos pruebas cubren la estructura antigua y la
nativa, conservación de IDs, contacto no referido e idempotencia.

El snapshot admite también is_freight_carrier, además de step_chofer y
step_carga, como flags derivados de estas migraciones de participantes.
Los demás valores de contactos se conservan. La publicación guarda además
el filestore de producción junto con el dump y la configuración.

Estado
------

Base integral 7e847ac87fbfc3c4dc0bb82415706c2c4c8b1323: 625 pruebas correctas
y 47 pruebas repetidas con assertions exactas de unicidad y logs limpios;
flujos reales y conservación de registros correctos. Publicada/verificada en
Desarrollo, respaldo /opt/steps_backups/stack_development_20261007T180144Z.

Paquete final 01b03224ef5279ddc209d2157198dae274fedfe5,
SHA256 c7535dad6602964d684558c257a8b235582c828c289450868f3d5d5801be1fce.
Dos guardas operacionales y 50 pruebas de Fletes correctas en la copia fresca
STACK_DEVELOPMENT_t54stack07f. Los otros 25 componentes conservan el código
integral ya aplicado/revisado; sus formularios y flujos se repitieron con
resultado correcto, incluyendo PDF históricos de nómina. Publicado/verificado
en Desarrollo, respaldo /opt/steps_backups/stack_development_20261007T182009Z.

La segunda copia fresca de Cerro superó Fletes pero detectó dos menús de
trazabilidad que dependían de XMLIDs de Studio ausentes en el destino.
No se promovió ni se reutilizó la copia fallida. step_agro_traceability
18.0.1.0.1 vincula esos mismos menús a Operaciones y Analítica nativas de
step_bpa_irrigation, conservando sus acciones y grupos. El verificador exige
esos padres nativos y un formulario efectivo de restricciones.

Paquete de navegación 98dd4e7f8d88633c37b73f7657300eab6805d96f,
SHA256 9c78a5e9ba33d3b0ee38049856edf0a976b9a0dd735d8484641a0cfd32279808.
Validación en nueva copia STACK_DEVELOPMENT_t54stack07g: 14 pruebas de
trazabilidad correctas, menú BPA nativo y formulario efectivos, ocho flujos
funcionales repetidos y conservación de tablas originales correcta.
Publicado y verificado en Desarrollo con respaldo completo
/opt/steps_backups/stack_development_20261007T183549Z.

La copia STACK_CERRO_t54stack07g cargó todas las migraciones y ejecutó 332
pruebas: una falló por depender de una categoría de embalaje preexistente;
otra por asumir un tipo interno de picking preexistente del cliente.
No se promovió esa copia. Los fixtures ahora preparan sus datos en la
transacción de prueba, sin crear categorías, tipos o ubicaciones en el cliente.

Paquete de fixtures b893ff3e3d70e655bc171527cce8c803748ab972,
SHA256 73ee888a53d2ac505b48f766b37009fe473a711174f049e5b32b3c1dbd63486c.
El código de ejecución coincide con 98dd4e7; solo cambian los dos fixtures.
La copia fresca STACK_DEVELOPMENT_t54stack07h pasó las 27 pruebas de
Guías/Control de fruta, todos los verificadores funcionales y comparación de
registros originales. Las guardas operacionales pasaron nuevamente.
Publicado/verificado en Desarrollo, respaldo
/opt/steps_backups/stack_development_20261007T184916Z.

STACK_CERRO_t54stack07h: migraciones cargadas y 332 pruebas sin fallos ni
errores; la comparación de registros originales también pasó. El verificador
posterior de Productores asumía una categoría de embalaje ya configurada.
69182da corrige únicamente esa herramienta: valida catálogo vacío y prueba
el selector con categoría/componente nativos transitorios, revertidos al final.
El paquete b893ff3 no cambia; se repite la verificación de Desarrollo y se
certifica la misma copia de Cerro que pasó migraciones, pruebas y conservación.
No se está reutilizando una migración fallida ni saltando suites fallidas.

El verificador de portada también asumía las 20 tarjetas de Desarrollo,
incompatible con la migración 18.0.2.5.2 que conserva intencionalmente las
variantes publicadas de cada cliente. 291d815 elimina esa suposición de QA;
c3c51e4 agrega comparación exacta de XML canónico de la portada original de
Cerro contra la copia probada, exceptuando solo el contenido del h1 modificado.
Resultado: HOME_CONTENT_PRESERVED_OK, dos vistas y dos traducciones originales
conservadas. Se exige además catálogo no vacío, encabezado exacto por idioma,
versión de módulo y fuentes del paquete probado.

El flujo final de nómina detectó que instalar Packing nativo por primera vez
no ejecutaba la normalización canónica de navegación (antes aplicada por el
publicador de nómina). step_packing_batch 18.0.1.0.1 ahora depende del Packing
nativo y de la política; su XML aplica el normalizador idempotente después de
cargar ambos y lleva Traslado lotes al Despacho nativo. Las raíces anteriores
conservan sus IDs, acciones y datos bajo Historial anterior administrativo.
Dos pruebas verifican acceso del operador de Inventario, formulario, grupos,
preservación de IDs e idempotencia. No se promueve la copia anterior.

Paquete final 6a24aa400e2f4a02fc800aa40a21d574258c6187,
SHA256 98107c7b9afcb19756bc89e4aaf5eb0e675b345f115e3fa6656ebdd22b47e542.
STACK_DEVELOPMENT_t54stack07i pasó las dos pruebas nuevas de navegación,
conservación de registros y los ocho verificadores funcionales, incluyendo
traslado de lotes nativo, BPA nativo, historial y archivo de nómina.
Publicado/verificado en Desarrollo, respaldo
/opt/steps_backups/stack_development_20261007T190632Z.

STACK_CERRO_t54stack07i pasó 334 pruebas sin fallos ni errores y la
comparación de IDs/columnas/importes originales. Certificados los ocho flujos
de Fletes, Exportaciones, Packing, Recepción, Productores, Configuraciones,
Portada y Nómina; formularios efectivos de las doce áreas base y navegación
nativa de Traslado lotes/BPA. Cerro mantiene Simple Digital sin históricos
del motor anterior (cero snapshots, coherente con su línea de base); los
739 PDF históricos pertenecen exclusivamente a Desarrollo.

Publicación final en Cerro
-------------------------

Publicado y verificado el mismo paquete 6a24aa4 en CERRO_EL_PLOMO.
Respaldo completo: /opt/steps_backups/stack_cerro_20261007T191454Z
(database.dump, odoo.conf, filestore y comparación antes/después).
Overlay privado:
/opt/steps-managed/stack/cerro/6a24aa400e2f4a02fc800aa40a21d574258c6187.

Se adquirió /run/lock/steps-environments.lock; línea de base sin cambios
concurrentes y sin downgrade. Los registros originales conservaron IDs,
columnas comerciales, cantidades e importes. Se repitieron los ocho flujos,
los formularios base y la navegación nativa con muestras revertidas. Servicio
odoo18-cerroelplomo.service activo y HTTPS correcto en
https://cerroelplomo.stepsapp.cl. Resultado: STACK_DEPLOY_OK y STACK_VERIFY_OK.

La comparación de portada contra la copia certificada confirmó dos vistas y
dos traducciones originales, sin alteraciones fuera del encabezado. No hubo
comentarios humanos nuevos en T54 al comprobarlo inmediatamente antes de la
publicación. Código y herramientas guardados y subidos a la rama canónica;
los resultados privados permanecen fuera del checkout.
