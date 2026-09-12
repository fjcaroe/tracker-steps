# ADR-001 — Arquitectura y contabilidad de Steps Gestión y Costos

**Estado:** Propuesto (Fase 0). Requiere validación de Codex y del dueño
funcional antes de Fase 2.
**Fecha:** 2026-09-02
**Contexto:** primera vertical “Presupuesto agrícola aprobado → gasto real
contable → desviación auditable” sobre el addon existente
`step_management_costs 18.0.1.1.0`.

Este ADR fija decisiones de arquitectura para el **primer corte de Fase 1** y
el rumbo de Fase 2. Se apoya en el patrón ya validado en Tesorería
(`docs/TESORERIA_RELEASE_2026-08-29.md`): núcleo portable + puentes
`auto_install`, seguridad por grupos encadenados, `ir.rule` global
multiempresa, migración idempotente del prototipo, pruebas en bases
desechables.

---

## D-A. Preservación del addon y de sus datos

**Decisión.** Se evoluciona `step_management_costs` in situ. No se crea un
segundo módulo con el mismo propósito. No se renombran modelos, tablas ni XML
IDs existentes. No se borran campos en esta versión.

**Consecuencias.**

- Modelos que se conservan sin cambio de `_name` ni de tabla:
  `step.management.cost.center`, `step.management.budget.group`,
  `step.management.exchange.rate`, `step.management.budget.template(.line)`,
  `step.management.operational.budget`, `step.management.budget.center`,
  `step.management.budget.line`, `step.management.budget.month`,
  `step.management.plan(.line)`, `step.management.historical.cost`.
- Secuencias conservadas: `seq_operational_budget` (`PPO/%(year)s/…`),
  `seq_management_plan` (`PLAN/%(year)s/…`).
- Los campos legado que queden sustituidos (p. ej. las 12/24 columnas de mes
  cuando se normalicen a líneas, en Fase 2) se marcarán `readonly` o
  `compute` durante una ventana de compatibilidad; **no se eliminan** en
  `18.0.2.0.0`.
- Cualquier estructura nueva se añade; los `state` existentes se amplían con
  valores nuevos (`superseded`), nunca se reetiquetan los actuales.

**Descartado.** Reescribir el addon o migrar a un `step_costs` nuevo: produce
menús y maestros duplicados y rompe los folios `PPO/…` ya emitidos.

---

## D-B. Contabilidad analítica como fuente única del gasto real

**Decisión.** El valor monetario del “realizado” proviene **exclusivamente de
`account.move.line` de asientos publicados** (`parent_state = 'posted'`),
imputado por **distribución analítica** (`analytic_distribution` sobre la
cuenta analítica del centro de costo, y planes adicionales para
temporada/actividad cuando existan). El módulo agrícola **no** crea un segundo
libro: expone un **servicio de lectura conciliable** (`analytic_actuals`,
Fase 2) y, en V1, sólo el **contrato** y el mapeo de los 25 campos.

**Consecuencias.**

- Producto, cantidad, UdM, OP/OT y demás atributos no contables se
  **enriquecen desde el documento origen** mediante contratos explícitos por
  origen (actividades, maquinaria, inventario, movilización, colación,
  cosecha, fletes), nunca recalculando el monto.
- Reversas, notas de crédito y cancelaciones se reflejan porque se lee el
  apunte con su signo real; al despublicar un asiento desaparece de la
  lectura sin proceso adicional.
- Los costos operacionales aún no contabilizados, si se requieren, son una
  **métrica separada** y jamás se suman al realizado contabilizado.
- La cuenta analítica del centro es el pivote (ver D-F).

**En V1 se entrega:** `DATA_MODEL.md` §mapeo de 25 campos + este ADR. **No** se
implementa el servicio ni una tabla `management.actual`.

**Descartado.** Copiar el asiento analítico a una tabla propia y mantenerla
sincronizada por hooks (lo que sugiere literalmente `1.6.10 Gestión.docx`):
duplica el libro, se desincroniza al despublicar y obliga a reconciliar dos
verdades.

---

## D-C. Histórico sólo para externos / ajustes

**Decisión.** `step.management.historical.cost` queda **reservado para gasto
real anterior a la puesta en marcha del ERP y para ajustes manuales
justificados**. No es la vía para el gasto real corriente (que sale de
analítica).

**Consecuencias.**

- Se añade procedencia obligatoria: `origin` (`external` / `adjustment`),
  `source_reference` (texto), `source_document` (adjunto), y — cuando el
  registro está confirmado — bloqueo de edición.
- El inventario de los `historical.cost` actuales se clasifica en el upgrade:
  los que no puedan clasificarse quedan marcados `origin = 'unreviewed'` y se
  **excluyen** de los comparativos hasta que el dueño los resuelva. No se
  borra ninguno.
- Los comparativos suman `analítica (posted) + historical.cost(external/
  adjustment, revisado)`, nunca dos veces el mismo hecho.

**Descartado.** Migrar los `historical.cost` a la nueva lectura analítica:
son de origen externo, no tienen asiento.

---

## D-D. Contrato / adaptador para presupuesto (propio o `account_budget`)

**Decisión.** El presupuesto propio (`operational.budget`) sigue siendo la
implementación por defecto, **detrás de una interfaz** `budget_adapter`
(Fase 2). Antes de duplicar “comprometido/realizado/teórico” se comprueba en
cada base la **presencia y edición de `account_budget`**; si está disponible,
un **puente opcional** `step_management_costs_account_budget`
(`auto_install`) genera y vincula `budget.analytic` / revisiones estándar y
reutiliza sus KPIs. Si no está, el adaptador propio responde y la capacidad
“comprometido” se implementa desde **PO confirmada no facturada** o se
**oculta** (nunca un cero engañoso).

**Consecuencias.**

- El núcleo **no** declara `account_budget` como dependencia dura.
- En V1 no se crea el puente ni el adaptador; se fija el contrato en este ADR
  y en `DECISION_LOG.md` D02/D17. La verificación de `account_budget` por base
  queda como comando de preflight (no ejecutable localmente, ver §Verificación).

**Descartado.** Depender de `account_budget` siempre (rompe Demo-SyS y
cualquier base sin el módulo) o reimplementar su motor completo (doble
mantenimiento).

---

## D-E. Núcleo portable y puentes opcionales

**Decisión.** Un único addon de aplicación `step_management_costs` con sólo
dependencias estándar: `base, mail, web, account, product` (las actuales).
Las integraciones agrícolas viven en puentes pequeños con `auto_install`,
instalables sólo cuando ambas partes existen. Nombres **propuestos** (a
confirmar en Fase 0/2, D13):

| Puente | Motiva | Depende de |
|---|---|---|
| `step_management_costs_account_budget` | Presupuesto analítico estándar | `account_budget` |
| `step_management_costs_agriculture` | Maestros `step_hr` (fundo, cuartel, especie, variedad, temporada, actividad) | `step_hr` |
| `step_management_costs_bpa` | Programa / instrucción / OT-BPA | módulo BPA |
| `step_management_costs_machinery` | Horas y costos de maquinaria | `step_machinery` |
| `step_management_costs_operations` | Actividades, cosecha, otras OT | módulos de operaciones |

**Consecuencias.**

- Demo-SyS recibe **sólo el núcleo**; nunca `step_agricultural_access` ni el
  stack agrícola (D12).
- El núcleo trae maestros propios mínimos (temporada, origen, versión) con
  **fallback portable**; los puentes los reemplazan por FK a los maestros
  canónicos cuando existen (D13).

**En V1:** ningún puente. Sólo el núcleo, endurecido.

**Actualización Corte 1 post Fase 6 (2026-09-04):** el puente
`step_management_costs_agriculture` sigue sin construirse. Al auditar
`step_hr` para prepararlo se encontró que `product.template.actividad_id`
apunta hoy a `account.analytic.account`, no al modelo `step.actividad` que
la respuesta del cliente da por hecho como maestro de Actividad (ver
`DECISION_LOG.md` D20). El puente usará el campo real cuando se construya;
no se corrige `step_hr` desde este addon.

---

## D-F. Cuenta analítica del centro — estrategia de transición

**Decisión.** No se convierte `cost_center.analytic_account_id` a
`required=True` en `18.0.2.0.0`. En su lugar:

1. `check_company=True` + dominio de empresa en el campo (relación válida).
2. **Gate en la aprobación**: `operational.budget.action_approve` exige que
   cada centro asignado tenga cuenta analítica **de la misma empresa** del
   presupuesto. Las aprobaciones nuevas quedan bloqueadas si falta o cruza
   empresa; la instalación y el upgrade **no** se bloquean.
3. **Pre-check de upgrade idempotente** (`post-migration.py`): inventaría
   centros sin cuenta y centros con cuenta de otra empresa, y escribe un
   informe de saneamiento al log. **No** crea ni elige cuentas por
   coincidencia ambigua; no asigna nada automáticamente.
4. Documentación para el operador: cómo crear/asignar el plan y las cuentas
   por empresa antes de aprobar.

**Consecuencias.** Datos heredados incompletos no rompen la actualización;
las cifras nuevas nacen imputables. La conversión a `required` real se evalúa
en Fase 2 tras el saneamiento.

**Descartado.** `required=True` inmediato (falla `NOT NULL` sobre filas
históricas, como ya ocurrió con `step_cosecha.product_uom_id`, ver
`AUDITORIA_PRODUCTO_AGRICOLA.md` §4.5.l). Autoasignar la “única cuenta que
calce por nombre” (elección ambigua, riesgo contable).

---

## D-G. Multiempresa

**Decisión.**

- `_check_company_auto = True` en todos los modelos persistentes con
  `company_id`: `cost.center`, `budget.group`, `budget.template`,
  `exchange.rate`, `operational.budget`, `budget.center` (nuevo `company_id`
  related-stored), `budget.line`, `budget.template.line` (nuevo `company_id`
  related-stored desde `template_id`), `historical.cost`, `plan`.
- `check_company=True` en `Many2one` compatibles: `cost_center.
  analytic_account_id`, `operational_budget.template_id`,
  `budget_center.center_id`, `budget_line.center_id`, `budget_line.group_id`,
  `historical_cost.center_id`, `historical_cost.group_id`,
  `budget_template_line.group_id`, `plan.budget_id`.
- Las `ir.rule` de aislamiento se convierten en **globales** (sin `groups`),
  dominio estándar
  `['|', ('company_id', 'in', company_ids), ('company_id', '=', False)]`
  (o el equivalente por relación para líneas/meses). Las reglas de grupo se
  unen y pueden **ampliar** acceso; las globales se **intersectan** — es lo
  correcto para aislamiento.
- Constraints Python para lo que `check_company` no alcanza:
  `plan.center_ids` (Many2many), coherencia
  `budget_line.template_line_id.company_id == budget.company_id`,
  `budget.month` vía `budget_line_id`.
- Modelos sin `company_id`: `budget.template.line`, `budget.center` y
  `budget.month` reciben `company_id` (related, `store=True` los dos primeros;
  `budget.month` ya lo tiene related no almacenado y se deja así porque nunca
  se filtra directamente). No quedan modelos persistentes sin `company_id`.

**Consecuencias.** El upgrade debe poblar los `company_id` nuevos
(`post-migration.py`, idempotente, desde el padre). Sin ese paso los stored
quedarían nulos.

---

## D-H. Aprobación, inmutabilidad y snapshot

**Decisión.**

- `operational.budget` gana: `approved_by_id`, `approved_at`, `revision`
  (int, default 1), `reopen_reason` (text), `revision_of_id`/`superseded_by_id`
  (M2o self), `approval_snapshot` (text/JSON) y `approval_hash` (char,
  sha256).
- `state` amplía a `('superseded', 'Reemplazado')`.
- `action_approve`: exige rol aprobador, transición `calculated → approved`,
  distribución mensual completa (D-I), cuenta analítica por centro (D-F);
  fija `approved_by_id/at`, calcula y congela `approval_snapshot` +
  `approval_hash`.
- `write()` y `unlink()` bloquean cambios en cabecera, `allocation_ids`,
  `line_ids`, `month_ids`, `currency_id`, `conversion_*`, cantidades y
  tarifas cuando `state in ('approved', 'closed', 'superseded')`. No existen
  bypasses por contexto enviados por el cliente.
- `action_reopen(reason)`: nombre técnico conservado por compatibilidad; sólo
  rol aprobador; crea una revisión editable con el motivo y mantiene el
  aprobado original inmutable. Nunca ejecuta `approved → draft` sobre el mismo
  registro.
- `action_new_revision()`: copia el presupuesto (`revision + 1`,
  `revision_of_id` = origen), estado `draft`; al aprobarse la copia, el
  origen pasa a `superseded` con `superseded_by_id`. Nunca se sobrescribe un
  aprobado.
- **Snapshot mínimo en V1:** blob JSON con líneas (centro, grupo, indicador,
  UdM, cantidad, tarifa, modo directo/cantidad, importe y meses con fecha y
  monto convertido), moneda, `conversion_rate_type`,
  factor y `target_value`, total y total convertido, timestamp; más
  `approval_hash`. **Migración siguiente (Fase 2):** modelo
  `step.management.budget.revision` + `…snapshot.line` de primera clase, con
  el blob como respaldo de compatibilidad.

**Consecuencias.** Un aprobado es reproducible y verificable por hash sin
tabla nueva. La reapertura es siempre trazable.

---

## D-I. Integridad del presupuesto

**Decisión (V1 — mínimo probado).**

- **No-divergencia por restricción, no por derivación.** En `budget.line`,
  `_check_monthly_distribution` (`@api.constrains`) exige que, cuando hay
  `month_ids`, `float_compare(sum(months.quantity), quantity,
  precision_rounding=uom/currency) == 0`. Nunca igualdad binaria de flotantes.
  Un cambio directo en un mes se revalida desde `budget.month`
  (`_check_parent_distribution`), porque `@api.constrains` sobre un One2many no
  se dispara al editar el hijo.
- `distribution_complete` (compute stored) = hay `month_ids` **y** la suma
  cuadra. Sin meses ⇒ `False` (una línea sin distribuir está incompleta).
- Si no hay meses, `quantity` sigue siendo editable y la línea queda
  `distribution_complete = False`.
- **Migración siguiente (Fase 2):** cuando los meses pasen a ser líneas de
  período canónicas (D14), `quantity` se **deriva** de la distribución
  (`sum(month.quantity)`) y deja de ser editable directamente.
- `action_approve` recolecta las líneas con `distribution_complete = False` y
  **falla con un `UserError` que las lista**. No completa la distribución en
  silencio (hoy `_compute_amounts` hace exactamente eso: usa `base_quantity`
  si no hay meses).
- Unicidad de `budget.center`: se reemplaza `_check_unique_center`
  (`search_count`, vulnerable a carrera) por
  `_sql_constraints = [('budget_center_uniq', 'unique(budget_id, center_id)',
  …)]`. El `pre-migration.py` deduplica filas existentes (conserva la de
  menor `id`, reasigna/borra las demás **sólo si son idénticas**; si difieren
  aborta con mensaje para revisión manual).

**Consecuencias.** Total y distribución no pueden divergir. Una distribución
incompleta es error visible en la vista (`decoration-danger`) y en la
aprobación.

**Tolerancia.** Se usa `self.env['decimal.precision']` /
`currency_id.rounding` y `uom_id.rounding`; el porcentaje de distribución se
valida con `float_compare`, nunca con `==`.

---

## D-J. Estrategia de upgrade desde `18.0.1.1.0`

**Decisión.**

- Manifiesto a `18.0.2.0.0` **en el mismo commit** que introduce
  `upgrades/18.0.2.0.0/`.
- `upgrades/18.0.2.0.0/pre-migration.py`:
  - deduplica `step_management_budget_center` por `(budget_id, center_id)`
    antes de crear el `unique` (idempotente; aborta si las filas duplicadas
    difieren en `hectares`/`notes`).
- `upgrades/18.0.2.0.0/post-migration.py`:
  - puebla `company_id` en `step_management_budget_center` (desde el
    presupuesto) y `step_management_budget_template_line` (desde la
    plantilla); idempotente (`WHERE company_id IS NULL`).
  - inicializa `revision = 1` donde sea `NULL`.
  - clasifica `historical.cost`: los existentes → `origin = 'unreviewed'`
    (nuevo campo; default para registros previos) sin tocar sus importes.
  - inventaría (log) centros sin cuenta analítica y con cuenta de otra
    empresa; **no** asigna nada.
- Reglas: idempotentes, sin IDs numéricos hardcodeados, sin `commit()`
  manual, sin `env.ref` a datos que puedan no existir sin
  `raise_if_not_found=False`.
- Se conservan modelos, tablas, registros, secuencias y XML IDs. El `state`
  sólo gana valores nuevos.

**Consecuencias.** La actualización de una base `18.0.1.1.0` preserva folios,
totales y relaciones; las pruebas de upgrade (cuando haya runtime) verifican
conteos y totales antes/después.

---

## D-K. Cosecha por centro y recursos encadenados (Corte V2 A, 2026-09-06)

**Decisión.** `harvest.plan.line` gana `center_id` (opcional, compatibilidad)
sin tocar `estimation.py`: el reparto centro×semana se deriva de nuevo en
`harvest_plan.py` a partir de `estimation.line_ids` (ya por centro) y la
curva semanal ya validada, evitando reabrir un modelo inmutable ya
desplegable. Los recursos del plan (envases, personal, maquinaria) se
modelan como una cadena configurable (`harvest.resource`, nodo→nodo o
nodo→kilos) en vez de columnas físicas por cargo/semana — mismo principio de
"núcleo portable, sin columnas rígidas por caso particular" que D-E/D13.
Ningún factor del `Anexo 1.6.9 plan de cosecha V2.xlsx` (4, 60, 55, 5, 30, 2,
10) se hardcodea: son valores de ejemplo, editables por plan.

**Consecuencias.** `harvest.plan` alcanza el mismo nivel de inmutabilidad y
revisión que el resto de documentos aprobables del addon (D-H), habilitando
que la Orden de Producción lo consuma como fuente trazable de tercera clase
(tareas, fito/ferti, cosecha) sin inventar un prorrateo donde la fuente no
lo demuestra (cosecha antes del Corte 2 no tenía centro; ahora sí, por dato
real, no por inferencia).

**Descartado.** Reabrir `estimation.distribution_ids` para agregarle
`center_id`: rompería la garantía de inmutabilidad de estimaciones ya
validadas en bases reales y duplicaría lógica que ya existe en
`estimation.line_ids`.

---

## D-L. Hechos históricos normalizados, no reconstrucción de `operational.budget` (Corte V2 B, 2026-09-07)

**Decisión.** Los dos archivos históricos oficiales del cliente
(`Anexo 1.6.2.1` presupuesto, `Anexo 1.6.10.3` real, ~16.000/~18.600 filas
cada uno) se cargan como hechos normalizados en
`step.management.historical.cost` (`dataset_kind = 'budget'|'actual'`, una
fila del archivo = una fila del modelo), **no** como
`step.management.operational.budget`. Reconstruir presupuestos operacionales
desde datos masivos exigiría "aprobar" miles de documentos artificiales que
nunca pasaron por el flujo real de aprobación descrito en D-H — viola
directamente esa invariante. La comparación (Corte V2 F) se hace agregando
por dimensiones (temporada, centro, grupo, especie…), igual que ya hace
`historical.cost` para el comparativo manual existente.

**Consecuencias.** `budget_import.py`/`operational.budget` siguen siendo el
camino correcto para la carga y aprobación de presupuesto **vigente/futuro**
(uso operacional continuo); el nuevo
`step.management.historical.import.batch` es exclusivamente para **datos
pasados** que sólo sirven de referencia comparativa, con su propio ciclo de
vida (ingresado → aprobado/bloqueado → reversa), sin tocar el motor de
aprobación de presupuesto.

**Descartado.** Generar un `operational.budget` por temporada/centro desde
el archivo histórico: además de la aprobación artificial, la cardinalidad no
calza — el histórico tiene una fila por año/mes/centro/producto, mientras
que un presupuesto operacional agrupa meses dentro de una sola línea por
centro/categoría/producto vigente para una temporada.

---

## D-M. Comprometido desde Compras real, no desde `account_budget` (Corte V2 C, 2026-09-07)

**Decisión.** El manifiesto agrega `purchase` como dependencia dura (mismo
criterio que D-E para `stock`: módulo estándar de Odoo, no un puente
agrícola). El "comprometido" de `stock.requirement` se lee directamente de
`purchase.order.line` (confirmadas, `product_qty - qty_invoiced`), nunca de
`account_budget` — aunque está instalado en Desarrollo/Demo, el cliente
confirmó (J5) que ese motor no representa este presupuesto de gestión.

**Consecuencias.** `net_to_buy` consume primero la disponibilidad de stock y
luego lo comprometido, cada uno una sola vez a través de los períodos
(mismo principio cronológico de R3/D22); con `virtual_available`
(`forecasted`) no se descuenta lo comprometido de nuevo, porque Odoo ya lo
incorpora como entrada prevista.

---

## D-N. Puente `step_management_costs_agriculture` (Corte V2 D, 2026-09-07)

**Decisión.** Se materializa el puente previsto en D-E/D13 para los
maestros agrícolas: `step_management_costs_agriculture`,
`auto_install=True`, `depends=["step_management_costs","step_hr"]`. No
convierte ningún campo del núcleo en obligatorio; agrega campos de sólo
lectura (`agri_*` en `cost.center`) y una precedencia de rendimiento
estándar (centro → variedad → grupo de variedad, indexada también por
`labor_id`) que `estimation.py` usa sólo si el usuario elige
`harvest_labor_id` — comportamiento del núcleo sin cambios si el puente no
está instalado o no se usa ese campo. Detalle completo y hallazgos de
auditoría en `DECISION_LOG.md` §"Corte V2 D" (D-N).

**Consecuencias.** El campo Actividad (D20) permanece deliberadamente sin
conectar — el maestro de rendimiento usa `labor_id`, un campo real e
independiente del bloqueo de D20.

---

## D-O. Puente `step_management_costs_machinery` (Corte V2 E, 2026-09-07)

**Decisión.** Se materializa el puente de maquinaria sobre
`step_machinery` (18.0.22.0.0), `auto_install=True`,
`depends=["step_management_costs","step_machinery"]`. No se creó un
documento de presupuesto paralelo: `step.management.budget.line` ya tenía
`category='machinery'` sin usar en el núcleo, así que el puente sólo le
agrega la vinculación a la maquinaria real (`machinery_vehicle_id`,
`machinery_labor_id`) y el cálculo de tarifa/desglose por componente
(`mc_standard_hourly_components/rate` sobre `fleet.vehicle`, con la misma
guarda de cero horas que ya usa `step_machinery`, replicada sin tocarlo).
El presupuesto que contiene la línea sigue aportando snapshot, revisión,
aprobación, multiempresa y moneda del núcleo sin duplicar nada.

**Consecuencia sobre el núcleo (no del puente):** se detectó que
`_create_revision()` reconstruía las líneas de una revisión con una lista
de campos hardcodeada — cualquier campo agregado por un puente vía
`_inherit` se perdía en silencio al revisar. Se generalizó a
`REVISION_LINE_FIELDS` (extensible, mismo criterio que
`PROTECTED_LINE_FIELDS`), corregido en el núcleo (`18.0.19.0.0`): beneficia
a cualquier extensión futura de `step.management.budget.line`, no sólo a
este puente. Detalle completo y hallazgos de auditoría en
`DECISION_LOG.md` §"Corte V2 E" (D-O).

---

## D-P. Comparativos, tablero y fuera de OP — sin puentes nuevos (Corte V2 F, 2026-09-07)

**Decisión.** El comparativo de temporada lee exclusivamente
`step.management.historical.cost` (el hecho normalizado de V2 B) — nunca
mezclado con la contabilidad analítica en vivo dentro de la misma
comparación, para no contar el mismo gasto dos veces por dos caminos. El
tablero existente (`get_management_dashboard()`) se **extendió**, no se
duplicó. La clasificación fuera de OP usa la clave centro + temporada +
grupo presupuestario; la dimensión actividad de la clave pedida por el
corte queda fuera — es exactamente D20 (semántica de
`product.template.actividad_id` sin confirmar), mismo criterio de "aislar
el campo bloqueado y seguir" ya aplicado en D-N.

**Consecuencia sobre el núcleo (no de este corte):** se detectó que una
lectura de gasto real por cuenta analítica podía atribuirlo en silencio al
centro equivocado cuando dos centros comparten intencionalmente una cuenta
analítica (escenario real, no hipotético). Se generalizó la protección que
ya existía acotada a un presupuesto
(`operational_budget._duplicate_analytic_centers()`) a un método
reutilizable en el núcleo, `step.management.cost.center
.account_to_center_map()`, que levanta un error explícito ante la
ambigüedad en vez de adivinar. Detalle completo en `DECISION_LOG.md`
§"Corte V2 F" (D-P).

---

## Verificación pendiente (sin runtime local)

No hay Odoo ni PostgreSQL en este equipo (`which odoo/psql` → nada; sólo
Python 3.12 para chequeos estáticos). Comandos exactos a ejecutar en una base
**desechable** antes de promover:

```bash
# edición y presencia de account_budget por base (solo lectura)
odoo shell -c <conf> -d <copia> --no-http <<'PY'
mods = env['ir.module.module'].search([('name','in',['account_budget'])])
print([(m.name, m.state) for m in mods])
PY

# instalación limpia + pruebas del addon
odoo -c <conf> -d mc_clean_$(date +%s) -i step_management_costs \
     --test-enable --test-tags step_management_costs --stop-after-init --log-level=test

# upgrade desde 18.0.1.1.0 sobre clon
odoo -c <conf> -d <clon_1_1_0> -u step_management_costs \
     --test-enable --test-tags step_management_costs --stop-after-init --log-level=test
```

Marcar la evidencia como **no ejecutada** hasta correr lo anterior.
