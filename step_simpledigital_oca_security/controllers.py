"""Authorize the supplier download routes before any supplier sudo search."""
from odoo import http
from odoo.http import request
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
    @http.route()
    def export_libro_remuneraciones_csv(self,date_from,date_to,include_header='True',company_id=None,**kwargs):
        return super().export_libro_remuneraciones_csv(date_from,date_to,include_header=include_header,
            company_id=authorized_company(request.env,company_id),**kwargs)
