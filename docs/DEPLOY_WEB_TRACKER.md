# Cómo desplegar Web Tracker a producción

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
