# Steps Tracker: movilidad, GPS y SIM
Entrega: 30 de septiembre de 2026. Rama: codex/web-tracker-redesign.

## Acceso
En el selector de aplicaciones de Odoo: **Steps Tracker**. Abre la portada del portal.
También: /web_tracker/#home; Configuración: /web_tracker/#settings.
Los usuarios necesitan los grupos Tracker de consulta, operación o administración.
El grupo administrador gestiona vehículos, GPS, asociaciones y SIM. Los otros roles
pueden consultar la guía, sin acceso al inventario privado de SIM. No se concedieron
permisos nuevos a usuarios existentes.

## Funciones entregadas
- Portada de servicio GPS para autos particulares, flotas empresariales y maquinaria.
- Resumen con enlaces a filtros; mapa con iconos por tipo; flota y protección.
- Alta y edición de vehículos desde Tracker, sin requerir registro en Odoo.
- Historial paginado de posiciones, exportación CSV de la flota filtrada, vistas guardadas.
- Inventario GPS por compañía: IMEI, modelo, firmware conocido y estado de validación.
- Asociación y desvinculación con motivo, control de concurrencia y trazabilidad.
  El historial permanece en la instalación original. No se reasigna con protección armada.
- Ficha SIM: teléfono, operador, modalidad, APN, responsable, notas sin credenciales.
- Fechas independientes: última/próxima recarga, vencimiento de datos, revisión de línea.
- Avisos en Inicio y Configuración, calculados con fecha de la compañía;
  descarga de calendario ICS con anticipación configurable (0–90 días).

Los avisos son recordatorios de fechas ingresadas. **No consultan saldo**, ni verifican
por sí mismos la vigencia de una SIM; no recargan, ni envían email/WhatsApp/push.
El archivo de calendario debe importarlo el usuario; no se actualiza remotamente.
Los vehículos sincronizados desde Odoo advierten que una nueva sincronización
puede reemplazar su ficha local.

## Al recibir el Coban 401C
1. Guardar modelo exacto, IMEI, manual y firmware si se conoce.
2. Confirmar operador, activación de la SIM, datos móviles y posibilidad de SMS de configuración.
   Verificar APN y cobertura/bandas con operador/proveedor; no asumir compatibilidad por el nombre.
3. En Tracker registrar vehículo; en Configuración agregar GPS y datos de SIM.
4. Steps realiza instalación física y valida protocolo/firmware. El receptor Coban
   y su integración de ingreso aún requieren habilitación y pruebas con la unidad real.
   **No usar la URL web ni el puerto HTTP de la API como destino del dispositivo.**
5. Cuando Steps confirme instalación y receptor, asociar GPS al vehículo y verificar
   primera posición, horas registrada/recibida, ACC, alimentación y reconexión.
6. Programar fechas de recarga/datos/vigencia según el operador, asignar responsable,
   importar calendario si se desea. Actualizar fechas tras cada recarga.
7. Mantener el control físico deshabilitado hasta aprobar instalación y pruebas.
   “Homologado” en un anuncio comercial no acredita la seguridad del relé en nuestro sistema.

No se publicaron comandos SMS genéricos: las variantes de firmware pueden diferir.
No se registró el GPS del usuario: aún no tenemos su IMEI, SIM ni firmware.

## Referencias revisadas
- [Traccar: alta e identificador del dispositivo](https://www.traccar.org/quick-start/):
  identificación por IMEI/serie y configuración separada del destino del equipo.
- [GPSWOX: SIM y conexión](https://www.gpswox.com/en/faq):
  SIM con datos, configuración del dispositivo y primera posición.
- [Wialon: intervalos de servicio](https://help.wialon.com/en/wialon-local/2204/user-guide/monitoring-system/units/unit-properties/service-intervals):
  eventos por fechas/intervalos como referencia para recordatorios de continuidad.
- [Entel: prepago](https://www.entel.cl/prepago):
  saldo, datos e inactividad tienen vigencias distintas. No extrapolar condiciones
  a otros operadores ni fijar 180 días como regla universal.
- [GPS-Trace: soporte de Coban 401](https://forum.gps-trace.com/d/2869-cant-connect-coban-401):
  confirmar hardware y destino; no inferir equivalencia con otros modelos Coban.

La diferenciación implementada reúne vehículo, GPS y continuidad de la SIM en una
sola vista, con responsable y fechas separadas; evita confundir “sin señal” con
vehículo detenido o saldo agotado.

## Validación y despliegue
Build TypeScript/Vite y lint de archivos nuevos/modificados; 22 pruebas backend,
incluyendo tenant, permisos, fechas, edición concurrente y conservación de historial.
QA de navegador local con API aislada: alta de auto, GPS, edición SIM y asociación.
Revisión móvil de portada, inventario y formularios.
Migración incremental: backend/tracker_py/migrations/20261001_device_configuration.up.sql.
El frontend portal es compartido por Desarrollo, Demo y Cerro El Plomo; se entrega
la misma versión y se actualiza el addon step_tracker_portal en las tres instancias.
El sitio legacy stepsapp.cl/web_tracker no cambia.

### Evidencia del despliegue
- Release: 58a097226d99c7582cdbdbb92a5c05c1c21e8560.
- Respaldo: /opt/backups/tracker-mobility-20260930T220639Z/ (cuatro bases,
  código API, addon de cada entorno y portal anterior; SHA256SUMS verificado).
- Migración PostgreSQL ensayada ida/vuelta y ciclo registrar/asociar/reasignar/
  desvincular probado sobre copia real; actualización Odoo ensayada en copia.
- Los tres dominios sirven assets/index-DFVMcV-F.js con SHA256
  b432c57a1dfa6e7788cf03a22f34e677e3d674c091b3634a014e7ea40cd491b1.
- Smoke HTTP autenticado en LAB_TAREAS, STEPS_DEMO y CERRO_EL_PLOMO:
  contexto, configuración, CSRF, bloqueo de ingestión por el proxy, sincronización
  de incidentes y acción del lanzador correctos. Flotas: 18, 18 y 0 respectivamente.
- Backend, tres servicios Odoo y timer de señal activos; nginx -t correcto
  con avisos de nombres HTTP duplicados que ya existían.
- Se comprobó en navegador el clic Odoo → Steps Tracker → /web_tracker/#home.
- Exportación CSV neutraliza fórmulas; calendario ICS valida fecha y aviso previo.
- Las copias temporales de QA fueron eliminadas; no se cargaron GPS de prueba
  en las bases reales. La validación física del 401C permanece pendiente.
