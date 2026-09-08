# Handoff — Corte V2 A (plan de cosecha, recursos y OP)

**Addon:** `step_management_costs` · **De:** `18.0.14.0.0` → **A:** `18.0.15.0.0`
**Fecha:** 2026-09-06/07 · **Autor:** Claude Sonnet 5 · **Estado:** implementado
y verificado en Odoo real, sin despliegue

## 1. Alcance

Primer corte de `PROMPT_CLAUDE_SONNET5_RESPUESTAS_V2_2026-09-06.md`. Resuelve
el bloqueo de cosecha del Corte 2 y entrega los recursos configurables del
plan de cosecha:

- **Cosecha por centro y semana:** `models/harvest_plan.py::action_generate`
  reparte el `total_kg` de **cada línea de la estimación** (ya por centro)
  entre las semanas de la curva validada, con residuo determinista a la
  última semana **de cada centro**. No se tocó `estimation.py`.
  `harvest.plan.line` gana `center_id` (opcional, compatibilidad — planes
  confirmados antes de este corte no lo tienen y no se les asigna nada
  retroactivamente), `species`, `variety`.
- **Revisión/inmutabilidad del plan de cosecha:** `harvest.plan` alcanza el
  mismo patrón que presupuesto/estimación/programa/OP
  (`revision`/`revision_of_id`/`superseded_by_id`/`confirmation_snapshot`/
  `confirmation_hash`); antes sólo tenía `draft/confirmed` sin revisión
  formal.
- **Recursos configurables encadenados:** `models/harvest_resource.py`
  (`step.management.harvest.resource` + `.week`) — cadena de nodos donde la
  fuente de cada uno es o bien los kilos semanales del plan o bien otro
  recurso del mismo plan; factor (divisor) y política de redondeo
  (`precisión de la UdM`/`hacia arriba`/`sin redondeo`) por recurso, snapshot
  congelado por semana. Cubre los ≥ 11 recursos pedidos (cajas, unidad de
  traslado, cosecheros, supervisor, jefe de cuadrilla, anotadores,
  tractoristas, cargador, pallets/día, viajes/día, maquinaria).
- **Envases reutilizables (C4):** mismo modelo con
  `is_reusable_container=True` — necesidad semanal máxima, inventario
  objetivo (`coverage_multiplier`, default 3, configurable), existencia real
  si hay producto vinculado, brecha. Nunca se mezcla con
  `step.management.stock.requirement` ni genera compras.
- **OP con cosecha como fuente:** `models/production_order.py` gana
  `source_type='harvest_line'`, sólo de un plan de cosecha **confirmado**
  (no borrador, no reemplazado), mismo contrato de huella/no-duplicación/
  snapshot que las otras dos fuentes. Una OP autorizada no cambia si el plan
  de cosecha se revisa después.

## 2. Seguridad

- ACL nuevas: `harvest.resource(.week)`, mismo patrón
  `readonly ⊂ user ⊂ manager`; `resource.week` sin `write` para nadie
  (modelo lo bloquea siempre en Python — es un cálculo del sistema).
- Reglas globales por empresa nuevas para ambos modelos.
- `check_company=True` en `source_resource_id` y `product_id` de
  `harvest.resource`; `_check_company_auto` en ambos modelos nuevos.
- `harvest_plan_line_id` en la línea de OP con `check_company=True` +
  `_sql_constraints unique(order_id, harvest_plan_line_id)` — mismo patrón
  que las otras dos fuentes.

## 3. Interfaz

- Formulario de plan de cosecha: pestañas «Centro / semana» (detalle con
  centro/especie/variedad), «Recursos» (lista editable con la cadena de
  factores y las columnas de envases reutilizables) y «Confirmación»; botón
  «Nueva revisión».

## 4. Migración

- Manifiesto `18.0.15.0.0`; sin dependencias nuevas.
- `upgrades/18.0.15.0.0/post-migration.py`: preflight de sólo lectura — cuenta
  planes de cosecha confirmados con líneas sin `center_id` (evidencia, sin
  corregir nada). `harvest.resource(.week)` son modelos nuevos, sin backfill.

## 5. Pruebas

`tests/test_v2_a_harvest.py` (18 pruebas nuevas), sin duplicar lo que ya
cubre `test_fase4_planning.py` (reconciliación de un solo centro,
inmutabilidad básica): dos centros y varias semanas, W53 con residuo por
centro, planes heredados sin centro no se completan solos, factores
encadenados (cajas→pallets), divisor cero bloqueado, las tres políticas de
redondeo, el valor semanal de un recurso no se edita a mano, factor
modificado después de confirmar sin alterar el snapshot ya congelado,
envases reutilizables (objetivo/brecha) sin mezclarse con necesidades de
stock, multiempresa (recurso de origen de otra compañía rechazado), revisión
tras confirmar, OP con cosecha como fuente (sin duplicar, vía constraint
SQL) y una OP autorizada que no cambia cuando el plan de cosecha se revisa
después.

### Verificación local

- `py_compile` de todos los `.py` del addon: OK.
- Parseo de los 28 XML del addon: OK.
- `git diff --check`: OK (mismos avisos LF/CRLF preexistentes).

### Verificación Odoo real en `odoo-new` (sólo bases desechables)

Mismo patrón que los cortes anteriores (SSH a `odoo-new`, clon de
`LAB_TAREAS` vía `pg_dump`/`pg_restore`, addon con precedencia en el
`addons_path` temporal). Se encontró y corrigió un bug real durante la
verificación (invisible a `py_compile`/parseo XML): el `Selection` de
`source_type` en `production.order.preview.wizard.line` no incluía
`harvest_line` — dos pruebas fallaban con `ValueError: Wrong value for
...source_type: 'harvest_line'`. Corregido agregando el valor faltante.

| Escenario | Resultado |
|---|---|
| Upgrade de clon de `LAB_TAREAS` (`18.0.4.0.0` → `18.0.15.0.0`) | RC 0 · **0 failed, 0 error(s) de 217 tests** (`odoo.tests.stats`: 255 tests, 193.6s, 81868 queries) |
| Instalación limpia sin demo (`--without-demo=all`) | RC 0 · **0 failed, 0 error(s) de 217 tests** (`odoo.tests.stats`: 255 tests, 45.7s, 38712 queries) |

217 = 203 (Corte 2) + 18 (Corte 2 producción/harvest de esta entrega, exacto
1:1 con los métodos `test_*` de `test_v2_a_harvest.py`) — la discrepancia
`stats` vs `result` sigue siendo la misma de cortes anteriores (heredada, no
bloqueante, sin explicar aún).

Bases (`MC_V2A_UPG`, `MC_V2A_CLEAN`), dump de `LAB_TAREAS`, directorio
temporal y scripts desechables eliminados al terminar. `LAB_TAREAS` no se
tocó (sólo se leyó vía `pg_dump`).

## 6. Decisiones y supuestos

Ver `DECISION_LOG.md` §"Corte V2 A": D22 (cosecha por centro/semana),
C2-V2/C4-V2 (recursos y envases). Nota de auditoría del propio corte: el
docx de respuestas V2 referencia notas numeradas que no existen en el
archivo para buena parte del bloque G/K/B/C/H/I/J/L — se resolvieron con las
decisiones explícitas del propio documento de continuación y con el análisis
directo del `Anexo 1.6.9 plan de cosecha V2.xlsx`; la única que sigue
genuinamente sin respuesta es **K3** (identidad de presupuesto/estimación
más allá de centro+temporada), que queda como estaba (D06, abierta).

## 7. Pendientes del cliente (lista separada)

- K3: si la identidad de presupuesto/estimación necesita fundo/especie
  además de centro+temporada.
- H1, K5, D20, documento definitivo de BPA-Riego, usuarios reales/calendario
  de UAT: bloqueados explícitamente, sin cambios este corte.

## 8. Confirmación de aislamiento

No se tocó `STEPS_DEMO_SYS`, ninguna otra sesión de Claude, ni bases reales
(`LAB_TAREAS` sólo se leyó vía `pg_dump`; todo lo escrito fue en bases
desechables `MC_V2A_*`, eliminadas al terminar). Sin commit ni push.

## 9. Siguiente

Corte V2 B: cargas históricas oficiales (presupuesto y real, `18.0.16.0.0`)
y plantillas versionadas.
