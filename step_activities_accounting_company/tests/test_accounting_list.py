from odoo.tests import TransactionCase, new_test_user, tagged
from odoo.tools.safe_eval import safe_eval


@tagged('post_install', '-at_install')
class TestActivitiesAccountingList(TransactionCase):
    def test_menu_follows_active_company_with_both_selected(self):
        first, second = self.env['res.company'].create([
            {'name': 'QA Asientos A'}, {'name': 'QA Asientos B'},
        ])
        operator = new_test_user(
            self.env, login='qa.activities.accounting.list', groups='account.group_account_manager',
            company_id=first.id, company_ids=[(6, 0, (first | second).ids)],
        )
        entries = {}
        other_entries = self.env['account.move']
        for company in first | second:
            journal = self.env['account.journal'].with_company(company).create({
                'name': 'QA Contabilización', 'code': 'QA191', 'type': 'general', 'company_id': company.id,
            })
            moves = self.env['account.move'].with_company(company)
            entries[company.id] = moves.create({'journal_id': journal.id, 'propio': True})
            other_entries |= moves.create({'journal_id': journal.id})

        for companies in (first | second, second | first):
            scope = self.env['account.move'].with_user(operator).with_context(allowed_company_ids=companies.ids)
            menu = scope.env.ref('step_hr.menu_acount_propio')
            action = menu.action._get_action_dict()
            self.assertEqual(action['res_model'], 'account.move')
            self.assertIn(menu.id, scope.env['ir.ui.menu']._visible_menu_ids())
            domain = safe_eval(action['domain'], dict(scope.env.context))
            candidates = other_entries | entries[first.id] | entries[second.id]
            self.assertEqual(scope.search([('id', 'in', candidates.ids), *domain]), entries[scope.env.company.id])
