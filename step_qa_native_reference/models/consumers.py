"""Keep native identities while moving only existing Steps overview logic."""
from odoo import api, models
from odoo.addons.step_quality_contracts.agriculture import inspection_summary, advisor_summary
from odoo.addons.step_quality_contracts.access import original_quality_provider


class QualityCheck(models.Model):
    _inherit = 'quality.check'

    @api.model
    def get_step_qa_dashboard(self, days=0):
        normal = self.sudo(False)
        return super(QualityCheck, normal).get_step_qa_dashboard(days=days)

    @api.model
    def _step_qa_inspection_summary(self, period_domain):
        return inspection_summary(self.sudo(False).env, period_domain)

    @api.model
    def _step_qa_advisor_summary(self, period_domain):
        return advisor_summary(self.sudo(False).env, period_domain)


class Package(models.Model):
    _inherit = 'stock.quant.package'

    def _trace_graph(self):
        normal = self.sudo(False)
        normal.check_access('read')
        original_quality_provider(normal.env)
        return super(Package, normal)._trace_graph()

    def _trace_search(self, model, domain):
        normal = self.sudo(False)
        if model == 'quality.check':
            original_quality_provider(normal.env)
        return super(Package, normal)._trace_search(model, domain)
