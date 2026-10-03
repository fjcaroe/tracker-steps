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
4. **Despliegue directo a producción** (decisión del 02-10-2026: la app se prueba con datos reales y
   todavía no la usa ningún cliente). Los ambientes preproductivos (Desarrollo, Demo, Cerro El Plomo)
   reciben las mejoras *después*, como futuras mejoras. Procedimiento al final de este documento.
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

### I3 · GPS en segundo plano (Android/iOS)  `[ ]`
- **Qué:** plugin nativo de ubicación en segundo plano (p. ej. `@capacitor-community/background-geolocation`)
  con notificación persistente "Steps está registrando tu ruta", permisos "siempre", ahorro de batería
  configurable y *fallback* a web. Detectar y avisar cuando el sistema mata la app.
- **Requisito externo:** Android Studio / Xcode y cuentas de desarrollador (ver Bloque F).
- **Aceptación:** jornada de 1 hora con pantalla apagada en un teléfono real, sin huecos > 2 min en la ruta.

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

> Decisión de arquitectura pendiente (confirmar con una persona antes de I9): la app antigua guardaba
> asientos y abordajes en Redis y está fuera de servicio; **no se reutiliza**. Los pasajeros viven en la API
> Tracker (PostgreSQL) y se sincronizan a Odoo; contratos de datos en I9.

### I9 · Modelo de servicio y nómina de pasajeros  `[ ]`
- **Qué:** servicios/viajes (ruta, paradas con horario, vehículo, conductor, capacidad real del vehículo) y
  **lista de pasajeros** por servicio (nombre, RUT/ID, parada de subida/bajada, asiento opcional). Diseño del
  esquema aditivo, endpoints y permisos (conductor ve solo sus servicios). Documento de diseño + migración +
  pruebas de API; sin interfaz aún, salvo pantalla de solo lectura "Mi servicio".
- **Aceptación:** crear un servicio con paradas y 3 pasajeros por API y verlo en la app del conductor asignado.

### I10 · Abordaje y descenso  `[ ]`
- **Qué:** marcar subida/bajada por pasajero (lista con búsqueda, **lector QR/código** y registro manual),
  contador de ocupados vs. capacidad, avisos de capacidad completa, ausentes/no-show, hora y posición del
  evento. Funciona sin señal (cola idempotente).
- **Aceptación:** servicio completo sin red → al reconectar el manifiesto final coincide con lo marcado.

### I11 · Paradas y avance del servicio  `[ ]`
- **Qué:** ruta del servicio con paradas, estado por parada (llegada/salida), estimación de llegada, desvíos y
  retrasos; cierre de servicio con manifiesto firmado (conductor) y novedades.
- **Aceptación:** el coordinador ve en la web el avance del servicio y los retrasos en tiempo casi real.

### I12 · Seguridad del pasajero y del conductor  `[~]` 02-10-2026 parcial: SOS con ubicación y aviso de exceso de velocidad hechos; faltan pausas de conducción y contactos de emergencia configurables
- **Qué:** botón SOS (aviso inmediato con ubicación a contactos y a la web), registro de exceso de velocidad
  y de pausas de conducción/descanso (jornada), números de emergencia configurables. Reutiliza incidentes
  y política de protección existentes; **no** habilita control físico del vehículo (bloqueado hasta E4).
- **Aceptación:** SOS visible en la bandeja de incidentes de la web en menos de 10 s, con ubicación.

---

## Bloque D — Gestión ligera (jefe de flota desde el teléfono)

### I13 · Vista de supervisor  `[x]` 02-10-2026 (falta: última posición por vehículo y auditoría explícita de quién atendió, hoy `handled_by`)
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

## Procedimiento de despliegue a producción (`/truck/`)

```bash
# Local: pruebas, commit e integración de la entrega en codex/steps-movil.
git push origin codex/steps-movil
# Registrar el SHA exacto publicado; usarlo como argumento del script remoto.
git rev-parse origin/codex/steps-movil

# Servidor odoo-new (stepsconsulting / us-central1-c):
release=$(mktemp -d /tmp/steps-movil-release-XXXXXXXX)
git clone --branch codex/steps-movil --no-single-branch --depth 1 \
  https://github.com/fjcaroe/tracker-steps.git "$release"
cd "$release"
bash scripts/deploy-steps-movil.sh SHA_EXACTO_REVISADO
```

El script compara fuentes con las variantes conocidas antes de tocar producción, compila y prueba
la app, respalda base/API/frontend, verifica el esquema en una copia PostgreSQL, publica la API
antes de la app y compara SHA-256 del JS servido. Si falla la verificación de publicación,
restaura la entrega anterior. Conserva `.env`, `.venv` y archivos de datos del servidor.
No usa las variables de Google Maps del Web Tracker: Steps Móvil usa Leaflet y una URL pública
de API. El procedimiento de `/web_tracker/` sigue siendo independiente.

Si la iteración cambia la API: `backend/tracker_py` se despliega siguiendo `docs/DEPLOY_WEB_TRACKER.md`
(respaldo de la base y del código, `rsync` excluyendo `.env` y `.venv`, reinicio de
`tracker-steps-api.service`, comprobar `/openapi.json`). Si cambia `step_tracker_portal`: respaldo de
`karo_consultorias`, ensayo en una copia y `-u step_tracker_portal` con el servicio detenido, como en la
entrega del 02-10-2026.

Los preproductivos (`desarrollo`, `demo`, `cerroelplomo`) sirven el mismo directorio de la app mediante
`/etc/nginx/snippets/steps-tracker-portal.conf`; **se actualizan solos al desplegar a producción**, por lo
que una mejora que requiera cambios de API o de módulo en esos ambientes debe probarse allí antes de
publicarse cuando ya haya clientes en ellos.

## Bitácora

| Fecha | Iteración | Commit | JS servido | Notas |
|---|---|---|---|---|
| 02-10-2026 | Base (web/PWA, jornada, GPS con cola, historial) | `f3355be` | `index-CGTxg_cA.js` | Proyectos Android/iOS generados, sin compilar |
| 02-10-2026 | I1 Jornada que no se pierde (retomar desde servidor, limpiar si ya está cerrada, reenvío al volver a primer plano, último envío visible) | ver rama `ticket/46-movil-i1-jornada-no-se-pierde` | `index-r-XhPasL.js` | Se ofrece *Retomar* en vez de retomar sola, porque `/sessions/my` lista las jornadas de los centros de costo del usuario, no solo las suyas (la sesión no guarda quién la inició). Sin verificar en terreno ni en dispositivo; respaldo del front: `steps-truck-frontend.pre-movil-20261002T012511Z` |
| 02-10-2026 | I2 Iniciar jornada sin señal (cola ordenada e idempotente, catálogos en caché, pantalla Pendientes de sincronizar; API: `id` de cliente en `/sessions/start`, reintento idempotente en `/work_orders`) | `62a8173` | `index-CaDWgI7Z.js` | API desplegada antes que la app (sin cambios de esquema). Respaldos: `/opt/fernando_odoo18/backups/tracker_py-i2-20261002T031459Z`, `tracker_steps-i2-20261002T031459Z.dump`; front: `steps-truck-frontend.pre-movil-20261002T031528Z`. Sin verificar en dispositivo real ni en modo avión físico |
| 02-10-2026 | I4–I8, I12 (parcial), I13, I14 (parcial), I15 (parcial): admin ve todos los centros, renovación de token, checklist, incidentes con foto, gastos con boleta, Mis tareas, resumen y ruta, SOS, supervisor, ajustes de terreno, diagnóstico. **No hechas:** I3 (necesita Android Studio/Xcode y cuentas), I9–I11 (pasajeros: I9 exige confirmar arquitectura), I16 (tiendas) | ver rama `ticket/46-movil-i4-i15` | ver nota del ticket | Migración aditiva `20261002_movil_field_ops.up.sql`. Sin verificar en dispositivo real |
| 02-10-2026 | I12 parcial: pausa de conducción sugerida (configurable, 240 min por defecto) | ver rama ticket/46-movil-i12-pausas | `index-pJKsYmXK.js` | Solo frontend; respaldo /var/www/steps-truck-frontend.pre-movil-20261002T113700Z. Sin verificar en terreno |
| 02-10-2026 | Mejoras tras prueba en terreno: la jornada abierta ya no parte sola (confirmación), pestaña Hoy con jornada y mapa, mapa real (Leaflet/OSM) en jornada, Hoy y Supervisor, rutas asignadas a máquinas con avance y alerta de desvío, flota en vivo, reportar robo | rama ticket/46-movil-mejoras | `index-BUjfcEpg.js` | API: tabla mobile_routes (migración aditiva 20261002_mobile_routes); respaldos /opt/fernando_odoo18/backups/tracker_steps-mejoras-20261002T114933Z.dump, tracker_py-mejoras-20261002T114917Z y /var/www/steps-truck-frontend.pre-movil-20261002T115008Z |
| 03-10-2026 | Restauración del build de `ticket/46-movil-mejoras` (I1–I15 parcial) | `e40c0fa` | `index-BUjfcEpg.js` | La corrida de la mañana desplegó por error un build de `codex/steps-movil` (I1 reimplementado, `index-DTpmu0dy.js`) que pisó lo ya publicado. Restaurado el build de la rama `mejoras`; respaldo del estado erróneo: `steps-truck-frontend.pre-movil-20261003T161339Z`. La rama `ticket/46-movil-jornada-persistente` queda obsoleta. Las siguientes iteraciones deben partir de `ticket/46-movil-mejoras`, no de `codex/steps-movil`. |
