# Steps App: preparación en Mac y continuación en iPhone/Watch

Fecha: 09-10-2026. Rama propia: `codex/steps-ios-mac`, creada desde
`origin/codex/steps-android-pilot` actualizado (`78e4cb7`), según el pedido.
La base canónica `origin/codex/steps-movil` es antecesora de esa rama.
El checkout original quedó sin modificaciones; el trabajo está en
`~/Projects/steps-ios-mac`. No se cambió ni publicó Odoo.

## Equipo inspeccionado

MacBook Pro Intel `MacBookPro14,2` (2017), 8 GB RAM, macOS Ventura 13.7.8.
Git y Command Line Tools disponibles; no hay Xcode completo ni simuladores.
No se detectó un iPhone por USB durante el inventario.

**Bloqueo local:** Xcode 26 requiere como mínimo macOS Sequoia 15.6;
este modelo no está en la lista oficial de Macs compatibles con Sequoia.
No instalar un Xcode antiguo como supuesto equivalente ni actualizar el sistema
con parches no oficiales para esta entrega. No se modificó macOS.
Fuentes: [requisitos de Xcode](https://developer.apple.com/xcode/system-requirements/)
y [compatibilidad con Sequoia](https://support.apple.com/en-us/120282).

El usuario tiene otro Mac corporativo en el que puede compilar y conectar el
iPhone. **No necesita instalar GPT/Codex allí.** Xcode, Git, Node y CocoaPods son
suficientes, respetando las políticas de su empresa.

Node 22.23.3 se instaló para el usuario en `~/.local/opt/`, con enlaces en
`~/.local/bin/`. Se verificó SHA-256 de la distribución oficial para Intel.
`~/.zprofile` agrega el PATH de herramientas locales; abrir una terminal nueva.
CocoaPods 1.16.2 y `xcodeproj` 1.27.0 se instalaron en `~/.gem/ruby/2.6.0/`
y sus comandos funcionan con el Ruby 2.6 del sistema. Para esa combinación local
se fijaron ActiveSupport 6.1.7.10 y concurrent-ruby 1.3.4; en el Mac corporativo
usar un Ruby mantenido. No se alteró el Ruby de macOS.

GitHub CLI se instaló también para el usuario y se verificó su SHA-256.
La autenticación de GitHub requiere que el titular complete el flujo de navegador;
no se copian credenciales desde Windows ni se publican tokens.
Logs y paquetes locales: `~/.codex/local-artifacts/steps-ios-mac/`.

## Cambios del piloto

`npm run ios:pilot` ejecuta ahora `build:pilot`, incluyendo la validación HTTPS
y el aviso visible «PILOTO · Desarrollo · Usa únicamente registros de prueba».
El endpoint se proporciona solo al proceso, sin crear ni registrar un `.env`:

```bash
cd ~/Projects/steps-ios-mac/mobile
VITE_STEPS_API_BASE=https://desarrollo.stepsapp.cl/steps_app/v1 npm run ios:pilot
```

El workflow **Steps Apple beta** acepta esta rama y prepara el piloto de Desarrollo
para iPhone/Watch con Xcode 26 estable. El modo demo continúa disponible en el
selector de ejecución manual. Los artefactos indican el modo y el commit.
Compilación, archivo sin firma y arranque son comprobaciones separadas: consultar
cada paso antes de afirmar que pasó. Los artefactos se retienen 14 días.
Ninguna ejecución sin firma genera una IPA instalable o una entrega TestFlight.

El scanner añadido para Android incluye implementación iOS; `cap sync ios`
debe registrar `CapacitorBarcodeScanner` y su dependencia `OSBarcodeLib` en Pods.
Se conserva el permiso de cámara y los identificadores `cl.stepsapp.movil`
y `cl.stepsapp.movil.watchkitapp`, independientes del identificador Android.

## Resultados comprobados en este Mac

| Comprobación | Resultado |
| --- | --- |
| `npm ci` con Node 22.23.3 | Aprobado |
| `npm test` | 171 pruebas, 17 archivos, aprobados |
| Build normal y `build:pilot` con endpoint de Desarrollo | Aprobados |
| Aviso visible y endpoint en bundle piloto | Ambos presentes |
| Validación de configuración HTTPS | 7 pruebas aprobadas |
| Backend Tracker con Python 3.12 y dependencias aisladas | 52 pruebas aprobadas |
| Herramientas `tools/tests` | 22 pruebas aprobadas |
| Preparador Ruby | App y StepsWatch registrados, esquema Steps compartido |
| Pods | Lockfile resuelto, scanner 2.2.6 / OSBarcodeLib 2.0.1 incluidos |
| `npm run ios:pilot` completo | **Falló** al final de sincronización por ausencia de Xcode completo |
| API HTTPS `GET /me` sin sesión | HTTP 401, respuesta `unauthenticated` |
| Firma / instalación física / permisos / sincronización real / Watch | Pendientes en el otro Mac |

El primer intento de pruebas backend con Python 3.9 del sistema falló en la
colección porque el código requiere Python 3.10+. Se repitió con Python 3.12.14
del runtime local en un entorno aislado y pasó; no se cambió el backend.

`cap sync ios` copió los assets piloto y actualizó plugins/Podfile; el proceso
terminó con error al invocar `xcodebuild` sobre Command Line Tools. El lockfile
no certifica compilación ni sincronización completa en este Mac.
El preparador evita una ruta fija a WatchOS11.0.sdk para Foundation y usa
`SDKROOT`, de modo que Xcode resuelve su SDK seleccionado.

`npm audit` informó tres avisos en dependencias de desarrollo ya presentes
(Vitest y sus dependencias mocker/tinypool); no se aplicó un cambio de versión
mayor fuera de esta preparación. Informe local fuera de Git.

## Continuación en el Mac corporativo

1. Instalar un Xcode **estable 26 o posterior compatible con ese macOS** desde
   Apple, abrirlo, aceptar la licencia y descargar las plataformas iOS/watchOS.
   La tabla oficial de Xcode indica el sistema requerido por cada versión.
   Confirmar con `xcodebuild -version` y `xcode-select -p`. Si está seleccionado
   Command Line Tools, seleccionar Xcode en Settings → Locations.
2. Instalar Node 22 y un Ruby mantenido con CocoaPods y `xcodeproj`; confirmar
   `node -v`, `pod --version` y `ruby -rxcodeproj -e 'puts Xcodeproj::VERSION'`.
   No hace falta instalar ChatGPT ni la extensión Codex.
3. En Terminal, obtener exactamente la rama entregada:

   ```bash
   mkdir -p ~/Projects
   cd ~/Projects
   git clone --branch codex/steps-ios-mac https://github.com/fjcaroe/tracker-steps.git steps-ios-mac
   cd steps-ios-mac/mobile
   npm ci
   npm test
   VITE_STEPS_API_BASE=https://desarrollo.stepsapp.cl/steps_app/v1 npm run ios:pilot
   open ios/App/App.xcworkspace
   ```

4. En Xcode seleccionar esquema **Steps**, un simulador iPhone y Run. Confirmar
   que arranca y muestra el aviso de Desarrollo; no usar una captura de demo como
   evidencia del piloto real.
5. En Xcode → Settings → Accounts, iniciar personalmente sesión con la cuenta
   Apple. Asignar el mismo Team en Signing & Capabilities de **App** y
   **StepsWatch**, con firma automática. Mantener ambos bundle IDs existentes.
   `STEPS_APPLE_TEAM_ID` también permite configurar el ID de equipo durante la
   preparación; es un identificador, nunca una contraseña.
6. Conectar y desbloquear el iPhone, aceptar «Confiar», habilitar Developer Mode
   si Xcode lo solicita y elegirlo como destino. Run debe instalar la aplicación
   firmada. Si falla la titularidad de los IDs, resolverla con el equipo Apple;
   no cambiar IDs para eludir el problema.
7. Instalar el acompañante en el Apple Watch enlazado desde la app Watch del
   iPhone. Activar «Compartir resumen» en Steps → Perfil → Apple Watch.

## Validación física pendiente

Usar únicamente una cuenta y datos de Desarrollo. Crear la cuenta desde la app
y pedir acceso a una empresa; el administrador debe aprobarla por el procedimiento
vigente. Esta tarea no crea cuentas ni modifica permisos en Odoo.

- Ingreso, cierre y reapertura: comprobar sesión persistente y aislamiento por empresa.
- Cámara/ubicación: probar permiso concedido y denegado; conservar ingreso manual.
- Sincronización: capturar sin señal, cerrar/reabrir, recuperar conexión, comprobar
  envío único y estado real. No usar jornadas o pendientes de producción.
- Watch: sin consentimiento no muestra datos; con consentimiento muestra empresa,
  módulos y contadores. Cambiar empresa, cerrar sesión y desactivar resumen deben
  limpiarlo. Desconectar más de cinco minutos debe ocultar el contexto vencido.
- «Abrir en iPhone» debe navegar a un módulo autorizado sin registrar operaciones.
- GPS Tracker requiere recorrido físico con pantalla apagada; la suite del cliente
  y el simulador no prueban continuidad ni consumo.

## TestFlight

Pendiente membresía Apple Developer y acceso al equipo/App Store Connect.
Una vez verificada la instalación física: seleccionar destino genérico iOS,
configurar un `STEPS_BUILD_NUMBER` único para iPhone y Watch, preparar de nuevo
el piloto, Product → Archive y Validate/Distribute desde Organizer con firma.
Registrar la aplicación existente con su bundle ID, completar las declaraciones
que correspondan y habilitar los testers en TestFlight cuando Apple procese el
build. No se generaron certificados, perfiles ni cuentas automáticamente.
