# Harvest: navegadores retenían versiones anteriores

La revisión del 26-11-2026 reprodujo las pantallas 0.0.3 y 0.0.5 comunicadas
por el cliente. Los tres destinos ya servían el paquete certificado 0.0.11,
commit `680e694cd0320c90366327a31e3f9475ab6f4cbb`, pero sus navegadores podían
seguir ejecutando archivos anteriores incluso después de una recarga normal.

Los paquetes reproducibles conservan `mtime=0`. El HTML de varias entregas
mide 657 bytes, aunque cambia el nombre del JavaScript. Nginx calculaba para
todas el mismo ETag `"0-291"` y la misma fecha Last-Modified. Una petición con
el identificador antiguo recibía 304. `Cache-Control: no-cache` exige consultar
al servidor, pero esa respuesta incorrecta autorizaba reutilizar el HTML viejo.
Sus recursos con nombres propios podían permanecer en la caché del navegador.

`publish_harvest_web.patch_config` desactiva ETag y If-Modified-Since en HTML,
service worker y manifiesto y usa `Cache-Control: no-store` para esos recursos.
Los JS/CSS con hash conservan su caché inmutable. `verify_shell_revalidation`
exige 200 y los bytes vigentes al enviar ambos validadores antiguos por separado,
también en `/cosecha/index.html`. La publicación futura ejecuta esa prueba.

## Reparación comprobada

`repair_harvest_cache.py` prepara un Nginx aislado por loopback, con los paquetes
archivados reales de Cerro. `check_harvest_cache_upgrade.cjs` abre cada versión
antigua en Chromium, cambia al paquete vigente y reproduce la versión retenida.
Después aplica la misma política corregida y exige 0.0.11 al recargar.
Comprueba conservación de localStorage, IndexedDB y la caché de otra aplicación.

La publicación de la corrección requiere ese resultado, el mismo paquete
certificado en los tres destinos, integridad de sus cinco archivos, respaldo
de las tres configuraciones, bloqueo compartido y ausencia de upgrade
concurrente. Cambia primero Desarrollo y comprueba las peticiones condicionales
antes de continuar con QA-Cerro y Cerro. Un fallo revierte las configuraciones.
No modifica addons, registros, credenciales, permisos ni archivos de la app.

`harvest_cache_browser_session.py` y `check_harvest_live_versions.cjs` verifican
en el HTTPS real la etiqueta 0.0.11, Configuración de cosecha, Sin tarja y Peso
estándar con perfiles existentes, sin escrituras de negocio. Retirar las
sesiones, el túnel y el Nginx temporal al terminar. Evidencia y respaldos viven
en los directorios privados de la operación, fuera de Git.

En los equipos afectados basta recargar una vez la pestaña con conexión. Una
pestaña que permanece abierta conserva su JavaScript en memoria hasta recargar.
No se elimina almacenamiento del navegador ni se reinstala Harvest; la corrección
no utiliza `Clear-Site-Data` ni borra los registros pendientes.
