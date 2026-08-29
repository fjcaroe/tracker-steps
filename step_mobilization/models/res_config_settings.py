# -*- coding: utf-8 -*-

from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    step_movi_journal_id = fields.Many2one(
        'account.journal', string="Diario Movilización",
        related='company_id.step_movi_journal_id', readonly=False)
    step_movi_document_type_id = fields.Many2one(
        'l10n_latam.document.type', string='Tipo de documento Movilización',
        related='company_id.step_movi_document_type_id', readonly=False)
    step_mobilization_offline_gps_retention_days = fields.Integer(
        related='company_id.step_mobilization_offline_gps_retention_days', readonly=False)
    step_mobilization_auto_close_session = fields.Boolean(
        related='company_id.step_mobilization_auto_close_session', readonly=False)
