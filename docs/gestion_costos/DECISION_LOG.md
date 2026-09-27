# Decision Log — Steps Gestión y Costos

**Fase:** 0. Estado de cada decisión: **Propuesta** (Claude), **Requiere
validación humana** (dueño funcional / Contabilidad / Codex) o **Cerrada para
V1** (aplicada en el primer corte de Fase 1, sin bloquear fases futuras).

Nada de lo aquí escrito se inventó como “respuesta del cliente”. Cuando una
planilla se contradice, se registra la contradicción y se deja la decisión
abierta.

Referencias: `docs/PLAN_DESARROLLO_GESTION_COSTOS_2026-09-02.md` §4 (tabla
D01–D18) y §4.1; `ADR_001_ARQUITECTURA_Y_CONTABILIDAD.md`.

---

## Decisiones del plan (D01–D18)

### D01 — Fuente del gasto real
- **Propuesta:** valor desde `account.move.line` publicado; imputación desde
  distribución analítica; enriquecimiento de producto/cantidad/UdM/OP/OT
  desde el documento origen por contratos; `historical.cost` sólo
  externo/ajuste. Ver ADR D-B, D-C.
- **Requiere validación:** Contabilidad — confirmar cuentas de resultado en
  alcance, tratamiento de NC/reversa/multimoneda, y si “ingresos” entra en V1
  o sólo costo.
- **Momento:** antes de Fase 2.
- **Estado V1:** sólo contrato + mapeo de 25 campos (`DATA_MODEL.md`). No se
  implementa lectura ni tabla.

### D02 — Presupuesto estándar (`account_budget`)
- **Propuesta:** detectar `account_budget` por base; usar puente
  `auto_install` + adaptador si está; nunca dependencia rígida. Ver ADR D-D.
- **Requiere validación:** TI/Contabilidad — ¿está instalado y con edición en
  Desarrollo / Demo / Demo-SyS? (no verificable en este equipo).
- **Momento:** Fase 0 → arrastrado a Fase 2 por falta de runtime.
- **Estado:** abierta; comando de preflight en ADR §Verificación.

### D03 — Temporada
- **Propuesta:** maestro `step.management.season` con rango de fechas
  configurable; valor inicial mayo–abril; configurable por empresa. Clave
  natural (empresa, código). Fallback portable; el puente
  `_agriculture` la mapea a `step.temporada`.
- **Requiere validación:** dueño funcional — nombre del maestro canónico y si
  la temporada es también cuenta analítica (el anexo 1.6.2.1 dice
  “temporada… que también es cuenta analítica”).
- **Momento:** Fase 1 (diseño) / Fase 2 (implementación).
- **Estado V1:** no se crea el maestro. `operational.budget.season` sigue
  siendo `Char`. Se documenta la deuda.

### D04 — Semanas
- **Propuesta:** ISO-8601; semana 53 soportada; semanas que cruzan mes se
  prorratean por días. `period_service` en Fase 4.
- **Requiere validación:** Operaciones — regla de prorrateo (por días
  naturales vs días hábiles) y manejo de la semana que cruza año.
- **Momento:** Fase 0 (regla) / Fase 4 (código).
- **Estado:** abierta. No aplica a V1 (V1 es mensual, temporada mayo–abril).
- **Confirmado (Corte 1 post Fase 6, 2026-09-04):** temporada común
  mayo–abril; reparto semanal por días naturales; semanas ISO 8601 lunes a
  domingo incluyendo W53 y el cruce 52/53/01; el residuo de redondeo va a la
  última semana del período. Ya implementado en `period_service.py`
  (`season_bounds`, `iso_weeks`, `distribute_monthly_to_weeks`); este corte
  sólo cierra la decisión y agrega cobertura donde faltaba, sin
  reimplementar.

### D05 — Fórmula de estimación
- **Propuesta:** `Total UE × factor de conversión a kg`; **no** volver a
  multiplicar por rendimiento (el texto de `1.6.4` duplica el rendimiento; el
  anexo visual usa conversión a kg — contradicción).
- **Requiere validación:** Agronomía.
- **Momento:** Fase 3.
- **Estado:** abierta, fuera de V1.

### D06 — Versión vigente / clave natural
- **Propuesta:** clave natural distinta por objeto:
  - presupuesto: `(company_id, season, template_id, revision)`,
  - plantilla: `(company_id, name, version)`,
  - estimación/programa/OP: a definir en su fase.
  Una “vigente” por clave (excluyendo `revision`).
- **Requiere validación:** Control de gestión — ¿la clave del presupuesto
  incluye `fundo`/`especie` o basta centro+temporada? El anexo mezcla ambos.
- **Momento:** Fase 2.
- **Estado V1:** se implementa `revision` + `revision_of_id` +
  `superseded_by_id` y el bloqueo de reemplazo (ADR D-H); la **constraint de
  unicidad de la clave natural completa** queda para Fase 2 (necesita el
  maestro de temporada, D03).

### D07 — Precio de programas fito/ferti
- **Propuesta:** política configurable; snapshot de fuente, precio, moneda,
  fecha y UdM al aprobar.
- **Requiere validación:** Compras/Contabilidad.
- **Momento:** Fase 5. Fuera de V1.
- **Confirmado (Corte 1 post Fase 6, 2026-09-04):** la política **oficial**
  al aprobar es el **costo estándar del producto** (`price_policy =
  'standard'`), ya implementada como default en
  `crop_program.py::_resolve_unit_price` desde Fase 5, con el precio
  congelado por aplicación y en el snapshot. Se **conservan** `last_invoice`
  y `manual` como alternativas configurables por programa (no se retiran):
  no hay instrucción del cliente de eliminarlas, y ya están snapshoteadas e
  probadas. Sin cambio de código en este corte; sólo se agrega una prueba de
  regresión (`test_price_policy_default_is_standard_and_freezes_standard_price`,
  Fase 7 corte 1) que fija el comportamiento.

### D08 — Redondeo de recursos
- **Propuesta:** personas/envases indivisibles → hacia arriba; insumos →
  precisión de la UdM.
- **Requiere validación:** Operaciones.
- **Momento:** Fase 4. Fuera de V1. (En V1 la tolerancia de cantidades usa
  `uom.rounding` / `currency.rounding` con `float_compare`.)
- **Confirmado (Corte 1 post Fase 6, 2026-09-04):** envases → `ceil(kg /
  kg_por_envase)` (ya implementado en `harvest_plan.py`); insumos (no
  personas ni envases) → precisión de la UdM (`uom.rounding` +
  `float_compare`, ya el criterio general del addon). C2 aún **no**
  resuelve personas/cuadrillas — el cliente indicó explícitamente que ese
  cálculo sigue pendiente (no se planifican personas todavía).

### D09 — Segregación de funciones
- **Propuesta:** el creador **no** aprueba su propio documento salvo permiso
  excepcional auditado (`group_management_approver` + traza en chatter). Ver
  ADR D-H.
- **Requiere validación:** Administración — ¿se permite la excepción y con
  qué registro? ¿aplica también a `historical.cost`?
- **Momento:** Fase 1.
- **Estado V1:** **Cerrada parcialmente.** Se implementa el rol aprobador y el
  gate de rol/transición en `action_approve`. La regla “el creador no aprueba”
  se implementa como **advertencia configurable** (parámetro
  `step_management_costs.enforce_segregation`, default *off* para no romper
  instalaciones de un solo usuario); Codex/dueño deciden si pasa a bloqueo
  duro.

### D10 — Importaciones
- **Propuesta:** vista previa + staging + errores por fila + clave
  idempotente (clave natural + hash de archivo/línea); nunca importación
  directa a definitivo; todo-o-nada por lote salvo opción explícita.
- **Requiere validación:** dueño funcional — plantilla versionada por caso
  (`Anexo 1.6.2.1`, `1.6.10.3`).
- **Momento:** Fase 2. Fuera de V1.

### D11 — “Fuera de OP”
- **Propuesta:** marcar una línea real como fuera de OP por **clave
  dimensional** (centro, temporada, actividad, grupo), no por texto.
- **Requiere validación:** Operaciones/Contabilidad.
- **Momento:** Fase 6. Bloqueado hasta que exista OP.

### D12 — Demo-SyS
- **Propuesta:** instalar **sólo el núcleo** si aporta valor funcional y pasa
  compatibilidad; nunca `step_agricultural_access` ni datos/scripts
  agrícolas. Ver ADR D-E.
- **Requiere validación:** dueño de producto.
- **Momento:** Fase 8. Fuera de V1 (sin despliegue).

### D13 — Dueño de maestros
- **Propuesta:** ADR de propiedad por maestro (centro, temporada, fundo,
  cuartel, especie, variedad, actividad): modelo canónico + fallback portable
  + clave de correspondencia + política de deduplicación + migración. En el
  núcleo, fallback `Char`/maestro propio mínimo; el puente `_agriculture`
  sustituye por FK a `step_hr`.
- **Requiere validación:** TI/Datos — confirmar que `step.cuartel.line` no es
  maestro de primera clase (ver `AUDITORIA_PRODUCTO_AGRICOLA.md` §2) y decidir
  su promoción.
- **Momento:** Fase 0 (ADR por maestro) → pendiente, arrastrado a Fase 2.
- **Estado V1:** no se tocan los `Char` de `cost.center`
  (`farm/plot/species/variety`).

### D14 — Datos heredados / normalización
- **Propuesta:** las líneas y períodos normalizados (mes/semana como líneas)
  son canónicos; los campos antiguos (12 columnas de mes) quedan `compute` o
  `readonly` tras migración verificada de igualdad de totales.
- **Requiere validación:** TI/Control de gestión — aceptar la ventana de
  compatibilidad y el criterio de “totales iguales antes/después”.
- **Momento:** Fase 1 (decisión) / Fase 2 (normalización real).
- **Estado V1:** **no** se normalizan aún las columnas de mes de la plantilla;
  se documenta. V1 sólo añade la constraint total = Σ meses en `budget.line`.

### D15 — Hecho real de 25 campos
- **Propuesta:** mapear cada uno de los 25 campos de `Anexo 1.6.10.1` a
  contabilidad / analítica / módulo origen, cubriendo signo, reversa, NC y
  moneda. Tabla en `DATA_MODEL.md` §“Mapeo del gasto real (25 campos)”.
- **Requiere validación:** Contabilidad/Operaciones — confirmar el mapeo,
  sobre todo OP/OT (dependen de módulos aún inexistentes) y
  Origen/Grupo Presupuesto (dependen de D21/PPT-21).
- **Momento:** Fase 0.
- **Estado V1:** **Cerrada como mapeo propuesto** (documento), no como código.

### D16 — Estados
- **Propuesta:** matriz estado–acción–rol–efecto para plantillas,
  presupuesto, estimación, programas, OP y OT-BPA. En V1 sólo plantilla y
  presupuesto (tabla abajo, §Matriz de estados V1).
- **Requiere validación:** dueño funcional — nombres de estado de cara al
  usuario (“Ingresado” vs “Borrador/Calculado”), y si “Anulado” permite
  reactivar.
- **Momento:** Fase 0.
- **Estado V1:** **Cerrada para plantilla y presupuesto.** Resto abierto.

### D17 — Comprometido
- **Propuesta:** capacidad opcional ligada a `account_budget`, o fallback
  probado desde PO confirmada no facturada; ocultar de UI/reportes si no
  existe (nunca cero engañoso). Ver ADR D-D.
- **Requiere validación:** Compras/Contabilidad.
- **Momento:** Fase 2. Fuera de V1.

### D18 — Catálogo de informes
- **Propuesta:** por cada salida/PDF: dataset, filtros, moneda, fórmula y
  regla de conciliación. Fuera de V1; se arrastra a Fase 7. La única regla que
  V1 aplica: **Var % se recalcula desde los totales**, nunca sumando
  porcentajes.
- **Requiere validación:** Control de gestión.
- **Momento:** Fase 0 → pendiente.

---

## Matriz de estados V1 (D16, alcance cerrado)

### `step.management.budget.template`

| Estado | Acción | Rol mínimo | Efecto |
|---|---|---|---|
| `draft` | `action_activate` | user | → `active` |
| `active` | `action_set_draft` | user | → `draft` (sin bloqueo; la plantilla no congela nada) |
| cualquiera | `action_archive_template` | user | → `archived`, `active=False` |

*Sin cambios de fondo en V1 salvo `_check_company_auto`.*

### `step.management.operational.budget`

| Estado | Acción | Rol mínimo | Precondición | Efecto |
|---|---|---|---|---|
| `draft`/`calculated` | `action_generate_lines` | user | plantilla con líneas, ≥1 centro, hectáreas > 0 | recrea `line_ids`, → `calculated` |
| `calculated` | `action_approve` | **approver** | distribución mensual completa; cada centro con cuenta analítica de la empresa; (opcional) creador ≠ aprobador | fija `approved_by_id`/`approved_at`, congela `approval_snapshot`+`approval_hash`, → `approved` |
| `approved` | `action_close` | approver | — | → `closed` (sigue inmutable) |
| `approved` | `action_reopen(reason)` | **approver** | `reason` no vacío | crea revisión `draft`; el original sigue aprobado e inmutable |
| `approved` | `action_new_revision` | approver | — | copia con `revision+1`, `revision_of_id`; al aprobar la copia el origen → `superseded` |
| `calculated`/`cancelled` | `action_set_draft` | user | no aprobado | → `draft` |
| `draft`/`calculated` | `action_cancel` | user | — | → `cancelled` (un aprobado sólo se corrige mediante revisión) |
| `approved`/`closed`/`superseded` | `write`/`unlink` de cabecera, centros, líneas, meses, moneda, tasas, cantidades | — | — | **bloqueado** (`UserError`) |

Roles: `readonly ⊂ group_management_user ⊂ group_management_approver ⊂
group_management_manager`. `manager` puede todo lo de `approver`.

---

## Contradicciones registradas (no se adivinan)

De `PLAN_DESARROLLO` §4.1 y de la lectura directa de los anexos:

| # | Contradicción | Evidencia | Decisión |
|---|---|---|---|
| C1 | Fórmula de estimación: el texto de `1.6.4` duplica el rendimiento; el anexo usa conversión a kg | `2 Estimación/1.6.4 …docx` vs `Anexo 1.6.4.1` | D05 abierta; no se hereda el doble producto. |
| C2 | Fertilización no multiplica por hectáreas en una planilla, aunque el requisito lo exige (fito sí lo hace) | `Anexo 1.6.6.*` vs `Anexo 1.6.5.*` | Se corrige al implementar (Fase 5): amplificar por hectáreas siempre. |
| C3 | El plan de cosecha omite semanas visibles después de W50 en su suma | `Anexo 1.6.9 plan de cosecha.xlsx` | Fase 4: sumar todas las semanas del rango de la temporada. |
| C4 | Reportes que suman hectáreas dentro de los importes | `Anexo 1.6.2.6`, `Anexo 1.6.10.2` | Fase 7: hectáreas nunca es una medida monetaria; datasets separan magnitud y moneda. |
| C5 | La variación % total se obtiene sumando porcentajes | `Anexo 1.6.10.2` | **Cerrada V1:** Var % se recalcula `variance / budget` desde los totales. |
| C6 | `#DIV/0!` en el presupuesto de maquinaria | `Anexo 1.6.2.5 Prespuesto maquinaria.xlsx` | Fase 6: horas presupuestadas = 0 debe ser error de datos, no división. |
| C7 | Estados de estimación, OP y OT-BPA inconsistentes entre texto e imágenes | docs de `2`, `3.3`, `3.5` | D16 abierto para esos objetos; V1 sólo cierra plantilla/presupuesto. |
| C8 | Hoja de plan de cosecha con rango hasta la fila 1.048.576 por formato residual | `Anexo 1.6.9` | D10: el importador acota filas/celdas y no confía en `max_row`. |
| C9 | `1.6.10 Gestión.docx` pide una “base de datos de gestión” que se actualiza junto con la contabilidad (segundo libro) | `4 Gestion/1.6.10 …docx` | **Cerrada V1 (ADR D-B):** el real se lee de analítica; no hay segunda tabla de montos. |
| C10 | No están definidos: precio de producto, redondeos, semana 53, semana que cruza mes, idempotencia de importación, regla exacta de “fuera de OP” | varios | D07, D08, D04, D10, D11 — todas abiertas. |
| C11 | El addon actual completa la distribución mensual en silencio (usa `base_quantity` si no hay meses) | `models/budget_template.py:167-174` | **Cerrada V1 (ADR D-I):** distribución incompleta = error visible en aprobación. |
| C12 | `season` es texto libre en `operational.budget` pero el anexo lo trata como maestro que además es cuenta analítica | `models/operational_budget.py:59` vs `Anexo 1.6.2.1` | D03 abierta. V1 no cambia el tipo. |

---

## Corte 1 post Fase 6 (2026-09-04) — respuestas del cliente

Fuente: `Preguntas_Cliente_Gestion_Costos_2026-09-04, respuestas (1).docx` y
`Formulario OP.pdf` (relevo completo en
`CONTINUACION_CLAUDE_RESPUESTAS_CLIENTE_2026-09-04.md`). Este corte entrega
los frentes que viven dentro del núcleo `step_management_costs`
(`18.0.12.0.0` → `18.0.13.0.0`); el puente de maestros con Actividades
(ver D20) queda para la siguiente entrega.

### D19 — Necesidades de stock vs. inventario real (nuevo)
- **Confirmado:** el cliente pidió cruzar la demanda consolidada
  (`step.management.stock.requirement`) con existencias reales de Odoo para
  obtener el faltante, pero no definió almacén, ubicación ni fecha de
  disponibilidad (F3 pendiente).
- **Decisión de implementación:** el cruce es **explícito y auditable**, no
  implícito. `stock.requirement` gana `warehouse_id` (vacío = todos los
  almacenes de la empresa, nunca una ubicación ambigua) y
  `availability_metric` (`on_hand` = `qty_available`, `free` = existencia −
  reservado, `forecasted` = `virtual_available`) — cada métrica con su
  propio significado, nunca mezcladas bajo una sola etiqueta. Cada línea
  gana `available_quantity` y `shortage_quantity = max(0, total −
  disponible)`; la cabecera registra `computed_at` (instante de la lectura).
- **Estado:** implementado en este corte (`models/stock_requirement.py`,
  dependencia nueva del manifiesto: `stock`).

### D20 — Maestro "Actividad": discrepancia real en `step_hr`
- **Hecho técnico observado (auditoría de código, no interpretación):** al
  auditar `step_hr` (worktree `C:\Users\tito4\Documents\Odoo\step_hr`, sólo
  lectura) se encontró que el campo vivo
  `product.template.actividad_id` (`models/product_template.py`) es
  `Many2one` a **`account.analytic.account`** (el mismo modelo que
  representa "centro de costo" en `step_hr`). El modelo `step.actividad`
  también existe en `step_hr`, pero no está conectado a ningún producto —
  su `Many2one` real está comentado en el código fuente.
- **Incógnita funcional (no resuelta):** la respuesta del cliente da por
  hecho que "Actividad" es un maestro independiente (`producto-labor,
  pestaña Agrícola, campo Actividad`), que calzaría con `step.actividad`. No
  hay evidencia en el código de que `product.template.actividad_id` (hoy
  apuntando a `account.analytic.account`) sea realmente ese maestro
  funcional, o si es un dato legado/mal modelado que casualmente comparte
  nombre. Sólo el dueño funcional/técnico de `step_hr` puede resolver esta
  incógnita.
- **Decisión temporal:** no se corrige `step_hr` desde este addon (fuera de
  mandato) y **no se construye el puente de maestros**
  (`step_management_costs_agriculture`, ítem 6 del documento del cliente)
  hasta tener esa confirmación. Esta incógnita no bloquea la Orden de
  Producción central (Corte 2) porque la OP usa snapshots de las fuentes que
  ya existen en `step_management_costs` (tareas planificadas y aplicaciones
  de programa), sin depender de `product.template.actividad_id`. Sí bloquea
  cualquier sustitución de maestros o dependencia agrícola nueva.
- **Momento:** Fase 8 (puente). No bloquea el Corte 2 por el motivo anterior.

### D21 — Dosis cero en la receta de un programa (nuevo, revisión R5)
- **Hallazgo:** el importador de Excel de recetas acepta `dose_per_ha == 0`
  sin error (sólo rechaza dosis negativa); no hay confirmación del cliente
  sobre si una dosis cero es válida (p. ej. una aplicación suspendida que
  se deja registrada en cero) o un error de captura.
- **Decisión temporal (sin confirmación del cliente):** se permite guardar
  y calcular en **borrador** con dosis cero (no se trunca ni se rechaza al
  importar/crear la línea), pero **se bloquea la aprobación** del programa
  si alguna línea de receta tiene `dose_per_ha == 0`
  (`crop_program.py::action_approve`). Es el mismo criterio que ya usa el
  addon para otras ambigüedades de datos (p. ej. D-I, distribución mensual
  incompleta): nunca aceptar en silencio algo ambiguo en el momento
  irreversible (aprobar), sí permitirlo mientras el documento es corregible.
- **Momento:** revisión post Corte 1 (2026-09-04), antes del Corte 2.
  Requiere confirmación de Agronomía/Compras para cerrarse definitivamente.

### Programas por temporada + centro de costo, misma variedad (D-crop-program)
- **Confirmado:** un programa fito/ferti es por **temporada y centro de
  costo**; el cuartel es un atributo del centro, no una unidad seleccionable
  aparte; todos los centros de un mismo programa deben corresponder a la
  misma variedad.
- **Estado:** `step.management.cost.center` es plano en el núcleo (no existe
  un segundo modelo "cuartel" — `plot` es un atributo `Char` del centro), así
  que no hay una jerarquía que reinterpretar. Se implementó: (a) se renombró
  la etiqueta de `crop_program.center_ids` de "Centros de costo / cuarteles"
  a "Centros de costo"; (b) nueva `@api.constrains` que exige la misma
  variedad entre los centros elegidos (los centros sin variedad informada no
  generan conflicto entre sí); (c) preflight de sólo lectura en
  `upgrades/18.0.13.0.0/post-migration.py` que registra en el log los
  programas existentes con centros de variedades mezcladas, sin bloquear el
  upgrade ni corregir nada automáticamente.

### Vista previa del plan semanal (D-weekly-preview)
- **Confirmado:** antes de borrar/recrear tareas automáticas debe existir
  una vista previa; las tareas manuales siempre se conservan (ya era el
  caso).
- **Estado:** implementado — `action_generate_weekly_tasks` ya no escribe
  directamente; abre `step.management.plan.weekly.preview.wizard`
  (transitorio) que muestra cuántas tareas se eliminarán/crearán/conservarán
  antes de confirmar.

---

## Corte V2 A (2026-09-06) — respuestas V2 del cliente

Fuente: `Preguntas_Cliente_Gestion_Costos_2026-09-06, respuestas V2.docx` y
`Anexo 1.6.9 plan de cosecha V2.xlsx` (relevo completo en
`PROMPT_CLAUDE_SONNET5_RESPUESTAS_V2_2026-09-06.md`). Nota de auditoría: el
docx referencia notas numeradas (`Ver nota 1`…`23`) para varias preguntas
(todo el bloque G de OP/OT, B2/B4, C3, K1–K3, I1–I3, H4/H5, J4, L2, M1/M2)
que **no existen** en el archivo (verificado extrayendo cada nodo de texto
del XML: sólo las notas con letra tienen cuerpo). La mayoría se resolvió
igual porque el propio documento de continuidad ya las define de forma
explícita en el plan de cortes; la única que sigue genuinamente sin
respuesta en ningún lado es **K3** (identidad de presupuesto/estimación más
allá de centro+temporada) — se deja como estaba (abierta, sin regla más
estricta).

### D22 — Cosecha por centro/semana (nuevo, resuelve el bloqueo del Corte 2)
- **Hallazgo verificado en el anexo:** `Anexo 1.6.9 plan de cosecha V2.xlsx`
  reparte kilos por **centro de costo y semana**, no un agregado único —
  demuestra el reparto que el Corte 2 no pudo usar como fuente de la OP.
- **Decisión:** `harvest.plan.line` gana `center_id` (nuevo, opcional para
  compatibilidad), `species` y `variety` (snapshot). La generación multiplica
  el `total_kg` de **cada línea de la estimación** (ya por centro) por el
  porcentaje de la curva semanal validada, con residuo determinista a la
  última semana **de cada centro** (no del total general). No se modifica
  `estimation.py`: `estimation.distribution_ids` (eje semana) sigue siendo el
  agregado de toda la estimación, compatible con lo ya validado; el reparto
  centro×semana se calcula de nuevo en `harvest_plan.py` a partir de datos
  que ya existen.
- **Compatibilidad:** los planes confirmados antes de este corte no tienen
  `center_id` en sus líneas y no se les asigna nada retroactivamente (no hay
  fuente que lo demuestre). Preflight de sólo lectura en
  `upgrades/18.0.15.0.0/post-migration.py`.
- **Ampliación:** `harvest.plan` gana el mismo patrón de
  revisión/inmutabilidad/snapshot+hash que presupuesto/estimación/programa/OP
  (antes sólo tenía `draft/confirmed` y "reabrir", sin revisión formal ni
  snapshot) — se trata como fuente de primera clase de la OP, que exige el
  mismo nivel de trazabilidad que las otras dos.
- **OP:** nueva fuente `harvest_line` (`step.management.production.order.line`),
  sólo de un plan de cosecha **confirmado** (no borrador, no reemplazado),
  mismo contrato de huella/no-duplicación/snapshot que las otras dos fuentes.
  Una OP autorizada nunca cambia si el plan de cosecha se revisa después;
  sólo una revisión nueva de la OP puede incorporar la fuente actualizada.

### C2-V2 — Recursos del plan de cosecha (nuevo)
- **Confirmado:** el plan de cosecha debe planificar envases/unidades de
  traslado, personal por cargo (cosecheros, supervisor, jefe de cuadrilla,
  anotadores, tractoristas, cargador) y maquinaria/transporte (pallets/día,
  viajes/día, tractor/coloso), con los factores registrados **al planificar**
  (snapshot), tal como lo muestra `Anexo 1.6.9 plan de cosecha V2.xlsx`.
- **Decisión de implementación:** modelo normalizado
  `step.management.harvest.resource` (nodo de una cadena: su fuente es o
  bien los kilos semanales del plan, o bien otro recurso del mismo plan) en
  vez de columnas físicas por cargo o semana. Cada recurso guarda su propio
  factor (divisor), política de redondeo visible (`precisión de la UdM` /
  `hacia arriba` / `sin redondeo` — nunca redondeo silencioso de personas,
  pallets o máquinas) y snapshot congelado por semana en
  `step.management.harvest.resource.week` (nunca editable a mano). Los
  factores del anexo (4, 60, 55, 5, 30, 2, 10) son ejemplos, **no** constantes
  del código.
- **Estado:** implementado en este corte (`models/harvest_resource.py`).

### C4-V2 — Envases reutilizables, listado aparte (nuevo)
- **Confirmado:** los envases reutilizables (bins, pallets) van en un listado
  aparte de las necesidades de stock consumible porque tienen un análisis
  distinto (retornan, no se consumen). El cliente referencia inventario ≥ 3
  veces la necesidad.
- **Decisión de implementación:** el mismo `step.management.harvest.resource`
  con `is_reusable_container=True` expone necesidad semanal máxima,
  inventario objetivo (`coverage_multiplier`, **configurable, default 3, no
  escondido**), existencia real (si hay `product_id` vinculado, lectura
  agregada de sólo consulta) y brecha contra el objetivo. Nunca se mezcla con
  `step.management.stock.requirement` ni genera compras automáticas.
- **Estado:** implementado en este corte.

### Pendientes explícitos que este corte NO resuelve
- K3 (identidad completa de presupuesto/estimación): sin respuesta en ningún
  lado; se deja como estaba (D06, abierta).
- H1 (catálogo de informes), K5 (normalización de columnas de mes), D20
  (semántica de Actividad), documento definitivo de BPA-Riego, usuarios
  reales/calendario de UAT: bloqueados explícitamente por el documento de
  continuación; no se inventa una respuesta.

---

## Corte V2 B (2026-09-07) — cargas históricas oficiales

### D-L — Hechos históricos normalizados, no reconstrucción de `operational.budget`
- **Decisión de arquitectura (registrada antes de tocar
  `historical_cost.py`, ver también `ADR_001` §D-L):** los dos archivos
  oficiales del cliente (`Anexo 1.6.2.1` presupuesto, `Anexo 1.6.10.3` real,
  L1) se cargan como **hechos históricos normalizados** —
  `step.management.historical.cost` gana `dataset_kind = 'budget'|'actual'`;
  **una fila del archivo = una fila del modelo**, nunca se reconstruye
  `operational.budget` (eso exigiría "aprobar" 16.000+ documentos
  artificiales que nunca pasaron por el flujo real). La comparación es
  agregada por dimensiones (temporada, centro, grupo, especie…), no por
  reconstrucción de documentos. Los registros manuales previos a este corte
  (comparación pareada presupuesto/real en la misma fila) siguen
  funcionando exactamente igual, con `dataset_kind` vacío.
- **Presupuesto y real no comparten fila física:** cada archivo tiene su
  propio lote (`step.management.historical.import.batch`, `dataset_kind`
  distinto), aunque ambos comparten el mismo modelo de staging seguro
  (`step.management.historical.import.line`) y casi la misma cabecera de 18
  columnas (sólo difiere la primera: "Versión Ppto" vs. "Tipo registro").
- **Real histórico:** procedencia `external`, estado inicial `entered`
  (Ingresado). Sólo el Aprobador/Control aprueba (`action_approve`, deja
  `locked=True`, reutilizando el bloqueo ya existente de `historical.cost`)
  o bloquea (`action_block`, además marca `origin='unreviewed'` —
  reutilizando la exclusión de comparativos ya definida en ADR D-C). Una
  corrección posterior a la aprobación es una **reversa** (nuevo lote con
  los mismos hechos en signo contrario) o un lote nuevo — nunca editar
  filas aprobadas.
- **Especie/variedad condicionadas por tipo de centro, no por regla
  global:** una fila cuyo centro resuelto tiene `cost_type = 'crop'` exige
  especie informada; el resto (operacional, administrativo, maquinaria,
  otro) no la exige. Verificado contra ambos archivos reales (Frutales
  siempre trae especie/variedad; Operacional/Administrativo no).
- **Fórmula de TC:** nunca se ejecuta una fórmula arbitraria de Excel. Sólo
  se acepta `=<celda Monto>/<celda Monto US$>` de la **misma fila** en la
  columna TC del real histórico (patrón exacto verificado por regex sobre
  las referencias de celda, nunca `eval`); cualquier otra fórmula, en
  cualquier columna, es error de fila.
- **Duplicados exactos:** se muestran siempre (nunca se ocultan); por
  omisión **se importan** (reflejan el archivo tal cual); el usuario puede
  marcar «Excluir duplicados exactos del lote» para importar sólo la
  primera ocurrencia, sin borrar las demás de la vista previa (auditoría).
- **Plantillas versionadas (L3):** `step.management.historical.template.version`
  — sólo el Administrador la mantiene; una cabecera que no calza con ninguna
  versión activa se rechaza con instrucciones (código de la plantilla
  vigente), nunca se adivina por nombre de archivo. Sembradas por
  `data/historical_template_versions.xml` con la cabecera exacta de los dos
  anexos oficiales.
- **Idempotencia y concurrencia:** clave de lote (empresa + tipo + versión
  de plantilla + hash de archivo) protegida por índice único parcial de
  Postgres (mismo patrón que R5), no sólo `search()`.

### Pendientes explícitos que este corte NO resuelve
- K3 sigue abierta (no relacionada con este corte).
- H1, K5, D20, BPA-Riego, usuarios reales/UAT: sin cambios.

---

## Corte V2 C (2026-09-07) — comprometido de compras

### D-M — Comprometido desde `purchase.order`, no desde `account_budget`
- **Confirmado (J5):** se necesita ver el comprometido (OC confirmadas y no
  facturadas) para saber cuánto falta comprar. `account_budget` está
  instalado en Desarrollo/Demo pero el cliente confirma que "no se ajusta
  a lo que se diseñó en este módulo" — no se usa como sustituto.
- **Auditoría real (`LAB_TAREAS`):** `purchase` 18.0.1.2 y `account_budget`
  18.0.1.0 instalados. Se usa `purchase.order.line` directamente
  (`state='purchase'`, `product_qty - qty_invoiced` como remanente),
  ambos campos reales del núcleo de Compras — no un modelo del puente de
  presupuesto estándar.
- **`stock.requirement.line` gana** `committed_quantity` (informativo,
  misma foto para todos los períodos del producto, igual que
  `available_quantity`) y `net_to_buy` (faltante acumulado menos lo
  comprometido, consumiendo ambos una sola vez, comprometido después de
  stock). `committed_purchase_line_ids` conserva la trazabilidad a las
  líneas de OC que componen el total.
- **Sin doble conteo con `virtual_available`:** con
  `availability_metric = 'forecasted'`, `net_to_buy` **no** vuelve a
  descontar lo comprometido — Odoo ya lo incluye dentro de
  `virtual_available` (entradas previstas). Con `on_hand`/`free` sí se
  descuenta, porque esas métricas no incluyen pedidos pendientes de
  recibir.
- **Nueva dependencia del manifiesto:** `purchase` (además de `stock`,
  agregado en el Corte 1 post Fase 6). Sigue el mismo criterio de D-E:
  módulo estándar de Odoo, no un puente agrícola.
- **No se crean solicitudes de cotización ni órdenes de compra
  automáticamente** — sólo lectura agregada de sólo consulta (`sudo()`,
  mismo motivo que `_read_product_availability`).

### Pendientes explícitos que este corte NO resuelve
- K3, H1, K5, D20, BPA-Riego, usuarios reales/UAT: sin cambios.

---

## Corte V2 D (2026-09-07) — puente con maestros agrícolas reales

### D-N — `step_management_costs_agriculture`, puente opcional auto-instalable
- **Auditoría de código (sólo lectura, `step_hr` de este mismo worktree —
  rama `codex/gestion-costos` también contiene una copia propia, verificada
  idéntica en los archivos relevantes contra `/opt/dev_odoo18/odoo_agriculture`
  de `odoo-new`):** confirmados `step.temporada` (cuenta analítica propia,
  sin usar en este corte — D03 sigue abierta), `step.fundo`, `step.especie`,
  `step.variedad(.line)`, `step.grupo.variedad(.line)`, `step.cuartel.line`
  (`centro_id` → `account.analytic.account`, `name`=cuartel,
  `plant_cuartel`=plantas), y la extensión real de
  `account.analytic.account` (`step_centro_costo.py`): `fundo_id`,
  `especie_id`, `variedad_id`, `grupo_variedad_id`, `has_cost` (hectáreas),
  `plant_cost` (plantas), `type_costo` — la cuenta analítica **es** el
  centro de costo en `step_hr`, no hay un segundo modelo.
- **Decisión:** nuevo addon `step_management_costs_agriculture`
  (`auto_install=True`, depende de `step_management_costs` + `step_hr`).
  No convierte ningún campo del núcleo en obligatorio ni reemplaza el
  `Char`/`Float` existente (D13, fallback portable intacto): agrega campos
  `agri_*` de sólo lectura en `cost.center` (relacionados a través de
  `analytic_account_id`) y extiende `estimation.py` con
  `harvest_labor_id` + precedencia de rendimiento estándar
  **centro → variedad → grupo de variedad** (cada nivel indexado también
  por `labor_id`, un campo real de los tres modelos, no inventado) y fuente
  de plantas (maestro del centro si está informado, si no el `Float` propio
  del núcleo). La procedencia elegida (`yield_source`/`plants_source`) se
  congela junto con el resto del detalle al validar (se extiende
  `PROTECTED_LINE_FIELDS` del núcleo).
- **Migración no destructiva:** `upgrades/18.0.1.0.0/post-migration.py` del
  puente copia `farm`/`species`/`variety` del maestro real al `Char` del
  núcleo **sólo cuando éste está vacío** — nunca sobrescribe un valor ya
  informado. No hay ambigüedad que resolver: la relación
  (`analytic_account_id`) ya es explícita y única antes de esta migración,
  a diferencia de un emparejamiento por texto.
- **Actividad (D20) sigue bloqueada:** este puente no conecta
  `product.template.actividad_id` a nada — sigue apuntando a
  `account.analytic.account`, semántica sin confirmar. El maestro de
  rendimiento se indexa por `labor_id` (un `product.template` real), un
  campo totalmente distinto e independiente del bloqueo de D20.
- **Núcleo sin puente:** `step_management_costs` solo, sin `step_hr`, se
  instala y prueba exactamente igual que en los cortes anteriores — el
  puente nunca se activa (los tests del puente ni siquiera se cargan sin
  `step_hr` presente, por dependencia dura del propio addon puente).

### Pendientes explícitos que este corte NO resuelve
- K3, H1, K5, D20, BPA-Riego, usuarios reales/UAT: sin cambios.
- `step.temporada` no se usa todavía (D03 sigue abierta; fuera del alcance
  explícito de V2 D, que sólo pedía verificar su existencia en código).

### Importación Excel de programas (D10, ampliación)
- **Confirmado:** agregar carga Excel de programas con staging, vista
  previa, errores por fila, idempotencia y aprobación segura, siguiendo los
  importadores existentes.
- **Estado:** implementado (`models/crop_program_import.py`, mismo patrón
  que `budget_import.py`). El encabezado (tipo, temporada, centros, política
  de precio) se define en el registro de carga antes de validar; el Excel
  sólo aporta las filas de receta. "Aprobación segura": el programa
  importado siempre nace en **borrador**, nunca se aprueba automáticamente.

### Pendientes explícitos que este corte NO resuelve
- C2 (recursos semanales adicionales/factores de personas), C4 (envases en
  necesidades de stock), fórmula de estimación (D05), precedencia de
  rendimiento estándar centro→variedad→grupo, Orden de Producción, PDF,
  integración OT — siguen fuera de alcance por instrucción explícita del
  documento del cliente (no forman parte de los 7 frentes de su "Corte 1")
  o porque dependen del puente de maestros (D20).

### Verificación real (Odoo, `odoo-new`/`LAB_TAREAS` desechable) — hallazgos
- **Dos defectos reales encontrados y corregidos en los fixtures
  compartidos del núcleo** (no en el modelo/lógica de negocio; sólo en
  `tests/test_management_costs.py` y los archivos que reutilizan sus
  helpers): con `step_hr` instalado junto al puente, `account.analytic
  .account.fundo_id` (ya conocido, ver más arriba) y, nuevo,
  `product.template.grupo_labor` (Selection, obligatorio, sin `default=`
  en Python — aportado por `step_hr`) rompían cualquier fixture que creara
  una cuenta analítica o un producto "pelado". Se generalizó el patrón ya
  usado para `fundo_id`: `extra_company_vals(env)` y
  `extra_product_vals(env)`, ambas defensivas (inspeccionan `_fields` en
  vivo; sin el puente instalado no hacen nada) y ambas importadas por los
  ~9 archivos de test del núcleo que crean `res.company`/`product.product`
  a mano. Clean install combinado (`step_management_costs` +
  `step_management_costs_agriculture`, `--without-demo=all`) quedó verde
  salvo la excepción documentada abajo.
- **Límite estructural documentado, no corregido (fuera de alcance —
  significaría tocar `step_hr` o el común de pruebas de contabilidad de
  Odoo, ninguno de los dos permitido):** `test_fase2_variance.py` hereda de
  `AccountTestInvoicingCommon` (común **de Odoo core**, no nuestro); su
  propio `setUpClass()` crea productos sin saber de `grupo_labor`. Con el
  puente agrícola instalado en la misma base, ese fixture del núcleo de
  Odoo revienta igual que los nuestros — pero no podemos parchear código de
  `account/tests/common.py`. Es un defecto de diseño de `step_hr` (campo
  obligatorio sin default utilizable en `create()` sobre un modelo tan
  compartido como `product.template`), no de este addon. No afecta
  instalaciones reales (ya tienen productos existentes); sólo a la
  combinación artificial "instalación limpia + puente + común de Odoo" que
  usa esta verificación. Corte V2 D se da por verde en clean install con
  esta única excepción documentada.
- **Bloqueo de verificación "upgrade" (clon de `LAB_TAREAS`), no atribuible
  a este addon:** un clon fresco de `LAB_TAREAS` tomado el 2026-09-07 falla
  al crear **cualquier** `res.company` (incluso sin relación alguna con
  `step_management_costs`: se reprodujo con las pruebas del núcleo solas,
  sin el puente) por `NotNullViolation` en `res_company.security_lead`
  (campo de `sale_stock`, con default Python normal). Confirmado por
  `ir_module_module.write_date`: `sale_stock` se modificó en `LAB_TAREAS`
  el mismo día a las 04:06, poco antes de esta ronda de pruebas —
  consistente con otra sesión/proceso tocando la base compartida en
  paralelo (el riesgo que la instrucción vigente pide evitar). No se
  investigó más para no interferir; **la vía "clean install" (arriba)
  queda como la verificación decisiva de este corte**.
  **Actualización (Corte V2 E, mismo día, ~07:30, casi 3.5 horas después):**
  se reintentó contra un clon fresco nuevo — mismo resultado exacto, y
  `sale_stock.write_date` sigue siendo el mismo 04:06 (no hubo actividad
  nueva en `ir_module_module` en las últimas 2 horas). Esto descarta la
  hipótesis de "colisión transitoria, esperar a que se calme": el estado
  es **permanente** desde que `sale_stock` se actualizó esa vez — no se
  resuelve solo con tiempo. Es un problema real del entorno compartido
  (`sale_stock` quedó sin poder resolver el default de `security_lead` para
  companies nuevas fuera de modo interactivo), ajeno a este addon y a
  `step_hr`; queda documentado para quien administre `odoo-new`/
  `LAB_TAREAS`, sin tocarlo. La vía de instalación limpia sigue siendo la
  verificación decisiva y suficiente de cada corte mientras esto no se
  resuelva.

## Corte V2 E (2026-09-07) — presupuesto de maquinaria

### D-O — puente `step_management_costs_machinery`, tarifa hora/máquina real
- **Auditoría de código (sólo lectura, `step_machinery` 18.0.22.0.0 en
  `odoo-new`, instalado sobre `step_hr`+`fleet`):** confirmados
  `fleet.vehicle` extendido (`consumption_line`/`radio_line`, O2M a
  `monthly.consumption.line`/`monthly.radio.line`; `step_total_hrs_mes`;
  `step_cost_hrmq_standar` ya calculado con guarda de cero horas —
  `sum(...)/horas if horas else 0.0`, replicada aquí, nunca dividir por
  cero), `type.service.machinery` (catálogo canónico real de 8 conceptos —
  combustible, aceites y lubricantes, repuestos, mantención correctiva,
  mano de obra, arriendo, mantención preventiva, depreciación mensual —
  códigos `"01".."08"`, sembrado por el propio `post_init_hook` de
  `step_machinery`), `step.hrs.machinery(.line)` (registro real de horas,
  con `cost_id` = cuenta analítica del centro y `labor_id` = `step.labor`,
  clave de la "relación demostrable" para imputar al centro), y
  `step.labor` (de `step_hr`: `es_maquina`, `grupo_labor`, `actividad_id`).
- **Decisión de diseño — no duplicar un documento nuevo:**
  `step.management.budget.line` **ya tenía** `category='machinery'` en el
  núcleo, sin usar. En vez de crear un documento de presupuesto de
  maquinaria paralelo, el puente extiende ese mismo detalle
  (`machinery_vehicle_id`, `machinery_labor_id`,
  `machinery_component_json`, `machinery_actual_hours`): el presupuesto que
  lo contiene ya aporta snapshot/hash, revisión, aprobación, multiempresa y
  moneda del núcleo (`operational_budget.py`) sin duplicar nada de eso.
- **Grupo presupuestario controlado:** `step.management.budget.group` no
  tenía ningún concepto de grupo reservado — se agrega
  `get_machinery_group(company)` (código fijo `HRMAQ`, propio de este
  puente, idempotente — no es un dato ni un ID de `step_machinery`, así que
  fijarlo no viola "no hardcodees IDs/nombres reales").
- **Tarifa por labor:** `step.management.machinery.labor.rate` (vehículo +
  labor → tarifa que reemplaza la estándar del vehículo completo; sin
  labor, o sin excepción para esa labor, se usa la tarifa estándar
  calculada desde los conceptos reales del vehículo).
- **Real por centro/maquinaria:** `machinery_actual_hours` (compute, no
  almacenado) suma `step.hrs.machinery.line.hrs_maquina` filtrando por
  `cost_id = center_id.analytic_account_id` **y** `machinery_ids =
  machinery_vehicle_id` — sólo cuenta cuando ambas relaciones están
  presentes ("relación demostrable"); un registro real sin `cost_id` no se
  imputa a ningún centro.
- **Hallazgo real en el núcleo, corregido (no un defecto de este corte,
  sino una limitación de extensibilidad pre-existente en
  `operational_budget.py`):** `_create_revision()` reconstruía las líneas
  de la nueva revisión con una lista de campos **hardcodeada** en
  `_revision_line_commands()`. Cualquier campo agregado por un puente vía
  `_inherit` (como `machinery_vehicle_id` de este corte) se perdía en
  silencio al crear una revisión — no fallaba, simplemente no se copiaba.
  Se generalizó a `REVISION_LINE_FIELDS` (conjunto a nivel de módulo, mismo
  criterio que `PROTECTED_LINE_FIELDS` en `crop_program.py`/
  `estimation.py`): cualquier puente futuro que agregue campos a
  `step.management.budget.line` debe sumarlos con
  `REVISION_LINE_FIELDS.update({...})`. `step_management_costs_machinery`
  ya lo hace. Corregido en el núcleo (`18.0.19.0.0`), no en el puente —
  beneficia a cualquier extensión futura de este modelo, no sólo a
  maquinaria.
- **Hallazgo real de orden de escritura en Odoo (no un defecto del núcleo,
  documentado como restricción de diseño):** actualizar en un mismo
  `write()` la tarifa de una línea **y** un comando `(1, id, vals)` sobre
  uno de sus `month_ids` existentes deja un estado intermedio inconsistente
  frente a `_check_monthly_distribution`/`_check_parent_distribution` del
  núcleo (Odoo procesa el comando del O2M —que dispara su propia validación
  cruzada contra la línea padre— antes que los campos simples de la propia
  línea dentro del mismo `write()`). `action_pull_machinery_rate()` evita
  el problema sin tocar el núcleo: (1) fija la tarifa nueva con los meses
  vacíos (`(5,0,0)`; la validación se salta sin meses), (2) recrea los
  meses ya con la tarifa correcta, cuando la línea ya la tiene. No hay
  ventana con datos inconsistentes.
- **Núcleo sin puente:** `step_management_costs` solo, sin `step_machinery`,
  se instala y prueba exactamente igual que en los cortes anteriores.

### Verificación real — resultado
Instalación limpia combinada (`step_management_costs` +
`step_management_costs_agriculture` + `step_management_costs_machinery`,
`--without-demo=all`): verde, salvo la misma excepción externa ya
documentada en Corte V2 D (`TestFase2Variance` vs. `step_hr.grupo_labor`,
ninguna relación con maquinaria). Verificación por upgrade de `LAB_TAREAS`:
sigue bloqueada por el hallazgo externo de `sale_stock.security_lead`
descrito arriba (confirmado persistente, no transitorio). Detalle completo
en `HANDOFF_V2_CORTE_E.md`.

### Pendientes explícitos que este corte NO resuelve
- K3, H1, K5, D20, BPA-Riego, usuarios reales/UAT: sin cambios.
- No se conecta automáticamente la tarifa de maquinaria al presupuesto
  general vía la Orden de Producción ni se generan asientos contables desde
  este puente — eso ya lo hace `step_machinery` con sus propios registros
  reales (`step.hrs.machinery`/`action_conta()`); este corte sólo presupone
  y concilia horas, no contabiliza.

## Corte V2 F (2026-09-07) — comparativos, tablero, clasificación fuera de OP

### D-P — comparativo de temporada, tablero ampliado, fuera de OP
- **Fuente única del comparativo (puntos 1-2, 7):**
  `step.management.season.comparison.wizard` lee exclusivamente
  `step.management.historical.cost` (el hecho normalizado del Corte V2 B) —
  no mezcla con la contabilidad analítica en vivo dentro de una misma
  comparación, evitando el doble conteo pedido explícitamente por el corte.
  Excluye `origin == 'unreviewed'`, igual que ya hacía el propio modelo.
  8 dimensiones (fundo, especie, variedad, centro, origen, grupo
  presupuestario, actividad, producto-labor); moneda: CLP
  (`actual_amount`/`budget_amount`) + USD (`source_amount_usd` del archivo
  cuando el hecho viene de una carga oficial V2 B; si no, el convertido en
  vivo del núcleo). La variación % siempre se calcula desde los totales ya
  sumados (temporada actual vs. anterior) — nunca sumando ni promediando
  porcentajes de fila — y queda marcada "sin base" (no "0 %") cuando la
  temporada anterior no tiene monto.
- **Tablero (punto 3):** se extendió `get_management_dashboard()` (ya
  existente) en vez de crear un tablero paralelo. Bloque «real vs.
  presupuesto» ya existía (`historical_cost`); se le agregó
  `variance_percent`/`budget_available` con la misma protección de cero.
  Bloques nuevos: `hectares_by_farm_species`/`hectares_by_variety`, en
  Python sobre `step.management.cost.center` (campos `farm`/`species`/
  `variety` ya existentes en el núcleo), sin mezclar centros sin dato con
  los que sí lo tienen («Sin clasificar» aparte).
- **Necesidades de stock en el tablero (punto 4):** bloque `stock`
  (necesidades/disponible/comprometido/neto), siempre presente — V2 C ya es
  parte del núcleo, no un puente opcional; sin documentos, ceros reales
  (nunca se ocultan campos).
- **Fuera de OP (punto 5), alcance reducido por D20:**
  `step.management.out.of.op.wizard` clasifica gasto real (apuntes
  publicados) por **centro + temporada + grupo presupuestario** —la
  dimensión **actividad** de la clave pedida por el corte queda
  deliberadamente fuera: la única fuente técnica para derivarla de un
  apunte real es `product.template.actividad_id`, exactamente D20 (bloqueo
  permanente, semántica sin confirmar). Aislado ese campo, se continúa con
  las tres dimensiones demostrables. La temporada de un apunte se deriva de
  su fecha con `period.service.season_of_date()` (inversa de
  `season_bounds`, nueva, mismo criterio F4-A1 — sin inventar maestro de
  temporadas, D03 sigue abierta). "Amparado por OP": existe una OP
  autorizada/reemplazada para esa clave con al menos una línea del mismo
  grupo. Nunca excluye ni mezcla: ambos casos se muestran juntos, marcados.
- **Folio derivado, nunca fabricado (punto 6):** cuando no hay OP que
  ampare un bucket, `source_label` deriva «Wxx/AAAA (derivado)» de las
  semanas ISO de los apuntes reales (`period.service.iso_weeks`); sin
  ninguna fecha, «Sin origen registrado». Nunca se inventa un folio.
- **Defecto real encontrado y corregido (núcleo, no de este corte):**
  `_read_real_cost_buckets()` (fuera de OP) armaba un diccionario
  `cuenta analítica → centro` con una comprensión simple; dos centros que
  comparten intencionalmente una cuenta analítica (fixture del núcleo,
  usada en otros tests para probar exactamente esa restricción) hacían que
  el gasto se atribuyera **en silencio** al centro que ganara la colisión
  de iteración, nunca al correcto. `operational_budget.py` ya tenía esta
  misma protección pero acotada a un presupuesto
  (`_duplicate_analytic_centers()`); se generalizó a
  `step.management.cost.center.account_to_center_map()` (nuevo método
  reutilizable, levanta `UserError` explícito ante la ambigüedad en vez de
  atribuir a ciegas) y el clasificador de este corte lo usa. Encontrado por
  `test_expense_backed_by_op_is_classified_in_op` contra Odoo real.
- **Núcleo sin los puentes:** ninguno de los cambios de este corte depende
  de `step_hr`/`step_machinery` — todo vive en `step_management_costs`
  puro; se verificó junto con ambos puentes instalados, sin regresiones.

### Verificación real — resultado
Instalación limpia combinada (núcleo + 2 puentes, `--without-demo=all`):
verde, salvo la misma excepción externa ya documentada en el Corte V2 D
(`TestFase2Variance`). Upgrade de `LAB_TAREAS` (clon fresco tomado hoy
~08:11, más de 4 horas después del primer hallazgo): mismo bloqueo externo
de `sale_stock.security_lead` (5 errores, ninguno atribuible a este
corte) — confirmado, otra vez, persistente. Un test propio
(`test_costs_block_variance_percent_zero_safe`) asumía datos vacíos para
"la compañía principal" y fallaba contra `LAB_TAREAS` real (que sí tiene
historia); corregido para probar el helper `_dashboard_costs_block()`
directamente en vez de todo `get_management_dashboard()` — lección: un
test que agrega sobre toda la compañía sin acotar a sus propios datos no es
válido contra una base con historia real. Detalle completo en
`HANDOFF_V2_CORTE_F.md`.

### Pendientes explícitos que este corte NO resuelve
- K3, H1, K5, D20, BPA-Riego, usuarios reales/UAT: sin cambios. H1 sigue
  bloqueando el catálogo completo de informes/PDF (instrucción explícita
  del corte: sólo las salidas ya confirmadas).
- Dimensión «actividad» en la clasificación fuera de OP: pendiente de D20.
- Drill-down hasta asiento (punto 7): cubierto parcialmente — el
  comparativo no trae aún un botón de apertura de apuntes por fila (sí lo
  tiene el clasificador fuera de OP, reutilizando el patrón de
  `budget_variance.py`); agregar el mismo botón al comparativo es una
  extensión menor, no bloqueada por nada, diferida por alcance de tiempo.

## Corte V2 G (2026-09-07) — auditoría de puentes OT operacionales

**Resultado del corte: auditoría completa, cero adaptadores nuevos.** El
propio documento del corte contempla este desenlace explícitamente ("sólo
si la auditoría demuestra contratos suficientes... si un puente concreto
sigue bloqueado, documenta ese puente y continúa con los demás") — se
auditaron las 8 áreas pedidas contra el código real de `odoo-new`
(`/opt/dev_odoo18/odoo_agriculture`, sólo lectura, nada modificado) y
ninguna quedó con un contrato lo bastante seguro como para crear un
registro real en el módulo destino sin fabricar datos ni asumir riesgos no
autorizados. El núcleo **no cambia de versión** (sigue en `18.0.20.0.0`):
no hay código nuevo que versionar. Detalle completo, con las 8 fichas de
auditoría (addon/dependencia, modelo/campo/estado, empresa/reglas de
acceso, clave idempotente, datos que aportaría `get_bridge_payload()`,
vínculo inverso, política de reversa, pruebas), en `HANDOFF_V2_CORTE_G.md`.

### D-Q — hallazgo transversal: la OP es planificación, el OT es ejecución
El hallazgo que explica el resultado de las 8 fichas es el mismo en casi
todas: `production.order.get_bridge_payload()` (ya construido en el Corte
2) entrega folio, temporada, semana ISO, lunes/domingo, centro/fundo/
cuartel/especie y el detalle por línea (actividad, grupo presupuestario,
producto, cantidad) — **agregado semanal de planificación**. Todos los
modelos reales de OT auditados (`step.cosecha.registry`,
`step.hrs.machinery(.line)`, `x_aplicacion_foliar`, `x_orden_de_flete`)
son documentos de **ejecución**: exigen cuadrilla/contratista, máquina y
conductor, hora exacta, litros/kilos reales — datos que la OP, por diseño,
no captura y no debería inventar (instrucción explícita: "no fabricar").
Fabricar esos campos con un valor por defecto (el primero de la semana, un
responsable cualquiera) violaría "no fabricar" tan claramente como
inventar un folio (ya resuelto de otra forma en el Corte V2 F, punto 6).
Esta tensión planificación/ejecución es estructural, no un vacío de datos
que se resuelva agregando un campo a la OP.

### Hallazgos adicionales por área (resumen; ficha completa en el handoff)
- **Maquinaria** (`step_machinery`, ya auditado en el Corte V2 E): mismo
  problema — `step.hrs.machinery.line` exige `machinery_ids` (vehículo
  real) y `employee_id` (conductor), que se deciden en terreno, no al
  autorizar la OP.
- **Cosecha** (`step_cosecha`, real, `step.cosecha.registry`): exige
  cuadrilla (`salary_id`) o contratista (`partner_id`) y tarja (kilos/cajas
  reales) — mismo problema, más profundo (esta app además genera
  asientos contables directamente al costear).
- **Proveedores**: no existe un modelo de OT propio — el trabajo de
  contratistas externos se registra dentro de Cosecha
  (`type_tarea = 'contratista'`); no hay una segunda ficha independiente.
- **Actividades**: `step.actividad`/`step.labor` (`step_hr`) son maestros
  (taxonomía), no documentos de OT con estado propio — son la dimensión
  que las OTs reales (Cosecha, Maquinaria, BPA) ya usan internamente. No
  hay "OT de Actividad" que auditar como documento separado.
- **Inventario** (`agri_inventory_operations`, modelo
  `production.work.order`): el propio manifiesto se identifica como
  `"(DEV)"` (desarrollo). Sin `company_id` (ninguno de sus campos lo tiene
  — viola `_check_company_auto` que usa el resto del ecosistema), ACL
  abierta a `base.group_user` sin roles, y usa `product.category`/
  `product.attribute.value` en vez de los maestros reales
  `step.especie`/`step.variedad` de `step_hr` — no hay mapeo limpio desde
  nuestros centros de costo (que sí usan los maestros reales). Bloqueado
  por calidad/madurez del módulo destino, no por falta de datos de origen.
- **Fletes** (`step_operations_ui`, real, `x_orden_de_flete`): el modelo
  destino es sólido (estado con Anulado incluido, `company_id`,
  `x_studio_fundo` real) pero la OP **no tiene ningún dato de flete** —
  ni tramo, ni transportista, ni camión, ni modalidad de frío. No es un
  problema de calidad del destino sino de que el origen simplemente no
  produce esa información en ningún punto del flujo actual.
- **BPA** (`step_bpa_irrigation`, real, `x_aplicacion_foliar`): el
  candidato más cercano a viable — mismo fundo/especie (vía el puente
  agrícola V2D, si está instalado; sin él, esos dos campos quedarían en
  blanco, nunca adivinados), `x_studio_objetivo_aplicacin` mapeable desde
  `target` de la aplicación del programa fitosanitario (Corte V2 A/Fase 5,
  catálogo por nombre normalizado, mismo patrón que
  `type.service.machinery`), hectáreas reales del programa. Pero **el
  modelo destino no tiene ningún estado de anulación** (`status1
  Ingresado → status2 → status3 → Contabilizado`, sin "cancel") — crear un
  registro automáticamente y no poder revertirlo limpiamente si el mapeo
  resultara equivocado es un riesgo que un corte de auditoría no debe
  asumir por cuenta propia. Se documenta como el candidato a retomar en un
  corte futuro, con una decisión humana explícita sobre: (a) crear
  automáticamente al autorizar vs. un botón manual "Generar borrador BPA"
  que el usuario dispare a propósito, y (b) si vale la pena depender de
  `step_bpa_irrigation` en el manifiesto o leerlo en forma defensiva
  (`self.env.get(...)`) — el propio código real de `odoo-new`
  (`step_agro_traceability/models/phyto_restriction.py`) usa el patrón
  defensivo precisamente por la historia de este modelo como
  personalización Studio, mientras que `step_bpa_irrigation` propio
  (`machinery_integration.py`) ya asume una dependencia dura — el
  ecosistema real no es consistente en esto y conviene una decisión
  explícita del cliente/equipo, no una elegida unilateralmente aquí.
- **Riego** (mismo addon `step_bpa_irrigation`, modelo
  `x_riego_y_fertilizacio`): sin campo `state` en absoluto — un registro
  plano sin ciclo de vida. No hay "autorizado"/"pendiente" que verificar
  antes de vincular, y nuestra OP tampoco distingue riego como tipo de
  labor separado hoy. Bloqueado por ambos lados.

### Pendientes explícitos que este corte NO resuelve
- K3, H1, K5, D20, BPA-Riego, usuarios reales/UAT: sin cambios.
- Ningún adaptador nuevo se construyó (resultado legítimo de este corte,
  ver arriba). `get_bridge_payload()` (Corte 2) queda disponible, sin
  consumidores nuevos.
- La decisión sobre si construir el puente BPA (el único candidato con
  camino técnico razonable) queda para el cliente: automático vs. manual,
  y dependencia dura vs. lectura defensiva de `step_bpa_irrigation`.
