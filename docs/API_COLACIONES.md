# Contrato HTTP de Colaciones

Versión del contrato: **2**. Todas las rutas son públicas por diseño: el token
del tótem es la credencial, es revocable desde Odoo y no da acceso a ningún
dato administrativo.

Cliente y servidor comparten origen en la PWA, por lo que no se habilita CORS.
La App móvil usa un cliente HTTP nativo, que no está sujeto a CORS.

Todas las respuestas llevan `Cache-Control: no-store` y `Content-Type:
application/json`.

## Principios

- **El cliente nunca decide negocio.** Producto, proveedor, cantidad, precio y
  estado los fija el tótem en Odoo. Cualquier campo extra del cliente se ignora.
- **Idempotencia por UUID.** Cada captura lleva un `client_uuid` generado en el
  dispositivo. Reenviarla nunca crea un segundo registro.
- **Errores diferenciados.** `terminal: true` significa "no reintentar"; un
  error temporal no lo lleva y debe reintentarse con espera creciente.

## `GET /colaciones/api/health`

No requiere token. Permite distinguir "servidor caído" de "token revocado" y
detectar un reloj desajustado en el dispositivo.

```json
{
  "ok": true,
  "api_version": 2,
  "capabilities": ["totem_config", "register", "batch_sync", "device_info", "server_time"],
  "max_batch_records": 100,
  "server_time": "2026-08-21T20:45:00Z",
  "min_app_version": "1.0.0",
  "recommended_app_version": "1.0.0"
}
```

Un servidor de la versión 1 no expone esta ruta; el cliente debe tratar el 404
como "sin lote disponible" y seguir usando `/register`.

## `GET /colaciones/api/totem/<token>`

```json
{
  "ok": true,
  "api_version": 2,
  "server_time": "2026-08-21T20:45:00Z",
  "name": "Tótem Casino Packing",
  "code": "TOTEM-01",
  "product": "Almuerzo estándar",
  "supplier": "Casino Los Aromos",
  "identification_method": "barcode",
  "allow_offline": true,
  "offline_max_hours": 72,
  "max_batch_records": 100
}
```

Errores:

| Estado | Cuerpo | Significado |
|---:|---|---|
| 404 | `{"ok": false, "terminal": true, "error": "totem_not_found"}` | Token inexistente, revocado o tótem archivado. |

## `POST /colaciones/api/register`

```json
{
  "token": "…",
  "identifier": "TRAB-0001",
  "client_uuid": "3f2a9c11-…",
  "event_datetime": "2026-08-21T20:45:00Z",
  "offline": false,
  "device": {"uuid": "…", "platform": "pwa", "app_version": "2026.08.21.3"}
}
```

`device` es opcional. `event_datetime` solo se respeta cuando `offline` es
`true`; en línea manda la hora del servidor.

Respuestas:

| Estado | Cuerpo | Significado |
|---:|---|---|
| 200 | `{"ok": true, "duplicate": false, "registration": "COL/0001", "employee": "…"}` | Registrada. |
| 200 | `{"ok": false, "duplicate": true, "message": "La colación ya estaba registrada hoy."}` | Ya existía: mismo UUID, o mismo trabajador/producto/día. |
| 404 | `{"terminal": true, "error": "totem_not_found"}` | Token inválido o revocado. |
| 422 | `{"terminal": true, "error": "rejected", "message": "…"}` | Trabajador inexistente, no habilitado, de otra empresa, sin `client_uuid`, captura offline demasiado antigua o reloj adelantado. |
| 5xx | — | Condición temporal: conservar y reintentar. |

## `POST /colaciones/api/sync`

Sincronización por lote. Máximo `max_batch_records` capturas por envío.

```json
{
  "token": "…",
  "device": {"uuid": "…", "platform": "android", "app_version": "1.0.0"},
  "records": [
    {"client_uuid": "…", "identifier": "TRAB-0001", "event_datetime": "2026-08-21T12:00:00Z", "offline": true}
  ]
}
```

```json
{
  "ok": true,
  "api_version": 2,
  "server_time": "2026-08-21T20:45:00Z",
  "results": [
    {"client_uuid": "…", "status": "registered", "registration": "COL/0001", "employee": "…"},
    {"client_uuid": "…", "status": "duplicate",  "registration": "COL/0002"},
    {"client_uuid": "…", "status": "rejected",   "message": "El trabajador no está habilitado."},
    {"client_uuid": "…", "status": "retry",      "message": "El servidor no pudo procesar la captura."}
  ]
}
```

Una captura inválida **no** aborta el lote: cada UUID recibe su propio estado.

| `status` | Acción del cliente |
|---|---|
| `registered` | Marcar `synced`. |
| `duplicate` | Marcar `synced`; el servidor ya la tenía. |
| `rejected` | Marcar `terminal_error`; no reintentar. |
| `retry` | Conservar `pending` con espera creciente. |

Un UUID que **no** aparece en `results` debe conservarse y reintentarse: el
cliente nunca da por sincronizado lo que el servidor no confirmó.

Errores del lote completo:

| Estado | `error` | Significado |
|---:|---|---|
| 404 | `totem_not_found` | Token inválido o revocado. |
| 422 | `invalid_batch` | `records` no es una lista, o supera el máximo. |

## Información del dispositivo

`device` guarda en el tótem el identificador de instalación, la plataforma y la
versión de la App, recortados a 64 caracteres. No se almacenan IP, modelo,
número de serie ni identificadores publicitarios. **Regenerar acceso** en Odoo
revoca el token y borra estos datos.
