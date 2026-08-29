# -*- coding: utf-8 -*-

from odoo import fields, models


class StepMoviContLine(models.Model):
    """Detalle de distribución contable por pasajero. Existía en step_hr sin
    usarse (nunca se poblaba, campos ocultos en la vista). Se conserva la
    tabla/modelo intactos; queda disponible como hook para que el adaptador
    agrícola registre la distribución por horas/labor si lo necesita — no se
    inventa una fórmula de negocio que no está confirmada en los documentos
    fuente."""
    _name = 'step.movi.cont.line'
    _description = 'Distribución contable de un pasajero (detalle auditable)'
    _rec_name = 'employee_id'

    employee_id = fields.Many2one('hr.employee', 'Empleado', required=True)
    movi_id = fields.Many2one('step.movi.registry', string="Viaje",
                               required=True, ondelete='cascade', index=True, copy=False)
    cod_nip = fields.Char(related='employee_id.pin', string='Código NIP')
    cost_id = fields.Many2one('account.analytic.account', "Centro de costo")
    labor_id = fields.Many2one('product.template', 'Labor/Tarea')
    hrs_total = fields.Float(string='Horas totales')
    hrs_porcen = fields.Float(string='Horas %')
    dist_movi = fields.Float(string='Distribución movilización')
