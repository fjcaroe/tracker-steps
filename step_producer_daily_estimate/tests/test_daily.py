from types import SimpleNamespace
from lxml import etree
from odoo.exceptions import ValidationError, UserError, AccessError
from odoo.tests.common import TransactionCase, new_test_user
from odoo.addons.step_producer_estimate_revision.tests.test_revision import EstimateRevisionCase


class DailyCase(TransactionCase):
    def sample(self, days=5):
        estimate = EstimateRevisionCase.sample(SimpleNamespace(env=self.env))
        market = self.env['step.fruit.market'].create({'name':'QA Market', 'code':'QA-%s'%estimate.id, 'abbreviation':'QA'})
        estimate.write({'user_id':self.env.user.id,'fruit_type':'organic'})
        estimate.estimate_line_ids.market_id = market
        estimate.action_validate_estimate(); estimate.action_activate_estimate()
        wizard = self.env['step.export.estimate.daily.wizard'].create({'start_date':'2026-11-02', 'working_days':str(days)})
        wizard.action_distribute()
        rows = self.env['step.export.estimate.day'].search([('estimate_id','=',estimate.id)])
        return estimate, wizard, rows

    def test_five_days_conserve_both_kilos(self):
        estimate, wizard, rows = self.sample()
        self.assertEqual(len(rows),10)
        self.assertAlmostEqual(sum(rows.mapped('export_kg')),100000)
        self.assertAlmostEqual(sum(rows.mapped('process_kg')),125000)
        self.assertTrue(all(r.date.weekday()<5 for r in rows))

    def test_six_and_seven_days(self):
        for days in (6,7):
            estimate,wizard,rows=self.sample(days)
            self.assertEqual(len(rows),2*days)
            self.assertAlmostEqual(sum(rows.mapped('export_kg')),100000)
            self.assertAlmostEqual(sum(rows.mapped('process_kg')),125000)

    def test_manual_adjustment_and_regeneration_preserved(self):
        estimate,wizard,rows=self.sample()
        rows[0].write({'process_kg':1,'export_kg':2})
        before=rows.read(['date','process_kg','export_kg'])
        wizard.action_distribute()
        self.assertEqual(rows.read(['date','process_kg','export_kg']),before)
        with self.assertRaises(ValidationError),self.env.cr.savepoint():rows[0].export_kg=1000000
        with self.assertRaises(ValidationError),self.env.cr.savepoint():rows[0].date='2026-11-20'

    def test_version_snapshot_and_week_number(self):
        estimate,wizard,rows=self.sample()
        self.assertEqual(estimate.estimate_line_ids.week_line_ids[0].week_number,45)
        with self.assertRaises(UserError):estimate.fruit_type='conventional'
        with self.assertRaises(UserError):estimate.estimate_line_ids.market_id=False
        new=self.env['step.export.estimate'].browse(estimate.action_new_estimate_version()['res_id'])
        self.assertEqual(new.fruit_type,'organic')
        self.assertEqual(new.estimate_line_ids.market_id,estimate.estimate_line_ids.market_id)
        self.assertFalse(new.estimate_line_ids.week_line_ids.mapped('day_ids'))
        new.action_validate_estimate();new.action_activate_estimate()
        self.assertEqual(rows.mapped('state'),['replaced'])
        with self.assertRaises(UserError):rows[0].export_kg=1

    def test_weekly_dimensions_and_daily_pivot(self):
        estimate,wizard,rows=self.sample()
        self.env.flush_all()
        report=self.env['step.producer.estimate.report'].search([('estimate_id','=',estimate.id)])
        self.assertEqual(report.mapped('fruit_type'),['organic'])
        self.assertEqual(report.mapped('market_id'),estimate.estimate_line_ids.market_id)
        total=rows.read_group([('id','in',rows.ids)],['export_kg:sum','process_kg:sum'],[])[0]
        self.assertAlmostEqual(total['process_kg'],125000)
        self.assertEqual(total['export_kg'],100000)

    def test_roles_menus_effective_form(self):
        env=self.env(context=dict(self.env.context,no_reset_password=True))
        user=new_test_user(env,login='qa-t78-planner',groups='stock.group_stock_manager')
        visible=env['ir.ui.menu'].with_user(user)._visible_menu_ids()
        for key in ('producer_markets','packing_markets','export_markets','daily_menu','wizard_menu'):
            self.assertIn(env.ref('step_producer_daily_estimate.'+key).id,visible)
        arch=etree.fromstring(env['step.export.estimate'].with_user(user).get_view(view_id=env.ref('step_producers.view_step_export_estimate_form').id,view_type='form')['arch'].encode())
        for name in ('approved_by_id','fruit_type','market_id','week_number'):
            self.assertTrue(arch.xpath('.//field[@name="%s"]'%name))
        other=env['res.company'].create({'name':'QA T78 other'})
        estimate,wizard,rows=self.sample()
        outsider=new_test_user(env,login='qa-t78-other',groups='stock.group_stock_user',company_id=other.id,company_ids=[(6,0,other.ids)])
        self.assertFalse(rows.with_user(outsider).with_context(allowed_company_ids=other.ids).search([('id','in',rows.ids)]))
