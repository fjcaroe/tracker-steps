# T92 · Inspección SAG en Desarrollo

Entregado el 18-10-2026 (Chile) para QA humano, exclusivamente en Desarrollo.
Ticket cerrado en etapa 4 con nota interna 9505, sin destinatarios ni notificaciones.

## Paquete publicado

- Módulo `step_packing_sag`, versión `18.0.1.0.1`.
- Commit del paquete: `5efdb14ef0eb8431f14da7006eef778d80571a14`.
- SHA-256: `de2252fce1c04fc7b784f02dca257200f9a327163a317182cc4869d921dcb94d`.
- URL: <https://desarrollo.stepsapp.cl/odoo/action-2238>, base `LAB_TAREAS`.
- Ruta funcional: Packing / Inspecciones / Inspección SAG.
- Overlay privado: `/opt/steps-managed/releases/development/5efdb14ef0eb8431f14da7006eef778d80571a14/`.
- Respaldo previo: `/opt/steps_backups/management_development_20261019T010411Z`.
- Prueba en copia: `MANAGEMENT_QA_DEVELOPMENT_t92ui`.
- Evidencia de copia: `/opt/steps-validation/management_development_t92ui/qa_passed.json`.

La publicación utilizó el mismo archivo probado, bloqueo compartido de ambientes,
validación de versiones y código cargado, y preservación de datos de negocio.
No se publicó en Cerro El Plomo ni en otra producción.

## Comportamiento entregado

Extiende la inspección nativa de Packing y enlaza OT, tarjas, país, especie,
productor, packing, inspector y contraparte con los registros existentes. El menú
de inspecciones internas conserva su acción y flujo. Los registros previos no se
convierten artificialmente en inspecciones del prototipo.

Incluye controles de preparación documental y física, requisitos consultados,
solicitud y horario externos, muestreo, laboratorio, tratamientos, resguardo,
SIF/libro foliado y archivos de respaldo propios. Un administrador de Inventario
registra aprobación o rechazo externos. La aprobación exige preparación conforme,
tratamiento resuelto, solicitud, muestreo y respaldo. El rechazo exige su causal.

Pendiente de laboratorio bloquea el despacho para el destino. Exige registrar la
comunicación del resultado antes de aprobar; no se puede eludir restableciendo la
fase o eliminando una inspección con servicio solicitado/pendiente. La
reevaluación crea otra inspección, sin heredar solicitud ni archivos. Una
aprobación anterior no habilita una reevaluación pendiente. Se conservan también
los bloqueos nativos de despacho.

La revisión visual detectó y corrigió el dominio circular del selector de OT: la
empresa de la inspección se obtiene de la propia OT y estaba vacía antes de
seleccionarla. El formulario ahora busca entre empresas activas y no permite
crear accidentalmente una OT desde el selector.

## Validación

Cuatro casos funcionales, sin fallos ni errores, en la copia fresca del destino y
nuevamente en el registro instalado, con transacciones descartadas:

1. Cierre real de OT y movimientos de inventario; preparación, solicitud,
   laboratorio, aprobación, destino y reevaluación pendiente.
2. Rechazo, evidencias obligatorias, cantidad de muestra y tratamiento.
3. Permisos de revisión, aislamiento entre empresas y validaciones de datos.
4. Inspección interna, menú, vistas y selector de OT por empresas activas.

Navegador: menú y lista, formulario nuevo, selección de `PRUEBA/OT/01`, especie y
productor relacionados, selección de una de sus tarjas resultantes y las cuatro
pestañas. La inspección visual no se guardó y se descartaron sus cambios. No se
registraron resultados SAG ficticios en los datos de negocio del servicio.

Se conservaron las advertencias preexistentes de vistas Studio y la dependencia
ausente `steps_api`, ya inventariadas antes del cambio; no impidieron los casos.
El modelo histórico `step.packing.inspection.sag` y la inspección nativa tenían
cero registros en el inventario previo. No se eliminaron tablas ni dependencias.

Evidencias privadas en `~/.codex/local-artifacts/t92-20261018/`:
`visual-review.json`, `development-qa.json`, `development-deploy.log` y capturas
de menú, lista, formulario, preparación, muestreo, tratamientos y resultado.
Los adjuntos originales y paquetes permanecen fuera del repositorio público.

## Alcance del prototipo

Fuente: PDF y DOCX adjuntos a T92. Referencia principal: Manual para Externos del
Programa Origen SAG v04, 10-07-2024, §§6.3–6.5 y 6.10, anexos 2 y 7.
Una inspección comprende una OT, un conjunto de tarjas y un país; una SIF oficial
con varios destinos requiere registros separados en este prototipo.

No agenda servicios, integra sistemas SAG, firma SIF ni emite certificados
fitosanitarios. No calcula aceptación sanitaria, niveles/tolerancias de mercado
ni prescribe tratamientos. Los requisitos vigentes y decisiones se verifican
ante SAG; el usuario registra la fuente y fecha de consulta. El prototipo queda
disponible para revisión humana en Desarrollo.
