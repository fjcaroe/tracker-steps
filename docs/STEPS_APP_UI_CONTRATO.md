# Steps App — contrato de interfaz para GPT/Astra (actualizado 04-10-2026)

La capa visual puede cambiar composición, jerarquía, iconografía y apariencia **sin tocar** autenticación, permisos, migración, almacenamiento ni sincronización. Este documento describe las pantallas y contratos implementados; no certifica funcionamiento nativo en Android/iOS. Para verlo sin Odoo: `cd mobile && npm run demo` (ver §6). Para un encargo visual acotado, usar [PROMPT_ASTRA_STEPS_APP_VISUAL.md](PROMPT_ASTRA_STEPS_APP_VISUAL.md).

## 1. Navegación y rutas

La app no usa URL por pantalla: la navegación se mantiene en el estado de `mobile/src/app/App.tsx`. Conservar ese mecanismo en esta entrega visual. Las rutas de archivos de las tablas son relativas a `mobile/src/`. Respetar estas condiciones de entrada:

| Pantalla (id) | Archivo | Condición para mostrarla | Salidas |
| --- | --- | --- | --- |
| `welcome` | `app/screens/Welcome.tsx` | `session.status === 'signed_out'` | login / registro / recuperar → `onboarding` o `portal` |
| `onboarding` | `app/screens/Onboarding.tsx` | sesión sin empresa activa y sin `needsOrgChoice` | aceptar invitación, solicitar acceso, confirmar correo |
| `company-picker` | `app/screens/CompanyPicker.tsx` | `needsOrgChoice` (varias membresías activas) | `session.selectOrg(uid)` |
| `portal` (tab *Inicio*) | `app/screens/Portal.tsx` | `orgUid` y `catalog` presentes | abrir módulo (`onOpen(id, view?)`) |
| `module:<id>` | `app/screens/ModuleHost.tsx` | módulo visible por catálogo + permiso | `onExit()` |
| `sync` (tab *Sincronización*) | `app/screens/SyncScreen.tsx` | empresa lista | reintentar, copia, otras cuentas |
| `profile` (tab *Perfil*) | `app/screens/Profile.tsx` | sesión iniciada | cambiar empresa, dispositivos, privacidad, cerrar sesión, eliminar cuenta |

Vistas internas de módulo (parámetro `view` de `ModuleProps`): Colaciones `persona` | `registrar`; Movilización `servicios` | `supervisor` (+ detalle de un servicio). Tracker conserva sus propias pestañas (`modules/tracker/**`).

## 2. Estados que cada pantalla debe poder mostrar

| Pantalla | Carga | Vacío | Error | Permisos | Offline |
| --- | --- | --- | --- | --- | --- |
| Bienvenida | botón «Un momento…» | — | mensaje por código (`app/messages.ts`) | aviso «sesión cerrada» (`notice`) | error de red claro |
| Incorporación | — | sin empresa | mensaje en `Banner` | explica que crear cuenta no da acceso | requiere red para aceptar/solicitar |
| Portada | «Validando tu acceso…» | «Aún no tienes módulos habilitados» | `notice` | acciones frecuentes solo con permiso; módulo incompatible → «actualiza la app» | `access`: `offline_valid` (aviso con hora límite) / `offline_expired` (bloquea acciones nuevas, conserva lo guardado) |
| Colaciones persona | «Cargando…» | «no vinculada a un trabajador» / «sin registros» | reintentar | sin permiso → aviso | error con reintento |
| Colaciones operador | «Cargando tótems…» | «no tienes tótems autorizados» | error de guardado (no hay falso éxito) | alcance por tótem | guarda en el teléfono; estado por registro |
| Movilización conductor | «Cargando servicios…» | «no tienes servicios asignados» | reintentar | `driver_not_linked` | servicio por iniciar/en curso/finalizado según lo local |
| Movilización supervisor | «Cargando…» | «no hay servicios hoy» | aviso | solo con `mobilization.supervise` | actualizar |
| Sincronización | `syncing` | «No hay nada pendiente» | `storageProblem`, `lastHalt` | `auth_required` | `lastHalt: network` |
| Perfil | dispositivos «Cargando…» | — | `Banner` | confirmaciones destructivas | cerrar sesión avisa de lo pendiente |

## 3. Componentes compartidos (`shared/ui`)

| Componente | Propiedades | Notas |
| --- | --- | --- |
| `Button` | `variant: 'default' \| 'primary' \| 'danger' \| 'quiet'`, props de `<button>` | objetivo ≥ 48 px |
| `Card` | `label?` | sección con nombre accesible |
| `Chip` | `tone: 'info' \| 'ok' \| 'warn' \| 'bad'` | estados de operación |
| `Banner` | `tone` | `role="alert"` si `bad`, si no `status` |
| `Empty` | `title`, `hint?` | estado vacío |
| `Spinner` | `label?` | carga |
| `Field` | `label`, `hint?` | etiqueta accesible + ayuda |
| `ScanField` | `label`, `hint?`, `value`, `onChange` | teclear/lector/cámara (experimental) con alternativa siempre disponible |
| `Sheet`, `Confirm` | `title`, `onClose` / `confirmLabel`, `onConfirm`, `onCancel`, `danger?` | hojas modales |
| `TopBar`, `NavBar` | `title`, `onBack?`, `right?` / `items`, `current`, `onSelect` | `badge` en la pestaña de sincronización |

Tokens: `shared/ui/tokens.css` (espaciado, radios, tipografía, tamaño táctil, tonos claro/oscuro); colores base en `styles.css`. Estilos de componentes: `shared/ui/ui.css`.

## 4. Límites entre vistas y servicios (lo que NO debe cambiar)

- **Permisos:** `session.can('<permiso>')`, `visibleModules(...)`. Las vistas no deciden accesos.
- **HTTP:** solo vía `colacionesApi`, `mobilizationApi`, `runtime.session.api`. Nada de `fetch` en vistas.
- **Escritura de campo:** siempre `runtime.enqueue(...)`, que **lanza** `StorageError` si no se pudo guardar: mostrar ese error, nunca éxito.
- **Estados de operación:** `pending | sending | confirmed | auth_required | rejected | blocked` (`STATE_LABEL` en `SyncScreen.tsx`); el motivo legible sale de `rejectionText` de cada módulo y `app/messages.ts`.
- **Suscripciones:** `useSession()`, `useSyncState()`, `useRuntime()` (`app/context.tsx`).

## 5. Datos de ejemplo y recorridos

Los tipos están en `shared/contracts.ts`. Escenarios ficticios (`src/testing/demo.ts`, `?scenario=`):

| Escenario | Qué muestra |
| --- | --- |
| `nuevo` | bienvenida → crear cuenta → incorporación sin empresa |
| `conductor` | portada con «Mis servicios»; servicio «Ruta prueba» por iniciar |
| `beneficiaria` | Colaciones persona con 6 registros de historial |
| `pendientes` | teléfono **sin señal**, 2 entregas pendientes y 1 rechazada («no habilitado») |
| `multiempresa` | elegir empresa; Norte: Colaciones+Tracker, Sur: Movilización |
| `supervisor` | servicio en curso con un pasajero y su autor |
| `sin-modulos` | empresa activa sin módulos |

Recorridos que ya pasan en pruebas de pantalla (`app/App.test.tsx`, `testing/demo.test.tsx`) y contra Odoo real (`mobile/e2e`): registro → incorporación; ingreso → portada por permisos; operar sin señal → confirmada; rechazo con motivo; cambio de empresa; cierre de sesión con pendientes; recuperación de acceso.

## 6. Cómo trabajar la apariencia

1. `cd mobile && npm run demo` → abrir `/?scenario=<nombre>`. Franja roja permanente «MODO DEMOSTRACIÓN».
2. Editar `mobile/src/shared/ui/*`, `mobile/src/styles.css` y la presentación de las pantallas acordadas. Para la estructura común se permiten clases y JSX en `mobile/src/app/App.tsx`, preservando hooks, condiciones, navegación y callbacks. Las vistas piloto están en `mobile/src/modules/colaciones/Colaciones.tsx` y `mobile/src/modules/mobilization/Mobilization.tsx`.
3. Conservar textos de acciones, nombres accesibles, roles, estados y significado de confirmaciones. No modificar pruebas para ocultar una regresión. Ejecutar `npm test` y `npm run build` una vez al cerrar; repetir tras una corrección pertinente. Cumplir además las verificaciones requeridas por `AGENTS.md`.
4. No tocar autenticación, APIs, permisos, hooks de negocio, colas, migraciones, adaptadores nativos, servicios de módulos ni archivos Odoo/backend. No reemplazar comportamientos reales por datos de demostración. El escenario demo conserva su franja identificadora.
5. Inspeccionar en navegador los escenarios priorizados y registrar límites de validación. Capturas y resultados generados van fuera del checkout; código y documentación útil quedan commiteados y publicados.
