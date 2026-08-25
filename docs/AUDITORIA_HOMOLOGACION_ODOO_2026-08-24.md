# Auditoría de homologación Odoo — 24 de agosto de 2026

## Resultado ejecutivo

Los aplicativos Steps compatibles están homologados en Desarrollo, Demo y
Demo-SyS. No se copiaron ni mezclaron bases de datos y no se modificó data.

No fue necesario desplegar ni actualizar módulos durante esta revisión: el
código común ya coincide byte a byte, las versiones instaladas coinciden y las
definiciones cargadas por Odoo tienen los mismos fingerprints. Demo-SyS conserva
su motor SimpleDigital y utiliza el adapter contractual específico, mientras
Desarrollo y Demo conservan el adapter agrícola.

Al comenzar no había procesos de Claude, actualizaciones `-u`, restauraciones ni
copias activas. Los tres servicios estaban y terminaron activos.

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
- Demo-SyS: `step_hr_contract_lifecycle_simpledigital` 18.0.1.0.0 y
  `l10n_cl_simpledigital_payroll` 18.0.1.0.0.

Los demás addons agrícolas presentes en Desarrollo y Demo también tienen el
mismo hash y la misma versión instalada entre esos dos ambientes. No se
intentaron instalar en Demo-SyS addons agrícolas cuyas dependencias o modelos no
pertenecen a la arquitectura SyS.

## Evidencia técnica

### Código y base de datos

- Hashes SHA-256 idénticos en los cinco addons comunes de los tres servidores.
- Fingerprints idénticos de las vistas, acciones, menús y campos cargados por
  Odoo para Colaciones, Libro de Remuneraciones y Gestión Contractual.
- Contratos/Finiquitos está integrado en Nómina en los tres ambientes:
  `Gestión contractual` y `Término laboral` cuelgan del árbol estándar de
  Nómina.
- No existe ningún menú raíz **activo** de Finiquitos. Desarrollo conserva el
  antiguo XML ID de Studio archivado (`active = false`), sin borrar su data.
- El menú `Emisión masiva` apunta en los tres entornos a la acción segura sin
  `active_ids`; la acción contextual usa
  `context.get('active_ids', [])`.
- El logo de Nómina es el mismo en las tres bases:
  `step_agricultural_branding,static/description/icon_payroll.png`.
- El usuario `fcaro.ruiz@gmail.com` está activo en las tres bases y tiene los
  diez grupos de Gestión Contractual, incluidos cálculo y aprobación de
  finiquitos.

### Pruebas funcionales de solo lectura

Se ejecutaron los métodos reales de los dashboards para junio de 2026:

| Ambiente | Colaciones | Nómina |
|---|---|---|
| Desarrollo | período `2026-06`, selector con 3 opciones | período `2026-06`, selector con 6 opciones |
| Demo | período `2026-06`, selector con 3 opciones | período `2026-06`, selector con 6 opciones |
| Demo-SyS | período `2026-06`, selector con 3 opciones | período `2026-06`, selector con 6 opciones y 3 liquidaciones reales |

La diferencia de cantidades responde a la data propia de cada base, no a una
diferencia funcional.

### Validación web

- Las tres portadas responden HTTP 200 y muestran la misma estructura visual,
  encabezado, soluciones, trazabilidad y acceso a la plataforma.
- Las pantallas de ingreso de los tres ambientes cargan usuario, contraseña,
  logos y estilos sin errores visibles.
- No se observaron errores ni advertencias de consola durante la navegación
  pública.
- La sesión de navegador disponible no estaba autenticada. La validación de las
  pantallas internas se completó mediante las definiciones reales de menús,
  acciones, vistas, permisos, modelos y llamadas de dashboard de Odoo, sin
  transmitir una contraseña ni alterar una sesión de usuario.

### Salud y rendimiento al cierre

| Servicio | Estado | Memoria aproximada | HTTP login |
|---|---|---:|---:|
| `odoo18-dev.service` | activo | 526 MiB | 200 / 0,17 s |
| `odoo18-demo.service` | activo | 382 MiB | 200 / 0,08 s |
| `odoo18-demo-sys.service` | activo | 269 MiB | 200 / 0,17 s |

No hubo errores nuevos en los tres servicios desde el inicio de la auditoría.

## Cambios y respaldos

Esta ejecución no realizó escrituras en las bases, addons ni configuraciones;
por lo tanto, no correspondía generar un nuevo backup ni reiniciar servicios.
El último respaldo verificable anterior al hotfix contractual permanece en:

`/opt/steps_backups/contract-url-hotfix-20260823-224842/`

Incluye dumps de las tres bases, copia previa del núcleo contractual, logs y
sumas SHA-256.

No se realizó `git push` ni se publicaron credenciales.

## Pendientes operativos no bloqueantes

1. Desarrollo registró antes de esta auditoría episodios de
   `The Connection Pool Is Full`. Usa `db_maxconn = 6`, `workers = 0` y dos
   hilos de cron. En el cierre sólo tenía dos conexiones inactivas y respondió
   normalmente, pero conviene dimensionar el pool y concurrencia por separado.
2. Desarrollo y Demo registran un fallo periódico del cron estándar
   `Attendance: Detect Absences for employees`: intenta crear una asistencia
   técnica para un empleado que ya figura con entrada. No está relacionado con
   los addons homologados y requiere corregir la inconsistencia de asistencia o
   la configuración del cron.
3. Desarrollo sigue avisando que `steps_api` está instalado en la base pero no
   es instalable desde el código disponible. No bloquea el arranque, aunque debe
   sanearse como deuda técnica.
4. Desarrollo mantiene `proxy_mode = False` detrás de Nginx, mientras Demo y
   Demo-SyS usan `True`. Las URLs base están congeladas con sus dominios
   correctos, pero conviene homologar esta configuración en una ventana de
   infraestructura controlada.

