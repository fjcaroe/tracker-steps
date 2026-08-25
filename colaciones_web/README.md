# Colaciones Web

Aplicación web progresiva (PWA) para el autorregistro de colaciones. Odoo 18
administra tótems, trabajadores, productos, proveedores, tarifas, registros y
valorización; esta aplicación contiene únicamente la experiencia del equipo de
terreno.

No necesita compilación: son módulos ES nativos servidos tal cual. `npm` se usa
solo para ejecutar las pruebas del núcleo.

## Estructura

```text
web/
  index.html                 interfaz del tótem
  styles.css
  sw.js                      service worker relativo al ámbito de registro
  manifest.webmanifest
  src/core/                  lógica compartida con la App móvil (sin DOM)
  src/adapters/web/          implementaciones específicas del navegador
  src/ui/                    presentación
  tests/                     pruebas del núcleo (node --test)
```

`src/core` es la **fuente de verdad** de la lógica de negocio del cliente. El
repositorio `steps_colaciones_mobile` lo consume como submódulo; no debe
copiarse ni duplicarse.

## Adaptadores

| Contrato | Web | Móvil |
|---|---|---|
| `transport` | `fetch` mismo origen | HTTP nativo de Capacitor (sin CORS) |
| `QueueRepository` | IndexedDB, con reserva en `localStorage` | SQLite |
| `TokenStore` | `localStorage` | Keychain / Keystore |
| `ScannerAdapter` | teclado + Web NFC | teclado + NFC nativo |
| `NetworkMonitor` | `navigator.onLine` + sondeo a `/health` | estado nativo + sondeo |
| `DeviceInfo` | UUID de instalación en `localStorage` | UUID de instalación nativo |

## Contrato

| Método | Ruta | Función |
|---|---|---|
| `GET` | `/colaciones/api/health` | Versión del contrato, capacidades y hora del servidor. |
| `GET` | `/colaciones/api/totem/<token>` | Configuración operativa del tótem. |
| `POST` | `/colaciones/api/register` | Registra una colación individual. |
| `POST` | `/colaciones/api/sync` | Sincroniza un lote con respuesta por UUID. |

La URL de asociación usa `#token=...`, por lo que el secreto no llega en la
solicitud de archivos estáticos ni queda en los registros del servidor. Tras
guardarlo, la App lo borra de la barra de direcciones.

Cada marcación usa un UUID de cliente: reintentar un envío nunca duplica el
registro.

## Offline

La primera apertura necesita conexión. Luego el service worker conserva la
interfaz y la última configuración válida del tótem.

Las capturas viven en IndexedDB con estados `pending`, `syncing`, `synced` y
`terminal_error`. Una captura solo pasa a `synced` con confirmación explícita
del servidor, nunca por haber enviado la petición. Los errores pasajeros
(502/503, red caída) reprograman el envío con espera creciente; los rechazos
funcionales (trabajador inexistente o no habilitado) se marcan definitivos y
dejan de reintentarse.

Al confirmarse una captura se borra el identificador del trabajador y solo
queda su versión enmascarada.

## Pruebas

```bash
npm test
```

## Despliegue

Ver [../docs/DESPLIEGUE_COLACIONES.md](../docs/DESPLIEGUE_COLACIONES.md).
La aplicación funciona tanto en la raíz de un host propio
(`https://colaciones.stepsapp.cl/`) como en un subdirectorio
(`https://desarrollo.stepsapp.cl/colaciones/app/`): todas las rutas del
manifiesto y del service worker son relativas.
