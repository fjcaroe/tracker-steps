# Colaciones: aplicación web, offline y App móvil

Actualizado: 2026-08-21

## Arquitectura implementada

Colaciones se divide en dos productos que comparten la misma lógica de negocio:

1. **Odoo 18 (`step_colaciones`)** administra productos, proveedores, tarifas,
   trabajadores, tótems, planificación, registros, validación, valorización,
   permisos e informes.
2. **Colaciones Web (`web/`)** es la PWA utilizada en el tótem. Es una
   aplicación estática independiente de las vistas de Odoo y consume su API
   por HTTPS.

Este es el mismo principio utilizado en Steps Tracker: experiencia operacional
especializada fuera de Odoo y administración/trazabilidad dentro de Odoo.

La App móvil (`fjcaroe/steps_colaciones_mobile`) **no reimplementa** esa lógica:
consume `web/src/core` como submódulo y solo aporta adaptadores nativos.

## URLs desplegadas

| URL | Ambiente | Base |
|---|---|---|
| `https://colaciones.stepsapp.cl/` | host propio de la App | Demo (`STEPS_DEMO`, puerto 8080) |
| `https://demo.stepsapp.cl/colaciones/app/` | ruta histórica, compatibilidad | Demo |
| `https://desarrollo.stepsapp.cl/colaciones/app/` | entorno técnico | Desarrollo (`LAB_TAREAS`, puerto 8075) |

La dirección de la App **no** se deduce de `web.base.url`: es una configuración
propia por compañía, en **Colaciones → Configuración → Ajustes**
(`colaciones_pwa_base_url`). Si se deja vacía, se conserva la ruta histórica
`/colaciones/app/` del mismo dominio de Odoo. Cambiarla no regenera los tokens
existentes.

La URL sin token muestra que el equipo aún no está asociado y explica cómo
hacerlo. El administrador crea un tótem en Odoo y usa **Abrir tótem**, o escanea
el código QR del formulario desde la App móvil. La asociación viaja como
`#token=...`; el fragmento no se envía en la solicitud de archivos estáticos y
la App lo borra de la barra de direcciones apenas lo guarda.

## Contrato Odoo ↔ aplicación

Detalle completo en [API_COLACIONES.md](API_COLACIONES.md).

| Método | Ruta | Función |
|---|---|---|
| `GET` | `/colaciones/api/health` | Versión del contrato, capacidades y hora del servidor. |
| `GET` | `/colaciones/api/totem/<token>` | Configuración operativa del tótem. |
| `POST` | `/colaciones/api/register` | Registra una colación individual. |
| `POST` | `/colaciones/api/sync` | Sincroniza un lote con respuesta individual por UUID. |

Cada captura incluye un UUID generado por el dispositivo. Odoo lo hace único,
por lo que reintentar una transmisión no duplica el registro. Además, la base de
datos impide más de una colación del mismo producto para un trabajador en un día.

El cliente nunca decide producto, proveedor, cantidad, precio ni estado: esos
valores los fija el tótem en Odoo y los campos extra del cliente se ignoran.

## Funcionamiento offline

- La primera apertura requiere internet para asociar el equipo.
- El service worker guarda la interfaz y el último ajuste válido del tótem, con
  rutas relativas al ámbito de registro para servir igual en host propio o en
  subdirectorio.
- Las capturas viven en IndexedDB, con reserva a `localStorage` si el navegador
  no la expone, y sobreviven a un cierre forzado.
- Estados: `pending`, `syncing`, `synced`, `terminal_error`. Una captura solo
  pasa a `synced` con confirmación explícita del servidor.
- Al recuperar conectividad la cola se transmite automáticamente, una sola vez:
  el motor de sincronización tiene guardia de ejecución única.
- Errores temporales (502/503, red caída) reprograman el envío con espera
  creciente y tope. Errores funcionales definitivos —trabajador inexistente o no
  habilitado— se marcan `terminal_error` y dejan de reintentarse.
- Odoo rechaza capturas que superan la antigüedad configurada en el tótem y
  también las que traen un reloj adelantado.
- Una cola llena o un equipo demasiado tiempo sin sincronizar avisan en pantalla.
- La actualización de la App espera a que no haya capturas en vuelo.

## Seguridad y privacidad

- No existen credenciales ni claves de infraestructura en el frontend.
- Cada tótem tiene un token revocable desde Odoo. **Regenerar acceso** invalida
  el enlace anterior y borra los datos del dispositivo asociado; la App queda
  bloqueada y deja de aceptar capturas.
- El identificador del trabajador se borra del dispositivo apenas el servidor
  confirma la captura; solo queda su versión enmascarada.
- Los identificadores se guardan enmascarados también en el registro de Odoo.
- El diagnóstico exportable no incluye el token completo, ni nombres ni
  identificadores.
- Productos, proveedores y trabajadores se filtran por compañía.
- La administración requiere los grupos Usuario o Administrador de Colaciones.
  La URL de la App la cambia el Administrador de Colaciones sin necesidad de
  acceso a los ajustes generales de Odoo.
- El tótem informa a Odoo un UUID de instalación, la plataforma y la versión de
  la App. No se guardan IP, modelo, número de serie ni identificadores
  publicitarios.

**Riesgo conocido:** el token viaja en la ruta de
`GET /colaciones/api/totem/<token>`, por lo que queda en los registros de acceso
del servidor. Es aceptable porque el token solo habilita la operación de un
tótem y se revoca en un clic, pero conviene considerarlo si se agrega un
registro de accesos externo.

## App Android/iOS

El repositorio `fjcaroe/steps_colaciones_mobile` empaqueta la misma lógica con
Capacitor. Decisiones:

- El núcleo compartido entra como submódulo Git, no como copia.
- Los archivos de la App van dentro del paquete: arranca sin internet.
- El cliente HTTP es nativo, por lo que no interviene CORS.
- La cola usa SQLite en lugar de IndexedDB.
- El token vive en Keychain/Keystore.
- La asociación se hace escaneando el código QR del formulario del tótem.
- NFC nativo se implementa detrás del mismo `ScannerAdapter`; el lector USB o
  Bluetooth tipo teclado sigue siendo la opción estable.

Modo kiosco es una fase administrada aparte: en Android requiere Device Owner o
Android Enterprise/MDM, y en iPad/iPhone Single App Mode sobre dispositivos
supervisados. No se simula ocultando botones del sistema.

## Despliegue

Ver [DESPLIEGUE_COLACIONES.md](DESPLIEGUE_COLACIONES.md) y la plantilla
[nginx/colaciones.stepsapp.cl.conf.example](nginx/colaciones.stepsapp.cl.conf.example).

Producción (`https://stepsapp.cl`) no se modifica hasta aprobar el piloto del
tótem y definir el dispositivo físico.
