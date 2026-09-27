# Despliegue posterior a revisión del trabajo de Claude — 8 de septiembre de 2026

## Resultado

- Home `step_demo_homepage 18.0.2.1.0`: Desarrollo, Demo y Demo-SyS.
- PreviRed `step_hr_previred 18.0.3.8.1`: Desarrollo, Demo, Demo-SyS y SyS.
- Gestión y Costos `step_management_costs 18.0.20.0.0`: Desarrollo y Demo,
  junto con los puentes agrícola y maquinaria `18.0.1.0.0`.
- Pagos por lotes `step_account_treasury_batch 18.0.1.2.0`: Desarrollo y Demo.
  Demo-SyS se omitió porque allí no está instalado `account_batch_payment`.

Los cuatro servicios Odoo quedaron activos y los dominios de Desarrollo,
Demo, Demo-SyS y SyS respondieron HTTP 200 en el control final estable.

## Respaldos

- `/opt/steps_backups/home_rollout_20260908-202624/`
- `/opt/steps_backups/gestion_costos_18_0_20_20260908-202854/`
- `/opt/steps_backups/previred_18_0_3_8_1_20260908-203426/`
- `/opt/steps_backups/treasury_batch_18_0_1_2_20260908-204720/`

Cada carpeta contiene dumps previos de las bases intervenidas, tar de los
addons anteriores y logs de actualización.

## Verificación y observaciones

- Home renderizado con 12 familias, 5 apps, un H1 y el hero nuevo tanto en
  Demo como en Demo-SyS.
- PreviRed había pasado antes el dry-run funcional sobre los casos reales de
  licencia médica en Demo-SyS; la promoción dejó la misma versión en los
  cuatro ambientes.
- Gestión y Costos fue promovido según su runbook: Desarrollo primero y Demo
  después. Los tres addons quedaron instalados en ambos.
- Pagos por lotes quedó en `18.0.1.2.0` en Desarrollo y Demo.
- El log de SyS conserva el aviso preexistente por ausencia de `pdf417gen` en
  los módulos DTE. Desarrollo registró una saturación transitoria del pool al
  reiniciar y ejecutar el cron de autolimpieza; el cron terminó y no hubo
  errores posteriores en estado estable.

## Aprobación del ticket 17 para SyS

El correo más reciente del hilo «T17 Somed, Carolina Medel, error imposiciones
con licencia médica», recibido el 8 de septiembre de 2026 a las 20:26, aprobó
explícitamente la revisión de Demo-SyS y el paso a la base servida en el puerto
8070. La actualización de `SyS` se ejecutó posteriormente, a las 20:36, con el
respaldo previo indicado arriba. La ruta `/odoo/` redirige al login, el servicio
permanece activo y `step_hr_previred` figura instalado en `18.0.3.8.1`.

## Git

- `codex/claude-work-consolidated-20260908`: home, Tesorería, maquinaria,
  correcciones de nómina, auditorías y documentación.
- `codex/gestion-costos`: implementación consolidada de Gestión y Costos.
- `ticket/17-somed-medel-licencia-medica` y
  `ticket/18-bienestar-parada-rima`: cambios y evidencia PreviRed.
- Repositorio independiente `stepconsulting/step_harvest`, rama `main`:
  dependencias revisadas y actualizadas.
