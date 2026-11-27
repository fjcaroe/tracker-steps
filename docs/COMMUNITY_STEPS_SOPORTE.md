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
