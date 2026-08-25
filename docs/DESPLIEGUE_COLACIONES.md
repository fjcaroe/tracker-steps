# Despliegue de Colaciones

Este documento describe cómo publicar el módulo Odoo `step_colaciones` y la
aplicación web del tótem. Producción no se toca sin autorización expresa.

## Entornos

| Entorno | Odoo | Base | Puerto | App del tótem |
|---|---|---|---:|---|
| Desarrollo | `https://desarrollo.stepsapp.cl` | `LAB_TAREAS` | 8075 | `https://desarrollo.stepsapp.cl/colaciones/app/` |
| Demo | `https://demo.stepsapp.cl` | `STEPS_DEMO` | 8080 | `https://colaciones.stepsapp.cl/` |

`colaciones.stepsapp.cl` es un host propio servido por su propio virtual host y
apunta su API al Odoo de **Demo**. La ruta histórica
`https://demo.stepsapp.cl/colaciones/app/` se conserva por compatibilidad con
tótems ya asociados.

Servidor: instancia GCE `odoo-new`, proyecto `stepsconsulting`, zona
`us-central1-c`.

```bash
gcloud compute ssh odoo-new --project=stepsconsulting --zone=us-central1-c
```

## Antes de cualquier cambio

Respaldar base, módulo, aplicación y virtual host, y registrar los checksums:

```bash
STAMP=$(date +%Y%m%d-%H%M%S)
DEST=/opt/fernando_odoo18/backups/colaciones-$STAMP
sudo mkdir -p "$DEST" && sudo chown postgres:postgres "$DEST"
sudo -u postgres pg_dump -Fc -d LAB_TAREAS  -f "$DEST/LAB_TAREAS.dump"
sudo -u postgres pg_dump -Fc -d STEPS_DEMO  -f "$DEST/STEPS_DEMO.dump"
sudo chown root:root "$DEST"
sudo tar czf "$DEST/step_colaciones-dev.tar.gz"  -C /opt/dev_odoo18/odoo_agriculture  step_colaciones
sudo tar czf "$DEST/step_colaciones-demo.tar.gz" -C /opt/demo_odoo18/odoo_agriculture step_colaciones
sudo tar czf "$DEST/var-www-colaciones.tar.gz"   -C /var/www colaciones
sudo cp -a /etc/nginx/sites-available/stepsapp "$DEST/nginx-stepsapp"
sudo cp -a /etc/nginx/sites-available/demo.stepsapp.cl "$DEST/nginx-demo"
sudo bash -c "cd '$DEST' && find . -type f ! -name SHA256SUMS.txt -print0 | sort -z | xargs -0 sha256sum > SHA256SUMS.txt"
```

## 1. Módulo Odoo

Clonar fresco en `/tmp` y copiar solo el módulo. No se edita el código dentro
del `addons_path`.

```bash
rm -rf /tmp/colaciones-deploy
git clone --branch <rama> --depth 1 \
  https://github.com/fjcaroe/steps_colaciones.git /tmp/colaciones-deploy

# Desarrollo
sudo rsync -a --delete --exclude '__pycache__' \
  /tmp/colaciones-deploy/odoo/step_colaciones/ \
  /opt/dev_odoo18/odoo_agriculture/step_colaciones/
sudo -u odoo /usr/bin/python3.10 /opt/odoo18/odoo-bin \
  -c /etc/dev_odoo18.conf -d LAB_TAREAS -u step_colaciones --stop-after-init --no-http
sudo systemctl restart odoo18-dev.service

# Demo (solo después de validar Desarrollo)
sudo rsync -a --delete --exclude '__pycache__' \
  /tmp/colaciones-deploy/odoo/step_colaciones/ \
  /opt/demo_odoo18/odoo_agriculture/step_colaciones/
sudo -u demo_odoo18 /usr/bin/python3.10 /opt/odoo18/odoo-bin \
  -c /etc/demo_odoo18.conf -d STEPS_DEMO -u step_colaciones --stop-after-init --no-http
sudo systemctl restart odoo18-demo.service
```

Pruebas del módulo (usar una base de trabajo, nunca Producción):

```bash
sudo -u odoo /usr/bin/python3.10 /opt/odoo18/odoo-bin \
  -c /etc/dev_odoo18.conf -d LAB_TAREAS -u step_colaciones \
  --test-enable --test-tags /step_colaciones --stop-after-init --no-http
```

## 2. Aplicación web

La PWA no se compila: se copian los archivos tal cual, excluyendo pruebas y
metadatos de desarrollo.

```bash
# Host propio (Demo)
sudo mkdir -p /var/www/colaciones_app
sudo rsync -a --delete \
  --exclude 'tests/' --exclude 'package.json' --exclude 'README.md' \
  /tmp/colaciones-deploy/web/ /var/www/colaciones_app/
sudo chown -R root:www-data /var/www/colaciones_app
sudo find /var/www/colaciones_app -type d -exec chmod 755 {} \;
sudo find /var/www/colaciones_app -type f -exec chmod 644 {} \;

# Ruta histórica de Desarrollo
sudo rsync -a --delete \
  --exclude 'tests/' --exclude 'package.json' --exclude 'README.md' \
  /tmp/colaciones-deploy/web/ /var/www/colaciones/app/
sudo chown -R root:www-data /var/www/colaciones
```

## 3. Nginx y certificado

La plantilla del virtual host está versionada en
[`nginx/colaciones.stepsapp.cl.conf.example`](nginx/colaciones.stepsapp.cl.conf.example).

1. Comprobar que el DNS del host apunta a la IP pública de `odoo-new`.
2. Instalar primero el bloque HTTP (solo ACME + redirección) y recargar Nginx.
3. Emitir el certificado sin tocar los de otros dominios:

   ```bash
   sudo certbot certonly --webroot -w /var/www/letsencrypt \
     -d colaciones.stepsapp.cl --cert-name colaciones.stepsapp.cl
   ```

4. Instalar el bloque HTTPS completo.
5. Validar y recargar; **nunca** reiniciar Nginx, hay otros sitios en el mismo
   servicio:

   ```bash
   sudo nginx -t && sudo systemctl reload nginx
   sudo certbot renew --dry-run
   ```

## 4. Configurar la URL en Odoo

En **Colaciones → Configuración → Ajustes**, campo *URL de la App de
Colaciones*:

- Demo: `https://colaciones.stepsapp.cl`
- Desarrollo: vacío (usa `/colaciones/app/` del propio dominio)

La configuración es por compañía. Cambiarla **no** regenera los tokens
existentes: los tótems ya asociados siguen funcionando.

## 5. Verificación

```bash
# La raíz entrega la App, no /web/login de Odoo
curl -sI https://colaciones.stepsapp.cl/ | head -3

# Un token inválido responde JSON desde Odoo, no el fallback HTML de la SPA
curl -s https://colaciones.stepsapp.cl/colaciones/api/totem/token-invalido

# El contrato que expone el servidor
curl -s https://colaciones.stepsapp.cl/colaciones/api/health

# Tipos MIME y cabeceras de caché
curl -sI https://colaciones.stepsapp.cl/manifest.webmanifest | grep -i -E 'content-type|cache-control'
curl -sI https://colaciones.stepsapp.cl/sw.js | grep -i -E 'content-type|cache-control'
```

En el navegador: la App carga, el manifiesto es instalable, el service worker
queda activo y la consola no muestra errores.

## Rollback

```bash
# Aplicación
sudo rsync -a --delete /ruta/al/respaldo/colaciones/app/ /var/www/colaciones_app/

# Módulo
sudo tar xzf "$DEST/step_colaciones-demo.tar.gz" -C /opt/demo_odoo18/odoo_agriculture
sudo -u demo_odoo18 /usr/bin/python3.10 /opt/odoo18/odoo-bin \
  -c /etc/demo_odoo18.conf -d STEPS_DEMO -u step_colaciones --stop-after-init --no-http

# Virtual host
sudo cp "$DEST/nginx-demo" /etc/nginx/sites-available/demo.stepsapp.cl
sudo nginx -t && sudo systemctl reload nginx

# Base (solo si es imprescindible; detiene el servicio)
sudo systemctl stop odoo18-demo.service
sudo -u postgres pg_restore -c -d STEPS_DEMO "$DEST/STEPS_DEMO.dump"
sudo systemctl start odoo18-demo.service
```

## Reglas duras

- Producción (`https://stepsapp.cl`) no se modifica sin autorización expresa.
- Nunca se versionan `.env`, dumps, certificados, tokens emitidos ni keystores.
- Siempre `nginx -t` antes de `systemctl reload nginx`.
- El token de un tótem no debe aparecer en listas, informes, registros ni
  capturas de pantalla.
