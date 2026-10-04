# Steps App — validación Android/iOS y requisitos de lanzamiento

Estado verificado el 04-10-2026 en el entorno de esta entrega (contenedor Linux, sin dispositivos).

## 1. Qué se pudo y qué no

| Comprobación | Resultado | Evidencia |
| --- | --- | --- |
| Dependencias nativas coherentes (Capacitor 7.6.9 + `geolocation` + `secure-storage`) | **Sí** | `npx cap sync android` y `npx cap sync ios` terminan bien; `npx cap doctor`: «Android looking great». Cambios en `mobile/android/capacitor.settings.gradle`, `app/capacitor.build.gradle` e `ios/App/Podfile`. |
| Compilar APK/AAB | **No (bloqueado)** | No hay Android SDK y `dl.google.com` no es alcanzable desde este entorno (`curl` → sin respuesta), así que no se pueden bajar `commandlinetools`/plataformas. Java 21 y Gradle 8.14 sí están. |
| Ejecutar en emulador o dispositivo Android | **No** | Sin SDK/emulador. |
| Compilar/ejecutar en iOS | **No (bloqueado)** | `npx cap doctor`: «Xcode is not installed» (se requiere macOS). |
| Almacén seguro nativo (Keychain/Keystore) | **Sin probar** | Código en `platform/secureStore.ts`; solo probado con sustituto en memoria. |
| HTTP nativo (CapacitorHttp para la API de Steps) | **Lógica probada, plataforma sin probar** | `platform/http.test.ts` (simulado). |
| Retorno desde segundo plano, conectividad real, permisos denegados reales | **Sin probar** en plataforma | En web: `visibilitychange`/`online`/`offline` y ubicación denegada están probados con simulación. |
| Seguimiento GPS en segundo plano | **No implementado** | La app pide ubicación solo al marcar un pasajero (primer plano). El Tracker usa su propio seguimiento con la app abierta (como hasta hoy). No se afirma que funcione en segundo plano. |

Un build web exitoso (`npm run build`) **no** valida nada de lo anterior.

## 2. Cambios nativos hechos y su efecto

- `android:allowBackup="false"` en `AndroidManifest.xml`. Motivo: el respaldo automático de Android puede restaurar datos locales (cola de operaciones, sesión) en otro teléfono; una cola de operaciones pertenece a UN dispositivo y la credencial vive en el Keystore, que no se restaura. **Consecuencia:** una instalación nueva en otro teléfono no hereda pendientes ni datos locales del Tracker por respaldo automático. Es deliberado; antes del piloto debe validarse que el Tracker no dependía de ese respaldo (el piloto no se despliega sobre las instalaciones vigentes).
- Se conserva el `appId` `cl.stepsapp.movil`, el nombre y la firma (ver `STEPS_APP_MIGRACION_OFFLINE.md §5`).
- Permisos Android declarados: `INTERNET`, `ACCESS_FINE_LOCATION`, `ACCESS_COARSE_LOCATION`. **No** hay `CAMERA` ni `ACCESS_BACKGROUND_LOCATION`. iOS: solo `NSLocationWhenInUseUsageDescription`; sin `NSCameraUsageDescription` ni `UIBackgroundModes`.

## 3. Procedimiento reproducible (cuando haya herramientas)

**Android** (Android Studio o SDK + JDK 17/21):

```bash
cd mobile && npm ci && VITE_STEPS_API_BASE=https://<odoo-de-PRUEBA>/steps_app/v1 npm run cap:sync
cd android && ./gradlew assembleDebug            # APK de depuración
adb install -r app/build/outputs/apk/debug/app-debug.apk
```

Lista de comprobación en el equipo, con el Odoo de demostración y los datos sintéticos:
1. Arranca y muestra la bienvenida. 2. Registro/ingreso. 3. Cerrar la app a la fuerza y reabrir: la sesión persiste (Keystore) y no pide ingreso. 4. Modo avión: registrar una entrega de Colaciones → «Pendiente»; reiniciar el teléfono; al volver la señal → «Confirmada» una sola vez. 5. Negar el permiso de ubicación al marcar un pasajero: la marca se guarda sin ubicación y se explica. 6. Enviar la app a segundo plano 5 min y volver: la sesión revalida y el catálogo se actualiza. 7. Revocar el acceso en Odoo y revalidar: desaparece el módulo. 8. Instalar la versión nueva SOBRE una instalación 1.2.x con jornadas pendientes: el Tracker conserva su jornada y aparece la compuerta de propietario; existe la copia `steps.backup.tracker.v1.*`.

**iOS** (macOS + Xcode 15+ + CocoaPods): `cd mobile && npm ci && npm run cap:sync && npx cap open ios`; firmar con el equipo de desarrollo; repetir la lista anterior en un iPhone real (el Keychain y el comportamiento en segundo plano no se validan en simulador).

## 4. Qué falta para un lanzamiento (no resuelto)

| Tema | Pendiente |
| --- | --- |
| Firma | Keystore de Android y perfil de aprovisionamiento/certificados de Apple. Conservar o cambiar `cl.stepsapp.movil` es una decisión de lanzamiento (afecta actualización y almacenamiento previo). |
| Google | ID de cliente OAuth Web/Android/iOS, huella SHA-1 del keystore, plugin nativo con flujo del sistema (RFC 8252) y `step_app.google_client_ids` en Odoo. |
| Apple | «Iniciar sesión con Apple» (guía 4.8) si hay registro público con Google, con verificación en servidor; no implementado. |
| Enlaces de retorno | Esquema/Universal Links y App Links para el retorno de OAuth. Hoy no hay flujo OAuth nativo activo. |
| Privacidad | URL pública de la política (`VITE_PRIVACY_URL`), ficha de privacidad de las tiendas (ubicación, identificadores), y revisión de la eliminación de cuenta (guías 5.1.1) con la política de retención de registros empresariales. |
| Segundo plano | Si Movilización necesita ruta continua: servicio en primer plano en Android y modos de fondo en iOS, con prueba en equipo. |
| Servidor | HTTPS con certificado válido, límites de tasa por IP/dispositivo, correo saliente para verificación/recuperación. |
| Distribución | Cuentas de desarrollador, revisión de tiendas, canal de pruebas internas (TestFlight / pruebas internas de Play). |
