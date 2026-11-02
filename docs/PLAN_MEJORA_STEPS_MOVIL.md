# Steps Móvil — plan de mejora por iteraciones

App de **conductores y operadores** (web instalable, Android e iOS) en `mobile/`, publicada en
`https://stepsapp.cl/truck/`. La web `web_tracker` queda para el usuario de oficina: estadísticas,
flota, zonas, protección y costos. **Steps Móvil es la herramienta de terreno**: registrar, avisar,
transportar pasajeros y no perder datos sin señal.

Este documento es la lista de trabajo. Cada **iteración** (I1, I2, …) cabe en una corrida de Helpdesk:
se toma una, se implementa, se prueba, se despliega y se marca aquí.

## Reglas de trabajo (para cada iteración)

1. **Una iteración por corrida.** Tomar la primera sin marcar (`[ ]`) cuyo prerrequisito esté cumplido.
2. Actualizar primero desde `origin/codex/steps-movil`, la rama canónica consolidada.
   Si se crea una rama de trabajo, integrar su resultado de vuelta a esa rama antes de desplegar.
   Código en `mobile/`; backend en `backend/tracker_py/`; módulo Odoo en `step_tracker_portal/`
   solo si la iteración lo pide. Las ramas históricas `ticket/46-*` no se despliegan por separado.
3. Pruebas: `cd mobile && npx tsc -b && npx vitest run`; backend `cd backend/tracker_py && python -m pytest -q`.
   La lógica nueva (cola, validaciones, reglas) lleva prueba. Para la interfaz usar `scripts/mock-api.mjs`
   y verificar en ancho 375 px.
4. **Desarrollo primero** (instrucción vigente del usuario, 01-11-2026): probar las nuevas funcionalidades allí antes de llevarlas a Cerro. La API y las interfaces de producción se conservan. No usar Demo como QA ni el publicador compartido histórico para promover mejoras sin autorización. I10 tiene una API de proceso independiente en Desarrollo; conserva la base y los maestros Tracker existentes. Ver `docs/T46_I10_ABORDAJE.md`.
5. Cambios de backend o de esquema: primero respaldo (`pg_dump -Fc tracker_steps`), migración aditiva
   (nunca borrar columnas ni tablas), y desplegar la API **antes** que la app.
6. Marcar la iteración (`[x]`), anotar fecha, commit y hash del JS servido, y dejar la nota
   `⟦IA-EVIDENCIA⟧` en el ticket. Si algo no se pudo verificar en terreno, decirlo.
7. Nada de claves en el repositorio ni en variables `VITE_` salvo URLs públicas.

## Estado de partida (02-10-2026)

Hecho: login (clave del Tracker o sesión Odoo), iniciar jornada (parte diario con máquina, labor, centro
de costo, campo, implemento, conductor, horómetro y litros), seguimiento GPS con cola sin conexión,
cierre con horómetro y combustible, historial, PWA con service worker, proyectos Capacitor
Android/iOS generados (sin compilar).

Limitaciones conocidas: el GPS se corta con la pantalla apagada o la app en segundo plano; los
usuarios Odoo no administradores entran sin centros de costo; no hay forma de retomar una jornada
abierta desde otro teléfono; no hay nada de pasajeros.

---

## Bloque A — Confiabilidad en terreno (primero: sin esto no hay datos reales)

### I1 · Jornada que no se pierde  `[x]` 02-10-2026
- **Qué:** al abrir la app consultar al servidor si el usuario tiene una sesión abierta (`GET /sessions/my?status=open`)
  y retomarla (otro teléfono, datos borrados, cierre del navegador). Si la sesión local ya está cerrada en el
  servidor, limpiar y avisar. Reenvío automático al recuperar red y al volver a primer plano
  (`visibilitychange`, `online`). Indicador permanente de "puntos pendientes" y "último envío".
- **Backend:** ninguno (usar lo existente). Verificar que `status` filtre bien en `/sessions/my`.
- **Aceptación:** matar la pestaña con una jornada abierta, volver a entrar → la jornada sigue, el contador
  conserva el tiempo real y los puntos pendientes se envían. Prueba unitaria de la reconciliación local/servidor.

### I2 · Iniciar jornada sin señal  `[x]` 02-10-2026
- **Qué:** si no hay red al iniciar, crear la jornada localmente (UUID de cliente), seguir registrando y
  sincronizar al volver la señal: crear parte → iniciar sesión → enviar puntos → cerrar. Cola de operaciones
  ordenada e idempotente, con pantalla "Pendientes de sincronizar" y reintento manual.
- **Backend:** aceptar `started_at` del cliente (ya existe en `SessionStart`) y, si hace falta, un
  `client_id` idempotente en `/work_orders` y `/sessions/start` para que un reintento no duplique.
- **Aceptación:** modo avión → iniciar, mover, cerrar → al reconectar queda un solo parte y una sola sesión.
  Pruebas de la cola de operaciones (orden, reintento, idempotencia).

### I3 · GPS en segundo plano (Android/iOS)  `[~]` 06-10-2026: implementación y pruebas simuladas; falta validación nativa/terreno
- **Qué:** plugin nativo de ubicación en segundo plano (p. ej. `@capacitor-community/background-geolocation`)
  con notificación persistente "Steps está registrando tu ruta", permisos "siempre", ahorro de batería
  configurable y *fallback* a web. Detectar y avisar cuando el sistema mata la app.
- **Requisito externo:** Android Studio / Xcode y cuentas de desarrollador (ver Bloque F).
- **Aceptación:** jornada de 1 hora con pantalla apagada en un teléfono real, sin huecos > 2 min en la ruta.
- Implementado: plugin compatible con Capacitor 7, notificación/permisos, perfil
  de batería, descarte de posiciones antiguas, HTTP nativo y cierre del watcher.
  La navegación entre pestañas conserva el registro; salir del módulo o cerrar
  sesión lo detiene. Los datos previos y claves locales se conservan.
- Android sincronizado; proyectos Android/iOS preparados. Este equipo no tiene
  Java/SDK Android ni Xcode. No se ha generado un APK/IPA ni certificado la hora
  de recorrido físico. `/truck/` usa `npm run build:tracker`, con el acceso y
  datos locales del Tracker actual. La versión unificada sigue siendo un piloto
  y no se publica como parte de esta mejora.

### I4 · Sesión y permisos sin fricción  `[x]` 02-10-2026
- **Qué:** que los **administradores Odoo vean todos los centros de costo** sin asignarlos a mano
  (`/auth/me/cost_centers` y `sessions/my` consideran `is_admin`); pantalla clara cuando un operador no tiene
  centros ("pide acceso a…" con botón de contacto); renovación de token antes de vencer; cierre de sesión que
  no deja jornadas huérfanas.
- **Backend:** `get_user_cost_centers` / `allowed_cost_center_ids` para `is_admin`; pruebas de aislamiento
  (un operador no ve centros ajenos).
- **Aceptación:** un administrador nuevo entra y puede iniciar jornada sin ajustes manuales; un operador sin
  centros recibe el mensaje y no un error genérico.

---

## Bloque B — El día de un conductor

### I5 · Revisión previa (checklist) e incidentes  `[x]` 02-10-2026 (falta: vista de incidentes en Odoo `step_tracker_portal`; la API y la vista Supervisor ya los muestran)
- **Qué:** checklist antes de partir (luces, frenos, neumáticos, aceite, extintor… configurable por tipo de
  vehículo) y reporte de incidencias (falla, accidente, daño, robo) con categoría, nota y **foto**, con
  ubicación y hora. Funciona sin señal (cola).
- **Backend:** tablas `vehicle_checklists`, `vehicle_checklist_items`, `incident_reports` (+ almacenamiento
  de fotos privado, URLs firmadas); endpoints bajo `/v1` o `/mobile`; el módulo Odoo `step_tracker_portal`
  muestra los incidentes en Tracker → Incidentes.
- **Aceptación:** una falla reportada desde el teléfono aparece en la web con foto, lugar y hora.

### I6 · Combustible y gastos en ruta  `[x]` 02-10-2026 (falta: enlazar con la rendición `step_expense_tracker`; los gastos quedan en `mobile_expenses` con boleta)
- **Qué:** cargas de combustible (litros, monto, estación, **foto de la boleta**, odómetro) durante la jornada,
  peajes y otros gastos del viaje. Se vinculan al parte y alimentan `step_expense_tracker` (rendiciones).
- **Backend:** endpoint de gastos de jornada; integración con "Traer desde Tracker" ya existente (Entrega A).
- **Aceptación:** una carga registrada en terreno aparece al armar la rendición del conductor.

### I7 · Mis tareas  `[x]` 02-10-2026 (falta: pantalla web para asignar; hoy se asigna con `PUT /work_orders/{id}` `assigned_user_id`, solo administrador)
- **Qué:** pantalla "Hoy" con las órdenes de trabajo asignadas al conductor (máquina, labor, campo, hora,
  indicaciones), iniciar jornada con un toque desde la tarea y marcar avance. Notificaciones locales de
  recordatorio.
- **Backend:** asignación de `work_orders` a usuario/conductor (campo nuevo, aditivo) y `GET /work_orders?mine=1`.
- **Aceptación:** el supervisor asigna una tarea en la web y el conductor la ve y la inicia sin llenar el formulario.

### I8 · Resumen de la jornada y mapa propio  `[x]` 02-10-2026 (ruta en SVG sin mapa base, funciona sin señal; falta alerta de salida de zona y comparación con la web)
- **Qué:** mapa en vivo con la ruta recorrida y los campos/zonas asignados; al cerrar, resumen (tiempo, km,
  combustible estimado, paradas) y compartirlo. Alertas de salida de zona o exceso de velocidad (solo avisos
  al conductor).
- **Backend:** reutilizar `/sessions/{id}/track` y zonas existentes (`/v1/zones` vía puente o endpoint móvil).
- **Aceptación:** al terminar, el conductor ve su recorrido sobre el mapa y las cifras coinciden con la web.

---

## Bloque C — Transporte de pasajeros

> Arquitectura confirmada por el usuario en este chat el 31-10-2026: los servicios y pasajeros viven
> en Tracker (PostgreSQL) y se sincronizan hacia Odoo. La app antigua Redis está fuera de servicio y
> **no se reutiliza**. Contrato de datos y alcance de I9 en `docs/T46_I9_SERVICIOS_PASAJEROS.md`.

### I9 · Modelo de servicio y nómina de pasajeros  `[x]` 31-10-2026
- **Qué:** servicios/viajes (ruta, paradas con horario, vehículo, conductor, capacidad real del vehículo) y
  **lista de pasajeros** por servicio (nombre, RUT/ID, parada de subida/bajada, asiento opcional). Diseño del
  esquema aditivo, endpoints y permisos (conductor ve solo sus servicios). Documento de diseño + migración +
  pruebas de API; sin interfaz aún, salvo pantalla de solo lectura "Mi servicio".
- **Aceptación:** crear un servicio con paradas y 3 pasajeros por API y verlo en la app del conductor asignado.
- Publicado en Tracker 1.3.0. API/backend 68 pruebas, app 165, ensayo funcional
  PostgreSQL en copia, migración repetida y datos antiguos conservados. Mi servicio
  revisado a 375 px; acceso limitado al conductor asignado. El contrato Odoo está
  definido; el consumidor automático no se instala en esta iteración. Nota interna
  9922. Próxima iteración elegible: I10. I3/I16 conservan requisitos externos.

### I10 · Abordaje y descenso  `[x]` 02-11-2026, solo Desarrollo
- **Qué:** marcar subida/bajada por pasajero (lista con búsqueda, **lector QR/código** y registro manual),
  contador de ocupados vs. capacidad, avisos de capacidad completa, ausentes/no-show, hora y posición del
  evento. Funciona sin señal (cola idempotente).
- **Aceptación:** servicio completo sin red → al reconectar el manifiesto final coincide con lo marcado.
- Entregado Tracker 1.6.1 en Desarrollo: preparar la nómina por 24 horas, registrar subida/bajada/ausencia, ocupación real, búsqueda, filtros y QR/código. Cola transaccional por cuenta, recibos idempotentes y revisión explícita de conflictos. Perfil y salida incluyen los pendientes. Ensayo de cinco eventos en copia PostgreSQL y navegador, revisión 390 px/escritorio y cuenta existente con PKFX47; 183 pruebas app y 83 API. API de Desarrollo separada, base compartida y tabla aditiva; Cerro y Steps compartido no reciben esta UI ni cambian su API/receptor. Nota interna 9952. Contrato Odoo v2 definido; consumidor automático, cámara física, APK/IPA y arranque autenticado completamente sin red no se certifican. Próxima iteración: I11.

### I11 · Paradas y avance del servicio  `[ ]`
- **Qué:** ruta del servicio con paradas, estado por parada (llegada/salida), estimación de llegada, desvíos y
  retrasos; cierre de servicio con manifiesto firmado (conductor) y novedades.
- **Aceptación:** el coordinador ve en la web el avance del servicio y los retrasos en tiempo casi real.

### I12 · Seguridad del pasajero y del conductor  `[~]` 02-10-2026 parcial: SOS con ubicación, aviso de exceso de velocidad y pausas de conducción configurables hechos; faltan contactos de emergencia configurables
- **Qué:** botón SOS (aviso inmediato con ubicación a contactos y a la web), registro de exceso de velocidad
  y de pausas de conducción/descanso (jornada), números de emergencia configurables. Reutiliza incidentes
  y política de protección existentes; **no** habilita control físico del vehículo (bloqueado hasta E4).
- **Aceptación:** SOS visible en la bandeja de incidentes de la web en menos de 10 s, con ubicación.

---

## Bloque D — Gestión ligera (jefe de flota desde el teléfono)

### I13 · Vista de supervisor  `[x]` 02-10-2026 (flota con última posición incluida en mejoras; auditoría disponible mediante `handled_by`, falta presentación explícita en la web)
- **Qué:** para roles manager/operator del puente Odoo: lista de vehículos con última posición y estado,
  jornadas abiertas, incidentes pendientes y atender/cerrar un incidente. Sin duplicar la web: solo lo urgente.
- **Aceptación:** un supervisor atiende un incidente desde el teléfono y queda en la auditoría.

---

## Bloque E — Experiencia y calidad

### I14 · Experiencia de terreno  `[~]` 02-10-2026 parcial: modo noche, modo guantes, tamaño de letra, sonido/vibración, ayuda de primer uso, versión y buscar actualización; falta revisión de accesibilidad con conductores reales
- **Qué:** botones grandes y modo guantes, modo noche, voz/sonidos de aviso, textos en español claro,
  tamaño de letra ajustable, accesibilidad (lector de pantalla, contraste), pantalla de ayuda "primer uso"
  con permisos de ubicación paso a paso, y versión visible con "buscar actualización".
- **Aceptación:** revisión de accesibilidad básica y prueba con 2 conductores reales.

### I15 · Observabilidad y soporte  `[~]` 02-10-2026 parcial: señal de vida (versión, pendientes, última sincronización), registro de errores y enviar diagnóstico; falta el panel de salud en la web
- **Qué:** registro de errores de la app (sin datos personales), "enviar diagnóstico" desde Perfil, versión de
  app en cada petición, panel de salud (última sincronización por conductor) en la web.
- **Aceptación:** ante un reclamo se puede ver qué versión usa el conductor y cuándo sincronizó por última vez.

---

## Bloque F — Publicación Android / iOS

### I16 · Builds firmados y tiendas  `[ ]`
- **Requisitos del usuario:** Android Studio, Xcode (Mac), cuenta Google Play y Apple Developer, íconos y
  textos de ficha, política de privacidad (ubicación, fotos).
- **Qué:** íconos y *splash* reales, `versionCode`/`CFBundleVersion` automáticos, firma de release, CI que
  genere APK/AAB e IPA, distribución interna (Play pruebas internas / TestFlight) y luego publicación.
- **Aceptación:** conductores de prueba instalan desde Play interno y TestFlight y registran una jornada.

---

## Orden recomendado

`I1 → I2 → I4 → I3` (confiabilidad), luego `I5 → I6 → I7 → I8` (día del conductor), después `I9 → I12`
(pasajeros; I9 requiere confirmar la arquitectura), `I13` y `I14/I15`, y `I16` en paralelo en cuanto se
disponga de las cuentas de tienda.

## Procedimiento histórico de despliegue a producción (`/truck/`)

Desde la instrucción vigente de noviembre, requiere autorización específica de promoción. Para I10 y su revisión en Desarrollo usar `tools/ops/deploy_mobile_boarding.py`; no ejecutar este procedimiento para una revisión periódica ni reemplazar las interfaces productivas.

```bash
# Local: pruebas, commit e integración de la entrega en codex/steps-movil.
git push origin codex/steps-movil
# Registrar el SHA exacto publicado; usarlo como argumento del script remoto.
git rev-parse origin/codex/steps-movil

# Servidor odoo-new (stepsconsulting / us-central1-c):
release=$(mktemp -d /tmp/steps-movil-release-XXXXXXXX)
git clone --branch codex/steps-movil --single-branch --depth 50 \
  https://github.com/fjcaroe/tracker-steps.git "$release"
cd "$release"
bash scripts/deploy-steps-movil.sh SHA_EXACTO_REVISADO SHA_BASE_SERVIDOR_REVISADO
```

El script compara fuentes con las variantes conocidas antes de tocar producción, compila y prueba
la app, respalda base/API/frontend, verifica el esquema en una copia PostgreSQL, publica la API
antes de la app y compara SHA-256 del JS servido. Si falla la verificación de publicación,
restaura la entrega anterior. Conserva `.env`, `.venv` y archivos de datos del servidor.
No usa las variables de Google Maps del Web Tracker: Steps Móvil usa Leaflet y una URL pública
de API. El procedimiento de `/web_tracker/` sigue siendo independiente.
La base debe ser un ancestro revisado cuyo código coincide con el servidor;
si queda fuera del clon superficial, profundizar esa rama antes de ejecutar.

Si la iteración cambia la API: `backend/tracker_py` se despliega siguiendo `docs/DEPLOY_WEB_TRACKER.md`
(respaldo de la base y del código, `rsync` excluyendo `.env` y `.venv`, reinicio de
`tracker-steps-api.service`, comprobar `/openapi.json`). Si cambia `step_tracker_portal`: respaldo de
`karo_consultorias`, ensayo en una copia y `-u step_tracker_portal` con el servicio detenido, como en la
entrega del 02-10-2026.

El despliegue compartido histórico de los sitios (`desarrollo`, `demo`, `cerroelplomo`) usaba el mismo directorio mediante
`/etc/nginx/snippets/steps-tracker-portal.conf`. Desde la entrega GPS 1.4.0, Desarrollo y Cerro usan alias móviles privados y deben publicarse explícitamente; Demo conserva el directorio compartido. Una mejora que requiera cambios de API o de módulo en esos ambientes debe probarse allí antes de
publicarse cuando ya haya clientes en ellos.

## Flota GPS Coban independiente — 31-10-2026, Tracker 1.4.0

Solicitud explícita del usuario: ver los autos de Cerro el lunes sin que el
conductor inicie una jornada. Publicado en Desarrollo y Cerro, desde el mismo
paquete 73a19bf87c32718e0d9c850dfaf32577e10a2b0b de la rama canónica.

Acceso: https://cerroelplomo.stepsapp.cl/truck/#gps, o botón GPS en Tracker.
Seleccionar en Odoo la compañía donde se registran los vehículos. También se
puede abrir desde el botón Ver flota GPS con Odoo de la pantalla de acceso.
El enlace directo funciona con los permisos actuales de consulta de Tracker;
no necesita una sesión clásica del Tracker, iniciar una jornada, datos locales
ni permiso de ubicación del teléfono. La entrada normal a las jornadas conserva
su acceso previo y el registro de una jornada activa sigue al cambiar de pestaña.
Esta entrega corresponde a la app web móvil; no genera un APK/IPA nuevo.

La vista consume GET /steps_tracker/api/fleet/snapshot mediante la cookie Odoo
del mismo origen. El puente existente firma la identidad y valida grupo y compañía.
No usa el token clásico para autorizar GPS, no expone IMEI/SIM y no acepta una
compañía elegida libremente por el cliente. Se conserva el modelo de activos,
dispositivos, asociaciones e historial existente. No hay migración ni cambio de
API, addons, credenciales o receptor. Un usuario con solo credenciales Tracker
debe iniciar sesión Odoo para leer esta flota; ese login no amplía sus grupos.

Actualiza cada 10 segundos mientras la pantalla está visible, y al recuperar red
o volver a la app. Muestra compañía, consulta, hora registrada y recibida, patente,
coordenadas y velocidad cuando el punto es reciente. Señal antigua se distingue
con marcador gris y no demuestra movimiento actual. Un vehículo sin posición se
lista sin inventar coordenadas. La red caída conserva el último resultado con
aviso; un permiso retirado o sesión expirada elimina las ubicaciones y pide Odoo.
Al ocultar la app se retira la instantánea hasta una consulta nueva. No se guardan
ubicaciones en almacenamiento local ni caché del service worker. El mapa compartido
renderiza el texto de sus tooltips mediante un nodo de texto, sin interpretar HTML.
La primera página admite hasta 500 vehículos y avisa si hay más en la web.

Validación: 172 pruebas móviles en Windows y Linux; TypeScript y build tracker.
Navegador 390 px: marcador real de Leaflet, actualización automática, error de red,
revocación, cambio de compañía, ausencia de inicio de jornadas y cero solicitudes
al GPS del teléfono. Copia fresca de tracker_steps: socket Coban TCP, captura,
aprobación, cola durable, deduplicación, ingesta, proyección de flota y aislamiento
por compañía. El número de jornadas de la copia permanece igual antes/después.
La respuesta sintética de esa copia se usó en la prueba de navegador del paquete
servido en Desarrollo. Nunca se colocan esas filas ficticias en producción.
El primer ensayo detectó falta de registro completo de modelos en el harness;
se corrigió la importación de app.main y se repitió con otra copia fresca.

Publicación: tools/ops/deploy_mobile_hardware_map.py qa|development|production
<checkout>. Checkout fresco canónico, commit exacto, npm ci, npm test y build:tracker.
Bloqueo /run/lock/steps-environments.lock, copia de configuración nginx y directorios
inmutables bajo /var/www/steps-mobile-releases/<commit>. Las inclusiones privadas de
Desarrollo y Cerro cambian únicamente sus alias /truck; conservan /web_tracker,
Demo, el sitio compartido Steps, la API, Teltonika y el receptor Coban. Las futuras
publicaciones web deben conservar también estos alias móviles privados, sin
reemplazarlos por el directorio compartido anterior.

Verificación real: sesión temporal de un administrador existente de Cerro, compañía
correcta, snapshot autenticado, mapa visible, actualización y cero escrituras de
negocio o llamadas a geolocalización. La sesión de revisión se elimina al terminar.
Todos los archivos servidos coinciden con el build. Fuentes API y receptor
permanecen idénticas. El verificador anterior de GPS y de la web completa también
pasó después de publicar la app móvil.

Entrada JS index-DLvUA7rS.js, SHA-256
75e517539614fbc7bc13bc770dfdd4a98ebb83134aca304728e3b9dd434cc1b8.
Evidencia privada /opt/steps-validation/mobile-hardware-map-20261031/
73a19bf87c32718e0d9c850dfaf32577e10a2b0b/ (qa.json, development.json,
production.json, private/functional.log, dump y qa-data/snapshot.json).
Respaldo de nginx Cerro: private/backup-production-20261101T023520Z.
Evidencia local ~/.codex/local-artifacts/mobile-hardware-map-20261031/.
Verificación repetible: acción verify del mismo publicador; pruebas de navegador
mobile-hardware-ui.cjs (copia) y mobile-hardware-native.cjs (sesión privada real).

Estado al entregar: aplicación publicada y receptor disponible; inventario real
de Cerro todavía vacío, sin vehículos ficticios. Faltan los cuatro IMEI, asociación
a sus vehículos y validación de la trama de cada unidad física antes de activar
seguimiento. Al transmitir una unidad aprobada, el móvil usa la misma posición de
la web sin depender de una jornada del conductor.

## GPS en prueba visible — 01-11-2026, Tracker 1.4.1

La flota solo mostraba activos: un equipo en captura, aún sin vehículo asociado,
podía recibir coordenadas válidas y dejar el mapa vacío. La consulta de los
administradores ahora incluye el diagnóstico autorizado de Configuración y
muestra los equipos en captura como GPS en prueba, con IMEI enmascarado,
contacto, posición recibida y marcador naranja. Los equipos deshabilitados sin
asociación se listan sin representar su posición antigua como seguimiento activo.
Los lectores y operadores conservan únicamente la flota autorizada. No se crean
vehículos ficticios ni jornadas para representar un equipo de prueba.

La lectura usa la sesión Odoo y confirma nuevamente usuario, compañía y rol antes
de incorporar los diagnósticos. Un cambio de ámbito descarta el resultado anterior;
revocar acceso limpia las ubicaciones. No se exponen teléfonos, notas o SIM en el
modelo de presentación móvil. La configuración fallida avisa sin inventar equipos.

Paquete publicado sin cambios entre Desarrollo y Cerro:
61e5193c8a98c180ba0cce30771a0c913e7750c4. Se conservan los alias privados,
la web, las instalaciones compartidas, API y receptor. Validación: 177 pruebas
móviles en Windows y Linux, TypeScript y build; copia fresca del destino con
socket Coban, cola durable, ingesta, aislamiento y proyección sin crear jornadas.
El navegador contra Desarrollo verificó el diagnóstico de esa copia, marcador,
actualización automática, pérdida de red, revocación y cambio de compañía.

En Cerro se verificó además el primer equipo físico: captura y marcador de prueba
con coordenadas reales. Tras confirmar el usuario su vehículo existente, se usó
el flujo de asociación y aprobación del receptor; una posición nueva posterior
a la asociación apareció en la flota y en el mapa móvil como vehículo con señal
reciente. La sesión temporal de revisión se eliminó. Esta comprobación corresponde
a una unidad; no acredita las restantes ni su instalación eléctrica en terreno.
Los identificadores, capturas y recibos de esa operación son evidencia privada.

Entrada JS index-CqnuoBVy.js, SHA-256
90828519d712e2cec0b63a062570b15c5710a52ac797b19776fa6c9959d16e6f.
Evidencia y respaldo: /opt/steps-validation/mobile-hardware-map-20261031/
61e5193c8a98c180ba0cce30771a0c913e7750c4/ (qa.json, development.json,
production.json y private/backup-production-20261101T033722Z).
Revisión de navegador: ~/.codex/local-artifacts/mobile-gps-bench-20261101/.
El verificador nativo exige también la presencia del marcador correspondiente,
tanto en captura como después de la asociación y activación.

## Retiro de pruebas clásicas antes del piloto real — 01-11-2026

El usuario solicitó retirar los datos de prueba que pudieran interferir en la
conducción y confirmó que todas las máquinas antiguas consultadas eran pruebas
propias. El inventario GPS de Cerro ya contenía únicamente el vehículo real;
el ruido estaba en la operación clásica compartida, sin columna de compañía.
No se interpretaron los vehículos de los otros tenants como pruebas ni se
modificaron los maestros de Odoo o los ejercicios de QA-Cerro.

Se retiraron 8 máquinas, 19 jornadas (4 abiertas), sus 65.130 puntos de prueba y
19 órdenes antiguas. No había rutas, servicios de pasajeros, incidencias,
gastos, checklists o lotes que eliminar. Se conservaron usuarios, catálogos
operativos y todo el dominio GPS, incluida la asociación y aprobación del
equipo real, sus posiciones previas y los puntos nuevos que siguió recibiendo.
No se creó una máquina clásica paralela para usar el GPS sin jornada.

Herramienta versionada: tools/gps/retire_legacy_test_data.py. El plan contiene
identificadores explícitos y huellas completas de los registros elegidos; se
guarda exclusivamente en evidencia privada. Rechaza cambios concurrentes,
ausencia del vehículo protegido o seguimiento no aprobado. Adquiere el bloqueo
compartido, bloquea las escrituras clásicas durante la transacción, respalda y
elimina en orden de relaciones sin desactivar restricciones. Compara las filas
ajenas antes/después y verifica la conservación de cada posición GPS existente.
El receptor sigue funcionando durante la operación.

Se restauró el dump en TRACKER_CLEAN_QA_20261101, con acceso público revocado.
La misma herramienta retiró los registros en esa copia; una API HTTP local con
el código efectivo de producción validó selector de máquinas, jornadas abiertas
e históricas, órdenes y rutas sin pruebas, conservando la proyección GPS real.
tools/qa/tracker/verify_legacy_retirement.py sella ese resultado y permite la
ejecución del mismo plan en origen, con un segundo respaldo inmediatamente previo.
No se cambiaron dependencias de la API productiva para estas pruebas.

Verificación real en Cerro: menú GPS y SIM, formulario autorizado, rechazo de
escritura inválida, app móvil con un vehículo y marcador real, y formulario de
jornada sin máquinas ni jornadas de prueba para retomar. El recorrido nativo
tools/qa/tracker/legacy-retirement-native.cjs comprueba también órdenes y rutas
vacías, sin crear jornadas ni solicitar ubicación al teléfono. Solo permite los
intercambios de sesión y el heartbeat normal de diagnóstico. API, Coban y
Teltonika permanecieron activos; no hubo publicación ni cambio de módulos Odoo.

Evidencia privada: /opt/steps-validation/cerro-tracker-cleanup-20261101/
(plan-v2.json, source-v2.dump, qa.json, qa.http.log, production.json y
pre-apply.dump). Respaldo inmediatamente previo SHA-256:
af6d8c3986d2b4e2f1eac783e33f358fe17acaa0cc3f3d99e23211b50230934c.
Capturas y recibos locales: ~/.codex/local-artifacts/cerro-tracker-cleanup-20261101/.
Los respaldos conservan datos privados y no deben subirse a Git. Si se necesitara
recuperar una prueba, extraer sus filas en una copia; no restaurar toda la base
sobre posiciones reales recibidas después de esta limpieza.

## Bitácora

| Fecha | Iteración | Commit | JS servido | Notas |
|---|---|---|---|---|
| 01-11-2026 | Diagnóstico GPS en prueba y primera unidad real asociada; Tracker 1.4.1 | `61e5193c8a98c180ba0cce30771a0c913e7750c4` | `index-CqnuoBVy.js` | 177 pruebas, copia TCP y mapa real autenticado antes y después de asociar el vehículo confirmado. Misma publicación privada en Desarrollo y Cerro. |
| 31-10-2026 | Flota GPS Coban sin jornada; Tracker 1.4.0, solo Desarrollo y Cerro | `73a19bf87c32718e0d9c850dfaf32577e10a2b0b` | `index-DLvUA7rS.js` | 172 pruebas móviles, copia fresca TCP → flota → mapa y sesión Odoo real. API/receptor/web compartida intactos. Ver sección de flota GPS. |
| 31-10-2026 | I9: servicios y nómina, consulta Mi servicio en Hoy; Tracker 1.3.0 | `0a0838f90292006c0d1ecb72db4cfe3f82f6f4ac` | `index-BpVsqkbJ.js` | 68 pruebas backend, 165 app, flujo de tres pasajeros y aislamiento en copia PostgreSQL; migración idempotente y datos antiguos conservados. Revisión 375 px. SHA-256 `d1a63335b27ded530f623c5e08f98dee21adf41e49f00300153b9044f5d549f5`. Todos los JS/CSS servidos verificados. Respaldo `movil-consolidado-20261031T212041Z`; API antes de app; fuente efectiva coincide con el commit. Nota silenciosa 9922, ticket abierto para el resto del plan. Contrato hacia Odoo definido, consumidor automático pendiente. |
| 06-10-2026 | I3 parcial: adaptador nativo de GPS en segundo plano, perfiles de precisión y continuidad entre pestañas; Tracker web `1.2.2` | `1421bd4` | `index-CCX85BHo.js` | 161 pruebas y compilación correctas; esquema PostgreSQL ensayado y contrato API comprobado. SHA-256 servido `dfada1fea6f766cfb69883a37f85d8ff371a5d537df4b512126192035aae92b8`. Respaldo `movil-consolidado-20261006T123553Z`. Build específico del Tracker; el piloto unificado no se publicó. No se compiló APK/IPA ni se probó con pantalla bloqueada en un teléfono real. |
| 02-10-2026 | Base (web/PWA, jornada, GPS con cola, historial) | `f3355be` | `index-CGTxg_cA.js` | Proyectos Android/iOS generados, sin compilar |
| 02-10-2026 | I1 Jornada que no se pierde (retomar desde servidor, limpiar si ya está cerrada, reenvío al volver a primer plano, último envío visible) | ver rama `ticket/46-movil-i1-jornada-no-se-pierde` | `index-r-XhPasL.js` | Se ofrece *Retomar* en vez de retomar sola, porque `/sessions/my` lista las jornadas de los centros de costo del usuario, no solo las suyas (la sesión no guarda quién la inició). Sin verificar en terreno ni en dispositivo; respaldo del front: `steps-truck-frontend.pre-movil-20261002T012511Z` |
| 02-10-2026 | I2 Iniciar jornada sin señal (cola ordenada e idempotente, catálogos en caché, pantalla Pendientes de sincronizar; API: `id` de cliente en `/sessions/start`, reintento idempotente en `/work_orders`) | `62a8173` | `index-CaDWgI7Z.js` | API desplegada antes que la app (sin cambios de esquema). Respaldos: `/opt/fernando_odoo18/backups/tracker_py-i2-20261002T031459Z`, `tracker_steps-i2-20261002T031459Z.dump`; front: `steps-truck-frontend.pre-movil-20261002T031528Z`. Sin verificar en dispositivo real ni en modo avión físico |
| 02-10-2026 | I4–I8, I12 (parcial), I13, I14 (parcial), I15 (parcial): admin ve todos los centros, renovación de token, checklist, incidentes con foto, gastos con boleta, Mis tareas, resumen y ruta, SOS, supervisor, ajustes de terreno, diagnóstico. **No hechas:** I3 (necesita Android Studio/Xcode y cuentas), I9–I11 (pasajeros: I9 exige confirmar arquitectura), I16 (tiendas) | ver rama `ticket/46-movil-i4-i15` | ver nota del ticket | Migración aditiva `20261002_movil_field_ops.up.sql`. Sin verificar en dispositivo real |
| 02-10-2026 | I12 parcial: pausa de conducción sugerida (configurable, 240 min por defecto) | ver rama ticket/46-movil-i12-pausas | `index-pJKsYmXK.js` | Solo frontend; respaldo /var/www/steps-truck-frontend.pre-movil-20261002T113700Z. Sin verificar en terreno |
| 02-10-2026 | Mejoras tras prueba en terreno: la jornada abierta ya no parte sola (confirmación), pestaña Hoy con jornada y mapa, mapa real (Leaflet/OSM) en jornada, Hoy y Supervisor, rutas asignadas a máquinas con avance y alerta de desvío, flota en vivo, reportar robo | rama ticket/46-movil-mejoras | `index-BUjfcEpg.js` | API: tabla mobile_routes (migración aditiva 20261002_mobile_routes); respaldos /opt/fernando_odoo18/backups/tracker_steps-mejoras-20261002T114933Z.dump, tracker_py-mejoras-20261002T114917Z y /var/www/steps-truck-frontend.pre-movil-20261002T115008Z |
| 03-10-2026 | Restauración del build de `ticket/46-movil-mejoras` (I1–I15 parcial) | `e40c0fa` | `index-BUjfcEpg.js` | La corrida de la mañana desplegó por error un build de `codex/steps-movil` (I1 reimplementado, `index-DTpmu0dy.js`) que pisó lo ya publicado. Restaurado el build de la rama `mejoras`; respaldo del estado erróneo: `steps-truck-frontend.pre-movil-20261003T161339Z`. La rama `ticket/46-movil-jornada-persistente` queda obsoleta. Recomendación histórica sustituida el 03-10 por la consolidación en `codex/steps-movil`. |
| 03-10-2026 | Consolidación de ocho ramas del ticket 46, I1 adaptada sin perder I2–I15 parciales y correcciones de sincronización | `fd1d870` | `index-zbpnCxRX.js` | Canonical: `codex/steps-movil`. Vitest 34/34, pytest 52/52 y ensayo PostgreSQL correctos; JS verificado por SHA-256. Respaldos: `movil-consolidado-20261003T230318Z` y `steps-truck-frontend.pre-movil-20261003T230318Z`. No probado en teléfono físico. |


## Monitor Google y telemetría — 01-11-2026

El panel /truck/#gps usaba Leaflet; la web principal ya usa Google Maps.
Se incorpora Maps JavaScript al panel, con la clave pública de navegador existente,
mapa satelital, tráfico, ajuste a flota y controles nativos. Diseño adaptable con
mapa amplio y fichas laterales; velocidad y frescura siguen usando datos reales.
No cambia el mapa de las jornadas ni el portal completo, Operación o costos.
Google se carga solo al abrir GPS. Si falla, las fichas siguen disponibles.

Evaluación de esta unidad física:
- Posición y velocidad: disponibles.
- ACC: decodificado; validar cableado antes de atribuirlo al encendido del motor.
- Rumbo: presente en las tramas F; falta ampliar almacenamiento y API hasta UI.
- Altura: campo vacío en las posiciones reales analizadas; no inferir cero metros.
- Batería interna: porcentaje confirmado en SMS check, no en las posiciones TCP.
  El paquete de estado de 22 campos requiere especificación del firmware; no adivinar.
- Alimentación externa: desconocida salvo alarma explícita. ACC no prueba alimentación.

Próximas mejoras de valor: alimentación y batería con hora de lectura, alertas de
corte o pérdida de comunicación, recorridos diarios sin jornada y filtrado de deriva
GPS al estacionar. Separar batería del equipo y del auto; un porcentaje aislado no
permite calcular autonomía. Ninguna de estas ampliaciones se presenta como instalada.

Herramientas: el decodificador GPS103 de Traccar sirve para contrastar variantes y
fixtures sin sustituir el receptor. Google Elevation ofrece altura del terreno,
que debe rotularse estimada y requiere API habilitada y revisión de consumo.
No se habilitan APIs adicionales ni consultas de elevación por cada actualización.
Fuentes primarias:
https://github.com/traccar/traccar/blob/master/src/main/java/org/traccar/protocol/Gps103ProtocolDecoder.java
https://developers.google.com/maps/documentation/javascript/elevation

El publicador mantiene copia fresca, respaldo, bloqueo y mismo paquete en Desarrollo
 y Cerro, sin cambios de API, receptor o módulos Odoo. Evidencia privada bajo
/opt/steps-validation/mobile-hardware-map-20261031/ y ~/.codex/local-artifacts/.


Entrega verificada: Tracker 1.5.0, paquete
06809e5db35e20cfa353b8961353abd650c2a9f4, mismo build en Desarrollo y Cerro.
177 pruebas en Windows/Linux, copia fresca TCP a flota sin jornada; navegador de
Desarrollo con polling, fallo de red, revocación y cambio de compañía. Sesión real
de Cerro: vehículo existente, marcador Google, móvil 390 px y escritorio 1440 px;
controles Satélite y Tráfico comprobados, sin escrituras de negocio ni GPS del
 teléfono. La sesión temporal se retira al terminar. Hashes de todos los archivos
servidos verificados; API, receptor, web completa y app compartida intactos.
Evidencia remota en mobile-hardware-map-20261031/<commit>/ con qa.json,
development.json, production.json y respaldos privados. Capturas locales en
~/.codex/local-artifacts/tracker-monitor-modern-20261101/.

Auditoría agregada con tools/gps/audit_coban_capabilities.py: 33 posiciones F,
32 con rumbo, 33 con altura vacía y 33 con ACC; 12 paquetes de otra variante
requieren especificación. No publica IMEI, coordenadas, contraseñas o tramas.

## I10 verificada en Desarrollo — 02-11-2026

Tracker 1.6.1, paquete `2abb2e0678cad981ca15ba90d91ec2c37cbe8275`. Evidencia privada: `/opt/steps-validation/mobile-boarding-20261102/2abb2e0678cad981ca15ba90d91ec2c37cbe8275/` (qa.json, development.json, postgres.log y respaldo). UI/cuenta existentes: `~/.codex/local-artifacts/t46-boarding-20261102/`. API dedicada en 8012; su código coincide con el mismo paquete probado, sin sustituir la API 8000 o el receptor. Las pruebas temporales y las sesiones de revisión se retiraron; cero servicios/eventos ficticios en el destino vivo. Cerro conserva cuatro registros GPS y Desarrollo uno. T46 sigue abierto para I11 y pendientes externos. La API actual de Desarrollo solo se reutiliza si su código y unidad coinciden exactamente; una modificación futura de esa API requiere revisar y certificar su actualización por separado.
