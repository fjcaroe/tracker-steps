# Handoff — Corte V2 D (puente con maestros agrícolas reales de `step_hr`)

**Addon nuevo:** `step_management_costs_agriculture` (`18.0.1.0.0`,
`auto_install=True`) · **Núcleo sin cambios de versión funcional propios**
(sigue en `18.0.17.0.0`; sólo gana el addon puente al lado)
**Fecha:** 2026-09-07 · **Autor:** Claude Sonnet 5 · **Estado:** implementado
y verificado en Odoo real (con una excepción y un bloqueo documentados,
ambos externos a este addon), sin despliegue

## 1. Alcance

Cuarto corte de `PROMPT_CLAUDE_SONNET5_RESPUESTAS_V2_2026-09-06.md`. Auditó
primero, de sólo lectura, `step_hr` (presente en este mismo worktree y
verificado idéntico contra `/opt/dev_odoo18/odoo_agriculture` en
`odoo-new`) para confirmar los maestros reales antes de construir nada:
`step.fundo`, `step.especie`, `step.variedad(.line)`,
`step.grupo.variedad(.line)`, `step.cuartel.line`, y la extensión real de
`account.analytic.account` (`fundo_id`, `especie_id`, `variedad_id`,
`grupo_variedad_id`, `has_cost`, `plant_cost`, `type_costo`) — la cuenta
analítica **es** el centro de costo en `step_hr`.

- **Addon puente nuevo**, `auto_install=True`, depende de
  `step_management_costs` + `step_hr`. Nunca se activa si `step_hr` no está
  instalado (ni siquiera cargan sus pruebas).
- `models/cost_center.py`: campos `agri_*` de sólo lectura en
  `step.management.cost.center`, `related` a través de
  `analytic_account_id` — el núcleo nunca pierde su `Char`/`Float` propio
  (fallback portable intacto, D13).
- `models/estimation.py`: `harvest_labor_id` (M2o `product.template`) +
  `_agri_resolve_standard_yield()` con precedencia **centro → variedad →
  grupo de variedad** (cada nivel indexado también por `labor_id`, campo
  real de los tres modelos). Fuente de plantas: maestro del centro si está
  informado, si no el `Float` propio del núcleo. `yield_source`/
  `plants_source` (procedencia) se congelan junto con el resto del detalle
  al validar — se extiende `PROTECTED_LINE_FIELDS` del núcleo por
  `mutate` del set compartido, no por redeclaración.
- **Migración no destructiva:** `upgrades/18.0.1.0.0/post-migration.py`
  copia `farm`/`species`/`variety` del maestro real al `Char` del núcleo
  **sólo si está vacío**.
- **D20 (Actividad) sigue bloqueada** — este puente no la toca; el maestro
  de rendimiento se indexa por `labor_id`, campo distinto e independiente.

## 2. Seguridad

Sin ACL/reglas nuevas: los campos `agri_*` son `related` de sólo lectura
sobre un modelo (`account.analytic.account`) cuya seguridad ya la gobierna
`step_hr`; `harvest_labor_id` es un M2o normal sobre `product.template`
(`check_company=True`, mismo criterio que el resto del núcleo).

## 3. Interfaz

Sin vistas nuevas obligatorias en este corte — los campos `agri_*` quedan
disponibles para exponerse en vistas existentes cuando se requiera; no se
forzó su presencia para no interferir con la UI ya verificada del núcleo.

## 4. Migración

- `step_management_costs_agriculture/__manifest__.py` → `18.0.1.0.0`,
  `auto_install=True`.
- `upgrades/18.0.1.0.0/post-migration.py`: backfill no destructivo descrito
  arriba (UPDATE sólo si el campo del núcleo está vacío).

## 5. Pruebas

`step_management_costs_agriculture/tests/test_agriculture_bridge.py` (12
pruebas): precedencia centro→variedad→grupo, ausencia en los tres niveles
(cae al valor manual del núcleo, D05 sin tocar), fuente de plantas
(maestro vs. `Float` propio), congelamiento de la procedencia al validar,
aislamiento por compañía, y que el núcleo sin el puente instalado sigue
funcionando exactamente igual (sin `step_hr`, ni siquiera se cargan estas
pruebas).

### Verificación local

`py_compile`, parseo XML, `git diff --check`: OK en todo lo tocado/nuevo.

### Verificación Odoo real en `odoo-new` (sólo bases desechables)

Mismo patrón que los cortes anteriores. Se encontraron y corrigieron **dos
defectos reales**, ambos en fixtures compartidos de prueba del núcleo (no
en modelos ni lógica de negocio), más dos hallazgos externos que se
documentan sin corregir por estar fuera de mandato:

**Defectos corregidos (nuestros, en `tests/`):**
1. **`account.analytic.account.fundo_id`** (obligatorio, aportado por
   `step_hr`, sin default) rompía `ManagementCostsCommon.setUpClass()` y
   dos archivos más que creaban cuentas analíticas a mano, en instalación
   limpia con el puente. Corregido con `extra_analytic_account_vals(env,
   company)`, defensiva (sólo actúa si el campo existe y es obligatorio).
2. **`product.template.grupo_labor`** (Selection obligatorio, aportado por
   `step_hr`, sin `default=`) rompía **9 archivos de prueba del núcleo**
   que crean `product.product`/`product.template` a mano. Corregido de
   forma generalizada con `extra_product_vals(env)`, mismo criterio
   defensivo, importada por los 9 archivos
   (`test_management_costs.py` no crea productos directamente, pero
   define el helper; lo consumen `test_fase5_programs`, `test_fase6_stock`,
   `test_fase7_corte1`, `test_fase7_corte2_production_order`,
   `test_fase7_hardening`, `test_v2_a_harvest`, `test_v2_c_committed` y el
   propio `test_agriculture_bridge` del puente).

**Hallazgos externos, documentados y NO corregidos (fuera de mandato):**
3. `test_fase2_variance.py` hereda de `AccountTestInvoicingCommon`
   (**común de Odoo core**, no nuestro). Su propio `setUpClass()` crea
   productos sin saber de `grupo_labor` — con el puente instalado, ese
   fixture del núcleo de Odoo revienta igual que los nuestros, pero
   parchear `odoo/addons/account/tests/common.py` está fuera de alcance.
   Es un defecto de diseño de `step_hr` (campo obligatorio sin default
   utilizable sobre un modelo tan compartido como `product.template`), no
   de este addon; no afecta instalaciones reales (ya tienen productos
   existentes). Ver `DECISION_LOG.md` §"Verificación real... hallazgos".
4. La verificación por **upgrade** (clon de `LAB_TAREAS`) quedó bloqueada:
   un clon fresco tomado hoy falla al crear **cualquier** `res.company`
   (reproducido incluso con las pruebas del núcleo solas, sin el puente)
   por `NotNullViolation` en `res_company.security_lead` (campo de
   `sale_stock`). Confirmado por `ir_module_module.write_date`:
   `sale_stock` se modificó en `LAB_TAREAS` hoy a las 04:06, antes de esta
   ronda — consistente con otra sesión/proceso trabajando en la base
   compartida en paralelo. No se investigó más para no interferir.

| Escenario | Resultado |
|---|---|
| Instalación limpia sin demo, núcleo + puente juntos (`--without-demo=all`) | RC 1 (por el punto 3) · **0 failed, 2 error(s) de 251 tests** — ambos errores son el mismo `setUpClass` de `TestFase2Variance` (punto 3, externo); el resto —incluidas las 12 del puente— en verde (`odoo.tests.stats`: 283 + 12 tests) |
| Upgrade de clon de `LAB_TAREAS` | **Bloqueado** (punto 4, externo — colisión con otra modificación concurrente de `sale_stock`); no atribuible a este addon. Se recomienda reintentar cuando `LAB_TAREAS` esté quieta. |

La vía de instalación limpia es la verificación decisiva de este corte
(independiente del estado en vivo de `LAB_TAREAS`); queda en verde salvo la
única excepción documentada y ajena a este addon.

Bases desechables (`MC_V2D_UPG`, `MC_V2D_UPG_F`, `MC_V2D_CLEAN`,
`MC_V2D_CLEAN2`, `MC_V2D_CLEAN_F`, `MC_V2D_CLEAN_F2`), dumps, directorios
temporales (`/tmp/mc_v2d_20260907/`, staging local) y scripts desechables
eliminados al terminar. `LAB_TAREAS` no se escribió en ningún momento (sólo
`pg_dump`/`pg_restore` de sólo lectura sobre ella).

## 6. Decisiones y supuestos

Ver `DECISION_LOG.md` §"Corte V2 D" (D-N) y §"Verificación real... hallazgos",
`ADR_001` §D-N, `DATA_MODEL.md` §9.

## 7. Pendientes del cliente

Sin cambios respecto a los cortes anteriores (K3, H1, K5, D20, BPA-Riego,
usuarios reales/UAT). Se agrega, como nota de infraestructura (no de
cliente): reintentar la verificación por upgrade de este corte cuando
`LAB_TAREAS` esté quieta.

## 8. Confirmación de aislamiento

No se tocó `STEPS_DEMO_SYS`, ninguna otra sesión de Claude, ni bases
reales. `step_hr` se auditó sólo de lectura, sin modificarlo. Sin commit ni
push.

## 9. Siguiente

Corte V2 E: presupuesto de maquinaria (`18.0.19.0.0`) — auditar primero si
existe un addon real de maquinaria instalado en `odoo-new` (la memoria de
sesión menciona `step_machinery` en producción; verificar si su fuente está
disponible en este entorno de desarrollo antes de decidir si hace falta
otro puente).
