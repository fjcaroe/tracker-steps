# Despliegue de Steps Task (`/task/`)

Runbook para publicar el módulo Odoo `step_task` y la PWA de labores. Réplica
del patrón de Steps Harvest (`/cosecha/`). **No se toca Producción sin
autorización expresa.**

## Componentes

| Pieza | Qué es | Dónde vive |
|---|---|---|
| Front PWA | React/Vite estático, `base:/task/`, PWA (`manifest.webmanifest` + `sw.js` scope `/task/`) | repo `step_task` (→ `github.com/fjcaroe/step_task`); build a `dist/`; se publica en `/var/www/task/` |
| Módulo Odoo | `step_task` — campos móviles en `step.tarja`/`step.tarja.registry`, controlador `/api/task/*`, consola (menú Task, tablero, Estados OT, transmisión), 4 informes XLSX | `addons_path` de cada instancia |
| API | Controlador same-origin del módulo. **No** hay servicio aparte: nginx `location /` cae a Odoo | — |

## Entornos

| Entorno | URL app | Odoo | Base | Puerto | Addons | Config | Servicio |
|---|---|---|---|---:|---|---|---|
| Desarrollo | `https://desarrollo.stepsapp.cl/task/` | `https://desarrollo.stepsapp.cl` | `LAB_TAREAS` | 8075 | `/opt/dev_odoo18/odoo_agriculture` | `/etc/dev_odoo18.conf` | `odoo18-dev.service` |
| Demo | `https://demo.stepsapp.cl/task/` | `https://demo.stepsapp.cl` | `STEPS_DEMO` | 8080 | `/opt/demo_odoo18/odoo_agriculture` | `/etc/demo_odoo18.conf` | `odoo18-demo.service` |

vhost nginx: bloque `# BEGIN STEPS TASK /task` en el server correspondiente de
`/etc/nginx/sites-available/stepsapp` (desarrollo) y
`/etc/nginx/sites-available/demo.stepsapp.cl` (demo), inmediatamente después del
bloque `# END STEPS HARVEST /cosecha`.

Servidor: instancia GCE `odoo-new`.

```bash
gcloud compute ssh odoo-new --project=stepsconsulting --zone=us-central1-c
```

## Estado actual (2026-09-07)

- **Desarrollo: PUBLICADO.** `step_task` instalado en `LAB_TAREAS`
  (`18.0.1.2.0`); front en `/var/www/task/`; bloque nginx agregado; verificado.
  Respaldo del vhost en `/opt/fernando_odoo18/backups/task-deploy-20260907-134321/`.
- **Demo: PENDIENTE.** Nada tocado (`STEPS_DEMO`, `/opt/demo_odoo18`, vhost demo).

## Bloque nginx `/task` (idéntico para ambos vhosts)

```nginx
    # BEGIN STEPS TASK /task
    location = /task { return 301 /task/; }

    location = /task/manifest.webmanifest {
        alias /var/www/task/manifest.webmanifest;
        default_type application/manifest+json;
        add_header Cache-Control "no-cache";
        add_header X-Content-Type-Options "nosniff";
    }

    location = /task/sw.js {
        alias /var/www/task/sw.js;
        default_type application/javascript;
        add_header Cache-Control "no-cache";
        add_header Service-Worker-Allowed "/task/";
        add_header X-Content-Type-Options "nosniff";
    }

    location ^~ /task/assets/ {
        alias /var/www/task/assets/;
        expires 30d;
        add_header Cache-Control "public, max-age=2592000, immutable";
        add_header X-Content-Type-Options "nosniff";
    }

    location ^~ /task/ {
        alias /var/www/task/;
        index index.html;
        try_files $uri $uri/ /task/index.html;
        add_header Cache-Control "no-cache";
        add_header X-Content-Type-Options "nosniff";
    }
    # END STEPS TASK /task
```

`/api/task/*` **no** necesita bloque: cae al `location /` que ya proxya a Odoo.

## Procedimiento (aplica a Desarrollo; para Demo, cambiar rutas/base/servicio)

### 0. Respaldo

```bash
STAMP=$(date +%Y%m%d-%H%M%S)
BK=/opt/fernando_odoo18/backups/task-$STAMP
sudo mkdir -p "$BK" && sudo chown postgres:postgres "$BK"
# Base objetivo (usar STEPS_DEMO en demo)
sudo -u postgres pg_dump -Fc -d LAB_TAREAS -f "$BK/LAB_TAREAS.dump"
sudo chown -R root:root "$BK"
# Módulo previo (si existía) + vhost
sudo test -d /opt/dev_odoo18/odoo_agriculture/step_task && \
  sudo tar czf "$BK/step_task.prev.tar.gz" -C /opt/dev_odoo18/odoo_agriculture step_task || true
sudo cp -a /etc/nginx/sites-available/stepsapp "$BK/nginx-stepsapp"
```

### 1. Módulo Odoo

Clonar fresco en `/tmp` y copiar solo el módulo. No editar dentro del
`addons_path`.

```bash
rm -rf /tmp/step_task-deploy
git clone --branch <rama> --depth 1 \
  https://github.com/fjcaroe/step_task.git /tmp/step_task-deploy      # o el repo Odoo si el módulo vive ahí

sudo rsync -a --delete --exclude '__pycache__' \
  /tmp/step_task-deploy/step_task/ \
  /opt/dev_odoo18/odoo_agriculture/step_task/
sudo chown -R root:odoo /opt/dev_odoo18/odoo_agriculture/step_task

sudo -u odoo /usr/bin/python3.10 /opt/odoo18/odoo-bin \
  -c /etc/dev_odoo18.conf -d LAB_TAREAS -i step_task --stop-after-init --no-http
# actualizaciones posteriores: -u step_task en vez de -i step_task
sudo systemctl restart odoo18-dev.service        # demo: odoo18-demo.service
```

Verificar:

```bash
sudo -u postgres psql -d LAB_TAREAS -tAc \
  "SELECT name,state,latest_version FROM ir_module_module WHERE name='step_task'"
curl --fail --silent https://desarrollo.stepsapp.cl/api/task/health
```

### 2. Front PWA

```bash
rm -rf /tmp/step_task-web && git clone --depth 1 \
  https://github.com/fjcaroe/step_task.git /tmp/step_task-web
cd /tmp/step_task-web
npm ci --no-audit --no-fund
npm run build                         # base ya es /task/  (o: npx vite build --base=/task/)

sudo mkdir -p /var/www/task
sudo rsync -a --delete /tmp/step_task-web/dist/ /var/www/task/
sudo chown -R root:odoo /var/www/task
sudo find /var/www/task -type d -exec chmod 755 {} \;
sudo find /var/www/task -type f -exec chmod 644 {} \;
```

### 3. nginx

```bash
# Insertar el bloque /task tras "# END STEPS HARVEST /cosecha" en el server
# desarrollo.stepsapp.cl de /etc/nginx/sites-available/stepsapp
sudo nginx -t
sudo systemctl reload nginx            # NUNCA restart: hay otros sitios en el mismo nginx
```

### 4. Verificación

```bash
curl -sIL https://desarrollo.stepsapp.cl/task/           | grep -i "HTTP/"
curl -s   https://desarrollo.stepsapp.cl/task/           | grep -oE 'assets/index-[A-Za-z0-9_-]+\.(js|css)'
# comparar ese hash con el que imprimió `npm run build`
curl -s -o /dev/null -w "%{http_code}\n" https://desarrollo.stepsapp.cl/task/sw.js
```

En el navegador (con usuario de la instancia, nunca credenciales copiadas):

1. `https://desarrollo.stepsapp.cl/task/` carga el shell; el aviso dice
   "Sin sesión de Odoo" hasta iniciar sesión en `.../web/login`.
2. Iniciar sesión en Odoo en la misma pestaña; `/task/` → Configuración →
   **Descargar maestros** debe traer trabajadores/labores/centros de costo.
3. Armar cuadrilla (lectura/manual/enrolado), crear OT, agregar detalle,
   cerrar, **Sincronizar**.
4. En Odoo: **Task → Registro OT → Estados OT** debe listar la OT en estado
   "En proceso" / "Cerrada"; abrir, **Aprobar**, **Transmitir**; verificar que
   el detalle quede consolidado por trabajador+centro+labor y que aparezca en
   Actividades.
5. **Task → Informes**: generar los 4 XLSX.
6. Móvil (≤ 767 px): el tablero de Odoo y la PWA hacen scroll vertical, sin
   desborde horizontal.

## Promoción a Demo

Repetir el procedimiento cambiando:

- addons: `/opt/demo_odoo18/odoo_agriculture/step_task`
- config: `/etc/demo_odoo18.conf`, base `STEPS_DEMO`, servicio `odoo18-demo.service`
- vhost: `/etc/nginx/sites-available/demo.stepsapp.cl` (mismo bloque `/task`)
- `/var/www/task/` es compartido por ambos hosts en este servidor: si Demo debe
  servir un build distinto al de Desarrollo, usar un directorio propio
  (`/var/www/task-demo/`) y apuntar el `alias` del vhost de demo ahí.

No copiar `STEPS_DEMO`, no tocar Producción, no reiniciar más servicios que
`odoo18-demo.service`.

## Rollback

```bash
# Front
sudo rsync -a --delete /ruta/al/backup/var-www-task/ /var/www/task/
# nginx
sudo cp -a "$BK/nginx-stepsapp" /etc/nginx/sites-available/stepsapp
sudo nginx -t && sudo systemctl reload nginx
# Módulo: desinstalar desde Ajustes → Aplicaciones, o restaurar la base
sudo -u postgres dropdb LAB_TAREAS && sudo -u postgres createdb -O dev_odoo18 LAB_TAREAS
sudo -u postgres pg_restore -d LAB_TAREAS "$BK/LAB_TAREAS.dump"
sudo systemctl restart odoo18-dev.service
```
