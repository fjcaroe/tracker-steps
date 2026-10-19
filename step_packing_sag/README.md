# T92 · Prototipo de inspección SAG

Solo Desarrollo, solicitado para QA. Extiende `step.packing.inspection` y reutiliza
Packing / Inspecciones / Inspección SAG. No crea maestros paralelos ni reemplaza
los registros históricos de `step.packing.inspection.sag` o Studio.

Referencia funcional: adjuntos del ticket 92, Manual para Externos del Programa
Origen SAG, versión 04 de 10-07-2024, §§6.3, 6.4, 6.5, 6.10 y anexos 2/7;
el DOCX adjunto aporta el esquema de controles. No se declara vigencia normativa
actual ni se codifican automáticamente tolerancias por mercado.

1. Crear una inspección con OT, tarjas, inspector, contraparte y un país.
2. Documentar requisitos y fecha de consulta; verificar documentación,
   habilitaciones/exclusiones, sala, presentación y embalaje. Resolver tratamiento.
3. Validar preparación. Registrar solicitud y horario obtenidos fuera de Odoo.
4. Registrar criterio, unidades y hallazgos del muestreo. Si corresponde, identificar
   la muestra/informe de laboratorio y dejar pendiente; conservar resguardo.
5. Adjuntar respaldo propio, identificar SIF/libro y folio externo. Un administrador
   de Inventario registra el resultado comunicado por SAG. Rechazo exige causal.
   Aprobar exige controles conformes, tratamiento resuelto y muestreo registrado.

La aprobación bloquea edición y eliminación mediante las reglas nativas. Para
reevaluar se crea otra inspección; las copias no heredan evidencias ni solicitud.
Una reevaluación pendiente impide reutilizar la aprobación anterior para ese país.
El despacho no acepta el prototipo para un destino diferente. Se conservan además
los bloqueos de inspecciones nativas existentes.

Cada registro corresponde a una OT, un conjunto de tarjas y un país. Una SIF oficial
puede comprender varios países: el prototipo no representa ese documento completo.
No agenda servicios, firma SIF, identifica plagas, prescribe tratamientos ni emite
certificados fitosanitarios. Las habilitaciones, condiciones por país y decisiones
deben comprobarse con SAG. Las inspecciones previas conservan su flujo histórico.

QA automatizado: cierre real de OT con movimientos de inventario, preparación,
solicitud, laboratorio, aprobación/rechazo, respaldo, tratamiento, destino,
reevaluación, permisos, compañías y separación de inspecciones internas.
