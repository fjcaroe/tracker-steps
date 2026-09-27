# Matriz de requisitos — Steps Gestión y Costos

**Fase:** 0 (Descubrimiento técnico)
**Addon auditado:** `step_management_costs` — commit base del worktree
`codex/gestion-costos` (creado sobre `origin/codex/web-tracker-redesign`,
HEAD `9aa55c1`).
**Versión del addon en el commit base:** `18.0.1.1.0`.
**Fuente funcional:** `C:\Users\tito4\Downloads\1.6 Módulo Gestión y Costos\1.6 Módulo Gestión y Costos`
(8 Word + 28 Excel; se revisaron los documentos y anexos de la primera
vertical: `1 Presupuesto/*` y `4 Gestion/*`, más `Menú general de Gestión y
Costos.xlsx`).

> El texto de los anexos es un mockup con contradicciones conocidas (ver
> `DECISION_LOG.md` §Contradicciones). Esta matriz clasifica **estado de
> implementación en el código**, no “conformidad con la planilla”.

> **Actualización de ejecución:** el inventario detallado inferior conserva la
> línea base auditada. El estado vigente después de Fase 3, corte 1 es
> `18.0.7.0.0`; esta tabla de avance prevalece sobre las marcas históricas de la
> línea base.

## Avance vigente — Corte V2 A (18.0.15.0.0)

Ver `HANDOFF_V2_CORTE_A.md` y `DECISION_LOG.md` §"Corte V2 A" para el
detalle. Resumen:

| Requisito | Estado vigente | Evidencia |
|---|---|---|
| C2-V2 — cosecha por centro/semana (resuelve bloqueo Corte 2) | ✅ | `models/harvest_plan.py::action_generate` (por línea de estimación × curva semanal, residuo por centro) |
| C2-V2 — recursos configurables encadenados (envases, personal, maquinaria) | ✅ | `models/harvest_resource.py` (`step.management.harvest.resource(.week)`) |
| C4-V2 — envases reutilizables en listado aparte | ✅ | `harvest_resource.py` (`is_reusable_container`, `coverage_multiplier` default 3, `inventory_gap`) |
| OP — cosecha como fuente trazable | ✅ | `models/production_order.py` (`source_type='harvest_line'`) |
| Plan de cosecha — revisión/inmutabilidad/snapshot | ✅ | `harvest_plan.py` (mismo patrón que presupuesto/estimación/programa/OP) |
| K3 — identidad completa de presupuesto/estimación | ⛔ pendiente | Sin respuesta del cliente en ningún documento; D06 sigue abierta |

## Avance vigente — Corte V2 B (18.0.16.0.0)

Ver `HANDOFF_V2_CORTE_B.md` y `DECISION_LOG.md` §"Corte V2 B". Resumen:

| Requisito | Estado vigente | Evidencia |
|---|---|---|
| L1/L3 — cargas históricas oficiales (presupuesto + real) | ✅ | `models/historical_import.py` (`step.management.historical.import.batch(.line)`) |
| D-L — hechos normalizados, sin reconstruir `operational.budget` | ✅ | `models/historical_cost.py` (`dataset_kind`), `ADR_001` §D-L |
| Especie/variedad condicionada por tipo de centro | ✅ | `historical_import.py::_parse_row` (`CENTER_TYPE_REQUIRES_SPECIES`) |
| Fórmula de TC segura (real histórico) | ✅ | `historical_import.py::_is_safe_rate_formula` |
| Duplicados exactos mostrados, política explícita | ✅ | `exclude_exact_duplicates` (default: se incluyen) |
| Plantillas versionadas, sólo Administrador | ✅ | `step.management.historical.template.version` + `data/historical_template_versions.xml` |
| Aprobación/bloqueo/reversa del lote | ✅ | `action_approve`/`action_block`/`action_create_reversal` |

## Avance vigente — Corte V2 C (18.0.17.0.0)

Ver `HANDOFF_V2_CORTE_C.md` y `DECISION_LOG.md` §"Corte V2 C". Resumen:

| Requisito | Estado vigente | Evidencia |
|---|---|---|
| J5 — comprometido desde OC confirmadas, no `account_budget` | ✅ | `models/stock_requirement.py::_committed_quantity` |
| `net_to_buy` sin doble conteo con `forecasted` | ✅ | `action_compute` (consumo cronológico separado stock→comprometido) |
| Trazabilidad a líneas de compra | ✅ | `committed_purchase_line_ids` |
| Nueva dependencia `purchase` | ✅ | `__manifest__.py`, auditado contra `LAB_TAREAS` (18.0.1.2 instalado) |

## Avance vigente — Corte V2 D (addon puente `step_management_costs_agriculture` 18.0.1.0.0)

Ver `HANDOFF_V2_CORTE_D.md` y `DECISION_LOG.md` §"Corte V2 D". Resumen:

| Requisito | Estado vigente | Evidencia |
|---|---|---|
| Auditoría de maestros reales (`step.fundo`, `step.especie`, `step.variedad(.line)`, `step.grupo.variedad(.line)`, `step.cuartel.line`, `account.analytic.account` agrícola) | ✅ | `DECISION_LOG.md` D-N, verificado contra el código real (worktree y `odoo-new`) |
| Precedencia de rendimiento estándar centro→variedad→grupo | ✅ | `step_management_costs_agriculture/models/estimation.py::_agri_resolve_standard_yield` |
| Plantas desde el maestro del centro | ✅ | `cost_center.py` (`agri_plants`), `estimation.py` |
| Procedencia congelada al validar | ✅ | `plants_source`/`yield_source`, `PROTECTED_LINE_FIELDS` extendido |
| Método "Kilos" sin doble rendimiento | ✅ (sin cambio) | D05 intacto — el puente no toca el método `kilos` |
| Actividad (D20) | ⛔ pendiente | No conectada; sigue bloqueada |
| Núcleo instala sin el puente | ✅ | `step_management_costs` sin `step_hr` — sin cambios de comportamiento |
| Verificación real, instalación limpia (núcleo + puente) | ✅ (1 excepción externa documentada) | `HANDOFF_V2_CORTE_D.md` §5 — `TestFase2Variance` (común de Odoo core, no nuestro) es incompatible con `step_hr.grupo_labor`; no corregible sin tocar código ajeno |
| Verificación real, upgrade de `LAB_TAREAS` | ⏸ bloqueada (externa) | `sale_stock` modificado por otra sesión/proceso en `LAB_TAREAS` el mismo día; reintentar cuando esté quieta |

## Avance vigente — Corte V2 E (addon puente `step_management_costs_machinery` 18.0.1.0.0, núcleo 18.0.19.0.0)

Ver `HANDOFF_V2_CORTE_E.md` y `DECISION_LOG.md` §"Corte V2 E". Resumen:

| Requisito | Estado vigente | Evidencia |
|---|---|---|
| Cero horas válido (con/sin gastos, sin división por cero) | ✅ | `mc_standard_hourly_components/rate`, `test_zero_hours_*` |
| Componentes reales (8 conceptos de `type.service.machinery`) | ✅ | `machinery_rate.py`, sin hardcodear nombres/IDs — se busca por `cod` |
| Vinculación por producto/maquinaria real verificada | ✅ | `machinery_vehicle_id` (`fleet.vehicle`, `check_company=True`) |
| Costo hora = suma de servicios / horas | ✅ | `mc_standard_hourly_rate` |
| Tarifa variable por labor | ✅ | `step.management.machinery.labor.rate` |
| Presupuesto general consume la tarifa vía grupo controlado | ✅ | `get_machinery_group()` (código `HRMAQ`), `category='machinery'` ya existente en el núcleo |
| Real imputado a centro/maquinaria con relación demostrable | ✅ | `machinery_actual_hours` (exige `cost_id` **y** `machinery_ids`) |
| Snapshot, revisión, aprobación, multiempresa, moneda | ✅ (reutiliza el núcleo, no duplicado) | `operational_budget.py`, `REVISION_LINE_FIELDS` extendido |
| No se modifica `step_machinery` | ✅ | Sólo `_inherit`/lectura |
| Núcleo instala sin el puente | ✅ | `step_management_costs` sin `step_machinery` — sin cambios de comportamiento |
| Verificación real, instalación limpia (núcleo + 2 puentes) | ✅ (misma 1 excepción externa que V2 D) | `HANDOFF_V2_CORTE_E.md` §6 |
| Verificación real, upgrade de `LAB_TAREAS` | ⏸ bloqueada (externa, confirmada persistente) | `HANDOFF_V2_CORTE_E.md` §6, `DECISION_LOG.md` §"Corte V2 E" |

## Avance vigente — Corte V2 F (núcleo 18.0.20.0.0, sin puentes nuevos)

Ver `HANDOFF_V2_CORTE_F.md` y `DECISION_LOG.md` §"Corte V2 F". Resumen:

| Requisito | Estado vigente | Evidencia |
|---|---|---|
| Comparativo de temporada, 8 dimensiones | ✅ | `wizard/season_comparison.py` |
| Medidas $ y US$, variación desde totales (nunca sumando %) | ✅ | `_compute_totals`, `test_totals_from_totals_not_from_percent_sum` |
| Tablero: real vs. presupuesto, hectáreas por fundo/especie, hectáreas por variedad | ✅ | `get_management_dashboard()` extendido, `_hectares_breakdown` |
| Necesidades/disponible/comprometido/neto en el tablero | ✅ | Bloque `stock` (V2 C ya es núcleo) |
| Clasificación fuera de OP: centro + temporada + grupo | ✅ (parcial — ver siguiente fila) | `wizard/out_of_op_classifier.py` |
| ...+ actividad (clave completa pedida por el corte) | ⛔ pendiente (D20) | Aislado explícitamente; extensión menor cuando D20 se resuelva |
| Mostrar fuera de OP por separado, sin excluir ni mezclar | ✅ | `backed_by_op` marcado, ambos casos en la misma lista |
| Enriquecer OP/OT, fallback Wxx/año ISO sin fabricar folio | ✅ | `source_label` |
| Sin doble conteo entre fuentes (histórico vs. en vivo) | ✅ | Comparativo lee sólo `historical_cost`; clasificador lee sólo `account.move.line`; nunca mezclados en una misma agregación |
| Dos compañías, permisos de consulta | ✅ | `test_two_companies_isolated`, `test_readonly_group_can_compute` |
| Verificación real, instalación limpia (núcleo + 2 puentes) | ✅ (misma 1 excepción externa que V2 D/E) | `HANDOFF_V2_CORTE_F.md` §6 |
| Verificación real, upgrade de `LAB_TAREAS` | ⏸ bloqueada (externa, confirmada persistente 3ª vez) | `HANDOFF_V2_CORTE_F.md` §6 |

## Avance vigente — Corte V2 G (auditoría, sin cambio de versión)

Ver `HANDOFF_V2_CORTE_G.md` y `DECISION_LOG.md` §"Corte V2 G". Resumen —
**resultado legítimo del corte: auditoría completa, cero adaptadores**
(el propio documento del corte contempla este desenlace):

| Área | Estado vigente | Motivo del bloqueo |
|---|---|---|
| Actividades | ➖ N/A | Sin modelo de OT propio — es una dimensión (taxonomía), no un documento |
| Cosecha | ⛔ bloqueado | `step.cosecha.registry` exige cuadrilla/contratista y tarja real; la OP no los produce |
| Maquinaria | ⛔ bloqueado | `step.hrs.machinery.line` exige vehículo/conductor real (ya auditado en V2 E) |
| Proveedores | ➖ N/A | No es un dominio separado — cubierto dentro de Cosecha (`type_tarea='contratista'`) |
| Inventario | ⛔ bloqueado | `agri_inventory_operations` es "(DEV)": sin `company_id`, ACL abierta, maestros no alineados |
| Fletes | ⛔ bloqueado | `x_orden_de_flete` es sólido, pero la OP no produce ningún dato de flete |
| BPA | ⏸ candidato, no construido | Datos suficientes, pero sin estado de anulación en destino — requiere decisión humana (automático/manual, dependencia dura/defensiva) |
| Riego | ⛔ bloqueado | `x_riego_y_fertilizacio` sin campo `state`; la OP tampoco distingue riego como labor separada |

## Avance vigente — Corte 2 (18.0.14.0.0)

Ver `HANDOFF_FASE7_CORTE2.md` para el detalle completo (R1–R6 + Orden de
Producción). Resumen:

| Requisito | Estado vigente | Evidencia |
|---|---|---|
| R1 — confirmación aplica exactamente la vista previa | ✅ | `models/planning.py::_weekly_task_fingerprint`, `wizard/plan_weekly_preview.py` |
| R2 — normalizar UdM antes de consolidar stock | ✅ | `models/stock_requirement.py::_bucket_quantity`, `models/crop_program_import.py` (UdM por defecto del producto) |
| R3 — faltante acumulado cronológico | ✅ | `models/stock_requirement.py::action_compute` (consumo cronológico por producto) |
| R4 — coherencia completa de variedad | ✅ | `models/crop_program.py::check_center_variety_coherence` (compartida con el importador) |
| R5 — importador Excel endurecido | ✅ | `models/crop_program_import.py` (enteros estrictos, `import_key_hash` + índice único parcial) |
| R6 — D20 documentado sin tocar `step_hr` | ✅ (sólo doc) | `DECISION_LOG.md` §D20 |
| Orden de Producción semanal (OP) | ✅ | `models/production_order.py`, `wizard/production_order_preview.py`, `views/production_order_report.xml` |
| PDF de la OP desde snapshot autorizado | ✅ | `production_order.py::_report_payload`, verificado sobre HTML renderizado |
| Envío simulado de la OP (sin SMTP real) | ✅ | `production_order.py::action_send_report` (encola `mail.mail`, nunca llama `.send()`) |
| API interna para el futuro puente OT | ✅ (contrato, sin integración) | `production_order.py::get_bridge_payload` |
| Integración con cosecha en la OP | ⛔ bloqueado | `harvest.plan.line` no tiene `center_id`; sin reparto arbitrario (ver `DECISION_LOG.md`) |
| Puente de maestros con Actividades | ⛔ pendiente | Discrepancia real encontrada en `step_hr` (D20); entrega siguiente |

## Avance vigente — Corte 1 post Fase 6 (18.0.13.0.0)

Ver `HANDOFF_FASE7_CORTE1.md` y `DECISION_LOG.md` §"Corte 1 post Fase 6"
para el detalle. Resumen:

| Requisito | Estado vigente | Evidencia |
|---|---|---|
| Vista previa antes de regenerar tareas semanales | ✅ | `wizard/plan_weekly_preview.py`, `models/planning.py::_build_weekly_task_commands` |
| Política de precio de programas = costo estándar (default) | ✅ (sin cambio de código) | `models/crop_program.py::_resolve_unit_price`, prueba de regresión Fase 7 corte 1 |
| Programas por temporada + centro de costo, misma variedad | ✅ | `models/crop_program.py::_check_center_variety`, preflight `upgrades/18.0.13.0.0` |
| Importación Excel de programas (staging seguro) | ✅ | `models/crop_program_import.py` |
| Necesidades de stock cruzadas con inventario real | ✅ | `models/stock_requirement.py` (`warehouse_id`, `availability_metric`, `available_quantity`, `shortage_quantity`, `computed_at`) |
| Puente de maestros con Actividades | ⛔ pendiente | Discrepancia real encontrada en `step_hr` (D20); entrega siguiente |

## Avance vigente — Fase 3, corte 1

| Requisito | Estado vigente | Evidencia |
|---|---|---|
| PPT-06 importación normalizada | ✅ | `models/budget_import.py`, staging protegido, idempotencia y agregación mensual |
| PPT-11 presupuesto general | ✅ | cantidad×tarifa o monto directo, validación UI y distribución monetaria |
| PPT-14/15 inmutabilidad y snapshot | ✅ núcleo | una corrección crea copia; original inmutable; snapshot mensual convertible |
| PPT-16 conciliación | ✅ | cantidad y monto mensual concilian según modo de cálculo |
| PPT-17 unicidad | ✅ | centro por presupuesto y mes por línea con constraints SQL |
| PPT-21 grupo producto→categoría | ✅ núcleo | resolución determinista filtrada por empresa |
| SEC-01..10 | ✅ núcleo | compañía, reglas globales, roles, gates y sin bypass por contexto |
| GES-01 | 🟡 | sólo apuntes publicados y conversión a moneda de presupuesto; A1–A5 pendientes |
| GES-03 | ✅ asistente | Budget/Actual/Var$/Var%, NC, cantidad con signo y drill-down |
| UPG-01..03 | ✅ | upgrades acumulativos hasta `18.0.6.0.0` probados sobre clon desechable |
| TST-01..03 (base F2) | ✅ | 57 tests en upgrade y clean install, 0 fallos/errores |
| EST-01 curvas base | ✅ núcleo | semanas W01–W53, grupos de calibre y clases; clave dimensional única y validación exacta 100 % |
| EST maestros base | ✅ núcleo | unidad de estimación→kg, categoría/clase de fruta y calibre/grupo, aislados por compañía |
| TST F3C1 | ✅ | 66 tests en upgrade y clean install, 0 fallos/errores |

## Leyenda de estado

| Estado | Significado |
|---|---|
| ✅ Implementado | Existe modelo/campo/lógica que cubre el requisito de forma utilizable. |
| 🟡 Parcial | Existe una base, pero incompleta o sin los controles que el requisito exige. |
| ⬜ Ausente | No hay nada en el código. |
| ⚠️ Contradictorio | El requisito de la planilla se contradice consigo mismo o con contabilidad; requiere decisión (ver `DECISION_LOG.md`). |
| ⛔ Bloqueado | No se puede implementar sin una decisión humana o sin un motor externo no garantizado. |

## Alcance de la primera vertical (obligatoria)

“Presupuesto agrícola aprobado → gasto real contable → desviación auditable”.
Sólo los requisitos marcados **[V1]** entran en el primer corte de Fase 1;
el resto queda documentado para fases posteriores.

---

## 1. Menú y navegación (`Menú general de Gestión y Costos.xlsx`)

| # | Requisito | Estado | Evidencia | Nota |
|---|---|---|---|---|
| MEN-01 | Menú raíz "Gestión y Costos" con Inicio/Panel | ✅ | `views/menu_views.xml:3-4`, `models/management_dashboard.py`, `static/src/js/management_dashboard.js` | Tablero OWL cliente. |
| MEN-02 | Sección Presupuesto: plantillas, carga excel, agrícola, general, maquinaria, análisis por indicador, informes | 🟡 | `views/menu_views.xml` | Plantillas + carga Excel (F2C1) + **presupuesto agrícola y general como entradas separadas** (F2C3) + 2 análisis pivote. Falta maquinaria e informes documentales. |
| MEN-03 | Sección Estimaciones | ⬜ | — | Fuera de alcance V1. |
| MEN-04 | Sección Planificación: tareas, plan de cosecha, fito, fertilización, OP, informes | 🟡 | `views/planning_views.xml`, `models/planning.py` | Sólo “tareas planificadas” manuales (`step.management.plan`). Resto ausente. |
| MEN-05 | Sección Gestión: gasto real, informes comparativos, gasto histórico | 🟡 | `views/historical_cost_views.xml`, `models/historical_cost.py` | Sólo `historical.cost` manual. “Gasto real” contable ausente. **[V1]** |
| MEN-06 | Maestros y Configuración | 🟡 | `views/menu_views.xml:14-17` | Centros, grupos, tipos de cambio. Faltan temporada, fundo, especie, variedad, actividad, origen, versión, UdM cálculo. |

---

## 2. Presupuesto (`1.6.2 Presupuesto plantillas y generales.docx` + anexos)

| # | Requisito | Estado | Evidencia | Nota |
|---|---|---|---|---|
| PPT-01 | Plantilla presupuestaria por hectárea, con indicadores (categoría, grupo, actividad, producto, UdM, tarifa) | ✅ | `models/budget_template.py:12-106` (`step.management.budget.template`) y `:108-199` (`.line`) | `base_hectares` normaliza. |
| PPT-02 | Distribución mensual en la plantilla (temporada mayo–abril) | 🟡 | `budget_template.py:139-150` (12 columnas `may..apr`), `MONTH_FIELDS` | Meses como **columnas físicas**, no líneas; temporada fija mayo–abril; sin año-mes real. |
| PPT-03 | Verificar que se distribuya el 100% de las cantidades | ⬜ | — | `_compute_amounts` (`:167-174`) toma `monthly if monthly else base_quantity`: si no hay meses usa el anual; **nunca valida el 100%**. **[V1]** (integridad). |
| PPT-04 | Función “duplicar plantilla” | 🟡 | Odoo `copy` genérico | Sin acción dedicada ni cambio de versión controlado. |
| PPT-05 | Cargar plantilla desde Excel (`Anexo 1.6.2.2`) | ⬜ | — | Fase 2. |
| PPT-06 | Cargar presupuesto desde Excel normalizado (`Anexo 1.6.2.1`: 18 columnas Versión…Valor US$) | ⬜ | — | Fase 2. Contrato de staging. |
| PPT-07 | Aplicar plantilla a uno o varios centros, amplificando por hectáreas | ✅ | `models/operational_budget.py:145-191` (`action_generate_lines`) | Escala `allocation.hectares / base_hectares`. |
| PPT-08 | Reintento de aplicación sin duplicar líneas | 🟡 | `operational_budget.py:157` (`budget.line_ids.unlink()` antes de regenerar) | Funciona por borrado+recreación; pierde ediciones manuales y `id`s. Sin clave natural. |
| PPT-09 | Estados: Ingresado / Aprobado / Anulado / Reemplazado | 🟡 | `operational_budget.py:92-96` (`draft/calculated/approved/closed/cancelled`) | No hay “Reemplazado”; hay `calculated`/`closed` extra. **[V1]**. |
| PPT-10 | Versión de presupuesto (maestro `anexo maestros presupuestos.xlsx`: nº, fecha tope, estado fenológico) | ⬜ | `operational_budget.py:59` (`season` es `Char` libre) | Sin maestro de versión ni clave natural (D06). **[V1]** parcial: revisión + reemplazo trazable. |
| PPT-11 | Presupuesto “general” (centros no agrícolas, formulario libre) | ✅ | `operational_budget.py` `budget_type` (`agricultural`/`general`); F2C3 | `general` no exige hectáreas en centros ni líneas, no admite plantilla/carga, no usa “Calcular”. Menús separados. |
| PPT-12 | Presupuesto de maquinaria (modelo de gasto/horas, `Anexo 1.6.2.5`) | ⬜ / ⚠️ | — | Fase 6. El anexo tiene un `#DIV/0!` (ver DECISION_LOG). |
| PPT-13 | Conversión a USD/EUR con dólar estimado por mes, separado de la tasa real Odoo | ✅ | `models/exchange_rate.py` (`step.management.exchange.rate`), `get_conversion` `:141-160` | Estimado mensual vs `actual` (`_convert`). Cumple “tasa presupuestada ≠ tasa real”. |
| PPT-14 | Aprobación inmutable; nueva versión reemplaza, no sobrescribe | ⬜ | `operational_budget.py:193-197` (`action_approve` sólo hace `write state`) | Sin `approved_by/at`, sin bloqueo de edición, sin snapshot, sin cadena de revisión. **[V1]**. |
| PPT-15 | Congelar entradas que reproducen el cálculo al aprobar (snapshot líneas/cantidades/moneda/TC) | ⬜ | — | **[V1]**: contrato + mínimo (blob + hash). Modelo `revision`/`snapshot.line` → Fase 2. |
| PPT-16 | Total anual concilia con la suma mensual (sin divergencia) | ⬜ | `operational_budget.py:294-297` (`amount = quantity*unit_price`), meses independientes | **[V1]**: fuente única + constraint con tolerancia. |
| PPT-17 | Unicidad de centro por presupuesto robusta a concurrencia | 🟡 | `operational_budget.py:238-247` (`_check_unique_center` con `search_count`) | Vulnerable a carrera. **[V1]**: reemplazar por `unique(budget_id, center_id)` SQL. |
| PPT-18 | Cuenta analítica obligatoria (misma empresa) para operar | 🟡 | `models/cost_center.py:27-30` (`analytic_account_id` opcional, `domain` company) | **[V1]**: exigir en aprobación de nuevas operaciones, sin `required=True` retroactivo; pre-check de upgrade. |
| PPT-19 | Análisis por indicador / ccosto / labor / distribución mensual (pivote, gráfico) | 🟡 | `views/operational_budget_views.xml:25-33` | Pivotes sobre `budget.line` y `budget.month`. Sin “Jornadas estimadas”, “Presupuesto por labor” como informes formales. |
| PPT-20 | Informes documentales de presupuesto (`Anexo 1.6.2.6`: data, resumen, jornadas, ccosto, labor) | ⬜ | — | Fase 7 (catálogo D18). |
| PPT-21 | Grupo presupuesto en categoría de producto; resolución producto→subcategoría→categoría | ⬜ | `models/budget_group.py` existe como maestro, sin herencia a `product.category`/`product.template` | Fase 2 (necesario para imputar gasto real). |
| PPT-22 | Maestros: Temporada, Fundo, Especie, Variedad, Categoría fruta, Tipo CCosto, Actividad, Producto-labor, UdM, Origen, Versión, UdM Cálculo, Dólar | 🟡 | `cost_center.py` (`farm/plot/species/variety` son `Char`), `budget_group.py`, `exchange_rate.py` | Sólo tipo ccosto (selección), grupo, dólar. Fundo/especie/variedad/actividad/temporada son texto libre → sin FK, sin unicidad, sin multiempresa propia (D13). |

---

## 3. Multiempresa, roles y auditoría (Plan §6)

| # | Requisito | Estado | Evidencia | Nota |
|---|---|---|---|---|
| SEC-01 | `company_id` en modelos persistentes | 🟡 | Presente en `cost.center`, `budget.group`, `budget.template`, `exchange.rate`, `operational.budget`, `historical.cost`, `plan`; **ausente** en `budget.template.line`, `budget.center`; `related` no almacenado en `budget.month` | **[V1]**. |
| SEC-02 | `_check_company_auto = True` en modelos con empresa | ⬜ | grep: ningún modelo lo declara | **[V1]**. |
| SEC-03 | `check_company=True` en relaciones compatibles | ⬜ | grep: ningún `Many2one` lo declara | **[V1]**. |
| SEC-04 | Reglas de aislamiento por compañía **globales** | 🟡 | `security/management_security.xml:20-31`: reglas `ir.rule` atadas a `group_management_user`, dominio `[('company_id','in',company_ids)]` | Son reglas *de grupo* (se unen, pueden ampliar), no globales; no cubren `budget.template.line` (sí), `budget.center` (sí vía `budget_id`), pero excluyen al admin. **[V1]**: volverlas globales con dominio estándar `['|',('company_id','in',company_ids),('company_id','=',False)]`. |
| SEC-05 | Constraints de compañía en relaciones indirectas que Odoo no valida | ⬜ | — | **[V1]**: `plan.center_ids` (M2M), `budget.line.template_line_id` vs empresa del presupuesto, `historical.cost.center_id`. |
| SEC-06 | Roles: conservar `group_management_user` / `group_management_manager` | ✅ | `security/management_security.xml:6-15` | **[V1]**: se conservan XML IDs. |
| SEC-07 | Introducir consulta, planificador/presupuestador, aprobador, administrador con implicaciones compatibles | ⬜ | Sólo 2 grupos | **[V1]**: `group_management_readonly`, `group_management_approver` (planner = `user` por ahora); cadena `readonly ⊂ user ⊂ approver ⊂ manager`. |
| SEC-08 | ACL por modelo: un usuario común no aprueba, reabre, cambia tasas ni borra detalle aprobado | 🟡 | `security/ir.model.access.csv`: `user` sin `unlink` salvo en `budget.center/month/plan.line`; tasas `user` read-only ✅ | **[V1]**: método-gates + bloqueo de `unlink` de detalle aprobado. |
| SEC-09 | Métodos públicos comprueban rol y transición, incluso por RPC | ⬜ | `action_approve/close/cancel/set_draft` no verifican grupo ni transición (salvo `action_generate_lines`) | **[V1]**. |
| SEC-10 | Auditoría de aprobación: `approved_by`, `approved_at`, revisión, motivo, hash/snapshot | ⬜ | — | **[V1]**. |
| SEC-11 | `mail.thread` en documentos clave | ✅ | `cost.center`, `budget.template`, `operational.budget`, `historical.cost`, `plan` heredan `mail.thread`/`mail.activity.mixin` | `budget.group`, `exchange.rate` no (aceptable). |

---

## 4. Gestión — gasto real y desviación (`1.6.10 Gestión.docx` + anexos)

| # | Requisito | Estado | Evidencia | Nota |
|---|---|---|---|---|
| GES-01 | Gasto real desde apuntes contables publicados (cuentas de ingreso/gasto), con actualización al (des)contabilizar | ⬜ / ⚠️ | — | **[V1]** (lectura conciliable, no tabla duplicada). Contradicción: el anexo modela una “base de datos de gestión” que se “actualiza junto con la contabilidad” — se resuelve con servicio de lectura analítica + enriquecimiento (D01, D15). |
| GES-02 | Base “gasto real”: 25 campos (Tipo Registro, Comprobante, Tipo Doc, Num Doc, Glosa, Fecha, OP, OT, Temporada, Año, Mes, Fundo, Especie, Variedad, Tipo CCosto, Centro, Origen, Grupo Ppto, Actividad, Producto-labor, UdM, Cantidad, Valor Real $, TC Real, Valor Real US$) | ⬜ | `Anexo 1.6.10.1` | **[V1]** sólo el mapeo campo→fuente (D15), no la tabla. |
| GES-03 | Informes comparativos real vs presupuesto (Budget / Actual / Var $ / Var %) por mes, centro, grupo, producto/labor, con drill-down al asiento | 🟡 | `models/historical_cost.py:60-66` (`variance`, `variance_percent`) sobre datos **manuales** | **[V1]**: recalcular Var % desde totales (no sumar %), drill-down a `account.move`. |
| GES-04 | Costo histórico externo (carga Excel normalizada `Anexo 1.6.10.3`, 18 columnas) con procedencia y bloqueo | 🟡 | `historical_cost.py` (`step.management.historical.cost`) editable a mano, sin `source`, sin archivo, sin bloqueo, sin import | **[V1]**: reservar el modelo para externo/legado, añadir procedencia; import → Fase 2. |
| GES-05 | No duplicar contabilidad, monedas, productos, UdM ni cuentas analíticas | 🟡 | El addon reutiliza `res.currency`, `product.product`, `uom.uom`, `account.analytic.account`; **pero** `historical.cost` puede volverse un segundo libro si se usa para todo | **[V1]**: ADR fija analítica como fuente del real. |
| GES-06 | Marcar línea real como “fuera de OP” por clave dimensional | ⛔ | — | D11, Fase 6. Requiere OP. |
| GES-07 | Comprometido (PO confirmada no facturada) o `account_budget` | ⛔ | — | D17, Fase 2. Ocultar si no existe motor. |

---

## 5. Estimaciones / Planificación / Fito / Ferti / Cosecha / OP

Todo el bloque está **⬜ Ausente** salvo la planificación manual de tareas
(`step.management.plan`, 🟡 sin vínculo real al presupuesto vigente). Fuera de
alcance de esta entrega por instrucción explícita del prompt. Contradicciones
de los mockups registradas en `DECISION_LOG.md`.

| # | Requisito | Estado |
|---|---|---|
| EST-01..EST-09 Estimaciones, curvas, calibres, clases, versiones, importación, informes | ⬜ |
| PLA-01 Tareas semanales desde presupuesto vigente | 🟡 (`models/planning.py`, sin derivación) |
| PLA-02 Plan de cosecha y recursos | ⬜ |
| FIT-01 Programa fitosanitario / OT-BPA | ⬜ |
| FER-01 Programa fertilización | ⬜ |
| STK-01 Necesidades de stock semana/mes/temporada | ⬜ |
| OP-01 Orden de producción semanal + integración OT | ⬜ |

---

## 6. Versionado, upgrade y pruebas (Plan §5.1, §9)

| # | Requisito | Estado | Evidencia | Nota |
|---|---|---|---|---|
| UPG-01 | Manifiesto `18.0.2.0.0` con upgrade correspondiente | ⬜ | `__manifest__.py:4` (`18.0.1.1.0`) | **[V1]**: subir sólo cuando exista `upgrades/18.0.2.0.0/`. |
| UPG-02 | `upgrades/18.0.2.0.0/pre-*.py` / `post-*.py` idempotentes, sin IDs numéricos, sin `commit()` | ⬜ | No hay carpeta `upgrades/` ni `migrations/` | **[V1]**. |
| UPG-03 | Conservar modelos, tablas, registros, secuencias y XML IDs | n/a | `data/management_sequences.xml` (`seq_operational_budget`, `seq_management_plan`) | **[V1]**: la migración no renombra ni borra. |
| TST-01 | `step_management_costs/tests/` activado | ⬜ | No existe `tests/` | **[V1]**. |
| TST-02 | Cobertura: 2 empresas, relaciones cruzadas, cada rol `with_user`, RPC de aprobación, edición/unlink tras aprobar, reapertura con motivo, conciliación mensual, cero hectáreas, idempotencia, preservación de datos | ⬜ | — | **[V1]**. |
| TST-03 | No sustituir pruebas por `scripts/validate_template_budget.py` (escribe y hace `commit()`) | ⚠️ | `scripts/validate_template_budget.py:144` (`env.cr.commit()`) | **[V1]**: se deja el script como está; las pruebas nuevas son `TransactionCase`. |

---

## 7. Resumen cuantitativo

| Estado | Requisitos (aprox.) |
|---|---|
| ✅ Implementado | 8 |
| 🟡 Parcial | 23 |
| ⬜ Ausente | 34 |
| ⚠️ Contradictorio | 4 (GES-01, PPT-12, + fórmula estimación y fertilización, fuera de V1) |
| ⛔ Bloqueado | 2 (GES-06, GES-07) |

**Entra en el primer corte de Fase 1 (V1):** SEC-01..SEC-11, PPT-03, PPT-09,
PPT-10 (parcial), PPT-14, PPT-15 (contrato+mínimo), PPT-16, PPT-17, PPT-18,
GES-03 (recálculo Var %), GES-04 (procedencia), UPG-01..UPG-03, TST-01..TST-03.
El mapeo requisito → cambio → prueba está en `../gestion_costos/` (se completa
en el handoff de esta entrega).
