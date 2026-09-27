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
y envía `/` a `/odoo/helpdesk`. Las rutas antiguas de Helpdesk abiertas desde
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

La URL principal para compartir es
`https://soporte.stepsapp.cl/odoo/helpdesk`. Un enlace directo al ticket 35 es
`https://soporte.stepsapp.cl/odoo/helpdesk/action-543/35`.
