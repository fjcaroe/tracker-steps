# Auditoría y homologación Odoo — 26 de agosto de 2026

## Resultado ejecutivo

Los aplicativos Steps están homologados según la arquitectura de cada entorno.
No se copiaron, reemplazaron ni mezclaron bases de datos o datos.

Claude dejó después de la auditoría anterior un release nuevo de
Actividades/Tracker, Control de Accesos Agrícolas y Movilización en Desarrollo y
Demo. El código, versiones, migraciones y definiciones cargadas coinciden entre
ambos ambientes. Demo-SyS no recibió esos addons porque corresponden al stack
agrícola y no al motor SyS/SimpleDigital.

No fue necesario actualizar módulos ni reiniciar servicios durante esta
auditoría. Como el despliegue de Claude no dejó un backup específico, se creó y
verificó un respaldo base posterior del estado validado de las tres instancias.

## Estado inicial

- No había procesos de Claude, actualizaciones `-u`, dumps, restauraciones ni
  sincronizaciones activas.
- Los tres servicios estaban activos y sin estado de fallo.
- Se utilizó la conexión SSH local configurada, ya que la cuenta activa de
  `gcloud` continúa sin acceso al proyecto de `odoo-new`.

## Release nuevo auditado

| Addon | Desarrollo | Demo | Demo-SyS |
|---|---:|---:|---:|
| `step_hr` | 18.0.1.3.0 | 18.0.1.3.0 | No aplica |
| `step_agricultural_access` | 18.0.2.0.0 | 18.0.2.0.0 | No aplica |
| `step_mobilization` | 18.0.1.0.1 | 18.0.1.0.1 | No aplica |

Evidencia del release:

- `step_hr` tiene el mismo SHA-256 completo en Desarrollo y Demo:
  `89cc37c10b4aa7ad2848cd36a622378fc8884d7f1ee9ef15743047830a421267`.
- `step_agricultural_access` coincide:
  `fa7bf06f16393c9c55ea988045585df4ded8acf6758e67d0d7da72b2cd6dcafc`.
- `step_mobilization` coincide:
  `cd3dca8b8e21394af61a8ad61ac5b8893c8bbc4a8ed6818de1fb221ebebe30fc`.
- Las versiones instaladas coinciden con los manifests.
- Los fingerprints de vistas, menús, acciones y campos son idénticos entre
  Desarrollo y Demo.

## Validación de Movilización

El addon quedó separado de Actividades y registrado como aplicación propia en
Operations.

- Existe un solo menú raíz activo `Movilización` por ambiente.
- No quedaron menús antiguos duplicados provenientes de `step_hr`.
- El menú utiliza el icono propio de `step_mobilization`.
- `fcaro.ruiz@gmail.com` tiene los ocho grupos del módulo en Desarrollo y Demo.
- Desarrollo conserva 7 viajes existentes; Demo conserva 0, respetando la data
  independiente de cada base.
- La migración de credenciales móviles quedó íntegra:
  - Desarrollo: 14 empleados y 7 viajes, sin UUID nulos o duplicados.
  - Demo: 13 empleados, sin UUID nulos o duplicados.

## Aplicativos comunes

Continúan idénticos en los tres ambientes:

| Addon | Versión |
|---|---:|
| `step_agricultural_branding` | 18.0.1.0.0 |
| `step_demo_homepage` | 18.0.1.0.3 |
| `step_colaciones` | 18.0.2.1.0 |
| `step_hr_remuneration_book` | 18.0.3.3.0 |
| `step_hr_contract_lifecycle` | 18.0.2.0.1 |

Adapters contractuales:

- Desarrollo y Demo: `step_hr_contract_lifecycle_agriculture` 18.0.1.0.0.
- Demo-SyS: `step_hr_contract_lifecycle_simpledigital` 18.0.1.0.0.

Validaciones adicionales:

- No existe un menú raíz activo de Finiquitos.
- El logo de Nómina es el mismo en las tres bases.
- El icono actualizado de Actividades fue inspeccionado visualmente y no
  contiene las iniciales `JE`; representa trabajadores agrícolas y control de
  labores. La imagen auxiliar utiliza únicamente la marca Steps.
- `fcaro.ruiz@gmail.com` conserva los diez permisos contractuales en las tres
  bases.
- Emisión masiva conserva la acción segura sin `active_ids` desde el menú.
- Las URLs base corresponden a sus tres dominios públicos.

## Dashboards y selectores

Se ejecutaron métodos reales de solo lectura para junio de 2026:

| Ambiente | Colaciones | Nómina |
|---|---|---|
| Desarrollo | selector con 3 períodos | selector con 6 períodos |
| Demo | selector con 3 períodos | selector con 6 períodos |
| Demo-SyS | selector con 3 períodos | selector con 6 períodos y 3 liquidaciones reales |

Las diferencias de cantidades corresponden a la data propia de cada base.

## Respaldo creado

Respaldo base posterior al release auditado:

`/opt/steps_backups/post-claude-baseline-20260826-090540/`

Incluye:

- dumps completos de `LAB_TAREAS`, `STEPS_DEMO` y `STEPS_DEMO_SYS`;
- addons Steps dirigidos de cada ambiente;
- adapters agrícola y SimpleDigital correspondientes;
- archivo `SHA256SUMS`.

Las seis sumas SHA-256 fueron verificadas correctamente.

## Salud y validación web

- Los tres servicios permanecieron activos; no fueron reiniciados.
- Los tres dominios responden HTTP 200.
- Tiempos observados en login: entre 0,06 y 0,08 segundos.
- No hubo errores nuevos de servicio durante la auditoría.
- Las tres portadas muestran la misma estructura, títulos, soluciones y marca.
- Las tres pantallas de ingreso cargaron campos, logos y estilos sin errores.
- La consola del navegador terminó sin errores ni advertencias de assets.

La sesión de navegador disponible no estaba autenticada. Las pantallas internas
se verificaron mediante las vistas, menús, acciones, permisos, modelos y métodos
reales de Odoo, sin transmitir contraseñas ni ejecutar acciones externas.

## Pendientes no bloqueantes

1. Restaurar la cuenta y proyecto correctos de `gcloud`; la conexión SSH local
   funciona, pero no reemplaza la administración del proyecto.
2. Sanear la referencia histórica a `steps_api` en Desarrollo y Demo.
3. Mantener en seguimiento el pool de conexiones de Desarrollo, el cron estándar
   de ausencias y `proxy_mode`, ya registrados en auditorías anteriores.

No se hizo `git push`, no se expusieron secretos y no se ejecutaron correos,
pagos, documentos tributarios, DT ni acciones externas reales.

