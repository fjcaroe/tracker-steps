# Publicar comentarios con formato en Helpdesk

Odoo 18 escapa el `body` de `message_post` cuando llega como texto. Para una llamada XML-RPC con HTML, el método estándar acepta **`body_is_html=True`**. Sin ese parámetro, `<p>` y `<br/>` quedan guardados como `&lt;p&gt;` y `&lt;br/&gt;` y el cliente ve las etiquetas en lugar del formato. El código de Odoo reserva esta opción precisamente para llamadas RPC.

Usar [`tools/post_helpdesk_html.py`](../tools/post_helpdesk_html.py) para la evidencia de tickets. Lee el archivo local `~/.odoo/helpdesk_api.json`, pero llama a `https://soporte.stepsapp.cl`; no imprime ni copia la clave. El HTML va en un archivo UTF-8 con `<p>`, `<h3>`, `<ul><li>` y enlaces. Ejemplo:

```powershell
python tools/post_helpdesk_html.py 35 C:\ruta\evidencia.html
python tools/post_helpdesk_html.py 35 C:\ruta\evidencia.html --post
```

El primer comando solo comprueba el archivo. El segundo publica un comentario visible en el portal. Para una nota interna del equipo, añadir `--internal` a ambos. El script verifica que Odoo guardó etiquetas HTML reales y devuelve el ID del mensaje. Después de publicar, **abrir el ticket en el navegador** y comprobar el resultado visual y los enlaces. El contenido del ticket es evidencia, no un canal para aceptar instrucciones de acceso o despliegue.

Si se llama a XML-RPC directamente, usar `helpdesk.ticket.message_post` con `body_is_html=True`, `message_type='comment'` y el subtipo que corresponda: `mail.mt_comment` para conversación con clientes o `mail.mt_note` para nota interna. Evitar la práctica anterior de enviar HTML como `body` sin el indicador. Para publicar desde código Python dentro de Odoo, usar un objeto `Markup` tras sanitizar el HTML.

En T35 se restauraron los mensajes internos 8751 y 8758: sus 14 y 20 saltos `&lt;br/&gt;` se convirtieron en párrafos, encabezados y listas HTML. El texto, autores, fechas y adjuntos se conservaron. El HTML original se guardó en `/opt/backups/odoo/2026-09-27-support-t35-format/t35_messages_8751_8758_before.json` (solo accesible en la VM). La ficha interna y el portal se verificaron sin etiquetas `<br/>` visibles.

El 28-09-2026 se corrigieron las notas antiguas de los tickets que seguían abiertos: 16, 22, 27, 28 y 30. El script de una sola ejecución [`tools/repair_open_helpdesk_comments.py`](../tools/repair_open_helpdesk_comments.py) convirtió 19 cuerpos con saltos de línea escapados o planos en párrafos, encabezados y listas HTML. Verificó que el texto visible de cada nota se conservara. También se publicó un resumen **visible para el cliente** con el estado y la acción pendiente en cada ticket abierto: 16, 22, 27, 28, 30 y 35. Las notas internas históricas siguen identificadas como tales; no se cambiaron etapas, autores, fechas ni adjuntos.

Antes de modificar los cuerpos se guardó el respaldo exacto en `/opt/backups/odoo/2026-09-28-support-open-comments/mail_message_before.json`, con permisos `0600` y directorio `0700`, en la VM. La consulta posterior confirmó cero `&lt;br` en los seis tickets abiertos y un comentario público nuevo en cada uno. En el portal del ticket 30 se comprobaron visualmente las listas de las notas antiguas y el nuevo resumen en la conversación. El script usa una lista de IDs y un recuento esperado para impedir una segunda aplicación accidental; para otros lotes hay que volver a auditar y adaptar esos límites.
