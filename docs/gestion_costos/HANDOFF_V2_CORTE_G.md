# Handoff — Corte V2 G (auditoría de puentes OT operacionales)

**Addon:** `step_management_costs` — **sin cambio de versión** (sigue en
`18.0.20.0.0`, la del Corte V2 F): este corte es una auditoría, no produjo
código nuevo.
**Fecha:** 2026-09-07 · **Autor:** Claude Sonnet 5 · **Estado:** auditoría
completa de las 8 áreas pedidas contra el código real de `odoo-new`
(sólo lectura); **cero adaptadores construidos** — resultado explícitamente
contemplado por el propio documento del corte ("sólo si la auditoría
demuestra contratos suficientes... si un puente concreto sigue bloqueado,
documenta ese puente y continúa con los demás").

## 1. Alcance y método

Séptimo corte de `PROMPT_CLAUDE_SONNET5_RESPUESTAS_V2_2026-09-06.md`.
Se auditó, de sólo lectura, el código real instalado en `odoo-new`
(`/opt/dev_odoo18/odoo_agriculture/`, el mismo árbol usado como fuente de
verdad en los Cortes V2 D y V2 E) para las 8 áreas pedidas: Actividades,
Cosecha, Maquinaria, Proveedores, Inventario, Fletes, BPA y Riego. Para
cada modelo real encontrado se registró: addon y dependencia; modelo,
campos y estados exactos; empresa y reglas de acceso; clave idempotente
disponible (o su ausencia); qué datos de
`production.order.get_bridge_payload()` (ya construido en el Corte 2)
alimentarían el puente; vínculo inverso OP↔OT; política de reversa/
cancelación del modelo destino; y si había base para pruebas sin efectos
externos.

**No se modificó ningún addon real** (`step_cosecha`, `step_machinery`,
`step_bpa_irrigation`, `step_operations_ui`, `agri_inventory_operations`,
`step_agro_traceability`) — auditoría estrictamente de lectura, igual
criterio que las auditorías previas de `step_hr`/`step_machinery` en los
Cortes V2 D/E.

## 2. Hallazgo transversal (por qué ningún puente quedó "listo")

`get_bridge_payload()` entrega un **agregado semanal de planificación**:
folio, temporada, semana ISO, lunes/domingo, centro/fundo/cuartel/especie,
y por línea: tipo de fuente, actividad, grupo presupuestario, producto,
UdM, cantidad. Es exactamente lo que una Orden de Producción es — qué se
planificó para un centro, en una semana, agregado por labor.

Los 4 modelos reales de OT/ejecución encontrados
(`step.cosecha.registry`, `step.hrs.machinery(.line)`,
`x_aplicacion_foliar`, `x_orden_de_flete`) son, sin excepción, documentos
de **ejecución**: exigen cuadrilla o contratista, máquina y conductor,
camión y transportista, hora exacta del día, litros o kilos reales — datos
que se conocen en terreno, en el momento de ejecutar, no al planificar ni
al autorizar una OP. No hay un campo que la OP pueda agregar para cerrar
esta brecha sin convertirse en un sistema de ejecución (fuera de su
propósito) o sin fabricar valores por defecto (prohibido explícitamente).

## 3. Fichas de auditoría

### 3.1 Actividades — sin modelo de OT propio
- **Addon y dependencia:** `step_hr` (ya auditado en el Corte V2 D).
- **Modelo/campo/estado:** `step.actividad` / `step.labor` son maestros
  (taxonomía: nombre, código, cuenta analítica, UdM, método de costeo).
  Ninguno tiene `state` ni ciclo de vida propio.
- **Conclusión:** no existe una "OT de Actividad" independiente que
  auditar como documento. La actividad es la dimensión que las OTs reales
  (Cosecha, Maquinaria, BPA) ya usan internamente (`labor_id.actividad_id`
  en todas ellas). Nada que construir aquí; no es un puente bloqueado, es
  un área sin documento de ejecución propio.

### 3.2 Cosecha — bloqueado (ejecución + contabilización directa)
- **Addon y dependencia:** `step_cosecha` (18.0.1.6.0), depende de
  `step_hr`, `fleet`, `sale`, `hr_payroll`, `purchase`, entre otros.
- **Modelo/campo/estado:** `step.cosecha.registry`. Estados: `in`
  (Ingresado) → `apro` (Aprobado) → `costo` (Costeo) → `cont`
  (Contabilizado). Campos clave: `type_tarea` (propio/contratista),
  `partner_id` (contratista), `salary_id`/`salary_id_contrac` (cuadrilla),
  `cost_id` (centro, cuenta analítica), `labor_id` (`product.template`),
  `fundo_id`, `total_kilos`/`total_boxes` (tarja real).
- **Empresa y acceso:** `company_id` requerido. ACL: `base.group_user`
  (sin roles graduados, a diferencia del núcleo).
- **Clave idempotente:** ninguna a nivel de modelo — el `name` se genera
  siempre desde una secuencia nueva en `create()`; un puente propio tendría
  que llevar su propia clave (p. ej. un campo en la línea de la OP que
  guarde el id del registro ya creado).
- **Datos del payload que alimentarían el puente:** centro/fundo, semana
  (aproxima la fecha), actividad, cantidad planificada — pero nada de
  cuadrilla/contratista ni de kilos reales, que son obligatorios para
  crear el registro.
- **Vínculo inverso OP↔OT:** no existe ningún campo en `step.cosecha
  .registry` que referencie una OP externa (lógico: el modelo es anterior
  a este módulo).
- **Reversa/cancelación:** `unlink()` bloquea el borrado sólo si
  `state == 'cont'` o ya tiene `invoice_id`/`reception_picking_id`; no hay
  `action_cancel()` explícito.
- **Conclusión:** bloqueado — faltan datos obligatorios que la OP no
  produce (cuadrilla/contratista, tarja real), y el modelo además
  contabiliza directamente al costear, elevando el riesgo de un registro
  mal formado. Además, la Cosecha real (kg por semana) ya se dejó fuera de
  la OP desde el Corte 2 por la misma razón (sin forma determinista de
  repartir kilos por centro) — este hallazgo es coherente con esa decisión
  previa.

### 3.3 Maquinaria — bloqueado (mismo patrón, ya auditado en V2 E)
- **Addon y dependencia:** `step_machinery` (18.0.22.0.0). Ya auditado a
  fondo en el Corte V2 E (ver `HANDOFF_V2_CORTE_E.md`).
- **Modelo/campo/estado:** `step.hrs.machinery(.line)`. Estados: `draft` →
  `progress` → `done` → `costed` → `accounted` (+ `cancel`).
- **Clave idempotente:** `unique(company_id, ot_number)`, con `ot_number`
  emitido siempre por `ir.sequence` en `create()` (no hay forma de pedir
  "el mismo" registro dos veces sin duplicar el correlativo).
- **Datos del payload:** centro, semana, actividad, cantidad — pero
  `step.hrs.machinery.line` exige `machinery_ids` (vehículo real) y
  admite `employee_id` (conductor), que se deciden en terreno.
- **Reversa:** `action_draft()` sólo si `state != 'accounted'`; sin
  `action_cancel()` visible más allá de eso.
- **Conclusión:** bloqueado, mismo motivo transversal (§2). El puente de
  presupuesto de maquinaria (Corte V2 E) es un caso distinto — lee la
  tarifa estándar del vehículo para *presupuestar*, no crea registros de
  horas reales.

### 3.4 Proveedores — no es un dominio de OT separado
- **Hallazgo:** no se encontró un modelo de "OT de proveedor" independiente
  en ninguno de los addons reales auditados. El trabajo de contratistas
  externos se registra **dentro de Cosecha**
  (`step.cosecha.registry.type_tarea = 'contratista'`, con `partner_id`)
  y, para maquinaria arrendada, dentro de `step.hrs.machinery` (que no
  distingue "propio" vs. "contratista" como concepto de primera clase,
  pero admite cualquier `fleet.vehicle`/`employee_id`). No hay una segunda
  ficha independiente que auditar; los hallazgos de §3.2 y §3.3 ya cubren
  el trabajo de terceros en sus respectivos dominios.

### 3.5 Inventario — bloqueado (módulo de desarrollo, no productivo)
- **Addon y dependencia:** `agri_inventory_operations`
  ("Agri Inventory Operations (DEV)" — el propio nombre lo marca como
  desarrollo), depende de `base`, `stock`, `mrp`.
- **Modelo/campo/estado:** `production.work.order`. Estados: `borrador` →
  `en_proceso` → `cerrada`.
- **Empresa y acceso:** **sin `company_id`** — ningún campo del modelo lo
  tiene, violando el criterio `_check_company_auto` que usa el resto del
  ecosistema (`step_management_costs` y todos los addons `step_*`
  auditados). ACL: `base.group_user` con los cuatro permisos abiertos, sin
  reglas de registro.
  Usa `product.category`/`product.attribute.value` para especie/variedad
  en vez de los maestros reales `step.especie`/`step.variedad` de
  `step_hr` que sí usa el resto del ecosistema (incluido nuestro propio
  centro de costo vía el puente V2 D).
- **Clave idempotente:** ninguna; `name` se genera por secuencia en
  `create()`, sin `_sql_constraints`.
- **Conclusión:** bloqueado por la calidad/madurez del módulo destino, no
  por falta de datos de origen — un modelo sin `company_id` no es seguro
  para escribir desde un puente multiempresa como el nuestro, y el
  desacople de los maestros reales de especie/variedad impide un mapeo
  limpio en cualquier caso.

### 3.6 Fletes — bloqueado (destino sólido, origen sin datos de flete)
- **Addon y dependencia:** `step_operations_ui` (18.0.2.0.3, "Experiencia
  Maquinaria y Fletes"), depende de `step_hr`, `step_machinery`.
- **Modelo/campo/estado:** `x_orden_de_flete`. Estado con **4 valores,
  incluido cancelación**: `status1` Ingresado → `status2` Autorizado →
  `status3` Contabilizado, más `cancel` Anulado. Campos:
  `x_studio_fundo` (`step.fundo`, real), `x_studio_transportista`
  (`res.partner`, proveedor), `vehicle_id` (`fleet.vehicle`), `route_id`/
  `tariff_id` (catálogos propios del módulo), `quantity`/`amount`
  (calculado desde la tarifa). Módulos satélite:
  `x_contabilizacion_de_f` (asiento contable) y `x_rastreo_camiones` (GPS,
  alimentado por Steps Tracker).
- **Empresa y acceso:** `company_id` requerido en el pedido y la tarifa;
  se deriva por `related` en contabilización y GPS. ACL:
  `base.group_user`.
- **Clave idempotente:** ninguna declarada; `x_name` con valor por
  defecto libre ("Nueva orden"), sin secuencia ni `_sql_constraints`.
- **Datos del payload que alimentarían el puente:** ninguno específico de
  flete. La OP no registra tramo, transportista, camión ni modalidad de
  frío en ningún punto de su flujo actual (planificación de tareas por
  centro/labor, no de transporte).
- **Conclusión:** bloqueado — a diferencia de Inventario, aquí el modelo
  destino es de buena calidad (estado completo, `company_id`, maestros
  reales); el bloqueo es enteramente del lado del origen: la OP
  simplemente no produce información de flete.

### 3.7 BPA — el candidato más cercano a viable, no construido
- **Addon y dependencia:** `step_bpa_irrigation` (18.0.2.3.1, "Steps - BPA
  y Riego"), depende de `step_hr`, `step_machinery`.
- **Modelo/campo/estado:** `x_aplicacion_foliar`. Estado:
  `status1` Ingresado → `status2` Aprobado → `status3` Costeado →
  `Contabilizado` — **sin ningún valor de cancelación/anulación**. Campos:
  `x_studio_fundo` (`step.fundo`), `x_studio_especie_1` (`step.especie`),
  `x_studio_objetivo_aplicacin` (M2o a `x_objetivo_o_plaga`, catálogo
  propio por nombre — mismo patrón que `type.service.machinery`),
  `x_studio_fecha_hora_planificada`, `x_studio_total_hectreas`,
  `x_studio_aprueba` (`hr.employee`), desglose de costo
  (productos/personal/maquinaria).
- **Empresa y acceso:** `company_id` requerido. ACL: `base.group_user`.
- **Clave idempotente:** ninguna declarada en el modelo — igual que
  Fletes, un puente propio necesitaría su propia clave de idempotencia
  (p. ej. un campo en la línea de la OP que registre el id ya creado, para
  que reintentar no duplique).
- **Datos del payload que alimentarían el puente:** centro (→ fundo/especie
  **sólo si el puente agrícola del Corte V2 D está instalado** — sin él,
  esos dos campos quedarían en blanco, nunca adivinados por texto),
  semana (→ lunes de la semana como fecha planificada, aproximación
  razonable y documentada, no una hora exacta inventada), hectáreas reales
  del programa fitosanitario/de fertilización (`crop.program.application
  .hectares`), objetivo/plaga (`target`, mapeable al catálogo por nombre
  normalizado).
- **Vínculo inverso OP↔OT:** no existe hoy; habría que agregarlo (un
  `Many2one` en la línea de la OP, en un addon puente nuevo).
- **Reversa/cancelación:** **no hay ningún estado de anulación** en
  `x_aplicacion_foliar` — crear un registro automáticamente y no poder
  revertirlo limpiamente si el mapeo resultara equivocado (p. ej. el
  objetivo/plaga mal emparejado) es un riesgo real que este corte de
  auditoría, por sí solo, no debe asumir.
- **Precedente real inconsistente encontrado en el propio código:**
  `step_agro_traceability/models/phyto_restriction.py` lee
  `x_aplicacion_foliar` de forma **defensiva** en tiempo de ejecución
  (`self.env.get(...)`, retorna `None` si no está, descubre las líneas
  "por capacidad, no por nombre" porque los sufijos que genera Studio no
  son estables entre bases) — documentando explícitamente el origen
  Studio del modelo. En cambio, `step_bpa_irrigation/models
  /machinery_integration.py` (del mismo autor, más reciente) ya usa
  `_inherit = "x_aplicacion_foliar"` sin guardas, asumiendo una
  dependencia dura. El ecosistema real no es consistente en este punto;
  no es una decisión que corresponda tomar unilateralmente en un corte de
  auditoría.
- **Conclusión:** no se construyó. Es el único candidato con datos de
  origen suficientes para un mapeo razonable, pero requiere una decisión
  humana explícita en dos ejes antes de construirlo: (a) ¿creación
  automática al autorizar la OP, o un botón manual "Generar borrador BPA"
  que el usuario dispare a propósito (mucho más seguro dado que no hay
  forma de anular)?; (b) ¿dependencia dura de `step_bpa_irrigation` en el
  manifiesto, o lectura defensiva como hace `phyto_restriction.py`? Con
  esas dos decisiones tomadas, el trabajo de construcción es de un alcance
  comparable al Corte V2 E (un addon puente, un método de generación con
  idempotencia propia, vistas, pruebas contra Odoo real).

### 3.8 Riego — bloqueado (sin estado, sin equivalente en la OP)
- **Addon:** mismo `step_bpa_irrigation`. **Modelo:**
  `x_riego_y_fertilizacio`. **Sin campo `state`** — es un registro plano
  (fundo, fecha, hectáreas a regar, litros de mezcla, "sólo riego"), sin
  ciclo de vida que verificar antes de vincular.
- **Conclusión:** bloqueado por ambos lados — el modelo destino no tiene
  un estado "autorizado" que exigir antes de escribir, y la OP tampoco
  distingue el riego como un tipo de labor separado de las demás tareas
  planificadas hoy. Es, junto con Actividades, el hallazgo más simple del
  corte: no hay suficiente estructura en ninguno de los dos lados para
  proponer siquiera un diseño de puente.

## 4. Pruebas

No se escribió código nuevo, por lo tanto no hay pruebas nuevas que
agregar a la suite. La auditoría en sí se validó leyendo el código fuente
real en `odoo-new` (rutas exactas citadas arriba), sin ejecutar nada
contra bases desechables — no hacía falta: no se creó, modificó ni tocó
ningún registro real ni de prueba.

## 5. Decisiones y supuestos

Ver `DECISION_LOG.md` §"Corte V2 G" (D-Q).

## 6. Pendientes del cliente

- Sin cambios respecto a los cortes anteriores (K3, H1, K5, D20,
  BPA-Riego, usuarios reales/UAT).
- **Nuevo, específico de este corte:** si se quiere retomar el puente BPA
  (§3.7, el único candidato viable), se necesita una decisión explícita
  sobre automático-vs-manual y dependencia-dura-vs-defensiva antes de
  empezar a construir.

## 7. Confirmación de aislamiento

Auditoría de sólo lectura. No se tocó `STEPS_DEMO_SYS`, ninguna otra
sesión de Claude, ni se modificó ningún addon real ni base de datos. Sin
commit ni push.

## 8. Siguiente

Con los Cortes V2 A–G cerrados (implementables en verde; V2 G resuelto
como auditoría sin bloqueos humanos pendientes salvo la decisión BPA
anotada arriba), corresponde: (1) la auditoría completa del backlog
(`MATRIZ_REQUISITOS.md`) contra el estado real de todo el módulo, ya
mantenida al día corte a corte; (2) el despliegue guardado a Desarrollo
(`LAB_TAREAS`) y luego Demo (`STEPS_DEMO`) según el runbook acordado —
pendiente de decisión del usuario sobre cuándo ejecutarlo. Ver
`SIGUIENTES_PASOS_2026-09-07.md` para el detalle accionable.
