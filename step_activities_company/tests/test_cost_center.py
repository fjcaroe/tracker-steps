from types import SimpleNamespace

from lxml import etree

from odoo.tests import TransactionCase, tagged
from odoo.tools.safe_eval import safe_eval


@tagged('post_install', '-at_install')
class TestCostCenterWithoutTariff(TransactionCase):
    def test_native_selectors_use_company_cost_plan_without_tariff(self):
        company = self.env.company
        other = self.env['res.company'].create({'name': 'QA Empresa Ajena'})
        plans = self.env['account.analytic.plan'].with_context(lang='en_US')
        cost_plan = plans.search([('name', 'in', ['Centro de costos', 'Centro Costos'])], limit=1)
        cost_plan = cost_plan or plans.create({'name': 'Centro de costos'})
        subplan = plans.create({'name': 'QA Sección', 'parent_id': cost_plan.id})
        other_plan = plans.create({'name': 'QA Actividad'})
        accounts = self.env['account.analytic.account'].with_context(lang='en_US', active_test=False)
        eligible, foreign, archived, activity = accounts.create([
            {'name': 'QA Centro', 'company_id': company.id, 'plan_id': subplan.id},
            {'name': 'QA Centro Ajeno', 'company_id': other.id, 'plan_id': cost_plan.id},
            {'name': 'QA Archivado', 'company_id': company.id, 'plan_id': cost_plan.id, 'active': False},
            {'name': 'QA Actividad', 'company_id': company.id, 'plan_id': other_plan.id},
        ])
        form = self.env['step.tarja'].get_view(
            view_id=self.env.ref('step_hr.view_step_tarja_form').id, view_type='form',
        )
        nodes = etree.fromstring(form['arch']).xpath("//list/field[@name='cost_id']")
        self.assertEqual(len(nodes), 3)
        context = {'parent': SimpleNamespace(company_id=company.id, pricelist_id=False),
                   'cost_id_domain': [activity.id]}
        fixtures = [('id', 'in', (eligible | foreign | archived | activity).ids)]
        for node in nodes:
            context['parent'].pricelist_id = False
            without_tariff = safe_eval(node.get('domain'), context)
            self.assertEqual(accounts.search(fixtures + without_tariff), eligible)
            context['parent'].pricelist_id = 1
            self.assertEqual(safe_eval(node.get('domain'), context), [('id', 'in', activity.ids)])
        task = self.env['step.tarja'].create({'name': 'QA Tarea sin tarifa', 'company_id': company.id})
        line = self.env['step.tarja.line'].create({'tarja_id': task.id, 'cost_id': eligible.id, 'hrs': 8})
        self.assertEqual(line.cost_id, eligible)
        self.assertFalse(task.pricelist_id)
        self.assertEqual(line.tarifa, 0)
