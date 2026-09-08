# Homologación Odoo — cierre del 2 de septiembre de 2026

## Resultado ejecutivo

Los módulos propios comunes de Steps quedaron homologados en Desarrollo, Demo
y Demo-SyS. Se conservó la data de cada base y los adaptadores específicos:
Blueminds/agricultura en Desarrollo y Demo, y SimpleDigital/SyS en Demo-SyS.
No se copiaron ni mezclaron bases de datos.

## Preflight

- No había actualizaciones de módulos, dumps, restauraciones ni sincronizaciones
  activas al iniciar el despliegue.
- Los tres servicios estaban activos y los tres dominios respondían HTTP 200.
- La recuperación paralela del incidente del 31 de agosto había concluido.

## Divergencias encontradas

1. Demo-SyS ya había recuperado los módulos comunes que el control del 1 de
   septiembre encontró desinstalados.
2. Tesorería permanecía en 18.0.1.1.1 en Demo-SyS, mientras Desarrollo y Demo
   tenían 18.0.1.2.0. El código de Demo-SyS tampoco incluía el release visual y
   funcional completo.
3. `fcaro.ruiz@gmail.com` seguía siendo administrador de Ajustes en Demo-SyS,
   pero había perdido los diez grupos explícitos de Gestión contractual. Esto
   podía reproducir el error de acceso a `hr.severance`.

## Respaldo verificable

Antes de escribir se generaron dumps en formato custom de las tres bases y un
respaldo del addon de Tesorería de Demo-SyS:

`/opt/backups/homologacion_codex_20260902-090311/`

Archivos:

- `LAB_TAREAS.dump` — 19.852.814 bytes
- `STEPS_DEMO.dump` — 22.848.332 bytes
- `STEPS_DEMO_SYS.dump` — 22.717.378 bytes
- `step_account_treasury_demosys_before.tgz` — 103.624 bytes

Cada dump fue validado con `pg_restore --list`; el tar fue listado y se
calcularon SHA-256 durante el respaldo.

## Cambios aplicados

- Se sincronizó únicamente `step_account_treasury` desde el release canónico de
  Desarrollo hacia el árbol de Demo-SyS.
- Se actualizó únicamente ese módulo en `STEPS_DEMO_SYS`.
- Demo-SyS quedó en `step_account_treasury` 18.0.1.2.0.
- Se repusieron de forma idempotente los diez grupos de Gestión contractual al
  usuario `fcaro.ruiz@gmail.com` en Demo-SyS.
- Se reinició únicamente `odoo18-demo-sys.service` para cargar código, assets y
  permisos. El 502 inicial durante el arranque fue transitorio; el siguiente
  control respondió 200.

## Evidencia de homologación

Versiones comunes en las tres bases:

| Módulo | Versión |
|---|---:|
| `step_account_treasury` | 18.0.1.2.0 |
| `step_agricultural_branding` | 18.0.1.0.0 |
| `step_colaciones` | 18.0.2.1.0 |
| `step_demo_homepage` | 18.0.1.0.3 |
| `step_hr_contract_lifecycle` | 18.0.2.0.1 |
| `step_hr_previred` | 18.0.3.4.0 |
| `step_hr_remuneration_book` | 18.0.3.3.0 |

Los hashes normalizados del código de los siete módulos dirigidos coinciden en
los tres árboles. Los fingerprints de las vistas cargadas también coinciden en
las tres bases para Tesorería, Colaciones, Libro de Remuneraciones,
Contratos/Finiquitos y Previred.

Controles funcionales de base:

- una aplicación raíz de Tesorería con el mismo logo en los tres ambientes;
- una aplicación raíz de Nómina con el mismo logo en los tres ambientes;
- cero aplicaciones raíz independientes de Finiquitos;
- selector mensual de Colaciones presente en los tres ambientes;
- nueve vistas del Libro de Remuneraciones y 32 vistas contractuales activas en
  cada base;
- diez grupos contractuales asignados al usuario solicitado en cada ambiente;
- URL base correcta para cada dominio;
- JS de semanas calendario de Tesorería servido con HTTP 200 en Demo-SyS.

## Salud final

- `odoo18-dev.service`: activo; HTTPS 200 (0,165 s).
- `odoo18-demo.service`: activo; HTTPS 200 (0,128 s).
- `odoo18-demo-sys.service`: activo; HTTPS 200 (0,074 s).
- Sin procesos de despliegue o restauración pendientes.
- Sin errores, trazas ni críticos nuevos en el servicio Demo-SyS después de la
  actualización.

El controlador de navegador disponible no pudo inicializarse en este control.
La equivalencia visual se verificó por código, assets servidos y fingerprints de
las vistas Odoo cargadas, pero no se adjuntaron capturas autenticadas nuevas.

No se ejecutaron pagos, correos, documentos tributarios/DT, archivos bancarios
ni integraciones externas. No se hizo git push y no se publicaron secretos.
