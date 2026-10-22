from odoo.tests import TransactionCase, Form, tagged
from odoo.tests.common import new_test_user


@tagged('post_install', '-at_install')
class SeasonNavigationCase(TransactionCase):
    def test_three_apps_open_the_existing_master_and_form(self):
        user = new_test_user(self.env, login='qa_t105_manager',
                            groups='base.group_user,account.group_account_manager,stock.group_stock_manager,step_management_costs.group_management_manager')
        menus = self.env['ir.ui.menu'].with_user(user)._visible_menu_ids()
        action = self.env.ref('step_hr.action_step_temporada')
        for name in ('export', 'packing', 'producer'):
            menu = self.env.ref('step_season_navigation.menu_' + name + '_seasons')
            self.assertEqual(menu.action, action)
            self.assertIn(menu.id, menus)
        self.assertEqual(action.res_model, 'step.temporada')
        seasons = self.env['step.temporada'].with_user(user)
        with Form(seasons, view='step_hr.view_temporada_form') as form:
            form.name = 'QA T105 temporada compartida'
        record = form.record
        for name in ('export', 'packing', 'producer'):
            target = self.env[self.env.ref('step_season_navigation.menu_' + name + '_seasons').action.res_model].with_user(user)
            self.assertIn(record, target.search([('id', '=', record.id)]))
            with Form(target.browse(record.id), view='step_hr.view_temporada_form') as form:
                self.assertEqual(form.name, record.name)
