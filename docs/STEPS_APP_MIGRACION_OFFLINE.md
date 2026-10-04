# Steps App — migración, funcionamiento sin señal y conservación de datos

## 1. Qué cambió y qué no

El Tracker se movió a `mobile/src/modules/tracker/` **sin cambiar sus claves de almacenamiento ni sus IDs**. Las claves actuales son (todas `localStorage`):

`steps_movil_token`, `steps_movil_pending` (puntos GPS por jornada), `steps_movil_points_rejected`, `steps_movil_finished_ids`, `steps_movil_active`, `steps_movil_outbox`, `steps_movil_outbox_ids`, `steps_movil_last_sync`, `steps_movil_settings`, `steps_movil_token_refreshed`, y por jornada `steps_movil_checked_<id>` y la ruta.

Por tanto una instalación existente que se actualice a la app unificada **conserva sus jornadas, GPS e historial sin migrar nada**. Las claves nuevas de la app unificada usan otro prefijo (`steps.*`): `steps.queue.v1.<persona>.<empresa>` (colas), `steps.session.v1.<persona>` (caché de permisos), `steps.device.uuid.v1` y, en el almacén seguro, `steps.tokens.v1`.

### Propietario de los datos antiguos

Las claves antiguas no dicen de quién son. **No se atribuyen automáticamente** a quien inicie sesión (`modules/tracker/lib/owner.ts`):

| Situación | Comportamiento |
| --- | --- |
| Sin datos locales | Quien entra queda como dueño. |
| Datos locales sin dueño conocido (versión anterior) | Compuerta «hay datos sin dueño conocido»: confirmar «son míos», o guardar copia. Mientras tanto no se envía nada. |
| Datos de otra cuenta del Tracker | Se bloquea el envío, se nombra al dueño y se ofrece guardar copia o entrar con la cuenta original. Nada se borra. |

Hacer esto sin red es seguro: la compuerta no necesita servidor.

## 2. Cola durable de la app unificada

`sync/queue.ts` + `sync/engine.ts`:

- **Ámbito.** Una cola por `(persona, empresa)`; cada operación lleva `module`, `kind` y `group`. Cambiar de empresa o de cuenta no mezcla ni elimina pendientes; las colas ajenas se listan y se pueden exportar pero **nunca se envían con otra sesión** (`runQueue` se niega si `sessionPersonId ≠ scope.personId`).
- **Persistir antes de anunciar.** `enqueue` escribe y verifica la lectura de vuelta; si falla lanza `StorageError` y la pantalla muestra el error (hay prueba de interfaz: no hay falso éxito).
- **Idempotencia.** El UUID de la operación nace en el dispositivo y es la clave del servidor. Doble pulsación → misma operación.
- **Estados.** `pending` → `sending` → `confirmed` | `rejected` | `auth_required`. Un `sending` heredado de un cierre brusco vuelve a `pending`.
- **Clasificación por contrato.** Un HTTP 400/404/409/422 del lote completo **no** descarta datos: se conserva y reintenta. Solo un `rejected` explícito por registro, o un código de negocio conocido del endpoint (`cannot_open`, `trip_not_found`…), es definitivo. 401/403 → `auth_required` y se detiene todo (no es rechazo del negocio). Red/5xx → se reintenta y detiene el envío.
- **Un rechazo no bloquea a los demás**: ni a otras jornadas ni a otros módulos. Dentro de un grupo, un fallo transitorio sí detiene lo posterior (no se cierra un viaje antes de enviar sus marcas).
- **Sin borrados automáticos.** Pendientes y rechazadas nunca se podan; solo se retiran confirmadas con más de 7 días. Cerrar sesión no toca las colas.
- **Reintentar real.** `runtime.retry()` devuelve rechazadas/bloqueadas a pendientes y ejecuta un envío; si ya hay uno en curso, encadena otra pasada al terminar. Volver a entrar reanuda lo que solo esperaba sesión.
- **Minimización.** Tras confirmar, se borra el identificador del trabajador/pasajero del payload guardado.
- **Exportación.** Todas las pantallas de problemas ofrecen «Guardar copia» (JSON) y «Reintentar».

### Puntos GPS del Tracker (PR #15)

El Tracker usa su propia cola de puntos. Se corrigieron (commit `162c3cf`): lote que solo sale de la cola si lo apartado se guardó y **verificó**; sin tope que expulse puntos antiguos; historial persistente de jornadas terminadas que descarta respuestas atrasadas del servidor; aviso, copia y reintento en la interfaz. Sigue en `localStorage`.

## 3. Autorización sin conexión

Ver ADR-5. Tras cada validación el servidor entrega `offline_until` (por omisión +72 h; configurable por empresa). Sin conexión: dentro del plazo se opera con los permisos de la última validación; vencido, **se bloquean acciones nuevas** y la cola se conserva. Se revalida al recuperar señal, al volver a primer plano y al cambiar de empresa. **Compromiso aceptado:** una revocación remota no llega a un teléfono desconectado hasta que vuelva a validar; el servidor aplica la política por registro descrita en `STEPS_APP_AUTORIZACION_API.md §3`.

## 4. Límites reconocidos del almacenamiento

`localStorage` reescribe todo el JSON en cada cambio (se observó coste cuadrático con miles de puntos) y no es transaccional. Está bien para el volumen del piloto de Colaciones y Movilización (cientos de operaciones) pero **no para GPS continuo de Movilización**. Por eso el puerto `KeyValueStore` es asíncrono y está listo para un adaptador SQLite (`@capacitor-community/sqlite`) en nativo e IndexedDB en web. **Pendiente**: requiere validación en dispositivo. La web guarda tokens solo en `sessionStorage`; en nativo, en Keychain/Keystore (`@aparajita/capacitor-secure-storage`, no probado en dispositivo).

## 5. Identificador y coexistencia

Se conserva `cl.stepsapp.movil`, nombre y firma: cambiarlos crea otra app y pierde el almacenamiento previo. Durante el piloto las instalaciones actuales siguen operativas; la actualización a esta versión (`2.0.0-piloto.1`) debe probarse primero con una instalación real que tenga jornadas pendientes (**pendiente**). Reversión: reinstalar la versión 1.2.x; los datos de Tracker no cambian de formato, por lo que son legibles por ella. Los datos de la cola nueva no existen en la versión anterior.

## 6. Propuesta de despliegue (no ejecutada)

Steps App y Steps Móvil/Tracker son entregas distintas del Web Tracker (`docs/DEPLOY_WEB_TRACKER.md`), que no se toca.

1. Odoo (primero Desarrollo/Demo): respaldar, instalar `step_mobile_portal`, luego `step_mobile_portal_colaciones`, `step_mobile_portal_mobilization` (requiere `step_mobilization` de `develop`) y `step_mobile_portal_tracker`; configurar los parámetros de `STEPS_APP_AUTORIZACION_API.md §4`; ejecutar las pruebas Odoo; verificar logs y recorridos con datos sintéticos.
2. Proxy: enrutar `/steps_app/` a Odoo y excluirlo de cachés.
3. Cliente: compilar con `VITE_STEPS_API_BASE` apuntando al ambiente objetivo (no el valor por omisión sin revisarlo) desde un checkout fresco de `codex/steps-movil`. Nunca compilar para producción apuntando a localhost; no poner secretos en variables `VITE_*`.
4. Android/iOS: `npm run cap:sync`, compilar y probar en dispositivo antes de cualquier tienda.
