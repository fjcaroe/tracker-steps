# step_task — Steps Task (app móvil + consola de labores)

Capa móvil + consola para el registro de labores de campo, análoga a
`step_cosecha` (Steps Harvest). Se apoya en el módulo de Actividades (`step_hr`):
la Orden de Trabajo es `step.tarja` y el detalle por trabajador es
`step.tarja.registry`.

## Fase 1 (este corte)

- **Modelos** (`_inherit`):
  - `step.tarja`: `mobile_status` (progress/closed/reviewed/sent), `mobile_uid`,
    `mobile_work_order`, `mobile_device`, `mobile_user`, `op_number`,
    `send_type` (parcial/total), `hora_inicio`, `hora_cierre`,
    `hr_ordinarias`, `hr_extras` (editables), `num_workers` (computed).
  - `step.tarja.registry`: `mobile_uid`, `read_method`, `event_datetime`,
    `relacion_trato`.
- **Controlador** `/api/task/*` (same-origin, sesión Odoo):
  `health`, `session` (`login_url=/web/login?redirect=/task/`),
  `ref/<resource>` (`workers`, `crews`, `farms`, `species`, `varieties`,
  `cost_centers`, `labors`, `contractors`), `bootstrap`, `recent`, `sync`
  (lote idempotente por `client_uuid`, savepoint por registro).
- **Secuencia** `step.task.mobile.ot`.

## Pendiente (fases siguientes)

- Menús de consola (Task / Registro OT / Informes / Maestros / Configuración).
- Tablero OWL `task_dashboard` (con reglas de scroll móvil).
- Aprobación → transmisión a Actividades (Registro Tareas / Registro Tareas
  Contratistas), sumando líneas por trabajador+centro+labor.
- Integración con `hr.attendance` (alta de cuadrilla = entrada, cierre OT = salida).
- Alertas: horas bajo/sobre jornada, producción bajo `can_std` / sobre `can_max`
  de la tarifa.
- 4 wizards XLSX: Data Steps Task, Horas diarias, Rendimientos diarios,
  Análisis de rendimientos.
- Mapeo definitivo de Especie/Variedad/Centro de costos a nivel de cabecera
  (hoy `step.tarja` los deriva de la tarifa `pricelist_id`).

## Frontend

PWA React/Vite en el repo `step_task` (hermano de `step_harvest`), `base:/task/`,
publicada en `/var/www/task/`.
