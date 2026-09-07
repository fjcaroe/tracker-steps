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

## Pendiente

### Fase 2 — captura móvil
- Descarga de maestros (`/api/task/bootstrap` → IndexedDB/localStorage).
- Cuadrillas: armar, asistencia por manual/barcode/QR/NFC, enrolado rápido
  (nombre/RUT/NIP/sexo), hora salida + salida anticipada, "repetir cuadrilla
  día anterior".
- OT: encabezado (cuadrilla, tipo, N° OP, N° OT, fecha, hora inicio, fundo,
  usuario, autorizador, especie, variedad, centro costos) → detalle (trabajador,
  labor + relación trato, cantidad, HO, HE; alta por digitación o lectura) →
  cierre (hora cierre, revisión).
- Cola offline con reintento/backoff; `sync` parcial (OT en proceso) y total.
- Componente lector barcode/QR (teclado-wedge) + Web NFC.

### Fase 3 — consola Odoo (`step_task`)
- Menús: Task / (Inicio Panel) / (Registro OT: Estados OT, Cuadrillas, Crear OT)
  / (Informes) / (Maestros: Centro Costos, Productos-Labores, Trabajadores,
  Contratistas, Cuadrillas) / (Configuración: Fundo, Especie, Variedad,
  Cuadrillas, parámetros).
- Tablero OWL `task_dashboard` (calcar `cosecha_dashboard.js/xml/scss`) con
  reglas de scroll móvil (`height:100%; min-height:0; overflow-y:auto;
  touch-action:pan-y`).
- Acciones: Estados OT → click detalle → Aprobar (`reviewed`) → Transmitir
  (`sent`) que vuelca a Actividades:
  - `tarja_type='propio'` → Actividades / Personal propio / Registro Tareas.
  - `tarja_type='contratista'` → Actividades / Contratistas / Registro Tareas
    Contratistas.
  - Sumar líneas por trabajador + centro de costo + labor en una sola.
- Glue `hr.attendance`: alta de cuadrilla = entrada; cierre OT = salida; cargar
  HO/HE. Configurar tipo de entrada en Asistencia.
- Alertas diarias: trabajador con < jornada u 0 horas; con > jornada de HO;
  producción (Σ cantidad/labor) bajo `pricelist.item.can_std` o sobre `can_max`.
- Decidir: `step.tarja` no tiene Especie/Variedad/Centro de costos a nivel
  cabecera (los deriva de `pricelist_id`). Añadir campos propios o resolver vía
  tarifa.
- `_rec` de líneas: el detalle móvil hoy va a `step.tarja.registry`; validar si
  la transmisión a nómina/costeo debe además poblar `step.tarja.line`
  (`onchange_salary_id` lo llena desde la cuadrilla y `envio_nomina` lo usa).

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
