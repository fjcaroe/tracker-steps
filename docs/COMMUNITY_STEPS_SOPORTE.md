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
