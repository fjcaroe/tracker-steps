# -*- coding: utf-8 -*-

from odoo import fields, models


class StepMoviRegistryLine(models.Model):
    _name = 'step.movi.registry.line'
    _description = 'Pasajero de un viaje de movilización'
    _rec_name = 'employee_id'

    employee_id = fields.Many2one('hr.employee', 'Empleado', required=True)
    movi_id = fields.Many2one('step.movi.registry', string="Viaje",
                               required=True, ondelete='cascade', index=True, copy=False)
    cod_nip = fields.Char(related='employee_id.pin', string='Código NIP')
    operacion = fields.Selection(
        selection=[('in', 'Entrada'), ('out', 'Salida')],
        string='Operación', required=True, copy=False)
    hr_in = fields.Datetime(string="Hora subida")
    hr_out = fields.Datetime(string="Hora bajada")
    passenger_event_id = fields.Many2one('step.mobilization.passenger.event', string='Evento origen',
                                          copy=False, readonly=True,
                                          help='Marca esta línea como proyección de un evento de la app móvil; '
                                               'evita duplicarla al re-sincronizar.')
    # informes / campos relacionados
    parent_name = fields.Char(related='movi_id.name', string='Nombre')
    date = fields.Date(related='movi_id.date', string='Fecha')
    recorrido_id = fields.Many2one(related='movi_id.recorrido_id', string='Recorrido')
    vehicle_id = fields.Many2one(related='movi_id.vehicle_id', string='Vehículo')
    responsable_id = fields.Many2one(related='movi_id.responsable_id', string='Responsable')
    partner_id = fields.Many2one(related='movi_id.partner_id', string='Transportista')
    chofer_id = fields.Many2one(related='movi_id.chofer_id', string='Chofer')
    pricelist_id = fields.Many2one(related='movi_id.pricelist_id', string='Lista de tarifa')
    company_id = fields.Many2one(related='movi_id.company_id', string='Empresa', store=True)
    state = fields.Selection(related='movi_id.state', string='Estado')
    invoice_id = fields.Many2one(related='movi_id.invoice_id', string='Contabilización')

    _sql_constraints = [
        ('event_unique', 'unique(passenger_event_id)',
         'Un evento de marcación sólo puede proyectarse una vez a una línea de pasajero.'),
    ]
