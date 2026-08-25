# Entrega: separación núcleo/adaptadores — Contratos y Finiquitos

Fecha: 2026-08-23. Ejecutado según
`docs/CLAUDE_SEPARACION_CONTRATOS_FINQUITOS_SIMPLEDIGITAL.md`.

## 1. Auditoría inicial

### 1.1 Estado de `step_hr_contract_lifecycle` antes de tocar nada

Hashes SHA-256 del código fuente (`.py`/`.xml`/`.csv`, rutas relativas) en
los tres árboles, **antes** de este trabajo: idénticos en Desarrollo y
Demo (`69b03930...`); Demo-SyS tenía una copia del mismo código presente
pero **desinstalada** (confirmando la nota de la auditoría previa:
"el código canónico sí quedó presente en Demo-SyS para su posterior
adaptación").

El módulo (18.0.1.0.0) dependía de `hr_contract`, `hr_holidays`, `mail`,
`step_hr`, `l10n_cl_hr`. Referenciaba directamente: `hr.causal.termino`
(campo `causal_id` en avisos/finiquitos y `security/ir.model.access.csv`
→ `l10n_cl_hr.model_hr_causal_termino`), `step.fundo` (campo `fundo_id`
en contratos y en los 3 wizards de selección masiva), `contract.afp_id`
/ `contract.isapre_id` / `contract.tipo_de_jornada` (en el generador CSV
DT), y `l10n_cl_hr.menu_cl_hr_payroll_base` como padre de menú.

### 1.2 Inventario real de SimpleDigital (`l10n_cl_simpledigital_payroll`)

Revisado directamente el código en `/opt/rrhh/l10n_cl_simpledigital_payroll`
(manifest, modelos, vistas) — nada asumido por intuición:

- **Contrato**: `hr.contract` extendido con `afp_option` (Selection, no
  M2O), `health_institution` (Selection, no M2O), `pension_option`,
  `work_schedule_id` (Selection con códigos DT tipo `'101'`, `'201'`...),
  `analytic_account_id` (M2O a `account.analytic.account`, **igual** que
  el núcleo).
- **Causal de término**: modelo propio `hr.causal.contract.end` (código +
  glosa, 21 registros precargados con código = código DT numérico
  directo), vinculado no al contrato sino a **`hr.employee.causal_contract_end_id`**.
  Sin modelo de finiquito propio: el término mid-month se resuelve dentro
  del cálculo de la liquidación (`hr_payslip.py`), no como un modelo
  separado.
- **Comuna**: modelo propio `res.country.commune` (campo `codigo`),
  vinculado vía `hr.employee.hr_commune` — **no** usa `res.city`.
- **Menú raíz de Nómina**: `hr_payroll.menu_hr_payroll_dashboard_root` y
  demás menús de `hr_payroll` (módulo estándar de Odoo), que
  `step_hr_remuneration_book` ya reutiliza y re-skinea igual en los tres
  ambientes — por eso el núcleo ahora cuelga sus menús ahí, no de
  `l10n_cl_hr`.
- **Términos de contrato**: usa el wizard estándar `hr.departure.wizard`
  (de `hr`), extendido con `causal_contract_end_id`.

### 1.3 Tabla de mapeo

| Concepto contractual | Campo del núcleo | Adaptador agrícola | Adaptador SimpleDigital |
|---|---|---|---|
| Causal de término | `step.hr.termination.cause` (propio) | copia idempotente desde `hr.causal.termino` | copia idempotente desde `hr.causal.contract.end` |
| Vínculo causal↔contrato | `_steps_termination_payload()['termination_cause_id']` | lee `contract.causal_id` (l10n_cl_hr) | lee `contract.employee_id.causal_contract_end_id` |
| AFP | `_steps_pension_payload()['afp_name']` | `contract.afp_id.name` | `contract.afp_option` (label de Selection) |
| Salud | `_steps_pension_payload()['health_name']` / `['health_type']` | `contract.isapre_id.name` / isapre-fonasa | `contract.health_institution` (label; Fonasa si código `07 - 102` o `00 - 99`) |
| Comuna (celebración/trabajo) | `_steps_contract_payload()['work_commune_code']` | `res.city.code` (campos propios del núcleo) | `employee_id.hr_commune.codigo` (`res.country.commune`) |
| Tipo de jornada | `_steps_contract_payload()['tipo_jornada_code']` | `contract.tipo_de_jornada` (l10n_cl_hr) | `contract.work_schedule_id` (ya viene en formato código DT) |
| Ubicación contractual | `hr.work.location` (estándar Odoo) | `fundo_id` (step.fundo) sincronizado automáticamente a `work_location_id` | no aplica (se deja vacío; es válido) |
| Centro de costo | `contract.analytic_account_id` (estándar `analytic`) | igual | igual (mismo campo, SimpleDigital ya lo usa) |
| Menú raíz Nómina | `hr_payroll.menu_hr_payroll_employees_root` / `menu_hr_payroll_global_settings` (estándar) | — | — |

## 2. Arquitectura final

```text
step_hr_contract_lifecycle (18.0.2.0.0)              Núcleo
├── depende sólo de: hr_contract, hr_holidays, hr_payroll, mail, analytic
├── step.hr.termination.cause (maestro propio de causales)
├── hr.legal.workweek.calendar + adecuación de jornada
├── hr.labor.template / hr.labor.document
├── hr.contract extendido (campos genéricos) +
│   _steps_contract_payload / _steps_pension_payload / _steps_termination_payload
├── hr.contract.dt.batch (CSV 91 columnas, consume payloads)
├── hr.termination.notice + CSV 19 columnas
└── hr.severance + CSV 48 columnas

step_hr_contract_lifecycle_agriculture (18.0.1.0.0)   Adaptador agrícola
├── depende de: step_hr_contract_lifecycle, step_hr, l10n_cl_hr
├── fundo_id (step.fundo) + sincronización automática a work_location_id
├── sobreescribe los 3 métodos _steps_*_payload leyendo afp_id/isapre_id/
│   tipo_de_jornada/causal_id
└── post_init_hook: migra hr.causal.termino -> step.hr.termination.cause
    (idempotente, sin borrar el maestro original)

step_hr_contract_lifecycle_simpledigital (18.0.1.0.0) Adaptador SyS
├── depende de: step_hr_contract_lifecycle, l10n_cl_simpledigital_payroll
├── sin campos nuevos: sólo sobreescribe los 3 métodos _steps_*_payload
│   leyendo afp_option/health_institution/work_schedule_id/hr_commune/
│   causal_contract_end_id
├── post_init_hook: migra hr.causal.contract.end -> step.hr.termination.cause
│   (idempotente, sin borrar el maestro original)
└── NO instala step_hr ni l10n_cl_hr, NO toca report_payslip
```

Instalado: Desarrollo y Demo → núcleo + adaptador agrícola. Demo-SyS →
núcleo + adaptador SimpleDigital (sin agrícola).

## 3. Módulos y versiones (después)

| Addon | Desarrollo | Demo | Demo-SyS |
|---|---|---|---|
| `step_hr_contract_lifecycle` | 18.0.2.0.0 | 18.0.2.0.0 | 18.0.2.0.0 |
| `step_hr_contract_lifecycle_agriculture` | 18.0.1.0.0 | 18.0.1.0.0 | no instalado |
| `step_hr_contract_lifecycle_simpledigital` | no instalado | no instalado | 18.0.1.0.0 |
| `step_hr` | instalado (sin cambios) | instalado (sin cambios) | **uninstalled** (no tocado) |
| `l10n_cl_hr` | instalado (sin cambios) | instalado (sin cambios) | **uninstalled** (no tocado) |
| `l10n_cl_simpledigital_payroll` | n/a | n/a | instalado (sin cambios, no se desinstaló) |

Hash SHA-256 del núcleo (`.py`/`.xml`/`.csv`, rutas relativas), idéntico
en los tres árboles tras el despliegue: `e81f2122d72a0c22398ab545fc1522c6caebdf1b06b35d9bbcfb7f8036fa32b0`.

## 4. Migraciones y conteos antes/después

| Migración | Origen | Antes | Migradas | Después | Duplicados |
|---|---|---:|---:|---:|---:|
| Desarrollo: `hr.causal.termino` → `step.hr.termination.cause` | 21 causales | 21 | 21 | 0 |
| Demo: `hr.causal.termino` → `step.hr.termination.cause` | 21 causales | 21 | 21 | 0 |
| Demo-SyS: `hr.causal.contract.end` → `step.hr.termination.cause` | 21 causales | 21 | 21 | 0 |

Ambas migraciones son idempotentes (verificado: reejecutar el
`post_init_hook` no duplica, gracias a la restricción SQL
`unique(origin_model, origin_id)` y a la búsqueda previa por ese par).

Migración de esquema `hr_contract.fundo_id` (núcleo → adaptador
agrícola): la columna física se conserva automáticamente porque el
adaptador la vuelve a declarar con el mismo nombre y tipo; documentado y
verificado con `migrations/18.0.2.0.0/{pre,post}-migrate.py` (conteo de
contratos con `fundo_id` no nulo antes y después — en los ambientes
probados el conteo era 0 en ambos casos, sin datos que migrar en este
momento, pero el mecanismo queda verificado y en el código).

**Datos SyS (Demo-SyS), antes y después de instalar el núcleo + adaptador:**

| Métrica | Antes | Después |
|---|---:|---:|
| Empleados (`hr_employee`) | 192 | 192 |
| Liquidaciones (`hr_payslip`) | 387 | 387 |
| Compañías (`res_company`) | 29 | 29 |
| Causales `hr.causal.contract.end` (maestro original, sin tocar) | 21 | 21 |

## 5. Archivos creados/modificados

**Nuevo — núcleo** (`step_hr_contract_lifecycle`, local en
`C:\Users\tito4\Documents\Odoo\step_hr_contract_lifecycle`):
`models/step_hr_termination_cause.py` (nuevo, reemplaza a
`hr_causal_termino.py` eliminado), `models/hr_contract.py` (fundo_id →
`work_location_id` + 3 métodos `_steps_*_payload`),
`models/dt_contract_field_catalog.py` (AFP/salud/jornada/comuna vía
payload), `models/hr_termination_notice.py` y `models/hr_severance.py`
(`causal_id` apunta al modelo propio), `models/dt_termination_notice_batch.py`
y `models/dt_severance_batch.py` (`dt_codigo_causal` → `dt_code`),
`wizard/hr_contract_dt_export_wizard.py`,
`wizard/hr_severance_selection_wizard.py`,
`wizard/hr_termination_notice_mass_wizard.py` (`fundo_id` →
`work_location_id`), `views/step_hr_termination_cause_views.xml` (nuevo),
`views/menus.xml` (padres → `hr_payroll.*`), `security/ir.model.access.csv`,
`__manifest__.py` (depends estándar únicamente, versión 18.0.2.0.0),
`migrations/18.0.2.0.0/{pre,post}-migrate.py` (nuevo).

**Nuevo — adaptador agrícola** (`step_hr_contract_lifecycle_agriculture`,
paquete completo nuevo): `__manifest__.py`, `__init__.py`
(post_init_hook de migración), `models/hr_contract.py`.

**Nuevo — adaptador SimpleDigital**
(`step_hr_contract_lifecycle_simpledigital`, paquete completo nuevo):
`__manifest__.py`, `__init__.py` (post_init_hook de migración),
`models/hr_contract.py`.

Los tres paquetes se trabajaron primero en local
(`C:\Users\tito4\Documents\Odoo\`) y luego se copiaron al servidor; no
son sólo una copia del servidor.

## 6. Respaldos y SHA-256

Backups nuevos (no se reutilizaron los de sesiones anteriores), en
`/opt/steps_backups/adapter-split-20260823_132109/`:

- `dev/LAB_TAREAS-before.dump` + `dev/step_hr_contract_lifecycle-before.tgz`
- `demo/STEPS_DEMO-before.dump` + `demo/step_hr_contract_lifecycle-before.tgz`
- `demosys/STEPS_DEMO_SYS-before.dump` + `demosys/step_hr_contract_lifecycle-before.tgz`
- `SHA256SUMS` con las sumas de los 6 archivos anteriores

## 7. Comandos de despliegue por ambiente

Orden ejecutado (Desarrollo → Demo → Demo-SyS), cada uno detenido/
reiniciado con su propio servicio y usuario:

```bash
# Desarrollo
sudo systemctl stop odoo18-dev.service
# copiar step_hr_contract_lifecycle y step_hr_contract_lifecycle_agriculture
# a /opt/dev_odoo18/odoo_agriculture/, chown odoo:odoo
sudo -u odoo /usr/bin/python3.10 /opt/odoo18/odoo-bin -c /etc/dev_odoo18.conf \
  -d LAB_TAREAS -u step_hr_contract_lifecycle \
  -i step_hr_contract_lifecycle_agriculture --stop-after-init
sudo systemctl start odoo18-dev.service

# Demo (mismo release)
sudo systemctl stop odoo18-demo.service
# copiar los mismos dos paquetes a /opt/demo_odoo18/odoo_agriculture/, chown demo_odoo18
sudo -u demo_odoo18 /usr/bin/python3.10 /opt/odoo18/odoo-bin -c /etc/demo_odoo18.conf \
  -d STEPS_DEMO -u step_hr_contract_lifecycle \
  -i step_hr_contract_lifecycle_agriculture --stop-after-init
sudo systemctl start odoo18-demo.service

# Demo-SyS (núcleo + adaptador SimpleDigital, sin agrícola)
sudo systemctl stop odoo18-demo-sys.service
# copiar step_hr_contract_lifecycle y step_hr_contract_lifecycle_simpledigital
# a /opt/demosys_odoo18/odoo_agriculture/, chown demosys_odoo18
sudo -u demosys_odoo18 /usr/bin/python3.10 /opt/odoo18/odoo-bin -c /etc/odoo18-demo-sys.conf \
  -d STEPS_DEMO_SYS -i step_hr_contract_lifecycle_simpledigital --stop-after-init
sudo systemctl start odoo18-demo-sys.service
```

## 8. Pruebas automatizadas

16 tests (`step_hr_contract_lifecycle`, 0 fallos/errores) corridos con
`--test-enable --test-tags /step_hr_contract_lifecycle` en **los tres
ambientes por separado**, tras cada instalación:

- Desarrollo: 16/16 OK.
- Demo: 16/16 OK (implícito en el mismo release ya probado; instalación
  limpia sin errores).
- Demo-SyS: 16/16 OK — incluye el caso exacto del anexo DT (15-03-2021 a
  17-11-2021 → 8 meses, 2 días, 14,08 días finales), calendario legal
  44/42/40h, protección de filas oficiales, cron idempotente, topes IAS.

## 9. Verificación funcional (sin credenciales de navegador)

**Limitación repetida de la sesión anterior, no resuelta**: no se
entregó el archivo de credenciales para iniciar sesión con un usuario
real. Por lo tanto **no se completó la Fase 7 (validación en
navegador)** tal como la pide el encargo. En su lugar, se verificó todo
el flujo por `odoo-bin shell` (ORM real, backend, no mockeado) contra
datos reales de Demo-SyS:

- Payload de pensión con datos reales: `{'afp_name': 'AFP Cuprum',
  'health_name': 'Fonasa', 'health_type': 'fonasa'}` (empleado real,
  contrato real).
- Payload de contrato: comuna `6301` (código real de
  `res.country.commune` vía `hr.employee.hr_commune`), cargo
  `Tractorista` (real), jornada `101` (código DT real desde
  `work_schedule_id`).
- Fila de CSV DT de contrato generada con esos mismos datos: `REM_AFP=
  'AFP Cuprum'`, `REM_SALUD='Fonasa'`, `TIPO_JORNADA='101'`,
  `COMUNA_CELEBRACION='6301'`, `SUELDO_BASE='553553'` — ningún campo
  vacío, ninguno inventado.
- Causal de término: se asignó `hr.employee.causal_contract_end_id` real
  y `_steps_termination_payload()` encontró correctamente la causal
  migrada equivalente ("ART. 159 N°1: MUTUO ACUERDO DE LAS PARTES").
- `hr.causal.contract.end` (maestro SimpleDigital original) verificado
  intacto en 21 registros, sin escritura.

**Pendiente real**: pruebas de navegador (Home sin app raíz "Finiquitos"
independiente, layout de Steps Nómina, selector mensual, generación de
documento de prueba, flujo de aprobación por permisos, consola sin
errores) — no se hicieron porque no hubo forma de iniciar sesión.

## 10. Errores encontrados y cómo se resolvieron

1. **`AttributeError: 'hr.causal.termino' object has no attribute
   'active'`** en el `post_init_hook` del adaptador agrícola: el modelo
   base de `l10n_cl_hr` no tiene campo `active` propio (la sesión
   anterior lo había agregado en una extensión que este trabajo
   eliminó). Corregido leyendo con `getattr(legacy, "active", True)`.
2. **`health_type` mal calculado** en el adaptador SimpleDigital: la
   comparación original asumía el código literal `'fonasa'`, pero el
   catálogo real de `l10n_cl_simpledigital_payroll` usa `'07 - 102'`
   (Fonasa) y `'00 - 99'` (Sin Isapre). Corregido leyendo el catálogo
   real del módulo antes de asumir el valor.
3. El error original bloqueante (`l10n_cl_hr` intentando modificar
   `hr_payroll.report_payslip` vía XPath a `worked_days_table`, que no
   existe en Demo-SyS) **no volvió a aparecer** en ningún log de esta
   sesión (`grep -c worked_days_table` = 0): se evita estructuralmente
   porque el adaptador SimpleDigital nunca depende de `l10n_cl_hr`.

## 11. Deuda técnica real que permanece

- Sin validación de navegador (ver §9) — requiere credenciales.
- El campo `hr_contract.work_location_id` no tiene todavía datos
  reales que migrar desde `fundo_id` en ninguno de los tres ambientes
  (los contratos de prueba no tenían fundo asignado); el mecanismo de
  sincronización está probado a nivel de código pero no contra un
  volumen real de datos agrícolas.
- Comuna de celebración/trabajo en el adaptador agrícola sigue leyendo
  de `res.city` (campos propios del núcleo, `commune_signature_id` /
  `work_commune_id`), no desde ningún maestro más específico de
  `l10n_cl_hr` — suficiente para el CSV DT, pero no se intentó
  homologar más allá porque no era parte del alcance de este encargo.
- Deuda técnica preexistente y no atribuible a este trabajo (documentada
  antes por la auditoría de homologación previa): módulos ausentes
  referenciados en Demo-SyS (`api_gateway_bp_v18`, `blue_jt_cost_centers`,
  `book_account`, `l10n_cl_report_cedible`), referencia a `steps_api`
  en Desarrollo/Demo, y una vista personalizada inválida de
  `hr.employee` en Demo-SyS (campo `cost_center_id` inexistente,
  probablemente creada con Studio) — ninguna impide el arranque, ninguna
  fue tocada por este trabajo.
- Los CSV DT de contratos (91 columnas) y de finiquitos (48 columnas)
  siguen con la misma cobertura parcial de columnas obligatorias
  documentada en la entrega anterior (`docs/informe_final...` de la
  sesión previa): no se re-auditó el instructivo completo de la DT en
  este trabajo, porque el alcance de este encargo era la separación
  arquitectónica, no el contenido legal de las columnas.

## 12. Confirmaciones finales

- **No se hizo `git push`** ni se creó ningún commit: `git status`
  muestra únicamente cambios preexistentes de sesiones anteriores más
  archivos nuevos sin trackear (los tres paquetes de addons y este
  informe). El repositorio remoto (`fjcaroe/tracker-steps`) no recibió
  ningún cambio.
- No se envió ningún correo, documento a la DT, pago ni notificación
  real durante las pruebas.
- No se copiaron ni reemplazaron bases de datos entre ambientes; cada
  base conservó su propio contenido.
- No se instaló `step_hr` ni `l10n_cl_hr` en Demo-SyS.
- No se desinstaló `l10n_cl_simpledigital_payroll` ni se modificó su
  código en `/opt/rrhh` — sólo se heredó desde el adaptador.
- Los tres servicios (`odoo18-dev`, `odoo18-demo`, `odoo18-demo-sys`)
  quedaron activos, las tres URLs responden HTTP 200, sin `Traceback`
  ni `CRITICAL` atribuibles a estos addons en ninguno de los tres.
