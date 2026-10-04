# Steps App — contrato de interfaz para GPT/Astra

La capa visual puede cambiar composición, jerarquía, iconografía y apariencia **sin tocar** permisos, migración ni sincronización. Todo lo de abajo ya funciona; no hay pantallas placeholder.

## 1. Mapa de pantallas

| Pantalla | Archivo | Cuándo aparece | Estados que cubre |
| --- | --- | --- | --- |
| Bienvenida (ingresar / crear cuenta) | `app/screens/Welcome.tsx` | Sin sesión | error, cargando, aviso de sesión cerrada, botón Google solo si está configurado |
| Incorporación | `app/screens/Onboarding.tsx` | Sesión sin empresa activa | sin empresa, invitación pendiente, solicitud en revisión, correo sin confirmar, error |
| Elegir empresa | `app/screens/CompanyPicker.tsx` | Varias empresas activas y ninguna elegida | — |
| Portada | `app/screens/Portal.tsx` | Empresa activa | validando, sin módulos, módulo incompatible, sin conexión (dentro/fuera de plazo), acciones frecuentes por permiso |
| Contenedor de módulo | `app/screens/ModuleHost.tsx` | Al abrir un módulo | cargando, fallo del módulo aislado |
| Colaciones — persona | `modules/colaciones/Colaciones.tsx` | Permiso `colaciones.read_own` | cargando, no vinculada, no habilitada, sin registros, error de red |
| Colaciones — operador | ídem | Permiso `colaciones.register` | sin tótems, plazo offline vencido, guardado, error de guardado, estado por registro |
| Movilización — conductor | `modules/mobilization/Mobilization.tsx` | `mobilization.drive` | sin servicios, por iniciar/en curso/finalizado, sobrecupo, ubicación denegada |
| Movilización — supervisor | ídem | `mobilization.supervise` | sin servicios, error de red |
| Tracker | `modules/tracker/**` | `tracker.session` | login propio, compuerta de propietario de datos locales |
| Sincronización | `app/screens/SyncScreen.tsx` | Pestaña | pendientes, con problema, reintento, copia, datos de otra cuenta, puntos GPS rechazados |
| Perfil | `app/screens/Profile.tsx` | Pestaña | empresa activa, accesos, dispositivos, privacidad, cerrar sesión (con aviso de pendientes), eliminar cuenta |

## 2. Componentes compartidos y tokens

`shared/ui/index.tsx` (Button, Card, Chip, Banner, Empty, Spinner, Field, Sheet, Confirm, TopBar, NavBar). Tokens de espaciado, radios, tipografía, tamaño táctil y tonos en `shared/ui/tokens.css`; los colores base siguen en `styles.css` (`--green`, `--lime`, `--ink`, …). Reglas: objetivos ≥48 px, etiquetas accesibles, modo oscuro por `prefers-color-scheme`, texto adaptable por `--font-scale`.

## 3. Límites entre vistas y servicios

- Las vistas **no** deciden permisos: preguntan `session.can('<permiso>')` y `visibleModules(...)`.
- Las vistas **no** hablan HTTP directamente: usan `colacionesApi`, `mobilizationApi` y `runtime.enqueue/retry/ops`.
- Cualquier escritura de campo pasa por `runtime.enqueue`, que **lanza** si no se pudo guardar; la vista debe mostrar ese error y nunca un éxito.
- El texto de errores sale de `app/messages.ts` y de `rejectionText` de cada módulo (por código estable, no por texto del servidor).
- Los estados de una operación son `pending | sending | confirmed | auth_required | rejected`; `STATE_LABEL` en `SyncScreen.tsx` los etiqueta.

## 4. Datos de demostración

`src/testing/fakeServer.ts` implementa el contrato `/steps_app/v1` en memoria con empresas «Empresa A/B», operadores, conductores y servicios ficticios. Es la fuente de las pruebas de pantalla (`app/App.test.tsx`) y sirve para capturas reproducibles. **No es evidencia del comportamiento de Odoo.**
