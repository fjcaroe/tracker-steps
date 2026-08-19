# © 2025 (Jamie Escalante <jamie.escalante7@gmail.com>)
# -*- coding: utf-8 -*-

from odoo import api, models, fields, _
from odoo.exceptions import UserError, ValidationError, RedirectWarning

class ResCompany(models.Model):
    _inherit = "res.company"

    step_journal_id = fields.Many2one('account.journal', string="Diario Contratista")
    step_document_type_id = fields.Many2one('l10n_latam.document.type', string='Tipo de Documento Contratista')
    step_cosecha_journal_id = fields.Many2one('account.journal', string="Diario Cosecha")
    step_cosecha_document_type_id = fields.Many2one('l10n_latam.document.type', string='Tipo de Documento Cosecha')
    step_movi_journal_id = fields.Many2one('account.journal', string="Diario Movilización")
    step_movi_document_type_id = fields.Many2one('l10n_latam.document.type', string='Tipo de Documento Movilización')
    # account_propio_id = fields.Many2one('account.account', string='Cuenta Transitoria Contabilización Propia')
    propio_journal_id = fields.Many2one('account.journal', string="Diario Transitorio para Contabilización Propia")
    movi_product_id = fields.Many2one('product.product', string='Servicio Facturación')
    gratificacion_legal = fields.Boolean('Aplica Gratificación L. Manual', default=True)
    sema_corrida_legal = fields.Boolean('Aplica Semana corrida Manual', default=True)
    gratifica = fields.Float(string='Gratificación', default=0.25, digits=(2, 2))
    sema_corrida = fields.Integer(string='Semana corrida', default=5)
    step_seguro = fields.Float(string='Seguro', default=0.07, digits=(2, 2))
    step_feriado = fields.Float(string='Feriado', default=0.05833, digits=(2, 5))
    step_ias = fields.Float(string='IAS', default=0.0833, digits=(2, 4))

    # Integración Web Tracker (monitoreo GPS de maquinaria agrícola)
    step_tracker_base_url = fields.Char(
        string='URL API Web Tracker',
        help='URL del backend de Web Tracker, sin barra final. '
             'Ej: https://stepsapp.cl/tracker-api (NO la URL del sitio web_tracker/).')
    step_tracker_username = fields.Char(string='Usuario de servicio Web Tracker')
    step_tracker_password = fields.Char(string='Contraseña de servicio Web Tracker')
    step_tracker_sync_enabled = fields.Boolean(string='Sincronización automática activa', default=False)

    @api.onchange('gratifica')
    def onchange_gratifica(self):
        self.ensure_one()
        for record in self:
            if record.gratifica:
                if record.gratifica > 5:
                    raise ValidationError(_("No puede sobrepasar el Tope!"))