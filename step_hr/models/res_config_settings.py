# © 2025 (Jamie Escalante <jamie.escalante7@gmail.com>)
# -*- coding: utf-8 -*-

from odoo import api, models, fields, _

class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    step_journal_id = fields.Many2one('account.journal', string="Diario Contratista", related='company_id.step_journal_id',
                                      required=False, readonly=False)
    step_document_type_id = fields.Many2one('l10n_latam.document.type', string='Tipo de Documento Contratista',
                                            related='company_id.step_document_type_id', readonly=False)
    step_cosecha_journal_id = fields.Many2one('account.journal', string="Diario Cosecha", related='company_id.step_cosecha_journal_id',
                                      required=False, readonly=False)
    step_cosecha_document_type_id = fields.Many2one('l10n_latam.document.type', string='Tipo de Documento Cosecha',
                                            related='company_id.step_cosecha_document_type_id', readonly=False)
    step_movi_journal_id = fields.Many2one('account.journal', string="Diario Movilización", related='company_id.step_movi_journal_id',
                                      required=False, readonly=False)
    step_movi_document_type_id = fields.Many2one('l10n_latam.document.type', string='Tipo de Documento Movilización',
                                            related='company_id.step_movi_document_type_id', readonly=False)
    # account_propio_id = fields.Many2one('account.account', string='Cuenta Transitoria Contabilización Propia', related='company_id.account_propio_id', readonly=False)
    propio_journal_id = fields.Many2one('account.journal', string="Diario Transitorio para Contabilización Propia",
                                           related='company_id.propio_journal_id',
                                           required=False, readonly=False)
    movi_product_id = fields.Many2one('product.product', 'Servicio Facturación', related='company_id.movi_product_id',
                                      required=False, readonly=False)

    step_tracker_base_url = fields.Char(related='company_id.step_tracker_base_url', readonly=False)
    step_tracker_username = fields.Char(related='company_id.step_tracker_username', readonly=False)
    step_tracker_password = fields.Char(related='company_id.step_tracker_password', readonly=False)
    step_tracker_sync_enabled = fields.Boolean(related='company_id.step_tracker_sync_enabled', readonly=False)

    def action_step_tracker_sync_now(self):
        self.ensure_one()
        counts = self.env['step.tracker.sync'].run_sync()
        message = _(
            'Sincronizado: %(machines)s máquinas, %(drivers)s conductores, '
            '%(fields)s predios, %(sessions)s sesiones, %(work_orders)s partes.'
        ) % {
            'machines': counts['machines'],
            'drivers': counts['drivers'],
            'fields': counts['fields'],
            'sessions': counts['sessions'],
            'work_orders': counts['work_orders'],
        }
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {'title': _('Web Tracker'), 'message': message, 'sticky': False, 'type': 'success'},
        }

