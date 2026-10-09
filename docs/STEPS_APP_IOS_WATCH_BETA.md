# Primera beta iPhone y Apple Watch

Fecha: 09-10-2026. Base: `origin/codex/steps-movil` (`b0c3acf`).

## Continuación en Mac del 09-10-2026

El piloto Android actualizado se prepara en `codex/steps-ios-mac`.
`ios:pilot` usa ahora `build:pilot` y conserva el aviso de Desarrollo.
El Mac Intel 2017 inspeccionado no soporta oficialmente el macOS necesario para
Xcode 26; el usuario dispone de otro Mac para compilar y conectar el iPhone.
Ver [STEPS_APP_IOS_MAC.md](STEPS_APP_IOS_MAC.md) para pruebas, herramientas,
compilación remota y continuación sin instalar GPT/Codex en el Mac corporativo.
La [ejecución 37989604975](https://github.com/fjcaroe/tracker-steps/actions/runs/37989604975)
aprobó con Xcode 26.6 la compilación iPhone/Watch para simulador, el archivo de
dispositivo sin firma y **la instalación/apertura real del piloto en simulador**.
La captura revisada muestra ingreso y aviso de Desarrollo. Código `164d1c8`,
versión nativa 2.0.0 (9). La firma y validación física siguen pendientes.

## Entrega y límites

Esta etapa prepara una beta nativa de la aplicación unificada y un acompañante
SwiftUI para Apple Watch. El primer paquete es **demostración con datos ficticios**:
permite elegir los siete recorridos del cliente, sin depender de una instalación
Odoo ni enviar operaciones empresariales. En demostración Tracker usa una
simulación aislada, sin su API ni almacenamiento antiguos; en el piloto real
conserva su ingreso propio.
Cambiar de recorrido reinicia los datos sintéticos; esta modalidad no sirve para
medir conservación de datos de terreno ni para operar en producción.

El flujo `Steps Apple beta` compila en macOS tanto simulador como archivo de
dispositivo **sin firma**. Un archivo sin firma no se instala en un iPhone ni se
sube a TestFlight. La firma requiere una cuenta Apple y un Mac/Xcode o una
infraestructura macOS con certificados autorizados. No se paga ni configura
ninguna cuenta automáticamente. No se modificó ni desplegó Odoo en esta etapa.

## Probar antes de pagar Apple Developer

Con un Mac, Xcode y un iPhone conectado se puede usar una cuenta Apple gratuita
(Personal Team) para pruebas personales. Los perfiles gratuitos caducan a los
siete días y sus capacidades tienen restricciones. TestFlight requiere membresía.
[Apple: cuentas y pruebas personales](https://developer.apple.com/help/account/basics/about-your-developer-account).

1. Obtener esta rama en un checkout propio en macOS; instalar Node 22 y CocoaPods
   (incluye `xcodeproj`). Instalar Xcode 26 o posterior y sus plataformas iOS/watchOS.
2. Ejecutar `cd mobile && npm ci && npm run ios:demo`.
3. Abrir `mobile/ios/App/App.xcworkspace`, esquema **Steps**. En Signing &
   Capabilities asignar el mismo Team a **App** y **StepsWatch**. Mantener
   `cl.stepsapp.movil` y `cl.stepsapp.movil.watchkitapp`.
4. Seleccionar el iPhone conectado, habilitar Developer Mode cuando lo solicite
   Apple y ejecutar Run. Si Apple no permite aprovisionar estos IDs con la cuenta
   usada, resolver la titularidad; no cambiar IDs para instalar sobre datos previos.
5. En la app, elegir conductor, beneficiaria, pendientes, multiempresa,
   supervisor, nuevo o sin módulos en «Recorrido de prueba».
6. En el reloj enlazado, instalar el acompañante desde la app Watch del iPhone.
   Si no está disponible, revisar el target StepsWatch y las plataformas en Xcode.
7. En Steps iPhone → Perfil → Apple Watch, habilitar «Compartir resumen».

El preparador `tools/ios/prepare_project.rb` registra fuentes nativas, crea el
target watchOS 10+, lo incorpora al iPhone y genera el esquema compartido Steps.
Es idempotente. `STEPS_APPLE_TEAM_ID` opcional asigna el Team (identificador,
no credencial). `STEPS_BUILD_NUMBER` es un entero positivo; iPhone y Watch usan
la misma versión 2.0.0 y número de compilación.

## Apple Watch: alcance del primer corte

- Empresa activa, módulos habilitados y contadores de la cola de Colaciones/
  Movilización. Los pendientes internos de Tracker siguen dentro de Tracker.
- «Abrir en iPhone»: solicita navegar a un módulo habilitado. El teléfono valida
  de nuevo el ámbito y acceso actuales. No registra ni cierra una operación.
- Actualización por WatchConnectivity: `updateApplicationContext` para el estado
  más reciente y `sendMessage` para refrescar/navegar cuando el iPhone es accesible.
- La persona habilita compartir por cuenta; está desactivado por defecto.
- No se transfieren tokens, contraseñas, nombres de personas, pasajeros, fotos,
  identificadores de trabajadores ni coordenadas. La empresa y los módulos se
  muestran únicamente mientras el contexto es válido.
- Resumen válido como máximo cinco minutos, acotado además por la autorización
  offline del teléfono. Cerrar sesión, cambiar empresa, vencimiento o desactivar
  el resumen generan un contexto vacío. Sin conexión no puede llegar una
  revocación inmediatamente: el reloj oculta el contexto al vencer su plazo.
- El reloj no persiste un historial. No promete seguimiento GPS autónomo, alertas
  de emergencias, notificaciones push ni acciones empresariales sin el teléfono.

Fuente de plataforma:
[WatchConnectivity](https://developer.apple.com/documentation/watchconnectivity/transferring-data-with-watch-connectivity),
[plugin local Capacitor 7](https://capacitorjs.com/docs/v7/ios/custom-code).

## Pasar de demostración a piloto real

Primero validar el servidor y flujos en Desarrollo según el registro canónico de
Odoo, sobre una copia autorizada. No usar Demo ni inferir la base por el checkout.
No instalar todavía la beta encima de un teléfono con datos de producción sin
la prueba de migración/actualización prevista en `STEPS_APP_MIGRACION_OFFLINE.md`.

En macOS, establecer `VITE_STEPS_API_BASE` al endpoint HTTPS autorizado que
termine en `/steps_app/v1`, y ejecutar `npm run ios:pilot`. El comando rechaza
un backend ausente, localhost, URLs con credenciales y rutas incorrectas.
La compilación piloto usa la sesión nativa segura, no el servidor falso.
Completar correo, política de privacidad, validación de eliminación de cuenta,
SSO de Tracker y OAuth si se incluyen en el alcance antes de publicación pública.

## Aceptación en dispositivos

1. iPhone: arranque, siete escenarios ficticios, navegación y permisos denegados.
2. Reloj: sin asociación no muestra empresa; habilitar muestra solo los módulos
   actuales. Cambiar empresa actualiza catálogo y no mezcla pendientes.
3. Cerrar sesión/desactivar resumen lo limpia. Desconectar el teléfono y esperar
   más de cinco minutos oculta la empresa y los módulos.
4. Abrir módulo solicita navegación, sin crear eventos. Una solicitud del ámbito
   anterior o de un módulo revocado se rechaza.
5. En piloto real: ingreso persistente, modo avión, reinicio, reenvío idempotente,
   revocación y actualización sobre datos pendientes. Para GPS: recorrido físico
   con pantalla apagada; un simulador no certifica continuidad ni consumo.

No afirmar «instalable en tu iPhone» hasta disponer de firma y verificar la
instalación real. Registrar aquí resultados de macOS/CI y dispositivos al obtenerlos.

El workflow selecciona un Xcode 26 estable y un simulador de la misma generación
del SDK. La primera compilación con Xcode 16.4 permitió comprobar las fuentes,
pero no sirve para un envío actual a App Store Connect: Apple exige Xcode 26+
y SDK iOS/watchOS 26 desde el 28-04-2026.
[Requisito oficial](https://developer.apple.com/news/upcoming-requirements/).

## Evidencia inicial del 09-10-2026 (antes de la continuación en Mac)

- Código nativo y paquete: `a550be6`; [PR de integración #19](https://github.com/fjcaroe/tracker-steps/pull/19)
  hacia `codex/steps-movil`, en revisión, sin despliegue del piloto.
- 169 pruebas móviles, 52 del backend Tracker, 22 de herramientas y 7 de
  configuración del endpoint aprobadas. Build normal y demostración aprobados.
- [Ejecución macOS/Xcode 26.6](https://github.com/fjcaroe/tracker-steps/actions/runs/37952429772):
  compilación iPhone + Watch para simulador **aprobada**; archivo Release para
  dispositivo **aprobado**, sin firma. Ambos paquetes están en los artefactos
  `Steps-Apple-demo-a550be6ac76342e055c4f51ca2c7a66f5abf6edb` (retención 14 días).
- **Arranque en simulador no validado en la entrega inicial**: dos intentos completos en infraestructura
  hospedada no llegaron a instalar la app; el último quedó en la migración del
  sistema `com.apple.locationd.migrator (CoreLocationMigrator.migrator)` hasta
  agotar el límite. El workflow queda fallido por esta comprobación, aunque
  conserva ambos binarios. No se ocultó ni convirtió el fallo en aprobación.
- Revisados en navegador: Colaciones con historial, inicio de servicio de
  Movilización y Tracker ficticio aislado. No sustituyen pruebas nativas.
- **Pendiente externo**: cuenta/equipo Apple para firmar y acceso a iPhone/Watch
  reales. No se generó una IPA firmada, no se instaló en teléfono y no se subió
  a TestFlight. Tampoco se certificaron GPS de fondo, cámara o conexión del reloj.
