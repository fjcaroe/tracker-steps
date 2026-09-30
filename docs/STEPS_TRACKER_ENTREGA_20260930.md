# Steps Tracker: entrega de software del 30-09-2026

Implementación de `IMPLEMENTACION_STEPS_TRACKER_LAYOUT_Y_PROTECCION.md` en la rama
`codex/web-tracker-redesign`. El documento original incluye aceptación de hardware
y piloto de campo: esos criterios no se acreditan con este release de software.

## Alcance

- Portal React en `/web_tracker/` para Desarrollo, Demo y Cerro El Plomo. Inicia
  en datos reales; el laboratorio sintético se activa explícitamente. Operación,
  Control de flota y Protección comparten búsqueda AND, filtros, selección y métricas.
- Se conserva `OperationsMap`. Los marcadores antiguos indican su fecha; un punto
  atrasado recibido ahora no demuestra movimiento actual. Alta, registro GPS y
  recepción se muestran como fechas diferentes.
- Preferencias versionadas por cliente/usuario, columnas permitidas en API;
  la demo guarda preferencias locales y simula incidentes únicamente en memoria.
- Dominio GPS independiente de sesiones laborales: clientes, activos, dispositivos,
  asignaciones históricas, posiciones idempotentes, políticas, incidentes y auditoría.
  El estado actual es una proyección reconstruida desde posiciones; todavía no se
  materializa una tabla `device_state`. No se atribuyen datos históricos por similitud
  de nombres, patentes o identificadores de bases distintas.
- `/v1` usa identidades Odoo firmadas por servidor, de 60 segundos, con un emisor
  por base y correspondencia explícita base/compañía → cliente. El navegador no
  recibe claves ni tokens administrativos; las escrituras pasan por CSRF de Odoo.
  Los endpoints históricos conservan su autenticación y semántica anteriores.
- Armado continuo; reglas de movimiento/ACC fuera de horario UTC, geocerca circular,
  alimentación, SOS y falla de comunicación. Horario/geocerca están en el contrato
  API; el formulario de esta entrega permite armado continuo y contactos de referencia.
- Avisos en bandeja y expediente con reconocimiento/cierre motivado. El envío externo
  a email/SMS/WhatsApp y las confirmaciones de entrega no están configurados. La UI
  lo indica; los contactos no se presentan como avisados.
- Toda solicitud de control físico se registra como rechazada. No existe adaptador
  de despacho ni respaldo SMS. Por tanto, no hay órdenes pendientes capaces de
  ejecutarse al reconectar. Se requiere una entrega posterior para habilitar control.
- Add-on `step_tracker_portal` depende de `step_tracker_odoo` y no redefine ninguno
  de sus modelos. Añade resúmenes `step.tracker.protection.*`, reglas por compañía
  y sincronización incremental con reintentos e idempotencia. No sustituye todavía
  el sincronizador histórico de sesiones de `step_tracker_odoo`/`step_hr`.

## Inventario y aceptación del 401C

El usuario informó que recibe hoy un **GPS Tracker 4G 401C Coban con relé y chip**.
Pendiente registrar variante exacta, firmware, SIM/APN, manual del lote y protocolo.
No se marca aprobado por el texto comercial “homologado”. No hay evidencia disponible
de una muestra 403A ni de pruebas de banco/campo del 401C.

El receptor Teltonika existente queda operativo. No se reutiliza su decodificador
para Coban. Traccar sigue siendo candidato: falta elegir una versión y probar tramas,
buffer, desconexión, reconexión y manejo de comandos con el ejemplar recibido.
`gps_spool.py` proporciona la frontera de cola SQLite durable para un receptor ya
verificado; no decodifica Coban y no se conecta automáticamente al dispositivo.
`assign_gps.py` permite registrar una asociación explícita una vez identificada
la unidad; rechaza apropiarse de una asignación vigente.

## Pruebas reproducibles

Desde `backend/tracker_py`: `python -m pytest -q`. La suite comprueba autenticación,
aislamiento por cliente y usuario, asignaciones históricas, deduplicación, posición
antigua, filtros AND, preferencias, roles, agrupación de incidentes, reconocimiento,
cierre, auditoría, rechazo de control y cursor de cambios. No prueba un relé físico.

Frontend: `VITE_ODOO_PORTAL=true npm run build` (PowerShell: variable de entorno de
proceso). ESLint en los componentes nuevos. Pruebas de navegador con datos sintéticos
y anchos 320/360/768/1024; luego comprobación HTTP, sesión Odoo y hash del bundle
en los tres destinos. La clave Maps se conserva en el servidor.

## Despliegue

Aplicar el proceso base de `DEPLOY_WEB_TRACKER.md`: push a la rama indicada, clon
fresco en `/tmp`, copia de `.env`/`.env.production` del servidor, `npm ci`, build,
rsync, `nginx -t`, reload y comparación del JS servido. Para los tres entornos
solicitados se utiliza `/var/www/web_tracker_portal/` y una inclusión Nginx limitada
a sus vhosts HTTPS; el sitio compartido `stepsapp.cl/web_tracker/` conserva su build.

El script `scripts/deploy-tracker-portal.sh` implementa la secuencia API → frontend
→ Odoo, con respaldos de las cuatro bases, backend y Nginx; ensayo up/down/up de
migración en copia de Tracker e instalación en copia de Desarrollo. Antes de copiar
fuentes comprueba modificaciones divergentes en el backend del servidor.

El archivo `/etc/tracker-bridge-keys.json` es privado y nunca se versiona. Se crea una
clave por base Odoo, guardada también en `ir.config_parameter` de esa base. Las
tablas nuevas pertenecen a la API; las tablas de sesiones no se migran ni se renombran.
La importación inicial toma solamente `fleet.vehicle` de la compañía identificada.
Los ocho equipos del Tracker histórico permanecen sin asignar a los nuevos clientes
hasta tener correspondencia explícita.

Roles: administradores Odoo pueden entrar; otros usuarios requieren `Tracker:
consultar flota`, `Tracker: atender incidentes` o `Tracker: administrar protección`.
El selector de compañía se toma de Odoo y se verifica contra compañías permitidas.
No se otorgan permisos nuevos automáticamente a todos los usuarios internos.

## Reversión

1. Deshabilitar `steps-tracker-signal.timer` y el cron del add-on nuevo.
2. Restaurar los archivos Nginx respaldados, ejecutar `nginx -t` y reload.
3. Restaurar código FastAPI desde `BACKUP/tracker_py`, conservando su `.env` y venv,
   y reiniciar únicamente `tracker-steps-api.service`.
4. Mantener las tablas GPS aditivas para preservar datos. El SQL `down` es para
   ensayo o una reversión deliberada después de respaldar los nuevos registros;
   eliminaría el historial nuevo y no se ejecuta rutinariamente en producción.
5. El módulo Odoo nuevo puede quedar instalado sin menús publicados. Restaurar
   una base completa solo si es necesario y después de conciliar escrituras
   posteriores al respaldo; no sobrescribir actividad del usuario automáticamente.

## Pendientes de aceptación del documento original

Capturas reales 401C/403A, prueba de una hora sin red, decisión y operación del
receptor, homologación por firmware/relé/instalación, segundo aprobador con MFA,
sensor de confirmación física y restitución, avisos externos/escalamiento,
acceso temporal de soporte, migración del sync histórico de sesiones,
vistas compartidas autorizadas, piloto de cinco vehículos y alcance contractual.
La habilitación de control físico permanece bloqueada hasta superar E4.
