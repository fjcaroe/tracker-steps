# Home Steps — rediseño de Desarrollo

Publicada en https://desarrollo.stepsapp.cl/ el 8 de septiembre de 2026.
Versión vigente: `18.0.2.1.0`, con catálogo de apps web y móviles.

## Resultado

Portada editorial con fotografía agrícola, navegación adaptable, catálogo de
doce familias con filtros por área, capacidades desplegables, explicación del
flujo operativo y sección de aplicaciones de terreno. Los accesos conservan
`/web/login`. Los textos se basan en los módulos y sus README del repositorio.
La pantalla ilustrativa no presenta datos de clientes ni métricas inventadas.

| Área | Familias presentadas |
|---|---|
| Campo y producción | Labores y asistencia; BPA, riego y trazabilidad; Cosecha y calidad |
| Recursos y logística | Maquinaria; Tracker GPS; Fletes y movilización |
| Personas | Remuneraciones y Previred; Contratos y finiquitos; Protección laboral; Colaciones |
| Finanzas | Tesorería y multimoneda; Gestión y costos |

El detalle incluye Libro de Remuneraciones, archivos DT, trazabilidad
fitosanitaria, Step Harvest e integración opcional de pagos por lotes. No
presenta los adaptadores o herramientas administrativas como productos aparte.

## Implementación

Módulo: `step_demo_homepage`, versión inicial `18.0.2.0.0`. Única dependencia: `website`.

- `views/homepage.xml`: contenido QWeb y estructura semántica.
- `static/src/scss/homepage.scss`: estilos encapsulados en `.step-demo-home`.
- `static/src/js/homepage.js`: filtros, anuncios accesibles y cierre del menú.
- `static/src/img/orchard-hero.jpg`: fotografía generada y optimizada (396.789 bytes).
- `migrations/18.0.2.0.0/post-migration.py`: actualización de la vista principal
  y sus copias activas con identidad Steps, incluyendo la copia de sitio 3318.

El catálogo completo y los detalles nativos siguen disponibles sin JavaScript.
Se respetan las preferencias de movimiento reducido. La fotografía secundaria
utiliza carga diferida. No se agregaron dependencias npm ni servicios externos.

## Despliegue y respaldo

Entorno: `LAB_TAREAS`, `/opt/dev_odoo18/odoo_agriculture`, servicio
`odoo18-dev.service`. Se actualizó únicamente `step_demo_homepage`.

Respaldo en el servidor:

`/opt/fernando_odoo18/backups/steps-home-20260908-045916/`

- `step_demo_homepage.before.tar.gz`: módulo anterior.
- `LAB_TAREAS.before.dump`: respaldo PostgreSQL completo (20.002.327 bytes).
- `upgrade.log`: registro de actualización.

El script de despliegue de esta entrega está en `tmp/deploy_steps_home_20260908.sh`.
Demo y Producción no fueron desplegados ni reiniciados.

## Verificación

- XML, sintaxis Python, referencias a imágenes, anclas únicas, dependencias y
  doce familias validados con `tmp/validate_steps_landing.py`.
- SCSS compilado correctamente y JavaScript comprobado con `node --check`.
- Actualización Odoo finalizó con código 0; ambas vistas 3310 y 3318 muestran
  el nuevo contenido, versión instalada `18.0.2.0.0`.
- Home y login públicos: HTTP 200. Servicio: activo.
- SHA-256 del XML, SCSS, JS y JPEG en servidor coincide con el código local.
- Revisión visual en escritorio y móvil; sin desbordamiento horizontal en
  viewports de 1440, 390 y 320 píxeles (ancho útil descontando barra vertical).
- Filtro Finanzas muestra dos soluciones; Todas restaura las doce. El detalle
  de Tesorería despliega sus capacidades. Menú móvil abre y Escape lo cierra.
- Ambas imágenes cargan al visitar sus secciones. Consola revisada sin errores
  ni advertencias capturados durante la comprobación.

## Ampliación: apps web y móviles

Publicada el mismo día como `18.0.2.1.0`. La navegación y el segundo botón del
hero llevan a `#apps`; el ancla anterior `#terreno` se conserva. El catálogo
mantiene las doce familias e incorpora cinco tarjetas con enlaces directos:

| Aplicación | URL principal | Publicación verificada en Nginx |
|---|---|---|
| Steps Harvest | https://desarrollo.stepsapp.cl/cosecha/ | `/var/www/cosecha/` |
| Steps Task | https://desarrollo.stepsapp.cl/task/ | `/var/www/task/` |
| Steps Tracker | https://stepsapp.cl/web_tracker/#live | `/var/www/web_tracker/` |
| Colaciones Steps | https://colaciones.stepsapp.cl/ | `/var/www/colaciones_app` |
| Steps Mobile Tracker | https://stepsapp.cl/truck/ | `/var/www/steps-truck-frontend/` |

El desplegable «Otros accesos de la operación» incluye Colaciones en Desarrollo
(https://desarrollo.stepsapp.cl/colaciones/app/, `/var/www/colaciones/app/`) y
Harvest anterior (https://stepsapp.cl/harvest/,
`/opt/movil_odoo18/step_harvest/dist/`). Las siete URLs respondieron HTTP 200.
Evidencia: `tmp/steps_public_apps_20260908.json`.

Harvest, Task y Colaciones tienen manifiestos de aplicaciones web instalables.
La interfaz publicada de Task confirma cuadrillas, órdenes de trabajo, captura
offline y sincronización con Actividades. La interfaz de `/truck/` identifica
el producto como Steps Mobile Tracker, con roles de conductor, administrador y
pasajero; se presenta como app web.

El bloque `#apps-mobile` diferencia los estados comprobados:

| Entrega | Estado mostrado | Evidencia y alcance |
|---|---|---|
| Colaciones Mobile · Android | En validación | APK de prueba y validación en emulador; falta validación en equipos físicos y distribución firmada. |
| Colaciones Mobile · iOS / iPadOS | En preparación | Proyecto generado; compilación y publicación para dispositivos Apple pendientes. |
| Movilización para choferes | Planificada | Integración disponible; cliente móvil dedicado pendiente. |

Fuentes: `../steps_colaciones_mobile/README.md`,
`../steps_colaciones_mobile/docs/ROADMAP.md` y
`docs/movilizacion/05_MANUAL_BREVE.md`. La futura app de Movilización se
distingue de la app web existente Steps Mobile Tracker. No se anuncian fechas
ni enlaces a tiendas que todavía no estén disponibles.

### Despliegue y verificación de la ampliación

- Cambios: manifiesto, QWeb, SCSS y migración `18.0.2.1.0/post-migration.py`.
- Respaldo de la versión anterior y de la base completa:
  `/opt/fernando_odoo18/backups/steps-home-apps-20260908-122317/`.
- Script: `tmp/deploy_steps_home_apps_20260908.sh`.
- Actualización Odoo finalizó con código 0; módulo instalado en `18.0.2.1.0`,
  ambas vistas principales actualizadas y render público comprobado.
- Validación local: doce familias, cinco apps web, siete destinos, tres estados
  móviles, anclas, activos, sintaxis Python y compilación SCSS correctos.
- Revisión visual del catálogo en escritorio y del bloque móvil en el sitio
  publicado. Ancho de página igual al ancho útil móvil: 375 / 375 píxeles.
- Los cinco enlaces principales apuntan a las URLs verificadas y abren otra
  pestaña con `noopener noreferrer`.
- Solo se actualizó Desarrollo; no se modificaron Nginx ni las aplicaciones
  enlazadas, Demo o Producción.

## Imagen y procedencia

Generada con la herramienta integrada `image_gen`, sin API externa ni credenciales.
Archivo usado: `step_demo_homepage/static/src/img/orchard-hero.jpg`.
Original de trabajo conservado en `tmp/steps_home_original.png` y en la carpeta
de imágenes generadas de Codex. Se convirtió a JPEG para reducir el peso sin
alterar la composición.

Prompt utilizado:

> Use case: photorealistic-natural. Asset type: wide landscape editorial hero photograph for Steps, a premium Chilean agricultural operations software website. Create an elegant authentic aerial drone photograph of a lush commercial fruit orchard in the central valley of Chile, late afternoon light, precise long parallel rows of richly green trees running diagonally from lower left to upper right, narrow warm earth service roads, distant Andes hazy foothills only in the top 15 percent, rich natural deep green foliage, subtle lime highlights, earthy brown between rows. Camera oblique aerial, cinematic and quiet, exceptionally detailed natural texture, sophisticated magazine agricultural photography. Wide 3:2 composition that also crops well vertically. No people in close up, no text, no typography, no logos, no graphic overlays, no UI, no watermarks. Natural realistic colors, avoid HDR, avoid artificial fantasy trees. This image will occupy the right half of a white and forest-green landing page hero.
