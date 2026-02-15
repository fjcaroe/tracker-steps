# © 2025 (Jamie Escalante <jamie.escalante7@gmail.com>)
# -*- coding: utf-8 -*-

from odoo import api, models, fields

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

