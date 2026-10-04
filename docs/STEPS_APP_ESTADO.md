# Steps App unificada — estado real de la entrega (04-10-2026)

Rama: `codex/steps-movil`. Lo que sigue distingue **escrito**, **probado** y **pendiente**; no mezcla uno con otro.

## Matriz de estado

| Capacidad | Implementado | Probado en web/Node | Probado en Odoo real | Probado en Android | Probado en iOS | Pendiente |
| --- | --- | --- | --- | --- | --- | --- |
| Núcleo de identidad, sesiones, autorización (puro) | Sí | **Sí** (20 pruebas) | No | — | — | — |
| Modelos Odoo `step_mobile_portal*`, API y vistas | Sí | Solo sintaxis/pyflakes | **No** (no hay Odoo en el entorno) | — | — | Instalar y correr `odoo -i … --test-tags` |
| Pruebas Odoo (TransactionCase/HttpCase, 4 módulos) | Escritas | — | **No ejecutadas** | — | — | Ejecutarlas; es probable que revelen ajustes |
| Cliente: sesión, empresa, portada, onboarding | Sí | **Sí** (servidor falso del contrato) | No | No | No | Probar contra Odoo |
| Cola durable, idempotencia, aislamiento, offline | Sí | **Sí** | No | No | No | Adaptador SQLite/IndexedDB (ADR-4) |
| Colaciones (persona + operador) | Sí | **Sí** (recorrido y pantallas) | No | No | No | Cámara/escáner; reserva de colación (no existe en el dominio) |
| Movilización (conductor + supervisor) | Sí | **Sí** (recorrido y pantallas) | No | No | No | GPS de ruta en segundo plano (no implementado); marcación manual por nombre (API lista, sin pantalla) |
| Tracker como módulo, con datos conservados | Sí | **Sí** (suite previa + compuerta de propietario) | — | No | No | Unir persona↔usuario Tracker (ADR-6) |
| PR #15: 3 defectos | Corregidos | **Sí** (regresiones) | — | No | No | — |
| Google Sign-In | Servidor listo | Contrato del verificador | No | No | No | Client ID OAuth + plugin nativo (PKCE/sistema) |
| Apple Sign-In | No | — | — | — | No | Requerido por 4.8 si hay registro público/Google en iOS |
| Almacén seguro nativo | Código | — | — | **No** | **No** | Validar `@aparajita/capacitor-secure-storage` en dispositivo |
| Proyecto Android/iOS actualizado (`cap sync`) | Sí | — | — | **Sin compilar** (no hay SDK) | **Sin compilar** (no hay macOS) | Compilar y probar |

## Pruebas ejecutadas en esta entrega

- `mobile/`: `npm test` → **117 pruebas, 11 archivos, aprobadas**; `npm run build` (incluye `tsc -b`) → correcto.
- `python -m pytest -q tools/tests` → **20 aprobadas** (núcleo puro de autorización/sesiones/proveedores).
- `pyflakes` sobre los cuatro addons: sin nombres indefinidos ni errores.
- **No ejecutadas:** pruebas Odoo (sin Odoo/PostgreSQL de Odoo en el entorno; el servidor de nightly no es accesible), `backend/tracker_py` (dependencias no instaladas aquí; **sin cambios en backend**), cualquier prueba en Android/iOS. Los recorridos de cliente usan un **servidor falso** del contrato (`src/testing/fakeServer.ts`), que no demuestra que Odoo se comporte igual.

## Cobertura de los criterios de aceptación

| Criterio | Dónde se prueba hoy | Estado |
| --- | --- | --- |
| Registro sin empresa no ve datos; invitación habilita solo lo asignado | `app/session.test.ts`, `App.test.tsx`; Odoo: `test_portal.py` | Web ✔ · Odoo escrito |
| Token externo inválido/expirado; no unir por correo | `tools/tests` (verificador), `session.test.ts`; Odoo: `TestIdentity` | Núcleo ✔ · Odoo escrito |
| Dos empresas/usuarios: aislamiento API, colas, dispositivos, administración | `journeys.test.ts`; Odoo: `TestAuthorization` | Cliente ✔ · Odoo escrito |
| Revocación en línea y vencimiento offline | `session.test.ts`, `journeys.test.ts` | Web ✔ |
| Colaciones: sin duplicados, permisos persona/operador separados | `journeys.test.ts`; `test_colaciones_app.py` | Web ✔ · Odoo escrito |
| Movilización: conductor ajeno, eventos una vez con autoría | `journeys.test.ts`; `test_mobilization_app.py` | Web ✔ · Odoo escrito |
| Tracker: cuota/fallos no pierden GPS; jornada cerrada no reaparece | `modules/tracker/lib/*.test.ts` | Web ✔ |
| Reinicio/actualización/migración | Compuerta de propietario; cola releída tras reinicio simulado | Parcial: **no** se probó una actualización real sobre una instalación con datos |
| Permisos nativos denegados, pérdida de señal, segundo plano | Ubicación denegada y sin red: sí (web); segundo plano nativo: no | Parcial |

## Qué falta por configuración o herramientas (acciones concretas)

1. **Odoo de prueba:** instalar los módulos y ejecutar sus pruebas (`docs/STEPS_APP_MIGRACION_OFFLINE.md §6`). Hasta entonces, el lado servidor es código revisado pero no ejecutado.
2. **Google:** crear los ID de cliente OAuth (Web/Android/iOS), cargarlos en `step_app.google_client_ids` y elegir el plugin nativo; asignar `googleIdToken` en `platform/google.ts`.
3. **Apple:** decidir y construir antes de publicar en iOS si hay registro público.
4. **Android:** SDK de Android; compilar, instalar, probar almacenamiento seguro, HTTP nativo, ubicación y el comportamiento en segundo plano.
5. **iOS:** macOS/Xcode o CI macOS; `pod install`, permisos de ubicación y Keychain.
6. **Correo saliente de Odoo** para el código de verificación (`step_app.send_mail=1`).
7. **Decisiones de datos:** dónde vive la identidad si hay varias bases Odoo (ADR-7); cómo unir una persona con su usuario Tracker existente (ADR-6); política de privacidad (URL para `VITE_PRIVACY_URL`).
8. **Almacenamiento transaccional** (SQLite/IndexedDB) antes de añadir GPS continuo a Movilización.

## Integración y ramas

Todo está en `codex/steps-movil` (rama canónica de Steps Móvil), en commits separados: PR #15 corregida → inventario/ADR + núcleo Odoo → puentes Odoo → núcleo del cliente → app unificada → documentación. No se fusionó ninguna rama de otro producto; `step_mobilization` (solo en `develop`/`codex/cierre-cambios-locales`) se declara como dependencia del puente y **no se copió**. La rama de integración propuesta en el encargo (`integration/steps-app`) no se creó porque esta sesión tiene fijada la rama de entrega; puede derivarse sin reescribir historia. Web Tracker (`codex/web-tracker-redesign`) no se tocó. No se desplegó nada ni se publicó en tiendas.
