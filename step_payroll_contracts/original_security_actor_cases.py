"""Normal-actor security cases on each actual payroll provider; no ACL changes."""
from odoo import api, Command
from odoo.exceptions import AccessError


class OriginalSecurityActorCases:
    __slots__ = ()

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        country = cls.env.ref('base.cl')
        foreign_country = cls.env.ref('base.us')
        company = cls.env['res.company'].create({
            'name': 'Private security adoption company', 'country_id': country.id})
        other_company = cls.env['res.company'].create({
            'name': 'Private security adoption second company', 'country_id': country.id})
        prefix = 'hr_payroll' if cls.NATIVE else 'payroll'
        user_group = cls.env.ref(prefix + ('.group_hr_payroll_user' if cls.NATIVE else '.group_payroll_user'))
        cls.actor = cls.env['res.users'].with_context(no_reset_password=True).create({
            'name': 'Private original payroll officer', 'login': 'private-original-payroll-security-officer',
            'company_id': company.id, 'company_ids': [Command.set(company.ids)],
            'groups_id': [Command.set((user_group | cls.env.ref('base.group_user')).ids)]})
        cls.scope = api.Environment(cls.env.cr, cls.actor.id,
            dict(cls.env.context, allowed_company_ids=company.ids), su=False)
        cls.company, cls.other_company = company, other_company
        cls.kind = cls.env['hr.payroll.structure.type'].create({'name': 'Private original security type'})
        cls.structure = cls._structure('Private original security structure', country)
        cls.foreign_structure = cls._structure('Private foreign security structure', foreign_country)
        cls.category = cls.env['hr.salary.rule.category'].create({
            'name': 'Private original security category', 'code': 'PRIVATE_ORIGINAL_SECURITY'})
        cls.rule = cls.env['hr.salary.rule'].create(cls._rule_values(cls.structure))
        cls.foreign_rule = cls.env['hr.salary.rule'].create(cls._rule_values(cls.foreign_structure))

    @classmethod
    def _structure(cls, name, country, company=False):
        model = cls.env['hr.payroll.structure']
        values = {'name': name, 'type_id': cls.kind.id, 'country_id': country.id}
        if 'code' in model._fields:
            values['code'] = 'PRIVATE_ORIGINAL_SECURITY'
        if 'parent_id' in model._fields:
            values['parent_id'] = False
        if 'company_id' in model._fields:
            values['company_id'] = company.id if company else False
        return model.create(values)

    @classmethod
    def _rule_values(cls, structure):
        values = {'name': 'Private original security rule', 'code': 'PRIVATE_ORIGINAL_SECURITY',
            'sequence': 10, 'category_id': cls.category.id, 'struct_id': structure.id,
            'condition_select': 'none', 'amount_select': 'fix', 'amount_fix': 1.0}
        if 'company_id' in cls.env['hr.salary.rule']._fields:
            values['company_id'] = False
        return values

    def case_officer_has_original_crud_or_generic_oca_readonly(self):
        self.assertFalse(self.scope.su)
        for name in ('payroll.group_payroll_manager', 'hr_payroll.group_hr_payroll_manager'):
            group = self.env.ref(name, raise_if_not_found=False)
            if group:
                self.assertNotIn(group, self.actor.groups_id)
        model = self.scope['hr.salary.rule']
        self.assertEqual(model.browse(self.rule.id).read(['code'])[0]['code'], 'PRIVATE_ORIGINAL_SECURITY')
        if self.NATIVE:
            record = model.create(self._rule_values(self.structure))
            record.write({'name': 'Private officer changed rule'})
            self.assertEqual(record.read(['name'])[0]['name'], 'Private officer changed rule')
            record.unlink()
            self.assertFalse(record.exists())
        else:
            for action in (lambda: model.create(self._rule_values(self.structure)),
                           lambda: model.browse(self.rule.id).write({'name': 'Must not change'}),
                           lambda: model.browse(self.rule.id).unlink()):
                with self.assertRaises(AccessError):
                    with self.env.cr.savepoint():
                        action()

    def case_foreign_country_is_blocked_including_warm_record(self):
        self.foreign_rule.read(['code'])
        record = self.scope['hr.salary.rule'].browse(self.foreign_rule.id)
        for action in (lambda: record.read(['code']),
                       lambda: record.write({'name': 'Forbidden country edit'}), lambda: record.unlink()):
            with self.assertRaises(AccessError):
                with self.env.cr.savepoint():
                    action()
        with self.assertRaises(AccessError):
            with self.env.cr.savepoint():
                self.scope['hr.salary.rule'].create(self._rule_values(self.foreign_structure))

    def case_original_field_access_does_not_assign_manager(self):
        names = ['code', 'amount_python_compute', 'condition_python', 'condition_other_input_id',
                 'amount_other_input_id', 'partner_id', 'not_computed_in_net', 'split_move_lines']
        model = self.scope['hr.salary.rule']
        self.assertTrue(all(name in model._fields for name in names))
        self.assertFalse(any(model._fields[name].groups for name in names))
        self.assertEqual(set(model.check_field_access_rights('read', names)), set(names))
        self.assertEqual(set(model.check_field_access_rights('write', names)), set(names))
        # No salary code or private formulas are read or evaluated by this case.
        self.assertFalse(self.scope.su)

    def case_global_originals_and_company_boundary_remain_distinct(self):
        record = self.scope['hr.salary.rule'].browse(self.rule.id)
        self.assertTrue(record.read(['id']))
        if self.NATIVE:
            self.assertNotIn('company_id', record._fields)
            # Native rules have a country policy and no invented owner. A
            # second same-country company does not narrow those global rules.
            self.assertEqual(self.structure.country_id, self.other_company.country_id)
            record.check_access('read')
        else:
            self.assertFalse(record.company_id)
            other_structure = self._structure('Private other-company security structure',
                self.other_company.country_id, company=self.other_company)
            values = self._rule_values(other_structure)
            values['company_id'] = self.other_company.id
            other = self.env['hr.salary.rule'].create(values)
            other.read(['code'])
            with self.assertRaises(AccessError):
                other.with_env(self.scope).read(['code'])
            # Even an authorized actor cannot inject an unassigned company
            # through context to widen the actual company rule.
            with self.assertRaises(AccessError):
                other.with_env(self.scope).with_context(allowed_company_ids=self.other_company.ids).read(['code'])
