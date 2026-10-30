"""Route one original action name to the registered stored Community renderer.

No action, external ID, report model, template or salary value is declared here.
The native runtime, without the real CE backend, follows its unchanged pipeline.
"""
from odoo import _, models
from odoo.exceptions import AccessError, UserError
from odoo.tools import is_html_empty


ORIGINAL_NAME = 'hr_payroll.report_payslip_lang'
TEMPLATE = 'step_simpledigital_oca_base.report_payslip'
RENDERER = 'report.' + TEMPLATE
BACKEND_MODULE = 'odoo.addons.step_simpledigital_oca_base.report.payslip_report'


class OriginalPayrollReportRoute(models.Model):
    _inherit = 'ir.actions.report'

    def _step_original_report_ce_renderer(self):
        if RENDERER not in self.env.registry:
            return None
        renderer = self.sudo(False).env[RENDERER]
        if (renderer._original_module != 'step_simpledigital_oca_base'
                or renderer._get_report_values.__module__ != BACKEND_MODULE):
            raise UserError(_('The original report requires the actual stored Community renderer.'))
        return renderer

    def _step_original_report_target(self, report_ref):
        if RENDERER not in self.env.registry:
            return None
        normal = self.sudo(False)
        # This is the official configuration lookup with sudo, never the salary
        # environment. Rebind a record argument to the actual caller's UID.
        configured = normal._get_report(report_ref)
        report = normal.browse(configured.ids).sudo()
        if len(report) != 1 or report.report_name != ORIGINAL_NAME:
            return None
        renderer = normal._step_original_report_ce_renderer()
        return normal, report, renderer

    def _step_original_report_values(self, target, docids, data=None):
        normal, report, renderer = target
        if (not isinstance(docids, (list, tuple)) or not docids
                or any(type(value) is not int or value <= 0 for value in docids)
                or len(set(docids)) != len(docids)):
            raise UserError(_('Select existing payslips once each to print the original report.'))
        context = normal.env.context
        for key in ('uid', 'user_id'):
            if key in context and (type(context[key]) is not int or context[key] != normal.env.uid):
                raise AccessError(_('The report cannot select another actor from context.'))
        if (any(key in context for key in ('force_user_id', 'report_user_id', 'employee_id', 'as_user'))
                or context.get('sudo') or context.get('report_sudo')
                or any(key in context for key in ('docs', 'doc_ids', 'doc_model', 'step_report_net'))):
            raise AccessError(_('The original report context contains unsupported actor or financial overrides.'))
        if data is not None:
            if not isinstance(data, dict) or set(data) - {'context', 'report_type', 'debug'}:
                raise UserError(_('The original report does not accept financial or document payloads.'))
            # Official PDF preparation sets debug=False before calling HTML.
            # Admit that inert literal, never arbitrary caller/template data.
            if 'debug' in data and data['debug'] is not False:
                raise UserError(_('Unsupported original report debug payload.'))
            if 'report_type' in data and data['report_type'] not in ('html', 'pdf'):
                raise UserError(_('Unsupported original report output type.'))
            transport = data.get('context', {})
            if not isinstance(transport, dict) or any(key not in context or context[key] != value for key, value in transport.items()):
                raise AccessError(_('Report transport context does not match the actual actor environment.'))
        if report.model != 'hr.payslip' or report.report_type not in ('qweb-pdf', 'qweb-html'):
            raise UserError(_('The original action must be a real payslip QWeb report.'))
        if report.groups_id and not (set(report.groups_id.ids) & set(normal.env.user._get_group_ids())):
            raise AccessError(_('Your role is not allowed to print this report action.'))
        # No cached attachment may be evaluated, retrieved or returned, even
        # when a request tries report_pdf_no_attachment to bypass this policy.
        if report.attachment or report.attachment_use:
            raise UserError(_('Attachment expressions and cached payroll reports require a separate admission.'))
        values = renderer._get_report_values(list(docids))
        if values['docs'].env.su or values['docs'].env.uid != normal.env.uid:
            raise AccessError(_('The stored payroll renderer did not retain the actual actor.'))
        values = dict(values, is_html_empty=is_html_empty,
                      report_type=(data or {}).get('report_type', 'html'))
        return values

    def _render_qweb_html(self, report_ref, docids, data=None):
        target = self._step_original_report_target(report_ref)
        if target is None:
            return super()._render_qweb_html(report_ref, docids, data=data)
        values = self._step_original_report_values(target, docids, data)
        return target[0]._render_template(TEMPLATE, values), 'html'

    def _pre_render_qweb_pdf(self, report_ref, res_ids=None, data=None):
        target = self._step_original_report_target(report_ref)
        if target is None:
            return super()._pre_render_qweb_pdf(report_ref, res_ids=res_ids, data=data)
        # Official preparation reads attachments before it calls the HTML
        # renderer. Full salary/child/field checks MUST run before that stage.
        self._step_original_report_values(target, res_ids, data)
        return super(OriginalPayrollReportRoute, target[0])._pre_render_qweb_pdf(
            target[1].id, res_ids=res_ids, data=data)
