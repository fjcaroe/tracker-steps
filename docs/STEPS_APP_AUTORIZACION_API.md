# Steps App — autorización y API (`/steps_app/v1`)

Implementación: `step_mobile_portal` (núcleo) y los puentes `step_mobile_portal_colaciones`, `step_mobile_portal_mobilization`, `step_mobile_portal_tracker`. Decisiones: `docs/STEPS_APP_INVENTARIO_Y_ADR.md`.

## 1. Matriz de módulos, roles y permisos

Los permisos viven en `step.app.module.role.permissions` (datos cargados por cada puente). **El servidor valida el permiso en cada llamada**; ocultar un botón o tarjeta en la app no autoriza ni protege nada.

| Módulo | Rol | Permisos | Vínculo exigido en la membresía | Puede |
| --- | --- | --- | --- | --- |
| `colaciones` | `persona` | `colaciones.read_own` | `employee_id` (trabajador, misma empresa, único) | Ver su habilitación y sus registros. |
| `colaciones` | `operador` | `colaciones.register` | — (alcance opcional por tótem: `scope_ids`) | Registrar entregas en los tótems de su empresa y alcance. |
| `mobilization` | `conductor` | `mobilization.drive` | `partner_id` marcado `step_chofer` (lo exige una restricción) | Ver/abrir/cerrar **sus** servicios y marcar pasajeros. |
| `mobilization` | `supervisor` | `mobilization.supervise` | — | Consultar servicios de su empresa y quién marcó cada evento. |
| `tracker` | `operador` | `tracker.session` | (pendiente, ADR-6) | Habilita el módulo; el Tracker conserva su API y login. |
| `tracker` | `supervisor` | `tracker.session`, `tracker.supervise` | (pendiente) | Ídem con vista de supervisión. |

Reglas transversales:

- **Vínculos explícitos.** Un registro público no crea `res.users`, `hr.employee` ni acceso administrativo. El vínculo persona↔trabajador/chofer lo hace un administrador a mano; nunca por nombre o correo coincidente. Cada vínculo y cambio de estado queda en `step.app.audit`.
- **Aislamiento por empresa.** Cada llamada con empresa exige cabecera `X-Steps-Org` (UID estable) y una membresía activa. «Empresa inexistente» y «sin membresía» responden igual (`organization_not_authorized`). Los viajes, tótems y registros se filtran por la empresa **autorizada**, jamás por un identificador del cliente.
- **Administración.** Los grupos `Consulta`/`Administrador de accesos` están acotados por regla de registro a las empresas permitidas del usuario Odoo. Suspender cuenta y cerrar sesiones globales se reservan a administradores del sistema, porque afectan a otras empresas de la persona. Suspender o revocar una **membresía** no toca la identidad ni otras membresías.
- **Sin `sudo()` general.** La API autentica primero y solo entonces eleva privilegios, con consultas acotadas a persona y empresa. Los modelos de dominio (`step.colacion.*`, `step.movi.*`) conservan sus validaciones (elegibilidad, duplicados, antigüedad offline, capacidad).

## 2. Endpoints

JSON plano, `Cache-Control: no-store`, sin cookies ni CSRF (credencial = `Authorization: Bearer`). Errores: `{"ok": false, "error": "<código>", "message": "...", "terminal": bool}`. El cliente decide por `error`.

| Método y ruta | Auth | Descripción |
| --- | --- | --- |
| `GET /health` | — | Versión de API, hora del servidor y proveedores disponibles. |
| `POST /auth/register` | — | Correo + contraseña (≥10 car., scrypt). Crea persona sin empresa y sesión. `409 email_in_use` si existe. |
| `POST /auth/login` | — | Bloqueo 15 min tras 5 intentos fallidos. Tiempo de verificación constante aunque la cuenta no exista. |
| `POST /auth/verify_email` | — | Código enviado por correo (si `step_app.send_mail=1`). |
| `POST /auth/google` | — | Valida firma, emisor, audiencia y expiración del ID token; identifica por `sub`. `503 provider_not_configured` sin `step_app.google_client_ids`. |
| `POST /auth/apple` | — | **Pendiente**: responde `503 provider_not_configured`. |
| `POST /auth/test` | — | Solo con `step_app.allow_test_provider=1` (nunca en producción). |
| `POST /auth/refresh` | refresh | Rotación; presentar un refresh ya usado **revoca la sesión** (`session_revoked`). |
| `POST /auth/logout` | sesión | Revoca la sesión actual. |
| `POST /auth/link/google` | sesión | Vincula Google a la cuenta **autenticada** (prueba de control), nunca por correo. |
| `GET /me` | sesión | Persona, proveedores, membresías, estado de incorporación. |
| `POST /invitations/accept` | sesión | Requiere código vigente y que el correo invitado esté **verificado** en la cuenta. |
| `POST /access/request` | sesión | Solicita membresía con el código corto de empresa (no otorga acceso). |
| `GET /catalog?supported=mod:ver,…` | sesión + org | Módulos autorizados y compatibles; informa los que exigen actualizar la app; `offline_until`. |
| `GET /devices`, `POST /devices/<id>/revoke`, `POST /account/delete` | sesión | Gestión de dispositivos y solicitud de eliminación. |
| `GET /colaciones/me`, `GET /colaciones/totems`, `POST /colaciones/register` | sesión + org | Ver §3. |
| `GET /mobilization/trips[/<id>]`, `POST …/open`, `…/close`, `…/events`, `GET /mobilization/passengers`, `GET /mobilization/supervisor/trips` | sesión + org | Ver §3. |

Sesiones: acceso 30 min, renovación 30 días rotatoria. Solo se guarda el SHA-256 de cada token. Revocar dispositivo o persona surte efecto en la siguiente llamada en línea.

## 3. Idempotencia y política de eventos capturados sin conexión

- **Colaciones:** `client_uuid` por captura; reenviar nunca crea otra (UUID o mismo trabajador/producto/día → `duplicate`, que el cliente trata como confirmada). El lote responde un estado por UUID: `registered`, `duplicate`, `rejected` (definitivo) o `retry` (temporal). El **token del tótem no sale de Odoo** y no sustituye la sesión personal. La autoría del operador queda en `step.colacion.registration.app_operator_id`.
- **Movilización:** `idempotency_key` por evento y dispositivo (`step.mobilization.passenger.event`, restricción única existente). El pasajero se resuelve en servidor (empleado activo de la empresa del viaje, por código o id): el conductor nunca recibe nóminas. Autoría en `app_person_id`. El dispositivo de la app se registra en `step.mobilization.driver.device` **sin token ni código de emparejamiento**, de modo que la API `/mobilization/v1` heredada no puede usarlo. Las credenciales de la API de dispositivos no se modificaron.
- **Revocación (ADR-5).** Un evento capturado en `t` se acepta si una concesión (módulo+rol, y alcance si lo hay) estaba vigente en `t` **y** el acceso a la empresa no había terminado antes de `t` (`membership.access_ended_at`). Si no, se rechaza con `grant_not_valid_at_capture`, `access_ended_before_capture` o `resource_out_of_scope`. Para sincronizar tras una suspensión, el endpoint de eventos acepta una membresía ya terminada **solo** para evaluar la política por registro; las lecturas en línea quedan cerradas.

## 4. Configuración (parámetros del sistema, sin secretos en el repositorio)

| Parámetro | Efecto |
| --- | --- |
| `step_app.google_client_ids` | IDs de cliente OAuth aceptados como audiencia (separados por coma). Sin él, Google responde `provider_not_configured`. |
| `step_app.send_mail` | `1` envía el código de verificación por correo saliente de Odoo. Por omisión no envía y solo registra. |
| `step_app.allow_test_provider` | `1` habilita `/auth/test`. **Solo en ambientes de prueba.** |
| `res.company.step_app_offline_hours` | Plazo sin conexión por empresa (1–720 h, por omisión 72). |

Limitaciones conocidas del piloto: `email_in_use` permite enumerar correos registrados (mitigado por bloqueo de intentos, no por límite de registro); no hay limitación de tasa por IP; Apple no está implementado.
