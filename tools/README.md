# Herramientas de trabajo

- `git/verify_handoff.py`: comprueba cambios pendientes y publicación de la rama.
- `git/test_verify_handoff.py`: pruebas aisladas del comprobador, sin acceso al servidor.
- `helpdesk/download_attachments.py --ticket ID`: descarga mediante consultas RPC; configuración privada en `~/.odoo/helpdesk_api.json`, destino fuera del checkout. No envía mensajes ni modifica tickets.
- `documents/map_docx_pages.py ARCHIVO.docx`: inspecciona texto y saltos de página almacenados en un DOCX. Requiere lxml; no sustituye la revisión visual del documento.
- `qa/check_steps_public_apps.py`: consulta las URLs públicas y escribe resultados en stdout. Redirigir la salida a un directorio de artefactos externo.

Las herramientas de cada producto están en sus ramas. `tools/history/` conserva
procedimientos de una fecha concreta; no usar esos scripts como un despliegue
vigente. Revisar el README correspondiente antes de ejecutarlos.
