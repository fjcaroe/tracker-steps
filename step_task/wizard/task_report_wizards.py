# -*- coding: utf-8 -*-
"""Asistentes de consola para los informes de Steps Task.

La lógica vive en ``step.task.report`` (compartida con el controlador
``/api/task/report/*`` para la PWA). Estos wizards sólo capturan los filtros,
piden el XLSX y lo ofrecen como descarga.
"""

import base64

from odoo import fields, models


class TaskReportMixin(models.AbstractModel):
    _name = 'task.report.mixin'
    _description = 'Base de asistentes de informe Steps Task'

    file = fields.Binary(string='Archivo', readonly=True)
    file_name = fields.Char(string='Nombre archivo', readonly=True)

    # Clave del informe en ``step.task.report``. Cada wizard la define.
    _report_key = None

    def _report_params(self):
        """Traduce los campos del wizard a los parámetros de ``step.task.report``."""
        return {}

    def action_generate(self):
        self.ensure_one()
        report = self.env['step.task.report']
        result = report.build(self._report_key, self._report_params())
        data = report.to_xlsx(result)
        self.write({
            'file': base64.b64encode(data),
            'file_name': result.get('filename', '%s.xlsx' % self._report_key),
        })
        return {
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }


class ReportTaskData(models.TransientModel):
    _name = 'report.task.data'
    _inherit = 'task.report.mixin'
    _description = 'Informe Data Steps Task'
    _report_key = 'data'

    date_from = fields.Date(string='Desde', required=True,
                            default=lambda s: fields.Date.today().replace(day=1))
    date_to = fields.Date(string='Hasta', required=True, default=fields.Date.today)
    only_transmitted = fields.Boolean(string='Solo transmitidas', default=True)

    def _report_params(self):
        return {
            'date_from': fields.Date.to_string(self.date_from),
            'date_to': fields.Date.to_string(self.date_to),
            'only_transmitted': self.only_transmitted,
        }


class ReportTaskHours(models.TransientModel):
    _name = 'report.task.hours'
    _inherit = 'task.report.mixin'
    _description = 'Informe de horas diarias por trabajador'
    _report_key = 'hours'

    year = fields.Integer(string='Año', required=True, default=lambda s: fields.Date.today().year)
    month = fields.Selection(
        selection=[(str(i), fields.Date.today().replace(month=i, day=1).strftime('%B').capitalize())
                   for i in range(1, 13)],
        string='Mes', required=True, default=lambda s: str(fields.Date.today().month))
    jornada_hours = fields.Float(string='Horas jornada', default=8.0)
    fundo_id = fields.Many2one('step.fundo', string='Fundo')
    crew_id = fields.Many2one('hr.salary.custom', string='Cuadrilla')

    def _report_params(self):
        return {
            'year': self.year, 'month': self.month, 'jornada_hours': self.jornada_hours,
            'fundo_id': self.fundo_id.id, 'crew_id': self.crew_id.id,
        }


class ReportTaskYield(models.TransientModel):
    _name = 'report.task.yield'
    _inherit = 'task.report.mixin'
    _description = 'Informe de rendimientos diarios por trabajador'
    _report_key = 'yield'

    year = fields.Integer(string='Año', required=True, default=lambda s: fields.Date.today().year)
    month = fields.Selection(
        selection=[(str(i), fields.Date.today().replace(month=i, day=1).strftime('%B').capitalize())
                   for i in range(1, 13)],
        string='Mes', required=True, default=lambda s: str(fields.Date.today().month))
    fundo_id = fields.Many2one('step.fundo', string='Fundo')
    crew_id = fields.Many2one('hr.salary.custom', string='Cuadrilla')

    def _report_params(self):
        return {
            'year': self.year, 'month': self.month,
            'fundo_id': self.fundo_id.id, 'crew_id': self.crew_id.id,
        }


class ReportTaskYieldAnalysis(models.TransientModel):
    _name = 'report.task.yield.analysis'
    _inherit = 'task.report.mixin'
    _description = 'Análisis de rendimientos'
    _report_key = 'analysis'

    date_from = fields.Date(string='Desde', required=True,
                            default=lambda s: fields.Date.today().replace(day=1))
    date_to = fields.Date(string='Hasta', required=True, default=fields.Date.today)
    fundo_id = fields.Many2one('step.fundo', string='Fundo')

    def _report_params(self):
        return {
            'date_from': fields.Date.to_string(self.date_from),
            'date_to': fields.Date.to_string(self.date_to),
            'fundo_id': self.fundo_id.id,
        }
