# -*- coding: utf-8 -*-
# Puerto desde Studio (steps_qa, app Packing Fruta > Orden de fabricacion) - ticket 34.
# Solo se portan los datos de cabecera del proceso de fruta. Las grillas de
# costeo que Studio agrego a la orden (mano de obra, maquinaria, servicios y
# materia prima) no se portan: casi no tenian uso y el costeo vive en
# Gestion y Costos.
from odoo import fields, models


class MrpProduction(models.Model):
    _inherit = 'mrp.production'

    fruit_process_type_id = fields.Many2one('step.packing.process.type', string='Tipo de proceso')
    fruit_shift = fields.Char(string='Turno')
    fruit_grower_id = fields.Many2one('res.partner', string='Productor')
    fruit_fundo_id = fields.Many2one('step.fundo', string='Productor - Fundo')
    fruit_species_id = fields.Many2one('step.especie', string='Especie')
    fruit_variety_id = fields.Many2one(
        'step.variedad', string='Variedad',
        domain="[('especie_id', '=?', fruit_species_id)]")
    fruit_commercial_variety_id = fields.Many2one(
        'step.variedad', string='Variedad comercial',
        domain="[('especie_id', '=?', fruit_species_id)]")
    fruit_type = fields.Char(string='Tipo de fruta')
    fruit_service_customer_id = fields.Many2one('res.partner', string='Cliente de servicio')
    fruit_receiver_id = fields.Many2one('res.partner', string='Recibidor')
    fruit_shipment_ref = fields.Char(string='Embarque')
    fruit_order_ref = fields.Char(string='Pedido')
