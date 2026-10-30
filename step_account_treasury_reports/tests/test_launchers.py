from odoo.exceptions import UserError
from odoo.tests import TransactionCase, tagged

from ..hooks import LAUNCHERS, post_init_reports
from odoo.addons.step_account_treasury.report_ownership import (
    BRIDGE, CORE, COMMUNITY, MENUS, NAMESPACES,
)


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
            ('module', 'in', (CORE, BRIDGE, COMMUNITY)),
            ('name', 'in', [row[0] for row in LAUNCHERS]),
        ]).unlink()
        post_init_reports(self.env)
        for name, kind, label, parent, sequence in LAUNCHERS:
            menu = self.env.ref(CORE + '.' + name)
            self.assertEqual(menu, self.env.ref(BRIDGE + '.' + name))
            self.assertEqual(menu.parent_id, self.env.ref(CORE + '.' + parent))
            self.assertEqual(menu.action, self.env.ref(COMMUNITY + '.action_' + kind))
            self.assertEqual(menu.sequence, sequence)

    def test_flags_ids_and_owners_survive_repeated_native_cleanup(self):
        data = self.env['ir.model.data']
        aliases = data.search([('module', 'in', NAMESPACES), ('name', 'in', MENUS)])
        self.assertEqual(len(aliases), 15)
        for index, entry in enumerate(aliases):
            entry.noupdate = bool(index % 2)
        fields = ['id', 'module', 'name', 'model', 'res_id', 'noupdate']
        before = aliases.sorted('id').read(fields)
        menus = self.env['ir.ui.menu'].browse(aliases.mapped('res_id'))
        presentation = menus.read(['name', 'groups_id', 'parent_id', 'sequence', 'active', 'action', 'write_date'])
        post_init_reports(self.env)
        loaded = self.env.registry.loaded_xmlids
        initial = set(loaded)
        try:
            for namespace in NAMESPACES:
                for unused in range(2):
                    loaded.update(entry.module + '.' + entry.name for entry in data.search([('module', '=', namespace)]))
                    loaded.difference_update(namespace + '.' + name for name in MENUS)
                    data._process_end([namespace])
                    self.assertEqual(aliases.exists().sorted('id').read(fields), before)
                    self.assertEqual(menus.read(list(presentation[0].keys())), presentation)
        finally:
            loaded.clear()
            loaded.update(initial)

    def test_retiring_alias_namespace_keeps_independent_community_owner(self):
        data = self.env['ir.model.data']
        namespace = 'step_treasury_report_retirement_fixture'
        before = {}
        for name in MENUS:
            menu = self.env.ref(COMMUNITY + '.' + name)
            before[name] = menu.read(['id', 'name', 'parent_id', 'groups_id', 'sequence', 'active', 'action'])
            data.create({'module': namespace, 'name': name, 'model': menu._name,
                         'res_id': menu.id, 'noupdate': False})
        data._module_data_uninstall([namespace])
        self.assertFalse(data.search([('module', '=', namespace)]))
        for name in MENUS:
            self.assertEqual(self.env.ref(COMMUNITY + '.' + name).read(list(before[name][0].keys())), before[name])

    def test_custom_target_rejects_adoption_atomically(self):
        data = self.env['ir.model.data']
        # The first row would recreate an alias; the last menu is deliberately
        # a custom target. No new alias or earlier target may survive rejection.
        data.search([('module', '=', COMMUNITY), ('name', '=', MENUS[0])]).unlink()
        menu = self.env.ref(CORE + '.' + MENUS[-1])
        menu.action = 'ir.actions.client,%s' % self.env.ref(CORE + '.action_treasury_dashboard').id
        fields = ['id', 'module', 'name', 'model', 'res_id', 'noupdate']
        domain = [('module', 'in', NAMESPACES), ('name', 'in', MENUS)]
        before = data.search(domain, order='id').read(fields)
        with self.assertRaisesRegex(UserError, 'acción personalizada'):
            post_init_reports(self.env)
        self.assertEqual(data.search(domain, order='id').read(fields), before)
