# Despliegue de mejoras Demo-Sys a SyS producción — 2 de septiembre de 2026

## Resultado

Se desplegaron en la base `SyS` las once mejoras que estaban validadas en
`STEPS_DEMO_SYS`. No se reemplazó la base productiva ni se copiaron empleados,
liquidaciones, asistencias o correcciones operacionales desde Demo-Sys.

## Respaldo previo

Directorio:

`/opt/backups/sys_prod_pre_payroll_rollout_20260902T073259Z`

Incluye:

- dump PostgreSQL de `SyS`;
- filestore completo de `SyS`;
- addons productivos anteriores;
- configuración del servicio;
- checksums SHA-256;
- logs de la prueba aislada y del despliegue productivo;
- archivo de los módulos finalmente desplegados.

El dump y ambos archivos comprimidos fueron abiertos y validados antes del
despliegue.

## Validación previa

El respaldo de producción se restauró en una base temporal, se regeneró su
identidad y se neutralizó. Los once módulos se instalaron correctamente en esa
copia antes de tocar la base real. La base temporal fue eliminada al terminar.

## Módulos instalados

| Módulo | Versión |
|---|---:|
| `step_account_treasury` | 18.0.1.1.1 |
| `step_accounting_multicurrency` | 18.0.2.0.1 |
| `step_agricultural_branding` | 18.0.1.0.0 |
| `step_colaciones` | 18.0.2.1.0 |
| `step_demo_homepage` | 18.0.1.0.3 |
| `step_hr_contract_lifecycle` | 18.0.2.0.1 |
| `step_hr_contract_lifecycle_simpledigital` | 18.0.1.0.0 |
| `step_hr_previred` | 18.0.3.4.0 |
| `step_hr_previred_simpledigital` | 18.0.2.1.0 |
| `step_hr_remuneration_book` | 18.0.3.3.0 |
| `steps_hr_payroll_correction` | 18.0.1.0.1 |

También se copiaron selectivamente las plantillas laborales validadas `Pl 1` y
`P1 Cto fijo`. No se importaron otros registros de Demo-Sys.

## Comprobaciones finales

- Servicio `odoo18-sys.service`: activo.
- URL productiva oficial: `https://sys.stepsapp.cl/`.
- Acceso directo por Odoo y a través de Nginx: HTTP 200; HTTP redirige a HTTPS.
- Módulos instalados: 326 en total; los once del alcance están en estado
  `installed` y con las versiones esperadas.
- Datos conservados: 199 empleados, 493 liquidaciones y 59.783 registros de
  asistencia, iguales a la línea base previa.
- Luis tiene el permiso `Nómina: corrección de finiquitos`.
- Acción y botón `Corregir finiquito`: activos.
- Plantillas laborales validadas: 2.
- SyS conserva su condición productiva y no está neutralizada.
- No quedaron bases temporales ni errores recientes del servicio.

## Vista previa del caso Sergio Albornoz

Se ejecutó solo la vista previa, sin confirmar ni modificar datos. Para una
fecha real de término de 07/08/2026, el asistente identifica:

- 1 contrato a corregir;
- 48 segmentos de asistencia posteriores;
- 1 liquidación a recalcular.

La corrección operacional queda pendiente de confirmación dentro del formulario
por un responsable de Nómina.

## Observaciones

La instalación informó campos obligatorios vacíos en algunos empleados y
contratos históricos. Son advertencias ya reproducidas en la prueba aislada y
no impidieron la instalación. No se inventaron datos para completar esos campos.
