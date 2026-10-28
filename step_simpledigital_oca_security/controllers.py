"""Authorize the supplier download routes before any supplier sudo search."""
from odoo import http, _
from odoo.http import request
from odoo.exceptions import UserError
from odoo.addons.step_payroll_contracts.history import stored_payslip_totals
from werkzeug.exceptions import BadRequest, Forbidden
from odoo.addons.l10n_cl_simpledigital_payroll.controllers.previred_txt import PreviredExportController
from odoo.addons.l10n_cl_simpledigital_payroll.controllers.libro_remuneraciones import LibroRemuneracionesController


def authorized_company(env, company_id):
    manager=env.ref('payroll.group_payroll_manager')
    # Group definitions pick one primary XML ID; an alias is not a has_group key.
    if manager not in env.user.groups_id:
        raise Forbidden()
    try:
        selected=int(company_id or env.company.id)
    except (ValueError,TypeError):
        raise BadRequest()
    if selected != env.company.id or selected not in env.companies.ids:
        raise Forbidden()
    model=env['hr.payslip']
    model.check_access('read')
    domain=[('company_id','=',selected)]
    # The supplier uses sudo internally. Deny when it could reveal hidden rows.
    if set(model.search(domain).ids)!=set(model.sudo().search(domain).ids):
        raise Forbidden()
    return selected


class Previred(PreviredExportController):
    @http.route()
    def download_previred_txt(self, period=None, company_id=None, **kw):
        return super().download_previred_txt(period=period,company_id=authorized_company(request.env,company_id),**kw)

    @http.route()
    def download_previred_csv(self, period=None, company_id=None, **kw):
        return super().download_previred_csv(period=period,company_id=authorized_company(request.env,company_id),**kw)


class Book(LibroRemuneracionesController):
    def _get_payslips(self, date_from, date_to, company_id):
        company_id = authorized_company(request.env, company_id)
        if date_from > date_to:
            raise BadRequest()
        # Keep the supplier's period and terminal-state contract, without elevation.
        payslips = request.env['hr.payslip'].search([
            ('date_from', '>=', date_from), ('date_to', '<=', date_to),
            ('company_id', '=', company_id), ('state', 'in', ['done', 'paid'])],
            order='employee_id, date_from')
        # Validate the complete history before any supplier row formatter can
        # catch an exception and replace an incomplete concept with zero.
        stored_payslip_totals(payslips)
        return payslips

    def _get_payslip_lines(self, payslip, rule_codes=None):
        if not payslip or payslip._name != 'hr.payslip' or len(payslip) != 1:
            raise UserError(_('The remuneration book requires one real saved payroll slip.'))
        # Never retain a supplier sudo environment or swallow incomplete history.
        actual = request.env['hr.payslip'].browse(payslip.id)
        totals = stored_payslip_totals(actual, rule_codes)
        # Preserve the real supplier API's integer truncation; this is not a new
        # Chile rounding policy or certification of its remaining CSV columns.
        return int(totals[actual.id])

    @http.route()
    def export_libro_remuneraciones_csv(self,date_from,date_to,include_header='True',company_id=None,**kwargs):
        return super().export_libro_remuneraciones_csv(date_from,date_to,include_header=include_header,
            company_id=authorized_company(request.env,company_id),**kwargs)
