# Mesa de ayuda de Steps

## Referencia del servicio original

En la restauración nativa de Steps se comprobaron los 243 tickets. Conservan
sus vínculos con dos equipos, cuatro etapas usadas, dos responsables y seis
contactos. Hay 1.795 mensajes y 418 adjuntos físicos asociados a tickets que
existen. Otros once adjuntos tienen asignado el modelo de ticket pero su
referencia no se encuentra entre los 243. Se mantienen en el respaldo.

Se probaron siete combinaciones de usuario y compañía. Los dos operadores
internos habituales abrieron la lista y el formulario de 50 campos, leyeron
17 valores y relaciones por ticket y tuvieron acceso de escritura a los 243.
Cada operador leyó el contenido de cuatro adjuntos con su cuenta. Una cuenta externa consultó cinco
tickets y tuvo denegada la búsqueda directa de adjuntos. El usuario público
tenía denegado el acceso al modelo. Una compañía del administrador tenía la
lista vacía. La referencia conserva las huellas de los valores, registros,
archivos leídos y decisiones, sin publicar contenido.

Desde el menú de todos los tickets, un operador creó un ticket de ensayo
con un equipo y un contacto existentes. Lo cambió a otra etapa del equipo
y volvió a abrirlo. Una segunda alta confirmó que el original consumió
exactamente un número de la secuencia de Mesa de Ayuda y lo usó como
referencia. En nueve tickets históricos la referencia difiere de su identidad
interna. Se conservaron las 243 referencias. Se revirtió cada operación y se comprobaron doce tablas,
incluidos los mensajes, destinatarios, adjuntos y permisos.

La referencia de permisos se reproduce con `run(env)` y el recorrido de
alta con `ticket_trial(env)` en `tools/community/probe_steps_support_history.py`.
Los comprobantes privados son `U44SB-steps-support-reference.json`,
`U44ST-steps-support-reference.json` y `U44SU-steps-support-reference.json`
en el directorio de custodia U40.

## Compatibilidad de maestros

La versión libre de OCA Helpdesk revisada usa el modelo `helpdesk.ticket`,
pero sus relaciones de equipo y etapa apuntan a `helpdesk.ticket.team` y
`helpdesk.ticket.stage`. En Steps apuntan a `helpdesk.team` y
`helpdesk.stage`. La migración debe conservar esas relaciones, los maestros
originales y las decisiones de acceso antes de habilitar el servicio en
Community. El censo y el ensayo de alta anteriores corresponden al sistema
original. [Fuente OCA revisada](https://github.com/OCA/helpdesk/tree/9fbf485f7ab7961fd06250965990523e05e00ecd/helpdesk_mgmt)

## Atención de tickets en Community

En U44H2 se instaló y actualizó el proveedor libre de seis archivos
`step_helpdesk_tickets` 18.0.1.0.1. Conservó los maestros, los dos menús
de tickets, los grupos y las reglas originales. Al comparar el primer ensayo
se encontró que cuatro tickets mostraban sus etiquetas en otro orden. El
original ordena las etiquetas por nombre, los equipos por secuencia y nombre,
y los tickets por prioridad e identidad. La versión corregida reprodujo los
tres órdenes.

Tras la actualización se comprobaron siete combinaciones de usuario y empresa.
Coincidieron el orden de las listas, los 17 valores y relaciones consultados
por ticket, la identidad de las filas editables y los archivos de muestra.
Los operadores abrieron los 243 tickets. La cuenta de portal pudo consultar
cinco y tenía denegada la modificación. El usuario público mantuvo denegada
la consulta. Un operador creó un ticket desde el menú original, consumió un
único número de la secuencia existente, cambió la etapa y reabrió la ficha.
El ensayo se revirtió y se comprobaron las doce tablas de historial.

La ficha propia muestra quince o dieciséis campos según los permisos. La
original reúne cincuenta, incluidos componentes de SLA, calificaciones,
foro y WhatsApp. La prueba anterior cubre la atención básica de tickets.
La consulta directa del modelo por la cuenta externa y el recorrido web del
portal se comprueban por separado.

Se preservaron 81 tablas de negocio y seguridad al instalar y repetir la
actualización. El esquema mantuvo sus 11.939 columnas, 5.650 restricciones
y 804 definiciones de contadores. El SHA-256 del paquete es
`00adc8a137ad753c097383a928c25a5c4bb4e5098c189c195e3fbb2805f57207`.
Los recibos privados son `U44H2-steps-support-install.json`,
`U44H2-steps-support-repeat.json`, `U44S2-steps-support-reference.json`,
`U44HC2-steps-support-reference.json` y `U44HT2-steps-support-reference.json`.

## Conversaciones y archivos del soporte original

Dos operadores internos abrieron las conversaciones de los 243 tickets con sus permisos habituales. Para cada uno se recuperaron los mismos 1.564 mensajes que devuelve el lector del hilo y los 418 archivos que muestra la ficha. Los archivos suman 49.063.343 bytes. La referencia privada compara por mensaje su identidad, contenido, autor, subtipo y adjuntos. Cada archivo se identifica por tamaño y SHA-256.

La cuenta de portal original sigue cinco tickets y es el contacto asignado a los cinco. El portal le presentó tres mensajes y las descargas de dos adjuntos por un total de 228.178 bytes. La ficha del adjunto tiene una comprobación de acceso independiente. El portal y el usuario público tuvieron denegadas las dos fichas en el modelo. El control revirtió las autorizaciones temporales que emitió Odoo al mostrar los mensajes y cotejó once tablas completas después de la consulta.

La lista nativa se abre en `/my/tickets` y tiene ruta paginada. El enlace de ficha de cada ticket se resuelve como `/my/ticket/<id>`. Existe también la variante del enlace de invitación. En el sistema original, el detalle pasa por la personalización de soporte de Steps. La prueba `probe_steps_support_thread.py` registra únicamente cantidades y huellas del contenido.

## Soporte y portal en la copia conjunta de Steps

H3 reúne los 160 módulos del producto recuperado de Ventas, CRM, Biblioteca e impresión y los dos módulos LGPL de soporte. Tickets y portal pasaron instalación y actualización. Al repetir la actualización de ambos en la versión 18.0.1.0.2 se conservaron las 313 tablas de negocio y permisos examinadas y los 15.183 objetos SQL protegidos. El cotejo incluye 11.964 columnas, 5.660 restricciones, 1.922 propietarios y permisos de relaciones y 807 definiciones de secuencias.

Los dos operadores abrieron los hilos y descargaron los mismos 418 archivos que en la referencia. La ficha conserva los autores y fechas de creación y modificación de los 243 tickets, tres equipos, siete etapas y 22 etiquetas. Coincidieron sus 1.100 valores. Una alta y un cambio de etapa con un operador confirmaron que Odoo registra al autor y la fecha de cada operación y conserva los datos de creación.

En el portal, el listado paginado en `/my/tickets` y las dos direcciones históricas de ficha, `/my/ticket/<id>` y `/helpdesk/ticket/<id>`, se probaron con sesiones autenticadas. El destinatario encontró los cinco tickets, los tres mensajes y los dos archivos que le correspondían, con sus mismos 228.178 bytes. Coincidieron la búsqueda, los ocho órdenes, las seis agrupaciones y los filtros por estado, período, asignación, etapa y prioridad. Otra cuenta y una sesión anónima tuvieron denegado el detalle de los cinco registros. En un ticket de ensayo funcionó el enlace de invitación vigente y se rechazaron el enlace inválido y el revocado. Tras la prueba coincidieron las quince tablas de control de cada copia.

Los dos módulos se identifican por los SHA-256 `327c5bc269d9ee64dab3bd49735f350300552466c046a8013566636b3e99adad` (tickets) y `4c70b5c6e9a7ddc1409fd93aece9cca5b028367c5955942ccbc579eebd223dbc` (portal). Los ocho recibos y ambos paquetes privados se comprueban con `python tools/community/verify_steps_support_suite.py <directorio>`. El SHA-256 del recibo conjunto es `7bbee05ec1426bc722570ff57a87824c130ac2ffbf1f210e5ff49b9e8d6a6c78`.

## Respaldo y recuperación de Steps con soporte

El respaldo de H3 se tomó después de terminar los ensayos funcionales de venta y facturación en borrador. El volcado final contiene 163.467 filas de 1.115 tablas y los valores y definiciones de 807 secuencias. El cotejo cubre también los 15.183 objetos SQL y el esquema completo. Su SHA-256 es `6ab22c9b15ce8074dad0e46ef9227cf935e4ebe1d7e021d7ff76e8b769a43485` para el volcado y `16b3614bf73602205bc296bcd04328369dcc547f477e9aaae1ab6fd60d5b41f4` para el esquema.

La restauración usa la custodia previa R (manifiesto `d45baa7b5c4894a31739d395b61a88f9c11a71b3edb54ecf414383b29296d3d9`) y las diez piezas del cierre H3 (manifiesto `4d50b17bdcf4cbe781c01569cbc12632e2dc114273497b56d4258ee298136dd1`). En la estación se reconstruyeron los 1.748 archivos físicos exactos con las copias allí conservadas. El contenido de todos coincidía con R, por lo que para H3 se trasladaron sólo 22.742.802 bytes. Su verificación independiente quedó en el recibo `d523ca585eb74a94bfa9cc1264df9109333ead6422fb71384cdb21e71f7d5fa8`.

La copia privada U46A se creó con el SQL final, un directorio escribible de adjuntos propio y los 162 módulos. En dos arranques separados, los operadores leyeron nuevamente los 243 hilos y sus 418 archivos. La cuenta invitada vio sus cinco tickets y descargó los dos adjuntos autorizados. Se comprobaron las restricciones de lectura y la instantánea íntegra de datos y contadores después de cada arranque. El recibo de la restauración inicial tiene SHA-256 `4cc59baa4b45404ac271cd5e5ddcd52152b83ad0633b4fe92518054d98caa937`.

Para comprobar las piezas conservadas fuera del servidor, ejecutar `python tools/community/verify_steps_support_backup.py <custodia-R> <cierre-H3> --sha256 <manifiesto-H3>`. La opción `--rebuild-filestore <carpeta-privada-vacía>` reconstruye y comprueba cada archivo. En el servidor de validación, `restore_steps_support_backup.py --sha256 <manifiesto-H3>` sólo admite como destino la copia de integración U46A y verifica el espacio de ambos volúmenes antes de crearla.

En dos arranques adicionales de U46A, Odoo confirmó la ubicación, versión y licencia efectivas de cada uno de los 162 proveedores. Los tres mensajes y las dos descargas de la cuenta invitada conservaron las huellas originales. La instantánea SQL y los archivos físicos volvieron a coincidir después de cada arranque. El recibo de esta comprobación tiene SHA-256 `8c6177caeed448f81659a48510a6cdbb18146ba293cfbf86b9c1a32c816319b7`.

## Orden del portal cuando varios tickets comparten responsable

La referencia nativa pedía al modelo ordenar por `user_id`. Los cuatro primeros tickets de la cuenta externa compartían responsable. Si se numeran los cinco tickets del ensayo por ID ascendente, el listado normal devolvía 4, 3, 2, 1, 5. Al paginar de dos en dos el propio sistema devolvía 3, 4 / 2, 1 / 5. La consulta original carecía de segunda clave de orden y estas secuencias se repitieron con tres configuraciones de planificación SQL.

El portal de Steps en la versión 18.0.1.0.3 incorpora el ID descendente como segunda clave cuando se elige «Responsable». Los cinco tickets conservan el orden nativo observado en la página completa y los mismos grupos en las páginas de dos. Se verificaron las tres páginas y su concatenación con las tres configuraciones SQL. Los recibos tienen SHA-256 `10959117c5353e17a5b02e2f279d7b3d5292d4e1fc9d3430be65ca8e86c37e1d` (original) y `cdf4e5ac4a8849eea4533f4c83932f6c173e9b8d287352f616d6b4548232fc66` (producto integrado).

El paquete de siete archivos, SHA-256 `23d61b9f8c3ed1f4e9c59f238fe38b8ff45d75b41c3035acd1dac1fc7920d68a`, se actualizó dos veces en la copia U46A de 165 módulos. El cotejo preservó 1.112 tablas completas, los 15.183 objetos SQL y los 1.748 archivos del filestore. Los cambios se limitaron a metadatos de módulo y vista y al disparador interno. La custodia de H3 conserva el paquete anterior.

Con los tres módulos fiscales y el portal 18.0.1.0.3, el recorrido HTTP de U46A coincidió con la referencia nativa en los cinco tickets, las ocho opciones de orden, seis agrupaciones, filtros, búsqueda, dos rutas de ficha y respuesta a invitaciones vigentes, inválidas o revocadas. Se comprobaron de nuevo los 418 archivos de los operadores y los dos de la cuenta invitada. Las 1.115 tablas, los 15.183 objetos SQL y los 1.748 archivos físicos se conservaron íntegros. Diez secuencias numéricas avanzaron por los registros de ensayo y se conservaron con su valor posterior. El recibo nativo tiene SHA-256 `9851776eb44ad2734a251cad40861aab9909d4aead78665b543cfe7ead736646` y el integrado `07b520bb5746f9a6eb0d1d22876e403cd42a868c18d06b969ec02047306473b1`.

## Custodia del producto integrado de 165 módulos

El respaldo definitivo de U46A reúne los 160 módulos recuperados de Ventas, CRM, Biblioteca e impresión, dos módulos de soporte y tres proveedores fiscales. El portal de soporte y el proveedor propio de facturas están en 18.0.1.0.3. Se conservaron además los 51 archivos de `l10n_cl` 18.0.3.1 y los 25 de `l10n_latam_invoice_document` 18.0.1.0. Sus huellas de árbol son `9d7de7aa6636f7f72a616171412ac0ff53bf7d6ebeab117ff03cb954e978b3b0` y `c6b2892e5cd07f111cec03798ec3cfca117dd30340d342c28eff72c3c929d2a7`.

El SQL final contiene 163.599 filas en 1.115 tablas, 807 secuencias y 15.183 objetos SQL de control. La huella de su esquema completo es `16b3614bf73602205bc296bcd04328369dcc547f477e9aaae1ab6fd60d5b41f4`. Los 1.748 archivos físicos coinciden íntegramente con la custodia anterior. La estación recibió once piezas diferenciales, 23.900.624 bytes, y verificó sus huellas junto con las de R y H3. El archivo incorpora treinta evidencias del portal, la actualización, las ventas, los documentos y las facturas. Los dieciocho recibos del contraste final de negocios se identifican por `37eb3501c72509dd7e954a2fdd839b145ad8499e5a60893db3531b4857c09bc8`.

El índice del respaldo tiene SHA-256 `347f4447e71372c279cdae51c2beb3baeb432dbdb584533818f9afc635eee772` y el volcado SQL `9d7cb6f9bbccaf3a933e021393fd43a1d8bbb9a11aa0ebf7106468b54c8c9583`. El verificador de custodia se ejecuta como `python tools/community/verify_steps_integrated_backup.py <custodia-R> <cierre-H3> <cierre-U46A> --sha256 <índice-U46A>`. El recibo de la estación tiene SHA-256 `d368d8ab27e7c7b544f9e48d9e09a28af36d3475ba241a8cce9b4b117f49024b`.

La restauración independiente U46B se realizó con PostgreSQL 12 en la estación. El entorno de ejecución requiere el suplemento `steps-fiscal-barcode-runtime.tar.gz` SHA-256 `ceb11a9bff6749120f0159f48be4bc67ac4d3d9be549291e6f7bbfcdede0e588` (451.827 bytes). Recupera las distribuciones originales de pdf417gen 0.7.1 y future 0.18.2 con sus licencias. Se cotejan además los 113 archivos de ejecución de Pillow 9.0.1. El origen y la recuperación generaron idénticos píxeles y PNG para una estampilla sintética. El primer arranque sin ese suplemento había conservado los tickets y fallado las 42 lecturas de facturas al dibujar la estampilla.

Con el suplemento verificado, dos arranques independientes cotejaron los 165 proveedores, las 42 lecturas de factura por los dos usuarios originales, los 243 hilos de soporte, los 418 adjuntos de los operadores y las dos descargas del invitado. En ambos arranques coincidieron las 163.599 filas, los 807 contadores, el esquema y los 1.748 archivos. Una vez guardada la prueba se cerró el servicio local. El recibo `U46B-cold-restore.json` tiene SHA-256 `4e9b59ded92f0a53afa13db69cde365d84251a4c86d462f3b2107c21c43b9f65`.
