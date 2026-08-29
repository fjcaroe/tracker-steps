# Auditoría y homologación Odoo — 27 de agosto de 2026

## Resultado ejecutivo

Los aplicativos Steps quedaron homologados según la arquitectura compatible de
cada ambiente. No se copiaron, reemplazaron ni mezclaron bases de datos o sus
datos.

Se detectó una divergencia real que no había quedado destacada en el control
anterior: `step_tracker_odoo` 18.0.1.0.0 estaba instalado en Demo, pero figuraba
disponible y no instalado en Desarrollo. Como el código completo de los addons
agrícolas era idéntico en ambos servidores y el módulo forma parte del producto
Steps, se respaldaron los tres ambientes y se instaló únicamente ese addon en
Desarrollo. No se activaron sincronizaciones, credenciales ni acciones externas.

Demo-SyS conserva su data y el adapter SimpleDigital. Steps Tracker no se instaló
allí porque pertenece al stack agrícola de Desarrollo/Demo y no es una
dependencia compatible o necesaria del stack SyS.

## Estado inicial y colisiones

- No había procesos de Claude, actualizaciones `-u`, dumps, restauraciones ni
  sincronizaciones en curso.
- Los servicios `odoo18-dev`, `odoo18-demo` y `odoo18-demo-sys` estaban activos.
- No hubo archivos modificados desde el control del 26 de agosto a las 09:00 UTC.
- El árbol completo `/opt/dev_odoo18/odoo_agriculture` era idéntico al de Demo
  mediante comparación recursiva por contenido, excluyendo caché Python.

## Respaldo verificable

Antes de escribir se creó:

`/opt/steps_backups/homologacion-20260827-0908/`

Contiene:

- `LAB_TAREAS.dump`
- `STEPS_DEMO.dump`
- `STEPS_DEMO_SYS.dump`
- addons dirigidos de Desarrollo, Demo y Demo-SyS;
- `SHA256SUMS`.

Las seis sumas SHA-256 fueron verificadas correctamente. El respaldo ocupa 74 MB.

## Cambio aplicado

| Ambiente | Acción | Resultado |
|---|---|---|
| Desarrollo | Instalación dirigida de `step_tracker_odoo` | 18.0.1.0.0 instalado |
| Demo | Sin escritura; ya era el release canónico | 18.0.1.0.0 instalado |
| Demo-SyS | Sin escritura; no aplica al stack SyS | Sin cambio |

La actualización terminó con código 0. Solo se detuvo y reinició
`odoo18-dev.service`; Demo y Demo-SyS no fueron reiniciados.

Validaciones de seguridad del Tracker en Desarrollo y Demo:

- cero compañías con sincronización habilitada;
- cron de sincronización inactivo;
- sin parámetros o credenciales configuradas;
- una aplicación raíz por ambiente;
- fingerprints idénticos de vistas y acciones;
- JS, XML y SCSS públicos responden HTTP 200 y tienen el mismo tamaño.

Después del cambio, la lista completa de módulos Steps instalados y sus versiones
es idéntica entre Desarrollo y Demo.

## Release común validado

| Addon | Versión común |
|---|---:|
| `step_agricultural_branding` | 18.0.1.0.0 |
| `step_demo_homepage` | 18.0.1.0.3 |
| `step_colaciones` | 18.0.2.1.0 |
| `step_hr_remuneration_book` | 18.0.3.3.0 |
| `step_hr_contract_lifecycle` | 18.0.2.0.1 |

Adapters contractuales:

- Desarrollo y Demo: `step_hr_contract_lifecycle_agriculture` 18.0.1.0.0.
- Demo-SyS: `step_hr_contract_lifecycle_simpledigital` 18.0.1.0.0.

Las vistas, acciones y menús de los cinco addons comunes tienen fingerprints
normalizados idénticos en las tres bases.

## Validación funcional

- No existe un menú raíz activo independiente de Finiquitos en ninguna base.
- `fcaro.ruiz@gmail.com` está activo y conserva los diez grupos de gestión
  contractual en los tres ambientes.
- La acción contextual de emisión masiva usa
  `context.get('active_ids', [])`; las acciones de menú mantienen contexto vacío.
- El logo de Nómina apunta en los tres ambientes a
  `step_agricultural_branding,static/description/icon_payroll.png`.
- Las URLs base corresponden a cada dominio público.

Se ejecutaron los métodos reales de solo lectura para junio de 2026:

| Ambiente | Colaciones | Nómina |
|---|---|---|
| Desarrollo | 3 períodos, 0 registros | 6 períodos, 0 liquidaciones |
| Demo | 3 períodos, 0 registros | 6 períodos, 0 liquidaciones |
| Demo-SyS | 3 períodos, 0 registros | 6 períodos, 3 liquidaciones |

La diferencia de cantidades en Demo-SyS corresponde a su data propia y se
conservó íntegramente.

## Salud y validación web

- Los tres servicios terminaron activos.
- No aparecieron errores, trazas ni fallos nuevos en los servicios después del
  despliegue.
- Los tres dominios responden HTTP 200; tras el calentamiento del registry, los
  tiempos observados fueron 0,04–0,05 segundos.
- Las tres portadas públicas muestran la misma estructura, propuesta de valor,
  títulos y marca Steps Agro.
- Las tres pantallas de acceso cargan sus dos campos y recursos sin errores de
  consola.

La sesión de navegador disponible no estaba autenticada. Las pantallas internas
se verificaron mediante definiciones cargadas, permisos, menús, modelos y métodos
reales de Odoo, sin transmitir contraseñas.

## Pendientes no bloqueantes

1. Sanear la referencia histórica a `steps_api` en Desarrollo y Demo; sigue
   apareciendo como módulo no instalable durante la carga del registry.
2. Restaurar la cuenta/proyecto correcto de `gcloud`; la conexión SSH local
   continúa operativa.
3. Mantener en seguimiento el pool de conexiones reducido de Desarrollo, el
   cron estándar de ausencias y la diferencia de `proxy_mode` ya documentada.

No se hizo `git push`, no se expusieron secretos y no se ejecutaron correos,
pagos, documentos tributarios/DT ni acciones externas reales.
