# Contactos: creación manual sin créditos de autocompletado

Solicitud del 28-10-2026: quitar el aviso de créditos al crear proveedores en
Cerro El Plomo y QA-Cerro, con revisión previa en Desarrollo.

`step_partner_manual_entry` 18.0.1.0.0 (AGPL-3) utiliza el addon Community
`partner_autocomplete` como punto de extensión, sin modificar sus fuentes.
Los campos de nombre y RUT usan los widgets nativos. Las relaciones a contactos
usan el selector local estándar con búsqueda, creación rápida y Crear/Editar.
Se desactiva la consulta de sugerencias y enriquecimiento externo desde estos
flujos, además del enriquecimiento automático de la empresa al iniciar sesión.
No se compran créditos ni se alteran tokens, claves o permisos.

La validación y normalización tributaria chilena se conservan. El prefijo de
país del ejemplo del mensaje estándar no obliga a ingresar CL en el RUT local.
El usuario corrigió el dígito verificador y creó el proveedor; el registro se
comprobó por lectura y no se modifica como parte de esta publicación.

Paquete inmutable: `3d32806fcdda54c7bf913467a8f3be51f21dc992`.
SHA-256: `2fc02dea0872939b917f76d86f12ff161564adbe57ec58f0159dd63fd4784a17`.

Las pruebas cubren el formulario real de compañía, guardado de proveedor,
búsqueda de contactos existentes y ausencia de llamadas a IAP. La API de
contacto externo se reemplaza por una excepción durante las pruebas para
fallar si se intenta usarla. La comprobación funcional usa perfiles existentes
sin elevar permisos, verifica menú/formulario y compila el asset efectivo.
Los contactos de prueba se crean únicamente en copias y se revierten.

El paquete `manual-contact` se limita a Desarrollo, Cerro y QA-Cerro, con
copias frescas, respaldo, bloqueo compartido, guardas de concurrencia y overlays
privados. QA-Cerro conserva sus datos y aislamiento, sin refrescar su base.

Al terminar la publicación, recargar la página permite que una sesión abierta
cargue el selector nativo del nuevo paquete.
