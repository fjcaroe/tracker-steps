# Cómo desplegar Web Tracker a producción

## Entrada independiente de Tracker — 02-11-2026

`/tracker` sirve el mismo paquete autenticado de Web Tracker, con acceso propio
adaptado a teléfonos y la identidad, contraseña y permisos actuales de Odoo.
El formulario prepara el CSRF nativo y envía las credenciales únicamente al
POST `/web/login` del mismo sitio; no guarda contraseñas ni crea otro sistema
de usuarios. Conserva la continuación de doble factor nativa y los enlaces
de compañía, vehículo y vista. Una sesión válida entra directamente a su
flota; una cuenta sin permisos muestra orientación sin exponer vehículos.
Salir vuelve a `/tracker`. El selector de compañía del navegador se limpia
después de autenticar otra cuenta, sin alterar sus membresías.

`configure_frontend` mantiene los alias privados móviles y la API exclusiva
de Desarrollo. Añade únicamente la entrada `/tracker` y su variante con barra.
En Cerro, las entradas `/truck` y `/truck/` redirigen a `/tracker`, conservando
la consulta; Desarrollo mantiene su aplicación móvil de pruebas. Los recursos
estáticos del portal conservan `/web_tracker/`, para compatibilidad de enlaces
existentes. No reemplazar la configuración privada con el snippet común.

Pruebas: `tracker-entry.cjs fixture` usa un servidor HTTP local sin datos
productivos para errores, CSRF, doble factor y diseño móvil/escritorio.
`tracker-entry.cjs real` verifica el formulario nativo real, credenciales
inválidas y, con el archivo privado opcional, acceso y salida de la cuenta de
previsualización existente. No emitir órdenes físicas durante la revisión.
`test_tracker_entry_routing.py` comprueba conservación de los otros servicios.
Publicar el mismo dist primero en Desarrollo y después en Cerro mediante
`deploy_tracker_frontend.py`, con copia fresca, respaldos y bloqueo compartido.
No cambian addons Odoo, sus versiones ni los datos de QA-Cerro.

Para corregir únicamente clases GPS confirmadas por el usuario, usar
`tools/gps/normalize_vehicle_types.py` con plan privado por UUID y patente.
Exige copia fresca, conservación de posiciones/asociaciones y respaldo antes
de aplicar el PATCH autorizado y auditado. La sincronización existente de
Flota conserva la clase explícita; no cambiar la selección nativa car/bike
del modelo de Odoo para representar una categoría que ese campo no admite.

Entrega comprobada: frontend `92c662e0ecb18b161a63959014679244699f632d`,
idéntico dist en Desarrollo y Cerro. Recibos de copia fresca, publicación y
respaldos en `/opt/steps-validation/tracker-parity-20261031/<commit>/`.
La normalización de clases se ensayó y aplicó con `e17c1b66`, con prueba y
respaldo privados en `/opt/steps-validation/tracker-entry-20261102/types/`.
Navegador real: credenciales inválidas permanecen en el formulario; las cuentas
de previsualización existentes entran y salen en ambos sitios, incluso con
consulta de compañía y fragmento Protección. Se exige recarga del documento
tras autenticar: un replace de la misma URL con fragmento no recarga React.
El administrador conserva sus cuatro GPS, verifica las dos clases corregidas
y abre el formulario nativo de permisos. Capturas y pruebas privadas en
`local-artifacts/tracker-entry-20261102`; sesión efímera de revisión retirada.

> Actualización 31/10/2026: la configuración Coban de Cerro usa los overlays
> privados de Desarrollo/Cerro y el publicador probado descrito en
> [Receptor y configuración GPS](COBAN_RECEIVER.md). No ejecutar una publicación
> global sobre el portal compartido. La restauración be359b82 incorpora también
> Operación y costos; para cambios solo de frontend usar
> `tools/ops/deploy_tracker_frontend.py` y conservar esta unificación. No desplegar
> un backend anterior al paquete
> e4a1cb7b: la API también sirve Steps Móvil y servicios de pasajeros.
>
> Portal autenticado de Desarrollo, Demo y Cerro el Plomo (septiembre 2026):
> utiliza `/var/www/web_tracker_portal/`, `VITE_ODOO_PORTAL=true` y el addon
> `step_tracker_portal`. Para la entrega de polígonos seguir también
> [Zonas y métricas](ZONAS_Y_METRICAS_TRACKER.md), con el script incremental
> `scripts/deploy-tracker-zones.sh`. No confundir estos destinos con el frontend
> histórico de `stepsapp.cl` descrito abajo.

Este documento existe para que **cualquier sesión de Claude Code** (o cualquier
persona) sepa desplegar sin tener que redescubrir el proceso cada vez. Si estás
leyendo esto porque el usuario pidió "sube los cambios al servidor" o "despliega
esto", seguí los pasos de abajo tal cual.

## De un vistazo

- **Repo:** `https://github.com/fjcaroe/tracker-steps` (público)
- **Rama de trabajo actual:** `codex/web-tracker-redesign` (no `develop` — ver
  nota abajo)
- **Servidor:** instancia GCE `odoo-new`, proyecto `stepsconsulting`, zona
  `us-central1-c`
- **URL pública:** https://stepsapp.cl/web_tracker/
- **API real de Web Tracker (backend):** https://stepsapp.cl/tracker-steps
  (proxy nginx a `127.0.0.1:8000`, prefijo recortado — **no** confundir con
  `stepsapp.cl/api/steps-truck/`, que es otra app en el puerto 9000)
- **Odoo** corre en el mismo servidor (`/` → `127.0.0.1:8069`)

## Acceso al servidor

```bash
gcloud compute ssh --zone "us-central1-c" "odoo-new" --project "stepsconsulting"
```

Esto requiere que quien lo ejecute tenga `gcloud` autenticado con una cuenta
con acceso al proyecto `stepsconsulting` (el usuario del proyecto es
`fernandocaro1198@gmail.com`).

## Componentes que forman una entrega completa

Una versión puede incluir tres componentes independientes en la misma instancia:

1. Frontend estático en `/var/www/web_tracker/`.
2. API FastAPI en `/opt/fernando_odoo18/apis/backend/tracker_py`, servicio
   `tracker-steps-api.service` y proxy público `/tracker-steps/`.
3. Módulo Odoo `step_hr` en el `addons_path` de la instancia Odoo.

Si el frontend empieza a consumir endpoints nuevos, se despliega primero la API,
se verifica su OpenAPI y recién después se publica el frontend. Odoo se actualiza
al final para que sus sincronizaciones nunca apunten a contratos inexistentes.

## Paso a paso para desplegar el frontend

**Importante:** `.env` y `.env.production` **no están en git** (se sacaron el
2026-08-19 porque el repo es público y tenían claves de Google Maps
expuestas). Viven **solo en el servidor**, en
`/opt/fernando_odoo18/apis/tracker-steps/.env(.production)`. Cualquier deploy
tiene que copiarlos desde ahí a un clon fresco antes de compilar — un `git
clone` nuevo no va a traer esos archivos.

Todo esto se corre **en el servidor** (después de conectarse por SSH), o como
un solo `--command` de `gcloud compute ssh` desde la máquina local:

```bash
set -e
rm -rf /tmp/tracker-steps-deploy
git clone --branch codex/web-tracker-redesign --depth 1 \
  https://github.com/fjcaroe/tracker-steps.git /tmp/tracker-steps-deploy
cd /tmp/tracker-steps-deploy

# .env es 640 root:odoo (más restrictivo que .env.production, que es 644)
sudo cp /opt/fernando_odoo18/apis/tracker-steps/.env .env
cp /opt/fernando_odoo18/apis/tracker-steps/.env.production .env.production
sudo chown $(whoami) .env

npm ci --no-audit --no-fund
npm run build

sudo rsync -a --delete --chown=root:odoo dist/ /var/www/web_tracker/
sudo nginx -t
sudo systemctl reload nginx   # no restart: no corta otras webs del mismo nginx
rm -rf /tmp/tracker-steps-deploy
```

## Paso a paso para desplegar el backend

El código productivo de FastAPI no tenía repositorio propio y fue incorporado en
`backend/tracker_py/`. Su `.env` continúa viviendo únicamente en el servidor.

Antes de reemplazar archivos, crear un respaldo recuperable y aplicar las
migraciones SQL. Para esta versión:

```bash
set -e
release=/tmp/tracker-steps-deploy/backend/tracker_py
target=/opt/fernando_odoo18/apis/backend/tracker_py
backup=/opt/fernando_odoo18/backups/tracker_py-$(date +%Y%m%d-%H%M%S)

sudo mkdir -p "$(dirname "$backup")"
sudo cp -a "$target" "$backup"

# La instalación histórica usaba un secreto JWT incorporado en el código.
# Genérelo una sola vez en .env antes de instalar la versión segura.
if ! sudo grep -q '^JWT_SECRET=' "$target/.env"; then
  jwt_secret="$(openssl rand -hex 32)"
  printf '\nJWT_SECRET=%s\n' "$jwt_secret" | sudo tee -a "$target/.env" >/dev/null
  unset jwt_secret
fi
sudo chmod 600 "$target/.env"

# Conserva .env y .venv del servidor; actualiza solo fuentes versionadas.
sudo rsync -a --delete \
  --exclude '.env' --exclude '.venv' --exclude '__pycache__' \
  "$release/" "$target/"
sudo chown -R fernandocaro1198_gmail_com "$target"

sudo -u postgres psql -d tracker_steps -v ON_ERROR_STOP=1 \
  -f "$target/migrations/20260820_master_crud.sql"

sudo systemctl restart tracker-steps-api.service
sudo systemctl is-active --quiet tracker-steps-api.service
curl --fail --silent http://127.0.0.1:8000/health
curl --fail --silent http://127.0.0.1:8000/health/capabilities
```

La primera rotación de `JWT_SECRET` invalida los tokens emitidos previamente;
los usuarios solo deben volver a iniciar sesión. Nunca imprimir, copiar al repo
ni enviar ese valor en logs.

Antes de publicar el frontend, verificar que `/openapi.json` exponga:

- `PATCH` y `DELETE /drivers/{driver_id}`.
- `DELETE /activities/{activity_id}`.
- `DELETE /labors/{labor_id}`.
- `PATCH` y `DELETE /implements/{implement_id}`.
- `GET /drivers`, `/activities`, `/labors` e `/implements`, con soporte para
  `include_inactive=true`.

Para rollback, restaurar el respaldo de código y reiniciar el servicio. La nueva
columna `implements.is_active` es compatible hacia atrás y no necesita eliminarse.

### Por qué así y no simplemente "hacer pull en el servidor"

Ya existe un checkout más viejo en
`/opt/fernando_odoo18/apis/tracker-steps` apuntando a `develop`, con
cambios locales sin commitear (entre otros, `step_hr/` borrado a mano) que
harían fallar un `git checkout` limpio de esta rama. Por eso el patrón es
**clonar fresco en `/tmp` en cada deploy** y no tocar ese checkout viejo — es
más lento (~10s más) pero cero riesgo de pisar algo. Si en algún momento se
decide fusionar `codex/web-tracker-redesign` a `develop` y usar ese checkout
como el oficial, actualizar este documento.

## Verificar que el deploy se aplicó

Después del `reload`, comprobar que el sitio sirve los archivos nuevos (los
nombres de archivo llevan un hash que cambia en cada build):

1. Mirar el nombre de archivo que imprimió `npm run build` (ej.
   `index-CnaYIWL4.js`).
2. Abrir `https://stepsapp.cl/web_tracker/` y revisar en Network que carga
   ese mismo nombre de archivo. Si coincide, el deploy es el correcto.

## Cosas que casi seguro vas a necesitar tocar en simultáneo

- Si cambiaste algo relacionado a Google Maps: las claves están en el
  proyecto GCP `stepsconsulting`. Ver `gcloud services api-keys list
  --project=stepsconsulting`. La clave del cliente se llama "Maps Platform
  API Key"; hay otra "Ruta Viva - Servidor local" que **no** se usa en el
  frontend (nunca debe referenciarse desde código con prefijo `VITE_`,
  porque eso la expondría en el bundle público).
- Si habilitás una API de Maps nueva: `gcloud services enable
  <servicio>.googleapis.com --project=stepsconsulting`. Verificar con
  `gcloud services list --project=stepsconsulting --filter="name:<término>"`.
- Cambios en `.env`/`.env.production` del servidor: **no se versionan**. Si
  hay que cambiar un valor, editarlo directo en
  `/opt/fernando_odoo18/apis/tracker-steps/.env(.production)` por SSH — no
  hay "subir" por git para esto.

## Actualización del módulo Odoo

- La integración está en `step_hr` y se despliega después de comprobar API y
  frontend. Copiarla al `addons_path`, respaldar previamente el módulo instalado
  y ejecutar la actualización `-u step_hr` con la misma configuración de Odoo
  usada por el servicio real.
- Verificar luego **Ajustes → Labores y Tareas → Web Tracker → Sincronizar ahora**
  y revisar el log de sincronización.
- Confirmar que en `https://stepsapp.cl/odoo` aparezca **Steps Tracker** como
  aplicación de primer nivel. Abrir su **Resumen**, alternar 7/30/90 días y
  comprobar las acciones de Sesiones, Partes y Reportes.
- Verificar que los recursos `tracker_dashboard.js`, `tracker_dashboard.xml` y
  `tracker_dashboard.scss` estén incluidos en `web.assets_backend`. Si Odoo
  conserva el bundle anterior, regenerar assets mediante la actualización del
  módulo y hacer una recarga completa del navegador; no editar adjuntos de
  assets directamente en la base de datos.
- No reiniciar Odoo junto con FastAPI: son servicios separados y deben validarse
  individualmente.

## Lo que este flujo NO hace todavía
- **No hace rollback automático.** Si un deploy rompe algo, el fix es hacer
  `git revert`/checkout del commit bueno y repetir el mismo proceso.

## Historial de contexto relevante (2026-08-19/20)

- El repo público tenía `.env` trackeado con claves de Google Maps reales.
  Se sacó de git (`git rm --cached` + `.gitignore`); las claves viejas siguen
  visibles en el historial de git de todas formas — pendiente rotarlas en
  GCP si se quiere cerrar el tema del todo.
- La URL real de la API (`VITE_API_BASE_URL`) es
  `https://stepsapp.cl/tracker-steps`, confirmada leyendo
  `/etc/nginx/sites-available/stepsapp` en el servidor.


## Monitor web adaptable — 01-11-2026

El inspector del vehículo ahora usa Resumen, Equipo GPS y Costos, conservando
historial, protección, edición, conectividad y las consultas de costos existentes.
Mapa, lista y ficha tienen altura coordinada; cada panel desplaza su propio
contenido. Las acciones de la ficha quedan siempre visibles. En móvil, mapa
primero, lista acotada, ficha con pestañas y navegación compacta. Cambiar de
vehículo reinicia la pestaña para no arrastrar el contexto anterior. Se conserva
la paleta verde/lima y el mapa Google instalado.

Se aplican los patrones de panel de apoyo y divulgación progresiva:
https://m3.material.io/foundations/layout/canonical-examples/overview
https://www.carbondesignsystem.com/building-blocks/core/patterns/disclosures

Paquete certificado e2735b0c276fab6a2280c47ff333c6bcc2ae5440. Compilación TypeScript
 y Vite; copia fresca de tracker_steps con GPS TCP, identidad Odoo y catálogos
clásicos. No hay cambios en API, módulos Odoo o receptor. Desarrollo recibe el
mismo paquete antes de Cerro. El publicador conserva los alias móviles privados;
no reconstruir su snippet desde la plantilla compartida borrando /truck/.

El servidor agotó espacio al instalar dependencias de compilación. Se retiró
únicamente la instalación incompleta propia y la copia QA transitoria ya certificada
de la limpieza anterior, manteniendo dumps y recibos. El build se hizo localmente
con el código canónico y las variables públicas existentes Maps/API/portal. Se
transfirió el dist a un checkout limpio del mismo código y se ensayó ese paquete
exacto en copia y Desarrollo antes de publicar. Los archivos estáticos deben tener
permisos públicos de lectura; nunca extender esos permisos a archivos .env.
Una copia privada .env no debe quedar junto al código que importa la API en QA:
python-dotenv intentaría leerla como postgres. No cambiar credenciales o permisos
para solucionar ese problema; separar los insumos del build del ensayo de API.

Aceptación repetible: tools/qa/tracker/web-monitor-layout.cjs, con sesión temporal
privada de un administrador existente. Comprueba selección real, pestañas,
flechas de teclado, costos, historial, igualdad de alturas y ausencia de desborde
horizontal a 1440 y 390 px. Bloquea escrituras de negocio durante la revisión.
Evidencia privada: /opt/steps-validation/tracker-parity-20261031/<commit>/
(qa.json, development.json, production.json, private/functional.log y respaldos).
Capturas: ~/.codex/local-artifacts/web-monitor-layout-20261101/.


## Historial convertido en explorador de recorridos — 01-11-2026

El historial de la flota abre un mapa Google con inicio/fin, tramos separados,
paradas probables, reproducción por muestra, control deslizante y perfil de
velocidad. El usuario elige últimas 24/2 horas o fechas de hasta 31 días. La
consulta existente se pagina de 500 en 500, hasta 10.000 por carga; si queda cursor,
se anuncia historial parcial y se permite ampliar. Se ordena cronológicamente,
se deduplica por ID y se filtra el límite superior en cliente. Las coordenadas
originales quedan en diagnóstico desplegable, no como contenido principal.

La distancia representa la traza filtrada y no un odómetro. No se unen huecos de
más de diez minutos, saltos de más de cinco kilómetros o velocidades inferidas
incompatibles. La geometría exige señales consistentes de movimiento; una lectura
alta aislada no convierte la deriva de banco en un viaje. También se excluye la
deriva estacionada cuando el período contiene un viaje real posterior. Velocidades
no informadas dejan huecos en el perfil. Las paradas son probables, sin inferir
motor ni alimentación desde ellas. Los puntos recibidos nunca se modifican.

Aproximar por calles utiliza la biblioteca moderna Google Routes, ya habilitada
en el proyecto, con la clave pública existente y una petición solo al pulsar el
botón. Se selecciona un tramo continuo, con origen/destino y hasta seis anclas
intermedias en orden; no se optimiza su orden ni se atraviesan cortes de señal.
El resultado estimado se distingue en azul discontinuo de la traza verde y se
puede quitar. Se rechazan detours mayores a tres veces la traza más 500 m. Una
sugerencia por calles es una hipótesis navegable, no una certificación del camino
histórico ni un ajuste GPS mediante Roads API. No reemplaza coordenadas ni métricas.
Se descartan respuestas antiguas al cambiar de tramo/período o cerrar el diálogo.

Referencias primarias:
https://developers.google.com/maps/documentation/javascript/routes/get-a-route
https://developers.google.com/maps/documentation/javascript/routes/intermediate-waypoints
https://developers.google.com/maps/documentation/roads/snap
Roads es una alternativa de map matching; esta entrega usa Routes existente y
no habilita nuevos servicios ni cambia credenciales.

Validación: nueve casos de cálculo (orden, duplicados, límites de fechas, deriva
prolongada, saltos, huecos, anclas acotadas, lecturas escasas y mezcla parada/viaje),
TypeScript/Vite y ensayo del flujo existente en copia fresca. El navegador de
Desarrollo usa posiciones sintéticas solo en respuestas interceptadas: paginación,
parada, corte, reproducción, período vacío, revocación, móvil y petición REAL a
Google Routes. La referencia sintética toma una ruta pública de Google para situar
sus muestras sobre calles transitables; no se inserta en bases. También se verificó
que una aproximación alejada de una traza ficticia se rechaza. En Cerro se comprueba
el mapa y la reproducción con posiciones físicas existentes, sin crear jornadas,
sin GPS del teléfono y sin escrituras de negocio.

Paquete final b4e2abdf (hash completo en qa.json, development.json y production.json),
misma compilación certificada en Desarrollo y Cerro. Publicación con dump, respaldo,
bloqueo y comparación de archivos servidos. API, receptor, móvil y módulos Odoo
permanecen intactos. Fuente de compilación local canónica; artefactos fuera del
checkout y traslado como tar para evitar modificar un dist mientras se transfiere.
Evidencia privada bajo /opt/steps-validation/tracker-parity-20261031/<commit>/ y
~/.codex/local-artifacts/tracker-route-history-20261101/.
Comprobaciones repetibles: tools/qa/tracker/fleet-trail.test.mjs y
route-history-native.cjs, con sesiones temporales existentes y cierre posterior.

## Protección guiada y video de capacitación — 01-11-2026

El panel muestra selección de vehículo, estado confirmado, motivo obligatorio
con opciones rápidas y confirmación del cambio. La bandeja y el expediente
separan reconocer/cerrar un incidente del armado de sus reglas. Los motivos
de protección, alta de incidente y seguimiento son independientes; abrir un
expediente ya no borra el motivo de otra acción. Se conservan los contactos,
horarios y zona al cambiar el estado. El GPS sigue registrando al desarmar.

Las lecturas de políticas e incidentes se resuelven de forma independiente.
Un fallo de la bandeja no convierte una política en un estado predeterminado;
un estado de protección no verificado bloquea su cambio. La confirmación
comprueba la versión antes de escribir, actualiza la versión devuelta al
guardar y ante 409 recarga sin repetir automáticamente la orden ni borrar
el motivo. Los errores y su recuperación se anuncian en el formulario.
Esto endurece el flujo frente a fallos y concurrencia; no establece la causa
de un error histórico cuyo texto no se haya conservado.

Pruebas: protection-guide-native.cjs cubre motivo vacío y foco, cancelar,
armado/desarmado, conflicto, conservación del motivo, SOS abierto mientras se
desarma, reconocimiento/cierre, lectura fallida, permiso denegado y móvil.
Sus respuestas sintéticas solo viven en el navegador. El ensayo de integración
en copia fresca añade armado/desarmado real de la API, versión obsoleta,
SOS independiente, cierre prematuro rechazado, permisos e historial GPS intacto.
La aceptación nativa de producción solo lee y cancela la confirmación; no arma
vehículos reales. No cambian API, receptor, móvil ni módulos Odoo. QA-Cerro
conserva su aislamiento y sus datos; no recibe configuración GPS productiva.

El mismo script con GPS_GUIDE_VIDEO=1 y GPS_PROTECTION_FIXTURE=1 graba el
recorrido de capacitación con datos ficticios. render_guide_video.py genera
MP4, narración española local con SAPI y subtítulos, sin servicios de voz externos.
Los archivos se guardan fuera del checkout, bajo local-artifacts. No se graban
sesiones, ubicaciones, números ni identificadores de clientes en el video.
Referencias: https://www.w3.org/WAI/tutorials/forms/notifications/ y
https://playwright.dev/docs/videos.

Paquete publicado: bc6d74df9094d2a53a327b76c90cb12437b2b081. El mismo dist
pasó copia fresca, navegador de Desarrollo y navegador nativo de Cerro en
1440 y 390 px. Recibos y respaldo en
/opt/steps-validation/tracker-parity-20261031/<commit>/; el log funcional
incluye PROTECTION_COPY_QA_OK. La revisión de Cerro mantuvo la protección
desarmada, sin escrituras de negocio ni órdenes físicas. Sesiones temporales
retiradas después de verificar el formulario. El MP4 de capacitación contiene
once capítulos y dura aproximadamente dos minutos.

### Video sin narración y comprobación de reproducción

La variante solicitada sin voz se graba con GPS_GUIDE_VIDEO=1,
GPS_PROTECTION_FIXTURE=1 y GPS_GUIDE_CLEAN_VIDEO=1. Usa un área de aplicación
de 1280×600; render_guide_video.py <artefactos> --silent añade arriba una banda de
texto hasta 1280×720, fuera de los controles inferiores del reproductor. El texto se quema en cada fotograma con ASS y permanece
visible también sobre las escenas con diálogos. No hay pistas de audio ni
dependencia de subtítulos opcionales del reproductor.

El archivo recorta la espera inicial y utiliza H.264 baseline 3.1, avc1,
yuv420p, 25 fps constantes, sin B frames y faststart. No basta con extraer
una imagen usando ffmpeg: verify_guide_playback.cjs reproduce y busca cada
capítulo del MP4 en Edge, comprueba píxeles reales decodificados para detectar
pantallas negras y conserva capturas. La grabación no modifica datos reales.
Se incluye además una versión GIF animada completa para visores sin soporte MP4.
Los resultados y el MP4 quedan en local-artifacts/tracker-video-silent-20261101.
Solo cambia la herramienta de capacitación; no se publica código de aplicación.
Referencia de formatos: https://developer.mozilla.org/en-US/docs/Web/Media/Guides/Formats/Video_codecs.

## Operaciones productivas con GPS real y registros nativos — 01-11-2026

La entrada #ops del portal utiliza FleetOperations y la misma identidad,
compañía, selección de vehículo y posiciones Coban que Flota. Ya no abre
ClassicApp, su laboratorio predeterminado ni sus catálogos/sesiones agrícolas
separados. La demostración de Flota solo se ofrece en LAB_TAREAS; Cerro no
ofrece el selector de datasets. Las rutas independientes anteriores se conservan
para sus consumidores, sin borrar históricos ni convertir maestros por nombre.

Resumen, recorrido, registros, costos y analítica tienen funciones comprobables.
Las posiciones se consultan con la identidad del portal, desde una fecha,
con cursor de 500 y límite de 10.000 por carga. Los períodos son 24 horas,
7 y 30 días; una carga parcial se anuncia y puede ampliarse. Al cambiar de
activo/período o perder acceso se descartan resultados anteriores. El CSV
incluye fuente, período y aviso de parcialidad; escapa fórmulas de hojas de cálculo.

Distancia y desplazamiento se calculan con las muestras filtradas del mismo
explorador de recorridos: no se unen huecos ni saltos ni se suman fluctuaciones
estacionarias como viajes. Las barras diarias usan el calendario de Chile.
El tiempo entre muestras con movimiento no se denomina horas de motor, y la
distancia GPS no se presenta como lectura física del tablero. No se fabrican
combustible, hectáreas, productividad ni días sin información.

Vehículo y lecturas usa exclusivamente los modelos nativos existentes
step.tracker.asset.link, fleet.vehicle y fleet.vehicle.odometer mediante la
sesión Odoo y sus ACL/reglas, con allowed_company_ids explícitos. El vínculo
se elige y confirma; no se deduce por patente. Guardar una lectura vuelve a
comprobar compañía/perfil y vínculo, valida coherencia cronológica y duplicados,
crea el registro nativo y comprueba lo guardado. Conserva la unidad del vehículo.
Sin lecturas, no presenta el cero predeterminado de la ficha como dato físico.
No se crea una tabla paralela ni se cambia un módulo Odoo.

Los accesos a aplicaciones proceden de los menús visibles del usuario y permanecen
en el mismo origen. Costos reutiliza el informe existente de Gestión y Costos /
Gastos / Contabilidad y su correspondencia explícita, sin elevar privilegios.
Su período y base de cálculo se explican por separado de la distancia GPS.
La navegación conserva el vehículo al volver al mapa y no emite otro token de
la operación clásica ni exige un segundo inicio de sesión.

Sincronizar Odoo consulta además la correspondencia explícita ya existente:
actualiza el activo GPS vinculado conservando UUID, asignación e historial.
Solo importa por source_id nativo los vehículos aún no vinculados y crea su
correspondencia validada. No invoca la importación antigua que podía duplicar
un activo Coban dado de alta manualmente y vinculado después con Flota.

Validación: operations-metrics.test.mjs y fleet-trail.test.mjs; navegador con
respuestas sintéticas locales para todas las pestañas, paginación, vínculo,
lecturas, incoherencias, duplicados, cambio de compañía, revocación, exportación
y móvil. real-operations-native.cjs en modo real solo consulta datos existentes.
operations-odoo-copy.py se ejecuta únicamente en TRACKER_OPS_QA_* neutralizada,
crea y revierte fixtures sobre los modelos nativos y verifica formularios,
lecturas, ACL y aislamiento. rehearse_tracker_odoo.py conserva dump/proof y
elimina la copia transitoria. El frontend requiere además el ensayo de API
en copia fresca de deploy_tracker_frontend.py. Publicar el mismo dist en
Desarrollo antes de Cerro, con respaldo y bloqueo; receptor, API, móvil y
addons efectivos permanecen intactos. QA-Cerro conserva aislamiento y datos.

El alta de un vehículo real conocido se realiza solo con datos privados
confirmados, un maestro nativo de marca inequívoco, respaldo y prueba de copia,
usando onboard_known_odoo_vehicle.py. Conserva el activo GPS y sus posiciones;
no inventa conductor, año, odómetro ni documentos financieros.

Entrega verificada: frontend 9c3aa991dad9cc542cbd5fb746640f1d8a29d9aa, mismo
dist en Desarrollo y Cerro. Recibos qa.json, development.json, production.json,
respaldos y ensayo de API en
/opt/steps-validation/tracker-parity-20261031/<commit>/. El ensayo incluye
OPERATIONS_COPY_QA_OK: conserva activo e historial e importa idempotentemente.
Los 17 casos de métricas/recorridos pasan. Navegador sobre Desarrollo comprueba
formularios, errores, revocación, exportación, sincronización y vista móvil con
fixtures locales. La revisión de Cerro consulta sin escrituras de negocio las
cinco pestañas, la ficha nativa ya vinculada y la respuesta financiera nativa;
capturas desktop/mobile y formularios fuera del checkout. Sesiones retiradas.

La prueba fresca nativa de Odoo conserva prueba y log en
/opt/steps-validation/tracker-native-operations-20261101/qa.json; comprueba
lecturas guardadas, formularios, permisos e aislamiento y revierte fixtures.
El vehículo real del piloto quedó vinculado al activo existente con respaldo,
sin lectura física inventada. Los costos por km/h del informe financiero aún
requieren su propia base de sesiones/horómetro y documentos; las métricas GPS
del nuevo panel no rellenan esa base ni crean asientos.

No se modificaron addons. verify_cerro_release_pair.py comprobó en Cerro y
QA-Cerro las versiones y hashes efectivos de step_tracker_portal (18.0.1.3.0)
y step_management_costs_tracker (18.0.1.1.1); prueba release-pair.json junto al
ensayo nativo. QA-Cerro no sirve el frontend Web Tracker en su nginx: conserva
su capacitación, aplicaciones instaladas y aislamiento, sin habilitar acceso
a receptores o datos GPS productivos para replicar esta interfaz.

## Explorador de recorridos — 01-11-2026

La vista muestra el recorrido completo sin selector de divisiones técnicas.
Las paradas son eventos filtrables por duración (3–60 minutos, 10 por defecto),
con marcadores opcionales y lista de diez eventos ampliable. Hoy y Ayer usan
el calendario del dispositivo, indicado en pantalla; también hay 2/24 horas,
7 días y rango con hora hasta 31 días. Filtrar eventos conserva distancia y traza.
La reproducción puede seguir el punto en el mapa. El GPX exporta exclusivamente
las líneas GPS filtradas, en segmentos separados ante discontinuidades, sin
convertir aproximaciones de Google en observaciones. Historial parcial se anuncia.
La aproximación solicita todas las líneas elegibles del período, hasta 12 por
acción; para rangos mayores pide acotar fechas. Nunca une cortes de señal.
Se comprueba el rechazo de desvíos excesivos y se conserva la traza ante errores.
route-history-native.cjs verifica filtros sin cambio de distancia, exportación
con discontinuidades, reproducción, Maps/Routes, fechas vacías, revocación y
móvil. Los fixtures solo viven en respuestas del navegador; no se almacenan.
Mismo paquete con deploy_tracker_frontend.py: copia fresca, Desarrollo, Cerro,
respaldo, bloqueo y hashes. No cambia addons, API, receptor ni la copia QA-Cerro.

Paquete servido y comprobado: ebcf9cee20f2006618531f9b6499b23bd9a96a7f.
Los recibos de copia fresca, Desarrollo y producción y sus respaldos están en
/opt/steps-validation/tracker-parity-20261031/<commit>/. Pasan 17 casos de
métricas/recorridos y el navegador sobre Desarrollo (fixtures) y Cerro (historial
real, solo lectura), escritorio y móvil. La prueba sintética usa dos recorridos
sobre calles separados por un corte y una parada: el GPX conserva el corte y el
filtro de duración no cambia la distancia. Capturas privadas en local-artifacts/
tracker-route-explorer-20261101. Las sesiones temporales se retiran al terminar.

## Costos y consulta de gastos del GPS real — 01-11-2026

AssetCostsPanel deja de navegar a la acción de servidor sin contexto. Consulta
fleet.vehicle.action_open_step_expenses con el ID del vínculo nativo explícito,
y lee hr.expense con el dominio devuelto, compañía y período del informe y ACL
actuales. Muestra hasta 100 gastos; los documentos abren su formulario nativo.
No se modifica la acción de servidor ni se crean gastos. El enlace antiguo
copiado fuera del panel conserva su limitación; el panel ofrece el acceso nuevo.

El informe conserva las cifras contables nativas e incorpora distancia del GPS
Coban filtrada con buildTrail en el mismo período (hora del dispositivo), con
cursor de 500 y máximo 10.000 muestras. No calcula costo por km si el historial
es parcial, falla, supera 31 días, no hay desplazamiento o falta costo accesible.
Sin apuntes atribuibles explica que faltan gastos contabilizados. El cociente
neto/km es una estimación y no cambia documentos, lecturas ni costos contables.
Las bases antiguas de sesiones/horómetro se muestran aparte con su explicación.
costs-native.cjs comprueba distancia y acceso a gastos, sin escrituras de negocio.
No hay cambios de addons: misma entrega de frontend en Desarrollo y Cerro,
con copia fresca del API, respaldo y bloqueo; QA-Cerro conserva aislamiento.

Paquete servido: c9932bbc56337ed3932023ffe2067cb187918a23, con copia fresca y
respaldos en /opt/steps-validation/tracker-parity-20261031/<commit>/.
Mismo dist verificado en Desarrollo (navegador con fixtures) y Cerro. El navegador
real confirma el nuevo acceso a gastos y kilómetros en Mapa y Operaciones,
sin escrituras. Capturas privadas: local-artifacts/tracker-costs-fix-20261101.
La prueba de Mapa abre la pestaña Costos por texto accesible, independiente de
si el contenedor declara role=tab o button. Sesiones temporales retiradas.

## Selección de compañía en teléfonos — 01-11-2026

TrackerCompanySelector consulta las compañías permitidas del propio usuario
mediante res.users.read y res.company.search_read. Permite cambiar la cookie
nativa cids y recarga por completo para descartar datos y formularios anteriores.
La elección se conserva en ese navegador. No cambia la compañía predeterminada
del usuario, membresías ni registros; el BFF mantiene la comprobación de permisos.
El enlace ?company=<id>#live selecciona únicamente una compañía de esa lista;
un ID ajeno muestra error y conserva la compañía activa. Se retira asset al
cambiar de compañía para evitar selección de un vehículo de la empresa anterior.
El estado vacío identifica la compañía y orienta al selector en vez de pedir
volver a crear/sincronizar vehículos existentes. Disponible también en Operación.
company-selection-native.cjs comprueba móvil, compañía vacía, selección explícita,
recarga persistente, enlace autorizado y rechazo de ID ajeno; modo fixture para
Desarrollo, modo real de solo lectura en Cerro. Solo cambia contexto de navegador.
Frontend publicado mediante copia fresca, Desarrollo y Cerro con el mismo dist,
respaldo y bloqueo. No se modifican addons, API, GPS ni datos de QA-Cerro.

Entrega verificada: b2cbfff219a027d647ec0bad6a8decb1767ecb07. Recibos de copia
fresca, Desarrollo, producción y respaldos en /opt/steps-validation/
tracker-parity-20261031/<commit>/. Navegador de Desarrollo con fixtures y
navegador real de Cerro pasan el cambio de compañía en 390 px, persistencia,
enlace autorizado y rechazo de compañía ajena. La prueba real espera además
el mapa Google renderizado. Capturas privadas en local-artifacts/
tracker-company-fix-20261101; sesiones retiradas tras la revisión.

## Vehículo personal en Desarrollo — 01-11-2026

El usuario pidió separar su vehículo y GPS personales del inventario productivo
para probar nuevas funciones en Desarrollo. La interfaz vigente ya estaba
publicada en Desarrollo. Nuevas mejoras se revisan allí antes de su entrega
explícita a Cerro; no se usa la copia QA-Cerro como origen de promoción.

manage_personal_tracker_transfer.py usa plan y hechos nativos privados, la
rama Web canónica y el bloqueo compartido. Requiere ensayo exacto sobre copias
frescas del Tracker, Desarrollo y Cerro, con correo/cron neutralizados. Conserva
UUID de activo, dispositivo, asociación y posiciones, trasladando su tenant y
el inventario/SIM/política/auditoría correspondientes. Difiere temporalmente la
FK compuesta dentro de la transacción, valida ambos lados y restaura su estado
no diferible antes de confirmar. No desactiva restricciones. El alta nativa
reutiliza marca/modelo y usuario, conserva lecturas, perfil y grupos funcionales
mapeables; no altera contraseñas ni las compañías autorizadas de producción.
La ficha/vínculo originales se archivan después de comprobar el alta destino.
No traslada documentos financieros; rechaza vehículos con gastos o conductor
que requieran otra migración. Los datos y ejercicios previos de Desarrollo se
conservan; no se refresca ninguna base desde otra.

API y receptor siguen compartidos, con datos separados por base/compañía. La
recepción adicional exige la lista privada /etc/tracker-coban-tenants.json;
Cerro conserva su soporte existente. El receptor elige la clave por emisor y
sondea por (emisor, compañía), sin confundir IDs iguales entre bases. No cambia
la IP/puerto del equipo ni se emiten SMS u órdenes físicas. Se exige outbox
personal drenado antes del cambio; no se reasignan paquetes antiguos pendientes.
El hardware productivo restante conserva IDs, SIM, modo y configuración. Las
unidades aún no asociadas siguen en inventario/captura hasta conocer el vehículo.

La interfaz de Desarrollo puede publicarse separadamente. Una mejora futura de
la API/receptor compartidos exige ensayo aislado previo y una publicación
controlada: cambiar el servicio compartido afecta su código efectivo en ambos
portales, aunque los registros y permisos estén separados.

Herramientas de revisión con el usuario real: personal-native-session.py crea
una sesión efímera sin escrituras de negocio; GPS_REVIEW_ASSET selecciona el
activo privado en los ensayos de Operación, recorridos y gastos. Retirar la
sesión después de la revisión. Los hechos, planes, respaldos, copias y capturas
se conservan fuera de Git bajo personal-transfer-20261101 y local-artifacts.

Entrega aplicada y verificada: 9e6e8753a4421a03a1d813f49f19a0d630f80cec.
Prueba exacta, copias neutralizadas, respaldo previo y delivery.json en
/opt/steps-validation/personal-transfer-20261101/<commit>/. Pasan 24 pruebas de
receptor, 20 de API y 3 del alcance de transferencia. El proceso qa-apply conserva
el mismo bloqueo desde la copia fresca hasta la publicación. Acepta contactos
nuevos y registros agregados de forma acumulativa; rechaza cambios de identidad,
asociación, configuración/protección, pérdida o alteración de muestras previas.
La API instalada y el receptor corresponden al paquete certificado. Las vistas
web y móvil de Desarrollo ya tenían el mismo HTML/paquete que Cerro; se verificó
su correspondencia sin reemplazar la interfaz ni los datos de capacitación.

Se reutilizó la cuenta existente y su contraseña de Desarrollo, con perfil y
lecturas confirmadas. La ficha fuente se archivó; el receptor productivo conserva
las cuatro unidades restantes y la recepción personal apunta a Desarrollo, sin
cambiar SMS ni dirección física. Permanecen los registros de QA que ya existían.
La identidad del activo real se comprueba por UUID, incluso si una patente se
repite en datos de prueba previos; no se vincula por coincidencia de patente.

La revisión posterior con ese usuario pasó Operación, lectura nativa, costos y
gastos, recorridos Google y reproducción y GPS móvil Google sin geolocalización
del teléfono ni inicio de jornada. Capturas privadas en local-artifacts/
personal-tracker-transfer-20261101. Se usa una lectura compartida y acotada del
bloqueo durante el navegador para evitar reinicios por otras publicaciones.
Las sesiones efímeras se retiraron con su prueba privada exacta; no se altera
ninguna sesión del usuario. cleanup_personal_sessions.py evita arrancar otro
registro ORM únicamente para retirar la sesión. Handoff limpio y publicado.
