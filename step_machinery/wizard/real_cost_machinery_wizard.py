# © 2025 (Jamie Escalante <jamie.escalante7@gmail.com>)
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import api, fields, models, tools, SUPERUSER_ID, _, Command
import base64
import calendar
from datetime import datetime, date, timedelta

class RealCostMachineryWizard(models.TransientModel):
    _name = 'real.cost.machinery.wizard'
    _description = 'Crear costos reales de maquinarias existentes'
    _check_company_auto = True

    @api.depends('date')
    def compute_wizard(self):
        for move in self:
            if move.date:
                move.temp_id = self.env['step.temporada'].search(
                    [('start_date', '<=', move.date),
                     ('end_date', '>=', move.date)], limit=1).id
                date_init = str(move.date.year) + '-' + str(move.date.month).zfill(2) + '-' + '01'
                move.date_init = datetime.strptime(date_init, '%Y-%m-%d')
                ultimo_de_mes = calendar.monthrange(move.date.year, move.date.month)
                move.date_to = str(move.date.year) + '-' + str(move.date.month).zfill(2) + '-' + str(
                    ultimo_de_mes[1])
                maquinas = self.env['step.hrs.machinery.line'].search(
                    [('date', '>=', move.date_init),
                     ('date', '<=', move.date_to),
                     ('progress_cost', '=', False)]).machinery_ids
                move.machinery_domain = maquinas.ids
                move.machinery_ids = maquinas.ids

    # Parámetros
    date = fields.Date(string='Fecha')
    date_init = fields.Date(string='Periodo Inicio', compute='compute_wizard', store=True)
    date_to = fields.Date(string='Periodo Fin', compute='compute_wizard', store=True)
    machinery_ids = fields.Many2many(comodel_name='fleet.vehicle', relation='machinery_ids_real_rel', string='Maquinarias')
    machinery_domain = fields.Many2many(comodel_name='fleet.vehicle', relation='machinery_ids_domain_rel', string='Maquinarias', compute='compute_wizard', store=True)
    mes_select = fields.Selection(
        [('today', 'Este mes'), ('last', 'Otro')], string='Mes a costear', required=False)
    # cost_id = fields.Many2one(
    #     'step.centro.costo', "Centro costos",
    # )
    company_id = fields.Many2one('res.company', string='Compañía', required=True, default=lambda self: self.env.company)
    temp_id = fields.Many2one("step.temporada", string="Temporada", compute='compute_wizard', store=True)


    def action_cost_create(self):
        resultado_ok = []
        resultado_err = []
        for machinery in self.machinery_ids:
            vals = {
                'name': str(machinery.name)+'/'+str(self.date),
                'machinery_ids': machinery.id,
                'date': self.date,
                'date_init': self.date_init,
                'date_to': self.date_to,
                # 'fundo_id': 1,
                'company_id': self.company_id.id,
                'temp_id': self.temp_id.id,
                # 'responsable_id': 1,
                'cost_id': machinery.cost_id.id,
                'state': 'draft',
            }
            create_real_cost = self.env['real.cost.machinery'].create(vals)
            create_real_cost.action_cost_detail()
            if create_real_cost:
                resultado_ok.append(create_real_cost.name or create_real_cost.id)
            else:
                resultado_err.append(create_real_cost.name or create_real_cost.id)
            self.env.cr.commit()
        resumen = "¡Transacción culminada!\n"
        if resultado_ok:
            resumen += "Enviadas OK: %s\n" % (", ".join(map(str, resultado_ok)))
        if resultado_err:
            resumen += "Con error: %s" % (", ".join(f"{n} ({m})" for n, m in resultado_err))

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Resultado de la transmisión',
                'message': resumen,
                'type': 'success' if resultado_err == [] else 'warning',
                'sticky': False,
            },
        }

    def action_cost_create_cost(self):
        resultado_ok = []
        resultado_err = []
        for machinery in self.machinery_ids:
            vals = {
                'name': str(machinery.name)+'/'+str(self.date),
                'machinery_ids': machinery.id,
                'date': self.date,
                'date_init': self.date_init,
                'date_to': self.date_to,
                # 'fundo_id': 1,
                'company_id': self.company_id.id,
                'temp_id': self.temp_id.id,
                # 'responsable_id': 1,
                'cost_id': machinery.cost_id.id,
                'state': 'draft',
            }
            create_real_cost = self.env['real.cost.machinery'].create(vals)
            create_real_cost.action_cost_detail()
            create_real_cost.action_costo()
            create_real_cost.action_regist_detail()
            if create_real_cost:
                resultado_ok.append(create_real_cost.name or create_real_cost.id)
            else:
                resultado_err.append(create_real_cost.name or create_real_cost.id)
            self.env.cr.commit()
        resumen = "¡Transacción culminada!\n"
        if resultado_ok:
            resumen += "Enviadas OK: %s\n" % (", ".join(map(str, resultado_ok)))
        if resultado_err:
            resumen += "Con error: %s" % (", ".join(f"{n} ({m})" for n, m in resultado_err))

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Resultado de la transmisión',
                'message': resumen,
                'type': 'success' if resultado_err == [] else 'warning',
                'sticky': False,
            },
        }

    def action_cost_create_conta(self):
        resultado_ok = []
        resultado_err = []
        for machinery in self.machinery_ids:
            vals = {
                'name': str(machinery.name)+'/'+str(self.date),
                'machinery_ids': machinery.id,
                'date': self.date,
                'date_init': self.date_init,
                'date_to': self.date_to,
                # 'fundo_id': 1,
                'company_id': self.company_id.id,
                'temp_id': self.temp_id.id,
                # 'responsable_id': 1,
                'cost_id': machinery.cost_id.id,
                'state': 'draft',
            }
            create_real_cost = self.env['real.cost.machinery'].create(vals)
            create_real_cost.action_cost_detail()
            create_real_cost.action_costo()
            create_real_cost.action_conta()
            if create_real_cost:
                resultado_ok.append(create_real_cost.name or create_real_cost.id)
            else:
                resultado_err.append(create_real_cost.name or create_real_cost.id)
            self.env.cr.commit()
        resumen = "¡Transacción culminada!\n"
        if resultado_ok:
            resumen += "Enviadas OK: %s\n" % (", ".join(map(str, resultado_ok)))
        if resultado_err:
            resumen += "Con error: %s" % (", ".join(f"{n} ({m})" for n, m in resultado_err))

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Resultado de la transmisión',
                'message': resumen,
                'type': 'success' if resultado_err == [] else 'warning',
                'sticky': False,
            },
        }



