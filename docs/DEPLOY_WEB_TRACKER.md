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

## Lo que este flujo NO hace todavía

- **No toca el módulo Odoo (`step_hr`)**: su integración con Web Tracker está
  programada (ver `docs/INTEGRACION_ODOO_WEB_TRACKER.md`) pero no instalada
  ni probada contra el Odoo real de este servidor. Instalar un módulo Odoo es
  un proceso aparte (copiarlo al `addons_path` que use esa instancia,
  `-u step_hr` o Apps → Actualizar) — no lo mezclar con este flujo.
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
