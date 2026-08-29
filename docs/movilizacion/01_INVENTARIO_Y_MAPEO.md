# Inventario y mapeo de propiedad — Movilización

Auditoría del estado real de `step_hr` antes de la extracción a `step_mobilization` /
`step_mobilization_agriculture`. Generado 2026-08-25. Fuente: lectura directa del
código en `C:\Users\tito4\Documents\Odoo` (no se asumió nada del documento de
instrucciones sin verificarlo en el código).

## 1. Modelos propios de Movilización (a mover, mismo nombre/tabla)

| Modelo | Archivo actual | Tabla | Owner actual | Destino | Estrategia |
|---|---|---|---|---|---|
| `step.movi.registry` | `step_hr/models/step_movi_registry.py` | `step_movi_registry` | step_hr | step_mobilization | mover archivo + reasignar `ir.model.data` (mismo `_name`/tabla) |
| `step.movi.registry.line` | `step_hr/models/step_movi_registry_line.py` | `step_movi_registry_line` | step_hr | step_mobilization | ídem |
| `step.movi.cost.line` | `step_hr/models/step_movi_cost_line.py` | `step_movi_cost_line` | step_hr | step_mobilization | ídem |
| `step.movi.cont.line` | `step_hr/models/step_movi_cont_line.py` | `step_movi_cont_line` | step_hr | step_mobilization | ídem — modelo muerto (nunca poblado, campos comentados en vista); se conserva la tabla/datos si existieran, se retoma su uso o se marca deprecado explícitamente |
| `hr.route` | `step_hr/models/hr_route.py` | `hr_route` | step_hr | step_mobilization | mover; **no** se renombra el modelo (evita re-registrar `ir.model`/`ir.model.fields` completos) |
| `hr.route.line` | `step_hr/models/hr_route_line.py` | `hr_route_line` | step_hr | step_mobilization | ídem |
| `product.pricelist.move.line` | `step_hr/models/product_pricelist_move_item.py` | `product_pricelist_move_line` | step_hr | step_mobilization | ídem |

Decisión de nomenclatura: **no** se renombran `_name`/tabla de estos 7 modelos. Renombrar
un modelo en Odoo obliga a reescribir también `ir_model.model`, recrear todos los
`ir_model_fields`, y romper cualquier referencia externa (`ref()`, dominios) sin
beneficio funcional — es exactamente el riesgo que el encargo pide evitar. La
identidad visual ("Movilización") ya la da el nombre del addon/aplicación, no el
nombre técnico del modelo.

## 2. Campos añadidos por step_hr sobre modelos estándar

| Modelo | Campo | Archivo:línea | ¿Exclusivo de Movilización? |
|---|---|---|---|
| `hr.employee` | `is_movi`, `recorrido_id` | `models/hr_employee.py:29-30` | Sí — mover |
| `hr.employee` | `step_work_schedule`, `is_propio`, `is_contratista`, `is_super*`, `contratista_id`, `costo_*` | mismo archivo | No — nómina/contratistas, se queda en step_hr |
| `res.partner` | `step_trans_person`, `step_chofer`, `transpor_id` | `models/res_partner.py:29-31` | Sí — mover |
| `res.partner` | `step_carga` ("¿Transporte de carga?") | mismo archivo | **No** — es flete/carga, dominio distinto, se queda en step_hr |
| `res.partner` | `step_export`, `is_productor`, `step_contra`, `productor_name`, `cod_fundo`, `cod_csg`, `cod_ggn` | mismo archivo | No — cosecha/contratista |
| `fleet.vehicle` | `step_min_pass`, `step_max_pass` | `models/fleet_vehicle.py:51-52` | Sí — mover |
| `fleet.vehicle` | `cost_id`, `analytic_id`, `mod_carga`, `step_tonelada`, `step_mtrs_cub`, `step_litros*`, `step_cant_*`, `step_product_id`, `step_cost_*`, `step_man_hrs`, `step_total_hrs_mes` | mismo archivo | No — costeo genérico de flota y flete, se queda en step_hr |
| `product.template` | `is_movi` | `models/product_template.py:28` | Sí — mover |
| `product.template` | resto (cosecha, BPA, labor, flete...) | mismo archivo | No |
| `product.pricelist` | `moviliza`, `move_item`, `transporte_id` | `models/product_pricelist.py:61-68` | Sí — mover |
| `product.pricelist` | `group_type`, `partner_id`, `partner_ids`, `cosecha`, etc. | mismo archivo | No — compartido con cosecha/contratista, `default_get` mezcla contextos: se deja el método en step_hr y step_mobilization sólo añade su propio contexto vía `_inherit`, sin tocar la lógica de cosecha/contratista |
| `res.company` | `step_movi_journal_id`, `step_movi_document_type_id` | `models/res_company.py:14-15` | Sí — mover |
| `res.company` | `step_journal_id`, `step_cosecha_*`, `propio_journal_id`, `movi_product_id`, `step_tracker_*`, payroll fields | mismo archivo | No. `movi_product_id` pese al nombre es un producto de facturación genérico histórico no ligado a `step.movi.*`; se queda en step_hr y se documenta la confusión de nombre |
| `res.config.settings` | `step_movi_journal_id`, `step_movi_document_type_id` (related) | `models/res_config_settings.py:17-20` | Sí — mover |
| `account.move` | `moviliza` | `models/account_move.py:22` | Sí — mover (nota: sin campo en la vista de formulario hoy; se añade en step_mobilization) |
| `account.move` | `propio`, `contra`, `cosecha` | mismo archivo | No |

`step.fundo`, `step.temporada`, `step.tarja` **no se tocan** — son propiedad de
step_hr/agricultura y `step_mobilization_agriculture` sólo los referencia.

## 3. Secuencias y datos

- `ir.sequence` `seq_step_moviliza` (código `step_moviliza_seq`, prefijo `MV`,
  `company_id=False`) — `data/ir_sequence.xml:54-60`. Se mueve. **Bug detectado**:
  secuencia global sin `company_id` → se corrige en el nuevo addon (secuencia
  por compañía, ver Riesgos).
- Sin datos demo para Movilización en ningún addon actual.

## 4. Vistas / acciones / menús a mover

`view_step_movi_registry_form/_list`, `action_step_movi_registry`,
`action_step_movi_registry_costeo`, `view_step_movi_line_*`,
`action_view_step_movi_line`, `view_step_movi_cost_*`, `action_view_step_movi_cost`,
`view_hr_route_form/_list`, `action_hr_route`, `step_product_pricelist_action_movi`,
`action_step_movi_in_invoice`, `action_partner_supplier_form_step` (hoy mezcla
`step_trans_person`/`step_carga`/`step_chofer` — se separa: Movilización sólo
usa `step_trans_person`/`step_chofer`, `step_carga` se queda en step_hr),
`menu_step_moviliza` y todo su árbol, `menu_step_movi_line`, `menu_step_movi_cost`,
`menu_prove_movi`, `menu_hr_route`. `menu_vehicle_step` pasa a apuntar a la acción
estándar `fleet.fleet_vehicle_action` igual que hoy (no exclusiva de movi, se deja
también un acceso equivalente en el nuevo menú "Maestros → Vehículos").

**`menu_step_tracker` / `action_step_tracker` / modelo `step.tracker` (3 campos,
sin lógica)**: confirmado que es un placeholder vacío, no comparte nada con el
tracker de maquinaria real (`step.tracker.machine/driver/session/...`, que vive
aparte y usa `menu_step_tracker_gps_root`). Se migra el placeholder a Movilización
como base de "Seguimiento en línea"; el tracker de maquinaria no se toca.

**Bug de menú detectado**: `menu_hr_movi` (`menu_views.xml:305-309`) se llama
"Movilización" pero su acción es `action_hr_salary_custom` (asistente de nómina,
no relacionado). Se corrige en la migración: el ítem de nómina se queda con su
nombre real en step_hr; no se traslada nada a Movilización desde ahí.

## 5. Seguridad

Confirmado: los 7 modelos anteriores + `hr.route.line` tienen acceso CRUD completo
para `base.group_user` (`security/ir.model.access.csv`), **sin `ir.rule`** de
ningún tipo (ni multiempresa ni por rol). Se reemplaza en el nuevo addon por los
9 grupos que pide el encargo (Fase 6) + reglas por `company_id`.

**Dependencia externa real encontrada**: `step_agricultural_access` referencia
`step_hr.menu_step_moviliza` (`views/agricultural_menu_security.xml:17`) para
ocultar/mostrar el menú vía el grupo `group_activities_transport`. Es la única
referencia cruzada de otro addon a IDs de Movilización en todo el repo.
Estrategia: `step_agricultural_access` pasa a depender de `step_mobilization` y
su regla de seguridad se actualiza al nuevo XML ID del menú raíz de Movilización.

## 6. Acoplamiento del dashboard de Actividades

`step_hr/models/activities_dashboard.py:137` hace `search_count` directo sobre
`step.movi.registry`; `step_hr/static/src/xml/activities_dashboard.xml:30,72`
abren `step_hr.action_step_movi_registry` desde dos botones KPI. Se elimina ese
KPI del dashboard de Actividades (o se sustituye por un contador opcional vía
un método que detecta si `step_mobilization` está instalado, ver Fase 5) y los
botones se quitan/redirigen.

## 7. Riesgos técnicos confirmados en código (ver auditoría completa más abajo)

Confirmados con archivo:línea — control de estado `cont`/`conta` roto (botón
"Pagado" inalcanzable, `action_pag` escribe un estado `'pag'` que no existe en
la selección), tarifa no encontrada antes de `cobro_type` (AttributeError sobre
`int`), costeo divide por `len(movi_line)` (cuenta entradas+salidas, no
pasajeros únicos), recálculo de costeo no limpia líneas previas (guardas
comentadas), búsqueda de `step.temporada` sin filtro de compañía,
`analytic_distribution` construido con concatenación de strings sin validar que
los ids existan, `account_control_ids[0]` sin guardas, cambio de estado antes de
crear el asiento sin control de reintento, dominio `fleet.vehicle` con
`driver_id=False`, tres campos de "transportista" inconsistentes en
`product.pricelist` (`partner_id`/`partner_ids`/`transporte_id`, este último
queda oculto justo cuando se necesita), `ondelete='cascade'` desde `fundo_id`
hacia `step.movi.registry`, subida/bajada modelada como un solo campo
`operacion` + `hr_in`/`hr_out` en vez de eventos, campos obligatorios en negocio
pero `required=False` en el modelo, `create()` con `@api.model` (no
`_create_multi`) que siempre sobrescribe `name`, un `print()`, imports sin uso,
campo duplicado en una vista de lista, textos de búsqueda copiados de otros
dominios ("Tareas Contratistas", "Costeo Moovilizacion"). Detalle completo con
cita de código en el reporte de auditoría del historial de esta sesión; se
resume aquí para no duplicar ~200 líneas.

## 8. `step.fundo` / `step.temporada` — acoplamiento agrícola

- FK real: `step.movi.registry.fundo_id → step.fundo` (`ondelete=cascade`).
- `step.temporada`: sin FK almacenada, sólo búsqueda en tiempo de ejecución por
  rango de fechas (sin filtrar compañía — bug corregido en el nuevo costeo).
- `step.tarja`: dependencia de **lectura** (no FK) — el costeo de movilización
  busca tarjas por fundo/fecha/compañía para resolver centro de costo y labor.
  Esta lectura pasa a vivir en `step_mobilization_agriculture` como adaptador;
  el núcleo (`step_mobilization`) sólo expone un hook/payload de distribución.

## 9. Step Tracker (maquinaria) — confirmado dominio separado

`step_tracker_odoo` (ya extraído previamente como ejemplo del mismo patrón) y la
copia interna en `step_hr` (`models/step_tracker.py`, `step_tracker_sync.py`)
son el tracker GPS de maquinaria agrícola vía FastAPI — modelos
`step.tracker.machine/driver/activity/labor/implement/field/session/work_order`.
**Cero solapamiento** de nombre de modelo/tabla con `step.movi.*`. No se toca.

## 10. Pruebas existentes

No existe ningún test para `step.movi.*` ni `hr.route` en todo el repositorio.
`step_hr` no tiene carpeta `tests/`. Se crean desde cero en `step_mobilization`.

## Nota sobre falso amigo léxico

"Movilización" también es un concepto de nómina no relacionado (haber de
movilización/transporte en indemnizaciones y libro de remuneraciones —
`step_hr_contract_lifecycle`, `step_hr_remuneration_book`). Confirmado que no
referencia ningún modelo de este inventario; no se toca.
