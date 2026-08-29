# -*- coding: utf-8 -*-
"""Reasigna la propiedad de los elementos de Movilización de step_hr a
step_mobilization SIN tocar ninguna tabla de datos de negocio.

Contexto (ver docs/movilizacion/02_ARQUITECTURA_Y_DECISIONES.md):
- step.movi.registry(.line), step.movi.cost.line, step.movi.cont.line,
  hr.route(.line) y product.pricelist.move.line CONSERVAN su _name y su
  tabla física. Sólo cambia qué addon declara sus vistas/acciones/menús.
- Este script debe correr como parte de la MISMA operación de actualización
  que instala step_mobilization por primera vez (`-u step_hr -i
  step_mobilization`), para que ningún registro quede sin una clase Python
  que lo declare durante la transición.
- Se reasignan ir.ui.view / ir.actions.act_window / ir.ui.menu porque, si no,
  la limpieza normal de Odoo las borraría al ver que step_hr dejó de
  declararlas (arrastrando consigo cualquier favorito/atajo que apunte a su
  ID). Los registros de ir.model.access.csv de Movilización NO se reasignan
  a propósito: el objetivo es justamente reemplazar el acceso CRUD abierto a
  base.group_user (riesgo detectado en la auditoría) por los grupos nuevos de
  step_mobilization, así que se dejan caer con la actualización de step_hr y
  las nuevas filas del CSV de step_mobilization las reemplazan.
- No se reasigna ir.model / ir.model.fields: Odoo los actualiza in-place por
  reflexión de la clase Python activa, sin importar qué addon la declare, así
  que no hay riesgo de pérdida ni necesidad de tocar ir_model_data para eso.
"""

import logging

_logger = logging.getLogger(__name__)

VIEWS = [
    'view_step_movi_registry_form',
    'view_step_movi_registry_list',
    'view_step_movi_line_pivot',
    'view_step_movi_line_graph',
    'view_step_movi_line_list',
    'view_step_movi_line_search',
    'view_step_movi_cost_pivot',
    'view_step_movi_cost_graph',
    'view_step_movi_cost_list',
    'view_step_movi_cost_search',
    'view_hr_route_form',
    'view_hr_route_list',
]

ACTIONS = [
    'action_step_movi_registry',
    'action_step_movi_registry_costeo',
    'action_view_step_movi_line',
    'action_view_step_movi_cost',
    'action_hr_route',
    'step_product_pricelist_action_movi',
    'action_partner_supplier_form_step',
    'action_step_movi_in_invoice',
]

MENUS = [
    'menu_step_movi_registry',
    'menu_step_movi_registry_costo',
    'menu_step_movi_tarifa',
    'menu_acount_movi',
    'menu_step_movi_line',
    'menu_step_movi_cost',
    'menu_prove_movi',
    'menu_hr_route',
]
# menu_step_moviliza (contenedor) y menu_step_tracker (placeholder vacío) NO
# se reasignan: no tienen equivalente de mismo ID en step_mobilization (la
# app nueva tiene su propio menú raíz, y "Step Tracker" fue reemplazado por
# el "Seguimiento en línea" real sobre step.movi.registry, no por otro
# placeholder). Se dejan caer con la actualización de step_hr.


def _reassign(cr, model, names):
    if not names:
        return
    cr.execute(
        "UPDATE ir_model_data SET module = 'step_mobilization' "
        "WHERE module = 'step_hr' AND model = %s AND name = ANY(%s) "
        "RETURNING name",
        (model, list(names)),
    )
    found = {row[0] for row in cr.fetchall()}
    missing = set(names) - found
    if missing:
        _logger.warning(
            "step_hr->step_mobilization: %s ir_model_data no encontrados para %s "
            "(module=step_hr) - probablemente ya migrados u orphaned: %s",
            model, model, missing,
        )
    _logger.info("step_hr->step_mobilization: reasignados %d registros %s", len(found), model)


def _seed_company_sequences(cr):
    """Crea, por cada compañía existente, la secuencia por-compañía que
    step_mobilization usará (step.movi.registry._next_sequence), sembrada con
    el valor actual de la secuencia global heredada para no reutilizar
    folios MV ya emitidos. La secuencia global antigua se conserva
    (renombrada) para trazabilidad, no se borra."""
    cr.execute("SELECT id, number_next, number_increment, padding, prefix "
               "FROM ir_sequence WHERE code = 'step_moviliza_seq' AND company_id IS NULL "
               "LIMIT 1")
    legacy = cr.fetchone()
    if not legacy:
        _logger.info("step_hr->step_mobilization: no había secuencia global step_moviliza_seq, nada que sembrar.")
        return
    legacy_id, number_next, increment, padding, prefix = legacy

    cr.execute("SELECT id, name FROM res_company")
    companies = cr.fetchall()
    for company_id, company_name in companies:
        cr.execute(
            "SELECT id FROM ir_sequence WHERE code = 'step_moviliza_seq' AND company_id = %s",
            (company_id,),
        )
        if cr.fetchone():
            continue
        cr.execute(
            "INSERT INTO ir_sequence "
            "(name, code, company_id, number_next, number_increment, padding, prefix, implementation, active) "
            "VALUES (%s, 'step_moviliza_seq', %s, %s, %s, %s, %s, 'standard', true)",
            (f"Movilización ({company_name})", company_id, number_next, increment, padding, prefix or 'MV'),
        )
    cr.execute(
        "UPDATE ir_sequence SET name = name || ' (legado, no usar)' WHERE id = %s",
        (legacy_id,),
    )
    _logger.info("step_hr->step_mobilization: sembradas secuencias por compañía desde number_next=%s",
                 number_next)


def migrate(cr, version):
    _reassign(cr, 'ir.ui.view', VIEWS)
    _reassign(cr, 'ir.actions.act_window', ACTIONS)
    _reassign(cr, 'ir.ui.menu', MENUS)
    _seed_company_sequences(cr)
