# Steps App unificada — inventario (Etapa 0) y decisiones de arquitectura

Fecha: 04-10-2026. Encargo: `docs/PROMPT_CLAUDE_STEPS_APP_UNIFICADA_2026-10-03.md`.
Rama de integración: `codex/steps-movil` (rama canónica de Steps Móvil; ver §5).

## 1. Inventario verificado

Se verificó contra `origin` el 04-10-2026. «Verificado» significa que se leyó el código en la rama indicada; no que se ejecutó contra un Odoo real (en el entorno de esta entrega no hay Odoo instalado).

| Dominio | Dónde está | Qué existe | Qué falta o debe adaptarse |
| --- | --- | --- | --- |
| Cliente móvil (Tracker) | `mobile/` en `codex/steps-movil` | React 19, TypeScript, Vite 7, Capacitor 7 (`cl.stepsapp.movil`). Jornadas, GPS, historial, tareas, supervisor, cola de operaciones y de puntos en `localStorage`. Login por usuario/contraseña propio del Tracker (JWT, 30 días). | Sin sesión personal unificada, sin empresas, sin módulos. Almacenamiento sin separar por identidad. |
| API Tracker | `backend/tracker_py` (FastAPI) | JWT propio; `/auth/login`, `/sessions/*`, `/mobile/*`. `POST /v1/classic-session` intercambia una identidad Odoo firmada (puente HMAC `steps-tracker-v1`, vida ≤ 90 s) por un token Tracker. | El usuario Tracker derivado de Odoo es nuevo (`odoo-<tenant>-<uid>`): **no** se une a usuarios Tracker existentes. Ver ADR-6. |
| Colaciones Odoo | `step_colaciones/` en `codex/steps-movil` | Tótem con token de acceso, API `/colaciones/api/*` (contrato 2), registro idempotente por `client_uuid`, lote, validaciones de elegibilidad/duplicado/antigüedad offline. | No existe el concepto de «persona» ni de operador con sesión propia: la credencial es el token del tótem. |
| Colaciones móvil/PWA | `docs/COLACIONES_WEB_Y_APP_MOVIL.md`, `colaciones_web/` y repo `steps_colaciones_mobile` | Documentación de una PWA y una app. | No se encontró aquí una app Android/iOS compilable de Colaciones; `colaciones_web/` es la PWA de tótem. El módulo móvil de este encargo se construye en `mobile/`. |
| Movilización Odoo | `step_mobilization/` **solo** en `develop` y `codex/cierre-cambios-locales` (no en `codex/steps-movil`) | Viajes (`step.movi.registry`), eventos de pasajero append-only (`step.mobilization.passenger.event`), puntos GPS, dispositivos de chofer con código de emparejamiento y token (hash), API `/mobilization/v1` con `X-Device-UUID`/`X-Device-Token`. | Las credenciales son por dispositivo, no por persona. No hay listado de «mis servicios». |
| Web Tracker | `codex/web-tracker-redesign` | Frontend web con su propio despliegue. | Fuera de alcance: no se toca ni se despliega. |
| PR #15 | head `8797edb` | Recuperación y sincronización móvil. | Tres defectos confirmados; corregidos en `162c3cf` (ver §4). |

### Hallazgos que condicionan el diseño

1. **Odoo ya es la autoridad de empresas y empleados**, y el puente Tracker ya firma identidades desde Odoo. Duplicar identidad en otro servicio crearía dos fuentes de verdad.
2. **`step_mobilization` no está en la base móvil.** Se declara como dependencia de un puente opcional; no se copia código de otra rama (el encargo prohíbe fusionar ramas de productos distintos para obtener un archivo).
3. **Los tres dominios usan `sudo()` tras autenticar** su credencial propia. El portal nuevo no puede heredar ese patrón: autentica primero, resuelve membresía y concesión, y solo entonces opera, acotando por empresa.
4. **`localStorage` reescribe todo el JSON en cada punto** (coste cuadrático medido al sembrar 5.001 puntos en pruebas) y no es transaccional. Es la causa estructural de varios riesgos del encargo; ver ADR-4.

## 2. Decisiones de arquitectura (ADR)

### ADR-1 — Dónde vive la fachada de API: **Odoo**, módulo `step_mobile_portal`

Contexto: hay que decidir entre un servicio nuevo, el backend FastAPI del Tracker u Odoo.

Decisión: la fachada de sesión, membresías y catálogo es un módulo Odoo (`/steps_app/v1/*`). Odoo ya administra empresas, empleados y conductores, y el encargo exige que el administrador gestione accesos desde Odoo. Un servicio adicional obligaría a sincronizar identidad y autorización y a operar otra pieza.

Consecuencias: el Tracker (FastAPI) mantiene su API y su JWT; se integra como módulo (ADR-6). Odoo no emite JavaScript ejecutable: solo catálogo y permisos.

### ADR-2 — Identidad, membresía y dispositivo son tres cosas

- `step.app.person`: la persona. Existe sin empresa. Un registro público **no** crea `res.users`, `hr.employee` ni acceso administrativo.
- `step.app.identity`: proveedor (`password`, `google`, `apple`, `test`) + identificador estable del proveedor (`sub`). Único por `(provider, subject)`. El correo no identifica ni une cuentas.
- `step.app.membership`: persona ↔ empresa, con estado y vigencia. Suspender una membresía no toca la identidad ni otras membresías.
- `step.app.grant`: concesión de módulo+rol dentro de una membresía, con vigencia y alcance opcional (p. ej. tótems).
- `step.app.device`/`step.app.session`: dispositivo y sesiones revocables. Un tótem compartido es un dispositivo de tipo `shared` y solo puede tener concesiones de operador.

### ADR-3 — Sesiones propias, opacas y revocables

Tokens aleatorios de 256 bits; en servidor solo se guarda su SHA-256. Acceso: 30 min. Renovación: rotatoria, 30 días, con detección de reutilización (un refresh ya usado revoca la familia). Revocar sesión o dispositivo desde Odoo surte efecto en la siguiente llamada en línea. No se usan JWT autocontenidos porque no se podrían revocar.

Validación de proveedores externos: el servidor verifica firma, emisor, audiencia y expiración del ID token de Google/Apple con una biblioteca mantenida (`google-auth`), configurada con `step_app.google_client_ids`. Sin esa configuración el endpoint responde `provider_not_configured`. El proveedor `test` solo existe si `step_app.allow_test_provider=1` y se rechaza en producción.

### ADR-4 — Almacenamiento en cliente: puerto transaccional, con IndexedDB en web y SQLite en nativo

El cliente accede a datos locales por una interfaz (`shared/storage`) con transacciones por lote, claves con ámbito `identidad/empresa/módulo` y verificación de escritura. En esta entrega se implementan: un adaptador en memoria (pruebas) y el adaptador `localStorage` con **escritura verificada y falla visible**. El adaptador SQLite (`@capacitor-community/sqlite`) y el de IndexedDB quedan **pendientes** (ver `STEPS_APP_ESTADO.md`): requieren dispositivo/emulador para validarse y no se declaran como hechos.

### ADR-5 — Autorización offline limitada

Una cuenta ya validada puede operar sin conexión hasta `offline_until` (por defecto 72 h desde la última validación, configurable por empresa). Vencido el plazo se bloquean **nuevas** acciones protegidas; la cola existente se conserva y no se descarta. Una revocación remota no puede llegar a un teléfono sin conexión: es el compromiso aceptado. Política de servidor para eventos capturados antes de una revocación: se aceptan si `captured_at` es anterior a la revocación y la concesión estaba vigente en ese instante (se compara con la historia de la concesión, no con su estado actual); si no, se rechazan con `grant_revoked`, se registran en auditoría y quedan en la cola del cliente como rechazo definitivo recuperable.

### ADR-6 — Tracker como módulo, sin romper sus datos

El módulo Tracker conserva su login y su JWT actuales dentro de la app unificada y todas las claves/IDs de jornada. Razón: el puente `classic-session` crea usuarios Tracker nuevos y huérfanos de las jornadas existentes. La unión persona↔usuario Tracker requiere una decisión de datos explícita (se propone un vínculo manual en Odoo); hasta entonces no se intercambia sesión. Estado: **pendiente por decisión de datos**.

### ADR-7 — Directorio de organizaciones y bases múltiples

Cada `res.company` recibe `step_app_org_uid` (UUID estable). El cliente nunca acepta una URL de servidor escrita por el usuario: la URL del backend viene de configuración de compilación (`VITE_STEPS_API_BASE`, público por diseño, sin secretos). Supuesto a validar con Fernando: **una sola base Odoo administra identidad** y es autoridad de las empresas que contiene. Si hubiese varias bases, habría que añadir un directorio central; el UID estable permite hacerlo sin migrar identidades.

### ADR-8 — Identificador de la app

Se **conserva** `cl.stepsapp.movil` y el nombre «Steps Móvil» durante el piloto, para no perder el almacenamiento previo ni romper la actualización de instalaciones existentes. Cambiar `appId`/firma crea otra app. El cambio de nombre comercial a «Steps» y la coexistencia se deciden en la etapa de lanzamiento.

## 3. Módulos Odoo a crear

| Módulo | Depende de | Contenido |
| --- | --- | --- |
| `step_mobile_portal` | `base`, `mail` | Núcleo: personas, identidades, membresías, concesiones, invitaciones, dispositivos, sesiones, auditoría, catálogo, API de sesión. |
| `step_mobile_portal_colaciones` | portal + `step_colaciones` | Roles `persona`/`operador`; API de habilitación propia y de registro por operador. |
| `step_mobile_portal_mobilization` | portal + `step_mobilization` | Roles `conductor`/`supervisor`; API de servicios asignados, eventos y cierre. |

## 4. PR #15

Los tres defectos del informe se reprodujeron sobre el head `8797edb` (el informe y su script de reproducción están en `codex/cierre-cambios-locales`) y se corrigieron en `162c3cf` con regresiones: lote que solo sale de la cola tras apartarse con escritura verificada; sin tope que expulse puntos; historial persistente de jornadas terminadas y descarte de respuestas obsoletas. La interfaz muestra aviso, copia y reintento de puntos apartados. 54/54 pruebas móviles pasan; no se probó en dispositivo.

## 5. Ramas

Rama de integración: `codex/steps-movil`. Esta sesión tiene fijada esa rama de entrega, por lo que no se creó una rama paralela; el trabajo está en commits separados por tema y puede moverse a `integration/steps-app` sin reescribir historia. No se fusionó ninguna rama completa de otro producto. `step_mobilization` se consume como dependencia declarada, no se copia.
