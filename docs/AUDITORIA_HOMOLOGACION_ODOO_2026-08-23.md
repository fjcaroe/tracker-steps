# Auditoría y homologación Odoo — 23 de agosto de 2026

## Resultado ejecutivo

Se revisó la entrega dejada por Claude y se consolidó un release único para
Desarrollo, Demo y Demo-SyS. Las bases permanecieron separadas y no se copiaron
datos entre ambientes.

Los tres servicios están activos, las tres portadas responden HTTP 200 y los
addons comunes tienen el mismo código fuente. Nómina, Libro de Remuneraciones,
Colaciones, la portada comercial y el branding quedaron en las mismas versiones
instaladas en las tres bases.

Queda una excepción funcional: `step_hr_contract_lifecycle` continúa sin
instalarse en Demo-SyS porque el addon entregado depende de `step_hr` y
`l10n_cl_hr`, mientras SyS usa `l10n_cl_simpledigital_payroll`. Forzar la
instalación intentó cargar una vista incompatible de liquidación; el proceso la
abortó, restauró el código anterior y levantó el servicio sin afectar la data.
El código canónico sí quedó presente en Demo-SyS para su posterior adaptación.

## Estado final

| Addon | Desarrollo | Demo | Demo-SyS |
|---|---:|---:|---:|
| `step_hr_remuneration_book` | 18.0.3.3.0 | 18.0.3.3.0 | 18.0.3.3.0 |
| `step_colaciones` | 18.0.2.1.0 | 18.0.2.1.0 | 18.0.2.1.0 |
| `step_demo_homepage` | 18.0.1.0.3 | 18.0.1.0.3 | 18.0.1.0.3 |
| `step_agricultural_branding` | 18.0.1.0.0 | 18.0.1.0.0 | 18.0.1.0.0 |
| `step_hr_contract_lifecycle` | 18.0.1.0.0 | 18.0.1.0.0 | No instalado |

Servicios finales:

- `odoo18-dev.service`: activo.
- `odoo18-demo.service`: activo.
- `odoo18-demo-sys.service`: activo.
- `https://desarrollo.stepsapp.cl/`: HTTP 200.
- `https://demo.stepsapp.cl/`: HTTP 200.
- `https://demo-sys.stepsapp.cl/`: HTTP 200.

## Release canónico consolidado

Se tomó como base:

1. Libro de Remuneraciones 18.0.3.3.0 de Demo, que coincidía con el código local
   y contenía el dashboard nuevo, selector de período y migración de perfiles.
2. Corrección de finiquito presente en Desarrollo, que calcula meses y días
   calendario. El caso 15-03-2021 a 17-11-2021 entrega 8 meses, 2 días y 14,08
   días finales, coincidente con el ejemplo oficial de la Dirección del Trabajo.
3. Colaciones, portada y branding desde el código local más completo.

El paquete inicial tuvo SHA-256:

`07b6c33ab0ab3f18e61a8d541ba4ba1cce16d84ba4453319cb400fe849e02960`

No se hizo `git push` ni se expusieron credenciales.

## Mejora adicional aplicada a Colaciones

La auditoría confirmó que el supuesto selector mensual de Colaciones no existía
en el código entregado: el dashboard seguía calculando solamente el día actual.
Se implementó `step_colaciones` 18.0.2.1.0 con:

- selector mensual común en los tres ambientes;
- meses disponibles obtenidos desde los registros reales, con un máximo de 24;
- recálculo por período de registros, pendientes, costo validado, personas,
  sincronizaciones offline, demanda por producto y últimos registros;
- estado vacío y etiquetas coherentes con el mes seleccionado;
- validación de backend para períodos explícitos, incluido junio de 2026.

Las llamadas reales de dashboard terminaron correctamente:

- `LAB_TAREAS`: Colaciones y Nómina OK.
- `STEPS_DEMO`: Colaciones y Nómina OK.
- `STEPS_DEMO_SYS`: Colaciones y Nómina OK; Nómina reconoció el motor Steps y
  devolvió datos reales de SyS para junio de 2026.

## Respaldos

Respaldos iniciales completos:

`/opt/steps_backups/homologacion-20260823-0505-clt/`

- `dev/LAB_TAREAS-before.dump`
- `demo/STEPS_DEMO-before.dump`
- `demosys/STEPS_DEMO_SYS-before.dump`
- copias comprimidas de los addons y archivos `SHA256SUMS` por ambiente.

Respaldos previos a Colaciones 18.0.2.1.0:

`/opt/steps_backups/colaciones-periodo-20260823-0520-clt/`

Cada ambiente contiene dump de base, addon anterior y suma SHA-256.

## Hallazgos adicionales

1. Desarrollo estaba detenido manualmente desde las 04:53 UTC, sin fallo de
   proceso. Fue actualizado y quedó activo.
2. Demo-SyS conserva deuda técnica previa: referencias a addons ausentes
   (`api_gateway_bp_v18`, `blue_jt_cost_centers`, `book_account` y
   `l10n_cl_report_cedible`). No impiden el arranque, pero deben depurarse.
3. Desarrollo y Demo conservan una referencia previa a `steps_api` no
   instalable. Tampoco impide el arranque.
4. Odoo reporta advertencias heredadas de campos antiguos, etiquetas repetidas
   y métodos `create` no batch. No pertenecen al release homologado, pero deben
   entrar en una auditoría técnica futura.

## Pendiente obligatorio: adapter contractual para SimpleDigital

No se debe instalar `step_hr_contract_lifecycle` en Demo-SyS con sus dependencias
actuales. La solución correcta es separar el núcleo contractual de los adapters:

1. núcleo compatible con `hr_contract`, `hr_payroll`, `hr_holidays`, `mail` y
   `analytic`;
2. adapter agrícola para `step_hr` y su maestro de fundos;
3. adapter SimpleDigital para `l10n_cl_simpledigital_payroll`;
4. maestro propio y estable de causales de término, con migración desde
   `hr.causal.termino` donde exista;
5. menús enlazados al dashboard de Nómina Steps sin depender de XML IDs de
   `l10n_cl_hr`;
6. pruebas con los 192 empleados y 387 liquidaciones de SyS antes de instalar.

Hasta completar ese adapter, Demo-SyS tiene el nuevo dashboard de Nómina, el
Libro de Remuneraciones y Colaciones homologados, pero no el flujo nuevo de
Contratos/Finiquitos.
