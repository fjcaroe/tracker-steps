# Cómo desplegar Web Tracker a producción

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
