# -*- coding: utf-8 -*-

from odoo import fields, models


class StepMoviCostLine(models.Model):
    _name = 'step.movi.cost.line'
    _description = 'Costo de pasajero de un viaje de movilización'
    _rec_name = 'employee_id'

    employee_id = fields.Many2one('hr.employee', 'Empleado', required=True)
    movi_id = fields.Many2one('step.movi.registry', string="Viaje",
                               required=True, ondelete='cascade', index=True, copy=False)
    cod_nip = fields.Char(related='employee_id.pin', string='Código NIP')
    recorrido_ent = fields.Char('Recorrido entrada')
    recorrido_sal = fields.Char('Recorrido salida')
    cost_in = fields.Float(string='Costo entrada')
    cost_out = fields.Float(string='Costo salida')
    cost_total = fields.Float(string='Costo pasajero')
    cost_id = fields.Many2one('account.analytic.account', "Centro de costo")
    labor_id = fields.Many2one('product.template', 'Labor/Tarea')
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

    def _get_extra_analytic_account_ids(self):
        """Hook de extensión: el núcleo no conoce campos agrícolas como
        product.template.actividad_id (los añade step_hr). El adaptador
        agrícola sobreescribe este método para sumarlos."""
        self.ensure_one()
        return []

    def _get_analytic_distribution(self):
        """Arma la distribución analítica sólo con cuentas realmente
        configuradas; ninguna clave 'False' concatenada (bug detectado en
        step_hr, que insertaba str(False) cuando faltaba cost_id/labor_id)."""
        self.ensure_one()
        account_ids = []
        if self.cost_id:
            account_ids.append(self.cost_id.id)
        account_ids += self._get_extra_analytic_account_ids()
        if not account_ids:
            return {}
        key = ','.join(str(account_id) for account_id in account_ids)
        return {key: 100}
