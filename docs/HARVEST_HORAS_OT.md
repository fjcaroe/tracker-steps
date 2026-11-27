# Harvest — T244 y T245

Harvest web 0.0.12 y `step_harvest_launcher` 18.0.1.7.0 se entregan juntos
en Desarrollo, Cerro y QA-Cerro. La publicación conserva la política de caché
de `HARVEST_CACHE_VERSIONES.md` y las colas por base, usuario y empresa.

La nueva OT selecciona `step.cosecha.ubicacion` del fundo elegido, pasada
entera positiva y tipo exportación/industrial. Usa los campos existentes
`cosecha_ubi_id`, `qty_pasada` y `type_cosecha`. Cambiar de fundo limpia la
ubicación. Los pendientes anteriores sin estos datos conservan su flujo;
no se completa ni reescribe el histórico durante la actualización.

El cierre captura inicio, fin y horas efectivamente trabajadas por persona.
Puede descontar pausas dentro del intervalo. La jornada objetivo procede de
`res.company.harvest_hours_per_day`, inicialmente ocho horas y configurable
en Cosecha. La primera asignación fija ese total para el día de esa cuadrilla.
Se muestran horas asignadas y saldo; marcar última OT utiliza el saldo y exige
el 100%. Se rechazan superposiciones, exceso, otra OT abierta y una jornada
ya cuadrada. Para corregir una asignación anterior debe reabrirse primero la
última OT. La OT enviada conserva su cierre.

Las horas se guardan en la OT y sus líneas nativas `registry_line.hrs` o
`registry_tarja_line.hrs`, con los trabajadores presentes en asistencia de
Cosecha o los integrantes nativos cuando aún no hay asistencia, y participantes
de las entregas. No crea asistencias, entradas de trabajo ni nómina. No modifica
horas manuales existentes ni duplica líneas al reintentar. La asignación usa un
bloqueo transaccional de la cuadrilla además del bloqueo nativo de la OT.

Certificar con `manage_management.py --kind harvest-app`, usando un run ID
`t244245_<commit8>` en copias frescas de los tres destinos. Ejecutar
`smoke_harvest_operations.py` (incluye `smoke_harvest_work_hours.py`), la prueba
de cuadrilla y `check_harvest_weight_ui.cjs` sobre el proxy de copia autorizado.
`check_harvest_hours_flow.cjs` usa el usuario y zona horaria existentes, habilita
un integrante nativo en el equipo y prueba crear, registrar, cerrar con horas,
aprobar, enviar y recargar desde la interfaz. Conserva capturas móviles y verifica
las líneas de costo originales. Las referencias largas deben ajustarse al ancho.
En Cerro y QA-Cerro seleccionar explícitamente `--company-id 1`, Agrícola Cerro
El Plomo SpA. La empresa holding predeterminada del perfil técnico no contiene
la operación de Harvest. La revisión usa empresas y permisos ya autorizados,
sin cambiar la empresa predeterminada del usuario ni los datos de capacitación.
El publicador requiere además las respuestas 10692 y 10696 y las evidencias
de campos, pasada obligatoria, cierre, reparto y líneas de costo. Publicar el
mismo paquete probado primero en Desarrollo, con respaldo, bloqueo compartido,
ausencia de downgrade y conservación del aislamiento de QA-Cerro. Revisar
versión, menú, formulario y flujo en los tres destinos antes de cerrar tickets.

## Entrega comprobada — 27-11-2026

Publicado el mismo backend `6275030a` (launcher 18.0.1.7.0 y operación 18.0.1.2.0)
y web `244cb47` (0.0.12) en Desarrollo, QA-Cerro y Cerro. Pasaron 91 pruebas nativas
en cada copia, 72 pruebas web y los flujos de enrolamiento, entregas, reparto de
jornada, costo nativo, cierre, aprobación, envío y recarga desde el cliente real.
Los dominios HTTPS mostraron 0.0.12 y el formulario nuevo. La revisión publicada
consultó datos y formularios, y conservó los datos de negocio.

Los publicadores conservaron respaldos, bloqueo compartido, ausencia de downgrade,
validadores de caché corregidos y paridad de archivos entre Cerro y QA-Cerro. La
verificación final confirmó el aislamiento de QA-Cerro. Se retiraron las sesiones
y servidores temporales de revisión. Los tickets 244 y 245 quedaron resueltos
con cambio de estado silencioso, comprobando ausencia de nuevos mensajes,
notificaciones y correos.

La cuadrilla productiva de Cerro necesita integrantes asignados antes de registrar
la jornada. Su certificación incluyó enrolamiento en la copia; la publicación
conservó el maestro operativo existente.
