from odoo import api, models, _
from odoo.exceptions import AccessError, ValidationError
from odoo.addons.step_export_branch_consolidation.models import branch_companies


class Comparisons(models.Model):
    _inherit = 'step.packing.order'

    @api.model
    def _producer_holding_companies(self, company_ids=None):
        permitted = branch_companies(self.env, self.env.company)
        if company_ids is None:
            return permitted
        if not isinstance(company_ids, list) or not company_ids or any(type(i) is not int for i in company_ids):
            raise ValidationError(_('Seleccione al menos una compañía o sucursal.'))
        selected = self.env['res.company'].browse(company_ids)
        if selected - permitted:
            raise AccessError(_('El panel solo incluye compañías del holding ya autorizadas al usuario.'))
        return selected

    @api.model
    def operational_comparison(self, kind='producers', filters=None):
        if kind != 'producers':
            return super().operational_comparison(kind=kind, filters=filters)
        filters = dict(filters or {})
        selected = self._producer_holding_companies(filters.pop('company_ids', None))
        # Scope only this read request; no membership or global company selection changes.
        scoped = self.with_context(allowed_company_ids=selected.ids)
        result = super(Comparisons, scoped).operational_comparison(kind=kind, filters=filters)
        permitted = self._producer_holding_companies()
        result.update(companies=[{'id': company.id, 'name': company.display_name} for company in permitted],
                      selected_company_ids=selected.ids)
        return result

    @api.model
    def producer_holding_counts(self, company_ids=None):
        companies = self._producer_holding_companies(company_ids)
        scoped = self.with_context(allowed_company_ids=companies.ids)
        return {
            'producers': scoped.env['res.partner'].search_count([('is_productor', '=', True)]),
            'farms': scoped.env['step.fundo'].search_count([('partner_id.is_productor', '=', True)]),
            'estimates': scoped.env['step.export.estimate'].search_count([('company_id', 'in', companies.ids), ('state', '=', 'current')]),
            'settlements': scoped.env['step.export.producer.settlement'].search_count([('company_id', 'in', companies.ids), ('state', 'in', ['draft', 'validated'])]),
        }
