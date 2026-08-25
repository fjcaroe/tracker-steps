# Promover los cambios de Demo a Desarrollo

Este documento es un runbook para que Claude lleve a **Desarrollo** el estado
funcional que ya fue validado en **Demo**, sin tocar Producción y sin clonar los
datos operacionales de Demo.

## Instrucción principal para Claude

> Lleva a `https://desarrollo.stepsapp.cl` los cambios de código y vistas que
> están funcionando en `https://demo.stepsapp.cl`. Usa Demo como referencia
> efectiva porque varias correcciones se publicaron directamente allí. Antes
> de copiar, respalda Desarrollo, compara los archivos y presenta el `dry-run`.
> No copies la base `STEPS_DEMO`, no toques Producción y no modifiques el addon
> proveedor de SimpleDigital. Actualiza únicamente los módulos instalados en
> Demo, reinicia solo `odoo18-dev.service` y valida escritorio y móvil.

## Entornos

| Entorno | URL | Base de datos | Addons propios | Configuración | Servicio |
|---|---|---|---|---|---|
| Desarrollo | `https://desarrollo.stepsapp.cl` | `LAB_TAREAS` | `/opt/dev_odoo18/odoo_agriculture` | `/etc/dev_odoo18.conf` | `odoo18-dev.service` |
| Demo | `https://demo.stepsapp.cl` | `STEPS_DEMO` | `/opt/demo_odoo18/odoo_agriculture` | `/etc/demo_odoo18.conf` | `odoo18-demo.service` |

Servidor:

```bash
gcloud compute ssh odoo-new --project=stepsconsulting --zone=us-central1-c
```

## Límites obligatorios

1. **No tocar Producción**:
   - `https://stepsapp.cl`
   - base `karo_consultorias`
   - `/etc/odoo18.conf`
   - `odoo18.service`
2. No restaurar ni copiar `STEPS_DEMO` sobre `LAB_TAREAS`.
3. No copiar registros de negocio, usuarios, contraseñas, sesiones, adjuntos,
   tokens ni configuraciones de compañías desde Demo.
4. No modificar `/opt/rrhh/l10n_cl_simpledigital_payroll`.
5. No usar `git reset --hard`, no limpiar el worktree y no incluir cambios
   ajenos en un commit.
6. No usar `rsync --delete` sin respaldo y `dry-run` previos.
7. Reiniciar únicamente `odoo18-dev.service`.

La portada nueva de Producción se aplicó como una vista de base de datos y **no
forma parte de esta promoción**.

## Inventario esperado

Este es el alcance conocido de las pantallas y módulos trabajados en Demo:

| Módulo | Cambios que deben llegar a Desarrollo |
|---|---|
| `step_hr` | Tableros Actividades y Tracker, incluyendo scroll móvil |
| `step_operations_ui` | Tableros Maquinaria y Fletes, vistas e integración nativa |
| `step_labor_protection` | Protección Laboral, menú y scroll móvil |
| `step_cosecha` | Dashboard y scroll móvil |
| `step_qa` | Centro de Calidad, vistas y scroll móvil |
| `step_bpa_irrigation` | Centro BPA y Riego, vistas nativas, seguridad y scroll móvil |
| `step_hr_remuneration_book` | Nómina/Libro, integración SimpleDigital, logo y scroll móvil |
| `step_colaciones` | Dashboard, operación de colaciones y scroll móvil |
| `step_agricultural_access` | Seguridad y visibilidad de menús agrícolas |

`step_demo_homepage` es específico de Demo. Solo llevarlo a Desarrollo si se
quiere también la portada pública agrícola allí; en ese caso, cambiar los
textos “Demo” por “Desarrollo” antes de actualizarlo.

La PWA `colaciones_web` se despliega por separado. No copiar
`/var/www/colaciones_app` de Demo a Desarrollo porque el enrutamiento y el host
son diferentes. Seguir `docs/DESPLIEGUE_COLACIONES.md` y publicar en Desarrollo
solo bajo `https://desarrollo.stepsapp.cl/colaciones/app/`.

## 1. Preflight

Conectarse al servidor y confirmar servicios y rutas:

```bash
set -euo pipefail

sudo systemctl is-active --quiet odoo18-demo.service
sudo systemctl is-active --quiet odoo18-dev.service
test -d /opt/demo_odoo18/odoo_agriculture
test -d /opt/dev_odoo18/odoo_agriculture

printf 'PRECHECK_OK\n'
```

Definir el inventario:

```bash
MODULES=(
  step_hr
  step_operations_ui
  step_labor_protection
  step_cosecha
  step_qa
  step_bpa_irrigation
  step_hr_remuneration_book
  step_colaciones
  step_agricultural_access
)
```

Comprobar el estado de instalación en ambas bases:

```bash
MODULE_SQL="'step_hr','step_operations_ui','step_labor_protection','step_cosecha','step_qa','step_bpa_irrigation','step_hr_remuneration_book','step_colaciones','step_agricultural_access'"

sudo -u postgres psql -d STEPS_DEMO -P pager=off -c \
  "SELECT name, state, latest_version FROM ir_module_module WHERE name IN ($MODULE_SQL) ORDER BY name;"

sudo -u postgres psql -d LAB_TAREAS -P pager=off -c \
  "SELECT name, state, latest_version FROM ir_module_module WHERE name IN ($MODULE_SQL) ORDER BY name;"
```

Reglas:

- Si un módulo está instalado en Demo pero no existe en Desarrollo, informar
  antes de instalarlo.
- Si está desinstalado en Demo, no instalarlo en Desarrollo por inferencia.
- Si el directorio no existe en Demo, detener la promoción de ese módulo.

## 2. Respaldo de Desarrollo

Respaldar la base objetivo y los módulos existentes:

```bash
set -euo pipefail

STAMP=$(date +%Y%m%d-%H%M%S)
BACKUP=/opt/fernando_odoo18/backups/demo-a-dev-$STAMP
DEV_ADDONS=/opt/dev_odoo18/odoo_agriculture

sudo mkdir -p "$BACKUP/modules"
sudo chown postgres:postgres "$BACKUP"
sudo -u postgres pg_dump -Fc -d LAB_TAREAS -f "$BACKUP/LAB_TAREAS.dump"
sudo chown -R root:root "$BACKUP"

for module in "${MODULES[@]}"; do
  if sudo test -d "$DEV_ADDONS/$module"; then
    sudo tar -czf "$BACKUP/modules/$module.tar.gz" \
      -C "$DEV_ADDONS" "$module"
  else
    sudo touch "$BACKUP/modules/$module.was_absent"
  fi
done
```

Registrar checksums de las fuentes de Demo:

```bash
DEMO_ADDONS=/opt/demo_odoo18/odoo_agriculture

for module in "${MODULES[@]}"; do
  sudo find "$DEMO_ADDONS/$module" -type f \
    ! -path '*/__pycache__/*' ! -name '*.pyc' -print0 \
    | sudo sort -z \
    | sudo xargs -0 sha256sum \
    | sudo tee "$BACKUP/$module.demo.sha256" >/dev/null
done
```

## 3. Comparación obligatoria

Guardar un `dry-run` por módulo:

```bash
for module in "${MODULES[@]}"; do
  sudo rsync -ani --delete \
    --exclude '__pycache__/' --exclude '*.pyc' \
    "$DEMO_ADDONS/$module/" \
    "$DEV_ADDONS/$module/" \
    | sudo tee "$BACKUP/$module.rsync-dry-run.txt"
done
```

Claude debe revisar el resultado antes de continuar. Detenerse si aparecen:

- `.env`, claves, dumps o certificados;
- archivos de configuración específicos de Demo;
- eliminaciones masivas no explicadas;
- módulos de terceros o código bajo `/opt/rrhh`;
- archivos de usuarios o adjuntos.

## 4. Sincronizar código Demo → Desarrollo

Después de revisar los `dry-run`:

```bash
for module in "${MODULES[@]}"; do
  sudo mkdir -p "$DEV_ADDONS/$module"
  sudo rsync -a --delete --chown=root:odoo \
    --exclude '__pycache__/' --exclude '*.pyc' \
    "$DEMO_ADDONS/$module/" \
    "$DEV_ADDONS/$module/"
done
```

No copiar bases de datos ni `filestore`.

## 5. Validación estática antes de actualizar Odoo

```bash
sudo -u odoo /usr/bin/python3.10 - <<'PY'
import ast
from pathlib import Path

root = Path('/opt/dev_odoo18/odoo_agriculture')
modules = {
    'step_hr', 'step_operations_ui', 'step_labor_protection',
    'step_cosecha', 'step_qa', 'step_bpa_irrigation',
    'step_hr_remuneration_book', 'step_colaciones',
    'step_agricultural_access',
}

for module in modules:
    for path in (root / module).rglob('*.py'):
        ast.parse(path.read_text(encoding='utf-8'), filename=str(path))
print('PYTHON_OK')
PY
```

Validar XML sin modificar archivos:

```bash
sudo -u odoo /usr/bin/python3.10 - <<'PY'
from pathlib import Path
from lxml import etree

root = Path('/opt/dev_odoo18/odoo_agriculture')
modules = {
    'step_hr', 'step_operations_ui', 'step_labor_protection',
    'step_cosecha', 'step_qa', 'step_bpa_irrigation',
    'step_hr_remuneration_book', 'step_colaciones',
    'step_agricultural_access',
}

for module in modules:
    for path in (root / module).rglob('*.xml'):
        etree.parse(str(path))
print('XML_OK')
PY
```

## 6. Actualizar módulos en `LAB_TAREAS`

Actualizar solamente los que figuren como `installed` en Demo y Desarrollo:

```bash
sudo -u odoo /usr/bin/python3.10 /opt/odoo18/odoo-bin \
  -c /etc/dev_odoo18.conf \
  -d LAB_TAREAS \
  -u step_hr,step_operations_ui,step_labor_protection,step_cosecha,step_qa,step_bpa_irrigation,step_hr_remuneration_book,step_colaciones,step_agricultural_access \
  --stop-after-init \
  --no-http
```

Si el comando falla, no reiniciar todavía: conservar el log, identificar el
módulo responsable y restaurar desde `$BACKUP` si no puede corregirse de forma
segura.

Si termina con código `0`:

```bash
sudo systemctl restart odoo18-dev.service
sudo systemctl is-active --quiet odoo18-dev.service
curl --fail --silent --output /dev/null https://desarrollo.stepsapp.cl/web/login
printf 'DESARROLLO_OK\n'
```

## 7. Validación funcional

Probar con un usuario de Desarrollo, nunca con credenciales copiadas desde
Demo.

### Escritorio

- Menús y logos de aplicaciones.
- Actividades y Tracker.
- Maquinaria y Fletes.
- Protección Laboral.
- Cosecha y Calidad.
- BPA y Riego.
- Nómina y Libro de Remuneraciones.
- Colaciones.

### Móvil

Usar al menos `390 × 844` y `440 × 956`. En cada dashboard comprobar:

- que el contenido tenga desplazamiento vertical;
- que el gesto cambie realmente `scrollTop`;
- que no haya desbordamiento horizontal;
- que botones, filtros y tarjetas sean utilizables;
- que Nómina muestre el logo de SimpleDigital.

Rutas directas útiles:

```text
https://desarrollo.stepsapp.cl/odoo/action-step_hr.action_step_activities_dashboard
https://desarrollo.stepsapp.cl/odoo/action-step_hr.action_step_tracker_dashboard
https://desarrollo.stepsapp.cl/odoo/action-step_operations_ui.action_machinery_dashboard
https://desarrollo.stepsapp.cl/odoo/action-step_operations_ui.action_freight_dashboard
https://desarrollo.stepsapp.cl/odoo/action-step_labor_protection.action_labor_dashboard
https://desarrollo.stepsapp.cl/odoo/action-step_cosecha.action_step_cosecha_dashboard
https://desarrollo.stepsapp.cl/odoo/action-step_qa.action_step_qa_dashboard
https://desarrollo.stepsapp.cl/odoo/action-step_bpa_irrigation.action_step_bpa_dashboard
https://desarrollo.stepsapp.cl/odoo/action-step_hr_remuneration_book.action_steps_payroll_dashboard
https://desarrollo.stepsapp.cl/odoo/action-step_colaciones.action_colaciones_dashboard
```

En los dashboards personalizados, el elemento raíz debe quedar acotado al
alto de `.o_action_manager` y ser el dueño del scroll en móvil:

```css
height: 100%;
min-height: 0;
overflow-y: auto;
touch-action: pan-y;
```

## 8. Evidencia de entrega

Claude debe informar:

1. ubicación exacta del respaldo;
2. módulos copiados y actualizados;
3. módulos omitidos y motivo;
4. resultado del upgrade de Odoo;
5. estado final de `odoo18-dev.service`;
6. pruebas HTTP;
7. validación móvil por dashboard;
8. diferencias restantes entre Demo y Desarrollo.

No declarar la tarea completa únicamente porque el servicio esté activo; las
pantallas y el scroll móvil deben comprobarse en el navegador.

## Rollback

Si Desarrollo queda inestable:

```bash
sudo systemctl stop odoo18-dev.service

for module in "${MODULES[@]}"; do
  if sudo test -f "$BACKUP/modules/$module.tar.gz"; then
    sudo rm -rf "$DEV_ADDONS/$module"
    sudo tar -xzf "$BACKUP/modules/$module.tar.gz" -C "$DEV_ADDONS"
  elif sudo test -f "$BACKUP/modules/$module.was_absent"; then
    sudo rm -rf "$DEV_ADDONS/$module"
  fi
done

sudo -u postgres dropdb LAB_TAREAS
sudo -u postgres createdb -O dev_odoo18 LAB_TAREAS
sudo -u postgres pg_restore -d LAB_TAREAS "$BACKUP/LAB_TAREAS.dump"

sudo systemctl start odoo18-dev.service
sudo systemctl is-active --quiet odoo18-dev.service
```

El rollback es destructivo para el estado posterior al respaldo. Ejecutarlo
solo después de confirmar que `$BACKUP` existe, que el dump es válido y que el
objetivo es exactamente `LAB_TAREAS`.
