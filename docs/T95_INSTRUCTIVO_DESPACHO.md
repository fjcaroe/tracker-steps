# T95 Mejoras del instructivo de despacho

Estado al 20-10-2026: versión 18.0.1.0.1 instalada y comprobada en Desarrollo.
Cerro El Plomo conserva su versión anterior. T95 está En espera por revisión web
pendiente; nota interna 9531, sin destinatarios ni notificaciones.

## Solicitud e implementación

Ticket 95, comentario 9530 y adjunto 3372. Se solicitaron Desarrollo y Cerro.
La extensión `step_packing_dispatch_improvements` hereda el instructivo nativo
`step.export.dispatch.order` y conserva sus IDs, líneas, filtros y maestros.
No sustituye el instructivo de embalaje ni el instructivo de embarque.

DUS, país, puerto de destino y agente de aduana proceden del embarque vinculado;
el código procede del contacto existente. Son referencias de lectura en el
instructivo y se mantienen en sus maestros originales. El transportista usa el
catálogo existente de contactos de carga y se propone al crear la guía.

Cada rol de exportación conserva su indicador y recibe un código independiente
que admite ceros iniciales: recibidor, naviera/aerolínea, consignatario, notify,
agencia de carga y agente de aduana. No se crean tablas paralelas ni se asignan
códigos inventados a contactos antiguos.

El formulario incorpora `mail.thread`, actividades y chatter estándar para
mensajes, correos y adjuntos. La entrega no envía correos de prueba.

PDF y XLSX se titulan Instructivo de despacho. Incluyen los campos del
encabezado, las doce columnas de carga y los cinco resúmenes: pallets por
camión, cantidad de camiones, pallets, cajas y kilos. El PDF horizontal repite
columnas en páginas siguientes. Excel conserva cantidades numéricas y trata
los textos como literales, sin interpretarlos como fórmulas ni enlaces.
El archivo Excel queda como adjunto privado del instructivo. Las acciones
comprueban el acceso y conservan las reglas por empresa existentes.

## Paquete final y pruebas

Commit: `6811c613d01d1ee5c48686074ad937ad7fb65f49`.
SHA-256: `f2c38d352d74883a0367ba610da73bc6b4fad210ad33c478ba040a0a5edf22e6`.
Versión: `step_packing_dispatch_improvements` 18.0.1.0.1, ocho archivos de módulo.

El paquete exacto pasó cuatro pruebas sin fallos/errores y cuatro comprobaciones
funcionales en cada copia fresca:

- Desarrollo: `MANAGEMENT_QA_DEVELOPMENT_t95d`.
  `/opt/steps-validation/management_development_t95d/qa_passed.json`.
- Cerro: `MANAGEMENT_QA_CERRO_t95d`.
  `/opt/steps-validation/management_cerro_t95d/qa_passed.json`.

Se compararon todas las columnas anteriores de las tablas de negocio, excluyendo
únicamente columnas nuevas. No se borran ni reinterpretan los históricos.
Las copias privadas tienen correo y cron desactivados y HTTP en localhost.
Desarrollo conserva su condición de único QA público.

Las pruebas verifican origen de los encabezados, transportista propuesto en la
guía, códigos por rol, nota interna con adjunto sin notificaciones, ambos
reportes y denegación entre empresas. El probe adicional renderiza PDF y XLSX
reales con ochenta líneas añadidas a la original y descarta la transacción.
Se inspeccionaron las dos páginas del PDF final de la copia de Cerro: encabezado
corporativo completo, columnas repetidas, última línea y resumen presentes.
Excel tiene doce columnas, cantidades numéricas, altura de fila para textos
envueltos y ninguna celda de fórmula.

Las copias anteriores detectaron y permitieron corregir un widget QWeb en una
celda, la apertura del asistente corporativo en vez del PDF y el recorte del
encabezado corporativo. La acción final usa `config=False`, conservando la
configuración de empresa; el papel reserva 40 mm arriba y 18 mm abajo, con
10 mm de separación de encabezado. Ninguna copia fallida acredita esta entrega.

## Publicación en Desarrollo

URL: <https://desarrollo.stepsapp.cl>.
Base: `LAB_TAREAS`. Servicio: `odoo18-dev.service`, activo.
Overlay privado:
`/opt/steps-managed/releases/development/6811c613d01d1ee5c48686074ad937ad7fb65f49/`.
Respaldo: `/opt/steps_backups/management_development_20261020T171010Z`.
Se utilizó `/run/lock/steps-environments.lock`, sin downgrade ni actualización
concurrente. El mismo archivo probado se publicó, sin sustituir raíces de addons
compartidas. La comprobación posterior confirmó versión, origen, formularios y
menú efectivos, los cuatro casos funcionales y ambos reportes, con rollback.

La versión previa 18.0.1.0.0 se instaló transitoriamente solo en Desarrollo,
con respaldo `/opt/steps_backups/management_development_20261020T162235Z`.
Quedó reemplazada por 18.0.1.0.1. No se instaló ninguna versión de T95 en Cerro.

## Revisión pendiente y continuación

La herramienta local de navegador falla antes de enumerar pestañas con
`failed to write kernel assets` y un error de ruta inexistente. Ocurre también
tras reiniciar el runtime y en la alternativa Windows. Esto no acredita un
problema de acceso a Odoo. No se declara revisado el formulario en navegador
ni se cierra el ticket por la comprobación del registro o un HTTP correcto.

Al recuperar la herramienta:

1. Abrir Packing / Despacho / Instructivo de despacho en Desarrollo. Comprobar
   campos de encabezado y botones PDF/Excel con un instructivo existente.
2. En Contactos / Exportación, revisar los seis códigos, junto a sus roles.
   No rellenar datos reales solo para obtener una captura.
3. Revisar chatter estándar y adjuntos sin enviar correos externos de prueba.
4. Comprobar el transportista propuesto en Crear guía, sin guardar guías ficticias.
5. Incorporar respuestas humanas nuevas antes de continuar. Promover el paquete
   exacto probado a Cerro con respaldo y bloqueo; si cambió el baseline del
   destino, repetir compatibilidad en copia fresca. La solicitud ya incluye
   Cerro; el pendiente es la verificación, no una nueva solicitud de permiso.
6. Comprobar versión, menú, formulario y flujo allí antes de cerrar T95 mediante
   nota interna sin notificaciones.

Herramienta remota: `/tmp/t95-instructivo-20261020/manage_management.py`.
Tipo: `--kind dispatch-improvements`. Paquete final: `release-d.tar.gz`.
Corrida definitiva: `t95d`; acciones `qa`, `compatibility`, `deploy`, `verify`.

Los adjuntos, respuestas, inventarios, archivos de prueba, capturas PDF, paquetes,
logs y comprobantes están fuera del repositorio en
`~/.codex/local-artifacts/tickets-heartbeat-20261020-1303/`.
