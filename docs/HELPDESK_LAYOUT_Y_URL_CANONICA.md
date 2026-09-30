# Helpdesk Steps: diseño y dominio canónico

La ticketera principal usa la base `karo_consultorias` en la instancia Odoo 18
de `odoo-new` (puerto 8069). El complemento `step_helpdesk_brand` instala una
identidad visual propia en las pantallas de Helpdesk: panel, listas, kanban,
formularios, conversación, informes y configuración. El estilo del backend se
activa cuando la barra de navegación contiene menús XML de `helpdesk` o la
ruta corresponde a Helpdesk (también en móvil); otros módulos Odoo conservan
su aspecto. Las páginas de lista y detalle del portal de tickets usan la misma
paleta.

`soporte.stepsapp.cl` apunta a la misma instancia. Nginx redirige HTTP a HTTPS
y envía `/` a `/soporte`, la portada pública del canal. Desde allí se puede
crear una solicitud mediante el formulario ya publicado del equipo o entrar
con una cuenta de cliente para ver sus tickets. Las rutas antiguas de Helpdesk abiertas desde
`35.222.25.110:8069` o `stepsapp.cl` redirigen a la misma ruta y consulta en
`https://soporte.stepsapp.cl` cuando el parámetro
`step_helpdesk_brand.canonical_enabled` vale `True`. En producción está
activado desde el 27-09-2026.

La redirección se aplica a peticiones GET/HEAD antes de enviar al visitante
anónimo al inicio de sesión. Conserva la ruta y los parámetros de consulta.
Otras rutas Odoo en la IP siguen funcionando sin pasar por el dominio de
soporte. El certificado Let's Encrypt de `soporte.stepsapp.cl` se emitió el
27-09-2026 y vence el 26-12-2026; la renovación automática está habilitada.

## Verificación del despliegue del 27-09-2026

- Módulo instalado y actualizado en `karo_consultorias`; `odoo18.service`
  activo tras el despliegue.
- Panel, lista, kanban, ficha del ticket, portal y vista móvil revisados en
  navegador. SCSS y JS compilaron sin errores.
- Se probó la redirección primero en una copia aislada de la base.
- La URL antigua por IP del ticket 35 responde 301 a
  `https://soporte.stepsapp.cl/odoo/helpdesk/action-543/35`.
- La misma ruta en `https://stepsapp.cl` responde 301 al dominio de soporte.
- `http://35.222.25.110:8069/odoo` conserva su origen. El ticket en el dominio
  de soporte lleva al login HTTPS del mismo dominio cuando no hay sesión.
- El HTTP del dominio de soporte responde 301 a HTTPS.

Las notas internas del chatter siguen siendo internas: el portal solo muestra
mensajes publicados para el cliente. El estilo nuevo no cambia esa regla de
visibilidad.

## Despliegue

1. Confirmar que `soporte.stepsapp.cl` resuelve a `35.222.25.110` desde fuera
   y desde la VM.
2. Instalar primero `deploy/nginx/soporte-http-only.conf` para responder al
   desafío ACME; validar con `nginx -t` y recargar.
3. Emitir un certificado Let's Encrypt para `soporte.stepsapp.cl` usando
   `/var/www/letsencrypt` como webroot. Instalar el vhost completo, validar con
   `nginx -t` y recargar.
4. Copiar `step_helpdesk_brand` al `addons_path` de `/etc/odoo18.conf`, actualizar
   la lista de aplicaciones e instalarlo en `karo_consultorias`. Conservar una
   copia del módulo y del vhost anteriores para revertir.
5. Comprobar panel, lista, detalle, kanban, informe y páginas del portal a
   través de HTTPS, con escritorio y ancho móvil. Revisar CSS y JS cargados.
6. Activar el parámetro canónico. Comprobar que la URL antigua del ticket 35
   responde 301 con `Location: https://soporte.stepsapp.cl/odoo/helpdesk/action-543/35`;
   una ruta Odoo ajena a Helpdesk en la IP debe permanecer en su origen.

La URL pública para compartir es `https://soporte.stepsapp.cl/`. El acceso
interno de agentes continúa en `https://soporte.stepsapp.cl/odoo/helpdesk`.
Un enlace directo al ticket 35 es
`https://soporte.stepsapp.cl/odoo/helpdesk/action-543/35`.

## Mejoras de atención

La portada pública separa dos recorridos: crear una solicitud y seguir las
existentes. La ruta estable `/soporte/nueva-solicitud` encuentra un equipo que
tenga formulario publicado en el sitio actual y envía a su página de Odoo;
si se despublica, vuelve a la portada. El formulario público muestra la
identidad Steps y sus etiquetas en español sin alterar nombres de campos ni
el envío estándar de Odoo. La página de confirmación entrega el número del
ticket y los accesos para continuar.

El portal muestra un acceso a crear solicitudes tanto en la lista como en la
ficha de ticket, además de un estado vacío que orienta al cliente. En el
backend, el filtro «Sin cliente» localiza solicitudes internas y tickets sin
cliente asociado. La ficha muestra una nota informativa solo en equipos
visibles para portal: una solicitud interna, como el ticket 35 creado por el
administrador, puede gestionarse sin cliente; si corresponde a alguien con
cuenta, se puede asociar para que la siga desde su portal. Los listados,
kanban e informes comparten la paleta y el espaciado de Steps.

La creación y confirmación de tickets se comprobaron con un ticket sintético
en una base aislada. También se verificó que el filtro y el aviso están en
las vistas resueltas por Odoo, y que las páginas públicas conservan un ancho
útil en móvil.

Se corrigió el error 500 de `/my/tickets`: la personalización del estado vacío
debe conservar `t-if="not grouped_tickets"` porque la plantilla base le sigue
con un `t-else`. La vista heredada compiló correctamente en la base de
producción después de actualizar el módulo.

En el detalle del portal, el hilo de comunicación sigue mostrando los mensajes
compartidos con clientes. Si el usuario pertenece al equipo de Helpdesk y tiene
permiso de lectura sobre el ticket, la página también muestra las notas
internas con sus adjuntos, además de un acceso a la ficha de gestión. El
ticket 35 conserva sus respaldos sin exponerlos a cuentas de clientes.

Antes de actualizar el módulo en `karo_consultorias` se guardaron la base, el
módulo anterior y el vhost anterior en
`/opt/backups/odoo/2026-09-27-support-v2/` (solo accesible en la VM). La copia
aislada de pruebas se retiró después de validar el recorrido.

## Ficha interna del ticket — 28 de septiembre de 2026

La ruta `/odoo/all-tickets/35` usa ahora una cabecera Steps con el número,
título y fecha de creación del caso. Los responsables y datos de contacto
quedaron en una sección propia, y la descripción original en otra. El panel
del historial dispone de más ancho en escritorio para leer mensajes largos;
el diseño también se revisó en móvil. Se conservaron el cambio de etapa,
los campos de Studio, el historial, las notas y los adjuntos.

La actualización de `step_helpdesk_brand 18.0.1.1.5` se validó primero en una
copia aislada de `karo_consultorias`: la vista combinada contiene una cabecera,
una sección de datos y el componente de conversación, y el ticket 35 existe.
Después del despliegue, `odoo18.service` quedó activo, `/web/login` respondió
HTTP 200 y la ficha se revisó visualmente en `soporte.stepsapp.cl` en escritorio
y móvil, sin errores del navegador. La base temporal de validación fue retirada.

Respaldo previo de base, filestore y módulo:
`/opt/steps_backups/support_ticket_layout_20260928_044525/`. El ajuste final
de estilos móviles tiene respaldo adicional en
`/opt/steps_backups/support_ticket_layout_20260928_044829/`.

## Mis tickets: filtros y actividad — 28 de septiembre de 2026

La lista del portal conserva la búsqueda y los grupos de Odoo. Agrega filtros
por cada etapa que tenga tickets visibles para la cuenta, respuestas sin
revisar y modificaciones de los últimos siete días. Se puede ordenar por
última modificación, fecha de creación, prioridad, referencia, asunto,
responsable o etapa. Cada fila muestra la etapa, la última modificación y
la fecha y autor del último comentario compartido con el cliente; la fecha
de creación queda bajo el asunto.

«Respuesta sin revisar» compara el último comentario público escrito por otra
persona con el último comentario que esa cuenta había visto al abrir el
ticket. El seguimiento es individual por cuenta. En un ticket que nunca se
ha abierto desde esa cuenta, sus respuestas existentes aparecen pendientes.
Las notas internas no se usan para esta marca ni para la columna de último
comentario. La fecha de última modificación sí refleja cambios de la ficha,
incluidos los cambios internos, por lo que ambas fechas se muestran por
separado.

La actualización se probó primero en una copia aislada de
`karo_consultorias` con un usuario de portal y un ticket sintético: la lista,
el filtro por etapa, el filtro por respuestas pendientes y el orden por
modificación respondieron HTTP 200. La respuesta pública se marcó pendiente
y dejó de estarlo al abrir el ticket; el filtro dejó de incluirlo. Ese usuario
no vio el ticket 35, ajeno a su cuenta.

En producción quedó instalado `step_helpdesk_brand 18.0.1.1.6` y
`odoo18.service` activo. Se verificó en `soporte.stepsapp.cl/my/tickets` que
las etapas aparecen en el menú de filtros, que «En progreso» devuelve cuatro
tickets de esa etapa para el administrador y que la lista muestra ambas fechas.
Se revisaron escritorio y móvil; en este último la tabla indica que se puede
deslizar para leer el último comentario. El respaldo previo está en
`/opt/steps_backups/support_portal_filters_20260928_1516/` (base, filestore
y versión anterior del módulo, solo en la VM).
