# -*- coding: utf-8 -*-

from odoo import fields, models


class ResCompany(models.Model):
    _inherit = "res.company"

    step_movi_journal_id = fields.Many2one('account.journal', string="Diario Movilización")
    step_movi_document_type_id = fields.Many2one('l10n_latam.document.type',
                                                   string='Tipo de documento Movilización')
    step_mobilization_offline_gps_retention_days = fields.Integer(
        string='Retención de puntos GPS (días)', default=180,
        help='Los puntos GPS crudos se conservan sólo este tiempo; los indicadores '
             'agregados de cumplimiento de recorrido no se ven afectados.')
    step_mobilization_auto_close_session = fields.Boolean(
        string='Cerrar sesión automáticamente al bajar el último pasajero', default=False,
        help='Si está desactivado, la app sólo ofrece cerrar y el chofer debe confirmar.')
