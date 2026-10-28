from odoo import api, fields, models, _
from odoo.exceptions import UserError

DTE_FIELDS = {'l10n_cl_dte_email': 'Correo DTE',
    'l10n_cl_sii_regional_office': 'Oficina regional SII',
    'l10n_cl_company_activity_ids': 'Actividades económicas',
    'l10n_cl_dte_resolution_number': 'Número de resolución SII',
    'l10n_cl_dte_resolution_date': 'Fecha de resolución SII'}


class Company(models.Model):
    _inherit = 'res.company'

    step_sii_configuration_pending = fields.Boolean(compute='_compute_step_sii_configuration')
    step_sii_missing_configuration = fields.Char(compute='_compute_step_sii_configuration')

    def _step_sii_missing_fields(self):
        self.ensure_one()
        if self.l10n_cl_dte_service_provider not in ('SII','SIITEST'):
            return []
        return [name for name in DTE_FIELDS if not self[name]]

    @api.depends('l10n_cl_dte_service_provider', *DTE_FIELDS)
    def _compute_step_sii_configuration(self):
        for company in self:
            missing=company._step_sii_missing_fields()
            company.step_sii_configuration_pending=bool(missing)
            company.step_sii_missing_configuration=', '.join(_(DTE_FIELDS[name]) for name in missing)

    def _step_check_sii_resolution(self):
        for company in self:
            missing=set(company._step_sii_missing_fields()) & {'l10n_cl_dte_resolution_number','l10n_cl_dte_resolution_date'}
            if missing:
                labels=', '.join(_(DTE_FIELDS[name]) for name in DTE_FIELDS if name in missing)
                raise UserError(_('Complete la configuración DTE de la empresa antes de procesar el documento con SII: %s',labels))


class Move(models.Model):
    _inherit = 'account.move'

    def _l10n_cl_edi_post_validation(self):
        # Preserve the provider's checks, including email requirements and the
        # native exceptions for document types; no real document is sent here.
        result=super()._l10n_cl_edi_post_validation()
        self.company_id._step_check_sii_resolution()
        return result
