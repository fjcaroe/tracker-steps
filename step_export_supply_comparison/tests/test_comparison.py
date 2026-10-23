from datetime import date
from lxml import etree
from odoo import Command
from odoo.exceptions import AccessError
from odoo.tests import Form
from odoo.tests.common import TransactionCase, new_test_user
from odoo.addons.step_producer_estimate_report.tests import test_report as fixtures


class ComparisonCase(TransactionCase):
    def sample(self):
        estimate, _ = fixtures.EstimateReportCase.sample(self)
        line = estimate.estimate_line_ids
        pallet = self.env['stock.package.type'].create({'name': 'QA T109 pallet'})
        program = self.env['step.export.sales.program'].create({
            'name': 'QA T109 sales', 'season_id': estimate.season_id.id,
            'species_id': line.species_id.id, 'variety_id': line.variety_id.id,
            'partner_id': estimate.producer_id.id, 'product_id': line.product_id.id,
            'package_type_id': pallet.id, 'date_start': date(2026, 11, 2),
            'date_end': date(2026, 11, 15), 'currency_id': self.env.ref('base.USD').id,
            'rate_to_usd': 1, 'pallets_per_container': 1, 'boxes_per_pallet': 10,
            'kg_per_box': 10, 'line_ids': [
                Command.create({'week_start': date(2026, 11, 2), 'container_qty': 1, 'price_per_kg': 2}),
                Command.create({'week_start': date(2026, 11, 9), 'container_qty': 2, 'price_per_kg': 2})]})
        estimate.action_validate_estimate()
        estimate.action_activate_estimate()
        program.action_validate()
        program.action_activate()
        self.env.flush_all()
        return estimate, program

    def totals(self, domain):
        self.env.flush_all()
        result = self.env['step.export.supply.comparison'].read_group(
            domain, ['sale_kg:sum', 'estimate_kg:sum'], [])[0]
        return result['sale_kg'], result['estimate_kg']

    def test_weekly_totals_dimensions_and_no_cartesian_multiplication(self):
        estimate, program = self.sample()
        domain = [('season_id', '=', estimate.season_id.id)]
        self.assertEqual(self.totals(domain), (300, 100))
        self.assertEqual(self.totals(domain + [('week_start', '=', '2026-11-02')]), (100, 40))
        self.assertEqual(self.totals(domain + [('week_start', '=', '2026-11-09')]), (200, 60))
        self.assertEqual(self.totals(domain + [('producer_id', '=', estimate.producer_id.id)]), (0, 100))
        self.assertEqual(self.totals(domain + [('program_id', '=', program.id)]), (300, 0))
        self.assertEqual(self.totals(domain + [('variety_id', '=', estimate.estimate_line_ids.variety_id.id)]), (300, 100))
        other = estimate.copy()
        other.action_validate_estimate()
        other.action_activate_estimate()
        self.assertEqual(self.totals(domain), (300, 200))
        rows = self.env['step.export.supply.comparison'].search(domain)
        self.assertEqual(len(rows), 6)
        self.assertEqual(len(rows.ids), len(set(rows.ids)))

    def test_only_current_versions_and_cancelled_estimates_are_excluded(self):
        estimate, program = self.sample()
        domain = [('season_id', '=', estimate.season_id.id)]
        draft = estimate.copy()
        draft.action_validate_estimate()
        self.assertEqual(self.totals(domain), (300, 100))
        newer = self.env[program._name].browse(program.action_new_version()['res_id'])
        newer.line_ids[0].container_qty = 3
        newer.action_validate()
        newer.action_activate()
        self.assertEqual(program.state, 'replaced')
        self.assertEqual(self.totals(domain), (500, 100))
        estimate.action_cancel_estimate()
        self.assertEqual(self.totals(domain), (500, 0))
        self.assertTrue(estimate.estimate_line_ids.week_line_ids.exists())

    def test_company_scope_and_report_is_read_only(self):
        estimate, _ = self.sample()
        company = self.env['res.company'].create({'name': 'QA T109 other'})
        user = new_test_user(self.env(context=dict(self.env.context, no_reset_password=True)),
            login='qa-t109-other', groups='base.group_user', company_id=company.id,
            company_ids=[Command.set(company.ids)])
        report = self.env['step.export.supply.comparison'].with_user(user).with_context(allowed_company_ids=company.ids)
        self.assertFalse(report.search([('season_id', '=', estimate.season_id.id)]))
        user.company_ids = [Command.link(estimate.company_id.id)]
        report = report.with_context(allowed_company_ids=estimate.company_id.ids)
        rows = report.search([('season_id', '=', estimate.season_id.id)])
        self.assertEqual(len(rows), 4)
        for operation in [lambda: rows.write({'sale_kg': 999}), rows.unlink,
                          lambda: report.create({'sale_kg': 999})]:
            with self.assertRaises(AccessError):
                operation()

    def test_native_pivot_week_grouping_and_source_form(self):
        estimate, _ = self.sample()
        model = self.env['step.export.supply.comparison']
        prefix = 'step_export_supply_comparison.'
        action = self.env.ref(prefix + 'report_action')
        menu = self.env.ref(prefix + 'report_menu')
        self.assertEqual(menu.parent_id, self.env.ref('step_export.menu_step_export_ops'))
        self.assertEqual(menu.action, action)
        self.assertEqual(action.view_mode, 'pivot,list,form')
        arch = etree.fromstring(model.get_view(view_id=self.env.ref(prefix + 'report_pivot').id, view_type='pivot')['arch'])
        self.assertEqual(arch.xpath("//field[@type='measure']/@name"), ['sale_kg', 'estimate_kg'])
        self.assertEqual(arch.xpath("//field[@type='col']/@interval"), ['week'])
        result = model.read_group([('season_id', '=', estimate.season_id.id)],
                                 ['sale_kg:sum', 'estimate_kg:sum'], ['week_start:week'], lazy=False)
        self.assertEqual(len(result), 2)
        self.assertEqual(sorted((r['sale_kg'], r['estimate_kg']) for r in result), [(100, 40), (200, 60)])
        row = model.search([('estimate_id', '=', estimate.id)], limit=1)
        form = Form(row, view=prefix + 'report_form')
        self.assertEqual(form.estimate_id, estimate)
