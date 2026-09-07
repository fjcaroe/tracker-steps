# Steps Task — Handoff Fase 1

App móvil + consola de registro de labores publicada en `/task/`
(`desarrollo.stepsapp.cl/task/` y `demo.stepsapp.cl/task/`), calcada del sitio
de cosecha (`/cosecha/` = Steps Harvest).

## Arquitectura (idéntica a cosecha)

| Pieza | Cosecha (referencia) | Task |
|---|---|---|
| Backend | controlador Odoo `step_cosecha/controllers/harvest_api.py`, rutas `/api/harvest/*`. Sin servicio: nginx `location /` → Odoo (:8069 prod / :8080 demo / :8075 dev). | `step_task/controllers/task_api.py`, `/api/task/*`. |
| Front | PWA React/Vite estática, `base:/cosecha/`, `/var/www/cosecha/`. Repo `github.com/fjcaroe/step_harvest` (versión vieja; la deployada solo existe como `dist/`). | Repo `C:\Users\tito4\Documents\step_task` (→ `github.com/fjcaroe/step_task`), `base:/task/`, `/var/www/task/`. |
| Dominio | `step.cosecha.registry` + `step.cosecha.tarja.registry.line`. | `step.tarja` (OT) + `step.tarja.registry` (detalle), ambos de `step_hr` (Actividades). |

## Ubicaciones

- **Módulo Odoo:** este worktree — `C:\Users\tito4\Documents\Odoo-steps-task`,
  rama `codex/steps-task` (desde `origin/develop`). Carpeta `step_task/`.
- **Front:** `C:\Users\tito4\Documents\step_task`, repo git propio (rama `main`).

## Hecho en Fase 1

### `step_task/` (Odoo) — commit `a34e042`
- `_inherit step.tarja`: `mobile_status` (progress/closed/reviewed/sent),
  `mobile_uid`, `mobile_work_order`, `mobile_device`, `mobile_user`, `op_number`,
  `send_type` (parcial/total), `hora_inicio`, `hora_cierre`, `hr_ordinarias`,
  `hr_extras` (editables), `num_workers` (computed), helper `_step_task_week_op`.
- `_inherit step.tarja.registry`: `mobile_uid`, `read_method`, `event_datetime`,
  `relacion_trato`.
- `controllers/task_api.py`: `health`, `session`
  (`login_url=/web/login?redirect=/task/`), `ref/<resource>`
  (`workers`, `crews`, `farms`, `species`, `varieties`, `cost_centers`,
  `labors` [product.template is_labor], `contractors`), `bootstrap`, `recent`,
  `sync` (lote ≤100, idempotente por `client_uuid`, savepoint por registro).
- `data/ir_sequence.xml`: `step.task.mobile.ot`.
- `__manifest__` depende de `step_hr`, `hr_attendance`, `account`.

**Falta probar contra Odoo real** (`-i step_task` en base dev). Cheques hechos:
`ast.parse` OK, XML OK, campos referenciados existen en `origin/develop`.

### `step_task/` front (PWA) — commits `7cc58fa`, siguiente
- React 18 + Vite + react-router, `base:/task/`, PWA (`public/manifest.webmanifest`
  + `public/sw.js` scope `/task/`).
- Sistema de diseño `src/styles.css` = bundle CSS de `/cosecha/` renombrado
  `.harvest-app`→`.task-app` (grilla sidebar 248px, `.topbar`, `.page`,
  `.metric-grid`, `.panel`, `.dashboard-grid`, `.order-list`, `.worker-table`,
  `.report-grid`, `.settings-layout`, `.modal`, `.toast`, `.bottom-nav` móvil).
- `src/lib/api.ts`: cliente tipado de `/api/task/*`.
- `SessionContext`: sesión = cookie Odoo; online/offline.
- `AppShell` + nav (Inicio, Cuadrillas, Registrar OT, Órdenes, Reportes,
  Configuración) + bottom-nav móvil.
- Páginas: **Inicio** (resumen de jornada: métricas, OT activa, acciones),
  **Login** (redirige a `/web/login`), **Órdenes** (lista/filtra OT vía
  `/api/task/recent`), stubs de Cuadrillas / Registrar OT / Reportes /
  Configuración con su alcance por fase.
- `npm run build` (tsc + vite) OK. Verificado en `vite preview` escritorio y
  móvil 375px (sidebar → bottom-nav, cards apiladas).

## Fase 2 — captura móvil (PWA)  ✅  commit front `c24d292`

- `lib/db.ts` + `context/TaskStore.tsx`: estado local persistido en
  `localStorage` (maestros, cuadrillas, OT con líneas). Cola de sync = líneas
  con `synced=false`; idempotencia por `client_uuid` (= id de línea).
- `lib/uuid.ts`: uuid + `today()` + `isoWeekTag()`.
- `components/ScannerInput.tsx`: lectura por pistola (teclado-wedge, ráfaga +
  Enter) + Web NFC (`NDEFReader`), reserva a escritura manual.
- `components/SearchSelect.tsx`: selector con búsqueda sobre maestros.
- **Cuadrillas**: crear (propia/contratista, fundo, jefe, contratista), sumar
  por lectura o del maestro, enrolado rápido (nombre/RUT/NIP/sexo), marca de
  asistencia (`checkIn`) al sumar, salida anticipada por trabajador, jornada
  horas + toggle H. extra, cerrar cuadrilla, "repetir día anterior".
- **Registrar OT**: encabezado (cuadrilla, N° OP=`W<semana>`, N° OT auto, fecha,
  hora inicio, fundo, autorizador, especie, variedad, centro costos) → detalle
  por trabajador (labor + relación trato, cantidad, HO, HE; por lectura contra
  la cuadrilla de la OT, o de un desplegable) → cierre (`closed`) con HO/HE de
  OT editables y reabrir; "repetir tarja día anterior"; envío parcial (OT en
  proceso) y transmitir total (OT cerrada).
- **Órdenes**: lista local con estado de sync por línea + acción parcial/total +
  sección de OT de la consola (`/api/task/recent`); `AppShell` con botón
  Sincronizar y badge de pendientes.
- **Configuración**: Descargar maestros (`/api/task/bootstrap`), conteos por
  maestro, parámetros de jornada/lectura/latencia, id de equipo.
- `tsc -b && vite build` OK. Verificado en `vite preview`: crear cuadrilla,
  enrolado rápido con marca de hora, crear OT, persistencia en `localStorage`
  entre navegaciones, layout móvil.
- **Pendiente menor**: reintento con backoff explícito de la cola (hoy es
  reintento manual con el botón Sincronizar); el `sw.js` no registra en el
  sandbox del preview pero sí en HTTPS real.

## Fase 3 — consola Odoo  ✅  commit `8effe1c` · instalada en dev `LAB_TAREAS`

- `step.tarja`: `mobile_especie_id` / `mobile_variedad_id` (encabezado consola);
  `task_alert_count` (store) + `task_alert_html` computados con las 4
  validaciones del doc 1.1.3 (horas < jornada, sin horas, horas > jornada,
  producción < `can_std` / > `can_max` de la tarifa `pricelist_id`).
- Acciones: `action_task_review` (→ `reviewed`), `action_task_transmit`
  (consolida líneas por `employee_id + cost_id + labor_id`, vuelca asistencia
  entrada/salida a `hr.attendance`, → `sent`, fija `send_type`),
  `action_task_reset_mobile`.
- `get_task_dashboard_data(days)` para el tablero.
- `views/step_tarja_task_views.xml`: list (decoración por `mobile_status`), form
  (statusbar, botones Aprobar/Transmitir/Reabrir, encabezado, detalle
  `tarja_registry` editable, pestaña Alertas), search con filtros y agrupados,
  acciones **Estados OT** (`action_step_task_ot_states`) y **Crear OT**
  (`action_step_task_crear_ot`).
- Tablero OWL `step_task.dashboard` (`static/src/js|xml|scss`, tema verde, KPIs,
  flujo de estados, últimas OT, panel "qué requiere atención", reglas de scroll
  móvil) + `ir.actions.client` `action_step_task_dashboard`.
- `menu_views.xml`: menú raíz **Task** — Inicio/Panel · Registro OT (Estados OT,
  Cuadrillas, Crear OT) · Informes (vacío, Fase 4) · Maestros (Centros de Costo,
  Productos/Labores, Trabajadores, Contratistas, Cuadrillas) · Configuración
  (Fundo, Especie, Variedad). Reutiliza acciones de `step_hr`.
- **Validado en dev**: `-i step_task` en `LAB_TAREAS` instala sin error; el
  servicio `odoo18-dev.service` recargó el registro solo; `get_task_dashboard_data`
  y el compute de alertas corren sobre datos reales; `/api/task/health` y
  `/api/task/session` responden en `https://desarrollo.stepsapp.cl`.
- **Pendiente de verificación con usuario dev** (no tengo credenciales): render
  del tablero OWL en el navegador y `action_task_transmit` con una OT real
  (consolidación + asistencia). El módulo quedó copiado en
  `/opt/dev_odoo18/odoo_agriculture/step_task` (ruta final; NO instalado en demo
  ni prod).

## Pendiente

### Deuda técnica de las Fases 2-3 a resolver
- `action_task_transmit` deja el detalle en `step.tarja.registry` consolidado y
  fija `mobile_status='sent'`, pero **no** puebla `step.tarja.line` (la línea de
  costeo/sueldo que `onchange_salary_id` llena desde la cuadrilla y que
  `envio_nomina` usa). Falta decidir/implementar ese volcado para que la OT
  transmitida entre completa al flujo de nómina de Actividades.
- Cola de sync sin backoff automático (hoy botón manual "Sincronizar").
- Encabezado consola usa `mobile_especie_id`/`mobile_variedad_id` propios; no se
  reconcilian con `especie_id`/`grupo_variedad_id` que derivan de `pricelist_id`.
- Sin grupos de seguridad propios: el menú Task se gatilla en `base.group_user`.
- Verificación pendiente con usuario dev: render del tablero OWL y transmisión
  con datos reales.

### Fase 4 — informes (wizards XLSX, patrón `hr_entry_xls_wizard`)
1. **Data Steps Task** (Anexo 1.1.3.3): 1 fila por línea de OT transmitida.
2. **Horas diarias** (Anexo 1.1.3.1): matriz trabajador × día del mes + TOTAL;
   marcar días sin horas / con exceso.
3. **Rendimientos diarios** (Anexo 1.1.3.2): matriz trabajador × labor × UdM ×
   día + TOTAL.
4. **Análisis de rendimientos** (Anexo 1.1.3.4): centro costos × labor con
   hectáreas/plantas/hileras del maestro vs Σ OT y columna Diferencia.

### Fase 5 — despliegue
- Bloques nginx `# BEGIN STEPS TASK /task` en vhosts `desarrollo.stepsapp.cl` y
  `demo.stepsapp.cl` (patrón textual del bloque `/cosecha`: `= /task` 301,
  `= /task/manifest.webmanifest`, `= /task/sw.js` + `Service-Worker-Allowed`,
  `^~ /task/assets/`, `^~ /task/`). `/api/task/*` no necesita bloque.
- Runbook `docs/DESPLIEGUE_TASK.md` (calcar `DESPLIEGUE_COLACIONES.md`):
  clonar front en `/tmp`, `npm ci && npm run build`, `rsync dist/ → /var/www/task/`,
  copiar `step_task/` al `addons_path`, `-u step_task` en `LAB_TAREAS` (dev) y
  `STEPS_DEMO` (demo), `nginx -t && systemctl reload nginx`, verificar hash del JS.
- Desarrollo: base `LAB_TAREAS`, `/opt/dev_odoo18/odoo_agriculture`,
  `odoo18-dev.service`, `/etc/dev_odoo18.conf`. Demo: `STEPS_DEMO`,
  `/opt/demo_odoo18/odoo_agriculture`, `odoo18-demo.service`.
