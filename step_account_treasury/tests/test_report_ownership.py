from odoo.exceptions import UserError
from odoo.tests import TransactionCase, tagged

from ..report_ownership import BRIDGE, CORE, MENUS, preserve_menus


@tagged('post_install', '-at_install')
class TestReportOwnership(TransactionCase):
    def test_alias_adoption_keeps_menu_and_permissions(self):
        name = MENUS[0]
        data = self.env['ir.model.data']
        data.search([('module', 'in', (CORE, BRIDGE)), ('name', '=', name)]).unlink()
        group = self.env.ref(CORE + '.group_treasury_manager')
        menu = self.env['ir.ui.menu'].create({
            'name': 'Private report', 'active': False, 'sequence': 87,
            'parent_id': self.env.ref(CORE + '.menu_treasury_bank').id,
            'groups_id': [(6, 0, group.ids)],
            'action': 'ir.actions.client,%s' % self.env.ref(CORE + '.action_treasury_dashboard').id,
        })
        data.create({'module': CORE, 'name': name, 'model': 'ir.ui.menu', 'res_id': menu.id})
        before = menu.read(['name', 'active', 'sequence', 'parent_id', 'groups_id', 'action'])
        preserve_menus(self.env)
        preserve_menus(self.env)
        self.assertEqual(self.env.ref(CORE + '.' + name), self.env.ref(BRIDGE + '.' + name))
        self.assertEqual(before, menu.read(['name', 'active', 'sequence', 'parent_id', 'groups_id', 'action']))
        self.assertTrue(all(data.search([('name', '=', name), ('module', 'in', (CORE, BRIDGE))]).mapped('noupdate')))

    def test_conflicting_alias_is_rejected(self):
        name = MENUS[1]
        data = self.env['ir.model.data']
        data.search([('module', 'in', (CORE, BRIDGE)), ('name', '=', name)]).unlink()
        for namespace, target in ((CORE, 'menu_treasury_bank'), (BRIDGE, 'menu_treasury_reports')):
            data.create({'module': namespace, 'name': name, 'model': 'ir.ui.menu',
                         'res_id': self.env.ref(CORE + '.' + target).id})
        with self.assertRaises(UserError):
            preserve_menus(self.env)

    def test_upgrade_requires_bridge_for_existing_reports(self):
        bridge = self.env['ir.module.module'].search([('name', '=', BRIDGE)])
        bridge.write({'state': 'uninstalled'})
        name = MENUS[2]
        data = self.env['ir.model.data']
        data.search([('module', 'in', (CORE, BRIDGE)), ('name', '=', name)]).unlink()
        data.create({'module': CORE, 'name': name, 'model': 'ir.ui.menu',
                     'res_id': self.env.ref(CORE + '.menu_treasury_reports').id})
        with self.assertRaises(UserError):
            preserve_menus(self.env, require_bridge=True)
