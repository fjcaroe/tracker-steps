# Notas legibles en la ticketera por XML-RPC

Odoo 18 **sí acepta HTML** en notas publicadas por XML-RPC. Su método
`helpdesk.ticket.message_post` escapa por defecto el parámetro `body` cuando
llega como cadena: `<p>Texto</p>` termina visible literalmente. Para indicar
que el contenido es HTML hay que enviar `body_is_html=True`. Odoo aplica su
sanitización habitual antes de guardar la nota.

Usar [scripts/post_helpdesk_note.py](../scripts/post_helpdesk_note.py) para
las próximas notas internas:

```powershell
python scripts/post_helpdesk_note.py 35 --html-file .\nota.html --attachment .\evidencia.pdf
```

El archivo HTML debe estar en UTF-8. La herramienta toma la configuración de
`~/.odoo/helpdesk_api.json`, adjunta los archivos al ticket, publica una nota
interna (`mail.mt_note`) y comprueba que el HTML y los adjuntos quedaron en
`mail.message`. No escribir claves ni tokens en la nota o en el repositorio.

Para una explicación clara al cliente, usar un título, párrafos breves, listas
para los cambios y comprobaciones, y enlaces con texto descriptivo. Si la nota
debe ser visible en el portal del cliente, revisar el destinatario y el subtipo
antes de publicar: `mail.mt_note` es una **nota interna**.

## Corrección aplicada al ticket 35

La nota `mail.message` **8759** se había publicado sin `body_is_html`; Odoo
guardó las etiquetas escapadas y la interfaz las mostró como texto. Se
reescribió el cuerpo de esa misma nota con HTML renderizable, texto más claro
y acentos UTF-8. Se conservaron sus adjuntos **3066** (acta) y **3067**
(logo), su asociación al ticket 35 y el estado del ticket.
