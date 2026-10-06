import json
from odoo.tests.common import TransactionCase, new_test_user, tagged


@tagged('post_install', '-at_install')
class TestEnvironmentMenus(TransactionCase):
    def setUp(self):
        super().setUp()
        self.menu = self.env['ir.ui.menu']
        action = self.env['ir.actions.act_window'].create({
            'name': 'Environment test contacts', 'res_model': 'res.partner',
            'view_mode': 'list,form',
        })
        self.root = self.menu.create({'name': 'Environment allowed root'})
        self.child = self.menu.create({
            'name': 'Environment allowed child', 'parent_id': self.root.id,
            'action': 'ir.actions.act_window,%s' % action.id,
        })
        self.other = self.menu.create({
            'name': 'Environment excluded root',
            'action': 'ir.actions.act_window,%s' % action.id,
        })
        self.env['ir.model.data'].create({
            'module': 'step_environment_policy', 'name': 'test_allowed_root',
            'model': 'ir.ui.menu', 'res_id': self.root.id,
        })
        self.env['ir.config_parameter'].sudo().set_param(
            'steps.environment.menu_root_xmlids',
            json.dumps(['step_environment_policy.test_allowed_root']),
        )

    def test_whitelist_keeps_descendants_without_recursive_search(self):
        visible = self.menu._visible_menu_ids(debug=True)
        self.assertIn(self.child.id, visible)
        self.assertIn(self.root.id, visible)
        self.assertNotIn(self.other.id, visible)
        self.assertIn(self.child, self.menu.search([('id', '=', self.child.id)]))

    def test_whitelist_does_not_override_menu_group_access(self):
        self.child.groups_id = self.env.ref('base.group_system')
        user = new_test_user(self.env, login='environment_plain', groups='base.group_user')
        visible = self.menu.with_user(user)._visible_menu_ids(debug=True)
        self.assertNotIn(self.child.id, visible)

    def test_missing_allowed_root_hides_apps(self):
        self.env['ir.config_parameter'].sudo().set_param(
            'steps.environment.menu_root_xmlids', json.dumps(['missing.module_root']),
        )
        self.assertFalse(self.menu._visible_menu_ids(debug=True))
