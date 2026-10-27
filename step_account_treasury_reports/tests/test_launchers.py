from odoo.tests import TransactionCase, tagged

from ..hooks import LAUNCHERS, post_init_reports
from odoo.addons.step_account_treasury.report_ownership import BRIDGE, CORE


@tagged('post_install', '-at_install')
class TestReportLaunchers(TransactionCase):
    def test_existing_launchers_are_never_written(self):
        menus = self.env['ir.ui.menu']
        for name, *_ in LAUNCHERS:
            menu = self.env.ref(CORE + '.' + name)
            self.assertEqual(menu, self.env.ref(BRIDGE + '.' + name))
            menus |= menu
        menus.write({'sequence': 87, 'active': False,
                     'groups_id': [(6, 0, self.env.ref(CORE + '.group_treasury_manager').ids)]})
        before = menus.read()
        post_init_reports(self.env)
        self.assertEqual(before, menus.read())

    def test_missing_launchers_are_created_with_legacy_aliases(self):
        self.env['ir.model.data'].search([
            ('module', 'in', (CORE, BRIDGE)),
            ('name', 'in', [row[0] for row in LAUNCHERS]),
        ]).unlink()
        post_init_reports(self.env)
        for name, label, parent, action_name, sequence in LAUNCHERS:
            menu = self.env.ref(CORE + '.' + name)
            self.assertEqual(menu, self.env.ref(BRIDGE + '.' + name))
            self.assertEqual(menu.parent_id, self.env.ref(CORE + '.' + parent))
            self.assertEqual(menu.action, self.env.ref('account_reports.' + action_name))
            self.assertEqual(menu.sequence, sequence)
