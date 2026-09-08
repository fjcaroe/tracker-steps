# Despliegue Gestión y Costos — 8 de septiembre de 2026

La versión consolidada se guardó en Git (`codex/gestion-costos`, commit
`d08c56c`) y se promovió siguiendo el orden del runbook: Desarrollo primero y
Demo después. Demo-SyS no fue intervenido para este producto.

## Versiones instaladas

| Ambiente | Núcleo | Puente agrícola | Puente maquinaria |
|---|---:|---:|---:|
| Desarrollo (`LAB_TAREAS`) | 18.0.20.0.0 | 18.0.1.0.0 | 18.0.1.0.0 |
| Demo (`STEPS_DEMO`) | 18.0.20.0.0 | 18.0.1.0.0 | 18.0.1.0.0 |

Los addons puente se instalaron durante esta promoción. Ambos servicios
quedaron activos y `desarrollo.stepsapp.cl` y `demo.stepsapp.cl` respondieron
HTTP 200.

## Respaldo

`/opt/steps_backups/gestion_costos_18_0_20_20260908-202854/`

Contiene un dump previo de cada base, respaldos de los módulos existentes y
los logs de actualización.

El puente BPA identificado en el Corte V2 G sigue fuera del alcance: requiere
las decisiones funcionales documentadas en `SIGUIENTES_PASOS_2026-09-07.md`.
