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
Cada operador descargó cuatro adjuntos. Una cuenta externa consultó cinco
tickets y tuvo denegada la búsqueda directa de adjuntos. El usuario público
tenía denegado el acceso al modelo. Una compañía del administrador tenía la
lista vacía. La referencia conserva las huellas de los valores, registros,
archivos leídos y decisiones, sin publicar contenido.

Desde el menú de todos los tickets, un operador creó un ticket de ensayo
con un equipo y un contacto existentes. Lo cambió a otra etapa del equipo
y volvió a abrirlo. El original asignó como referencia el número de identidad
del nuevo ticket. Se revirtió la operación y se comprobaron doce tablas,
incluidos los mensajes, destinatarios, adjuntos y permisos.

La referencia de permisos se reproduce con `run(env)` y el recorrido de
alta con `ticket_trial(env)` en `tools/community/probe_steps_support_history.py`.
Los comprobantes privados son `U44SB-steps-support-reference.json` y
`U44ST-steps-support-reference.json` en el directorio de custodia U40.

## Compatibilidad de maestros

La versión libre de OCA Helpdesk revisada usa el modelo `helpdesk.ticket`,
pero sus relaciones de equipo y etapa apuntan a `helpdesk.ticket.team` y
`helpdesk.ticket.stage`. En Steps apuntan a `helpdesk.team` y
`helpdesk.stage`. La migración debe conservar esas relaciones, los maestros
originales y las decisiones de acceso antes de habilitar el servicio en
Community. El censo y el ensayo de alta anteriores corresponden al sistema
original. [Fuente OCA revisada](https://github.com/OCA/helpdesk/tree/9fbf485f7ab7961fd06250965990523e05e00ecd/helpdesk_mgmt)
