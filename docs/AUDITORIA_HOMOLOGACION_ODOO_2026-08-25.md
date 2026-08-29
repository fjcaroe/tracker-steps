# Auditoría y homologación Odoo — 25 de agosto de 2026

## Resultado ejecutivo

Los aplicativos Steps comunes continúan homologados en Desarrollo, Demo y
Demo-SyS. No se copiaron, reemplazaron ni mezclaron bases de datos o datos.

La auditoría encontró una referencia de asset rota en Desarrollo y Demo dentro
de `step_expire_database`: el manifest declaraba un JavaScript que nunca estuvo
presente. El navegador cargaba la página, pero registraba dos errores por
ambiente al construir `web.assets_frontend_lazy`.

Se corrigió el manifest, se incrementó el addon a `18.0.1.0.1`, se respaldaron
las dos bases y los dos addons afectados y se desplegó secuencialmente en
Desarrollo y Demo. Demo-SyS no usa ese addon, no presentaba el error y no fue
modificado.

## Estado inicial

- No había procesos de Claude, actualizaciones `-u`, copias, dumps o
  restauraciones activos.
- `odoo18-dev.service`, `odoo18-demo.service` y
  `odoo18-demo-sys.service` estaban activos.
- La cuenta activa de Google Cloud había cambiado a un proyecto sin permiso
  `compute.instances.get` sobre `odoo-new`. Se utilizó la conexión SSH local ya
  configurada, sin cambiar cuentas, proyectos ni credenciales.

## Release canónico validado

| Addon común | Desarrollo | Demo | Demo-SyS |
|---|---:|---:|---:|
| `step_agricultural_branding` | 18.0.1.0.0 | 18.0.1.0.0 | 18.0.1.0.0 |
| `step_demo_homepage` | 18.0.1.0.3 | 18.0.1.0.3 | 18.0.1.0.3 |
| `step_colaciones` | 18.0.2.1.0 | 18.0.2.1.0 | 18.0.2.1.0 |
| `step_hr_remuneration_book` | 18.0.3.3.0 | 18.0.3.3.0 | 18.0.3.3.0 |
| `step_hr_contract_lifecycle` | 18.0.2.0.1 | 18.0.2.0.1 | 18.0.2.0.1 |

Adapters esperados:

- Desarrollo y Demo: `step_hr_contract_lifecycle_agriculture` 18.0.1.0.0.
- Demo-SyS: `step_hr_contract_lifecycle_simpledigital` 18.0.1.0.0 sobre
  `l10n_cl_simpledigital_payroll`.

Addon auxiliar corregido:

- Desarrollo y Demo: `step_expire_database` 18.0.1.0.1.
- Demo-SyS: no instalado y no requerido.

## Diferencia encontrada y corrección

El manifest incluía en frontend y backend:

`step_expire_database/static/src/js/remove_expire_msg.js`

El archivo no existía. El comportamiento vigente depende únicamente de
`static/src/scss/hide_expiration.scss`, por lo que se eliminaron las dos
referencias inexistentes sin inventar lógica JavaScript. También se normalizó
el autor del manifest a `Steps Consulting`.

El manifest final tiene el mismo SHA-256 en ambos entornos:

`e8460e358d3b10fbd25fdbd4c21729ca5fc3577d5b4116dfaaf0311d0b269900`

## Respaldo

Respaldo verificable anterior al cambio:

`/opt/steps_backups/expire-assets-hotfix-20260825-090541/`

Contiene:

- `dev/LAB_TAREAS-before.dump`
- `demo/STEPS_DEMO-before.dump`
- copias comprimidas de `step_expire_database` de ambos ambientes;
- `SHA256SUMS`;
- logs de actualización por ambiente.

## Evidencia de homologación

- Los hashes completos de los addons comunes coinciden entre los ambientes en
  que corresponde instalarlos.
- Las versiones instaladas coinciden con sus manifests.
- Los fingerprints de vistas, menús, acciones y campos de Colaciones, Libro de
  Remuneraciones y Gestión Contractual son idénticos en las tres bases.
- No existe un menú raíz activo de Finiquitos.
- Nómina utiliza el mismo logo Steps en los tres ambientes.
- `fcaro.ruiz@gmail.com` está activo y posee los diez grupos contractuales en
  las tres bases.
- La acción de emisión masiva usa el contexto seguro y su acción de menú no
  depende de `active_ids`.
- Las URLs base son correctas para cada dominio.

Pruebas de dashboards para junio de 2026:

| Ambiente | Colaciones | Nómina |
|---|---|---|
| Desarrollo | selector con 3 períodos | selector con 6 períodos |
| Demo | selector con 3 períodos | selector con 6 períodos |
| Demo-SyS | selector con 3 períodos | selector con 6 períodos y 3 liquidaciones reales |

## Validación web final

- Las tres portadas conservan el mismo contenido y estructura visual.
- Las tres pantallas de ingreso cargan logos, estilos y campos correctamente.
- Después del hotfix se abrió una sesión de navegador nueva y no se registraron
  errores ni advertencias de assets en Desarrollo, Demo o Demo-SyS.
- Los tres dominios responden HTTP 200.
- Tiempos finales observados en login: Desarrollo 0,14 s; Demo 0,15 s;
  Demo-SyS 0,08 s.
- No hubo errores nuevos en los servicios después de la validación final.

La sesión de navegador disponible no estaba autenticada. Las pantallas internas
se validaron mediante las vistas, menús, acciones, permisos y métodos reales de
Odoo sin transmitir contraseñas ni ejecutar acciones externas.

## Pendientes no bloqueantes

1. Desarrollo y Demo siguen informando al cargar el registro que `steps_api`
   figura instalado en base pero no es instalable desde el código disponible.
   Es una deuda previa y no impidió el hotfix ni el arranque.
2. La cuenta activa de `gcloud` ya no apunta al proyecto autorizado para
   `odoo-new`. La conexión SSH local funciona, pero conviene restaurar la cuenta
   y proyecto correctos para futuras operaciones de infraestructura.
3. Se mantienen los pendientes operativos descritos en la auditoría del 24 de
   agosto: dimensionamiento del pool de Desarrollo, cron de ausencias y
   homologación futura de `proxy_mode`.

No se hizo `git push`, no se expusieron secretos y no se ejecutaron correos,
pagos, documentos tributarios, DT ni acciones externas reales.

