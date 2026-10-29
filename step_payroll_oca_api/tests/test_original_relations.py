"""Exercise original policies on real records and the official JSON unlink path."""
from odoo import api, Command
from odoo.exceptions import UserError
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class OriginalRelationsCase(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.companies = cls.env["res.company"].create([
            {"name": "Private original relations A", "country_id": cls.env.ref("base.cl").id},
            {"name": "Private original relations B", "country_id": cls.env.ref("base.cl").id},
        ])
        actor = cls.env["res.users"].with_context(no_reset_password=True).create({
            "name": "Private original relations manager", "login": "private-original-relations-manager",
            "company_id": cls.companies[0].id, "company_ids": [Command.set(cls.companies.ids)],
            "groups_id": [Command.set([cls.env.ref(name).id for name in (
                "base.group_user", "payroll.group_payroll_manager", "account.group_account_manager")])],
        })
        cls.scope = api.Environment(cls.env.cr, actor.id, dict(cls.env.context,
            allowed_company_ids=cls.companies.ids), su=False)
        cls.kind = cls.scope["hr.payroll.structure.type"].create({"name": "Private original relations type"})
        cls.structure = cls.scope["hr.payroll.structure"].create({
            "name": "Private original relations", "code": "PRIVATE_ORIGINAL_RELATIONS",
            "company_id": False, "parent_id": False, "type_id": cls.kind.id})
        cls.category = cls.scope["hr.salary.rule.category"].create({
            "name": "Private original relations category", "code": "PRIVATE_RELATIONS", "company_id": False})
        cls.rule = cls.scope["hr.salary.rule"].create({
            "name": "Private original relations rule", "code": "PRIVATE_RELATIONS", "sequence": 1,
            "company_id": False, "struct_id": cls.structure.id, "category_id": cls.category.id,
            "condition_select": "none", "amount_select": "fix", "amount_fix": 100})

    def account(self, company, code):
        return self.scope["account.account"].with_company(company).create({
            "name": "Private original relations account", "code": code,
            "account_type": "expense", "company_ids": [Command.set(company.ids)]})

    def property_snapshot(self):
        self.rule.flush_recordset(["account_debit", "account_credit"])
        self.env.cr.execute("SELECT account_debit,account_credit FROM hr_salary_rule WHERE id=%s", [self.rule.id])
        return self.env.cr.fetchone()

    def test_original_relation_metadata_and_actual_default_structure_foreign_key(self):
        for name in ("account_debit", "account_credit"):
            field = self.scope["hr.salary.rule"]._fields[name]
            self.assertTrue(field.company_dependent)
            self.assertEqual((field.comodel_name, field.ondelete), ("account.account", "restrict"))
        field = self.scope["hr.payroll.structure.type"]._fields["default_struct_id"]
        self.assertEqual((field.comodel_name, field.ondelete), ("hr.payroll.structure", "set null"))
        self.env.cr.execute("""SELECT c.confdeltype,c.confrelid::regclass::text,c.convalidated
            FROM pg_constraint c JOIN pg_attribute a ON a.attrelid=c.conrelid AND a.attnum=c.conkey[1]
            WHERE c.contype='f' AND c.conrelid='hr_payroll_structure_type'::regclass AND a.attname='default_struct_id'""")
        self.assertEqual(self.env.cr.fetchall(), [("n", "hr_payroll_structure", True)])

    def test_empty_default_structure_unlink_clears_only_the_original_reference(self):
        empty = self.scope["hr.payroll.structure"].create({
            "name": "Private deletable original default", "code": "PRIVATE_EMPTY_DEFAULT",
            "company_id": False, "parent_id": False, "type_id": self.kind.id})
        self.kind.default_struct_id = empty
        original_type_id, original_structure_id = self.kind.id, self.structure.id
        empty.unlink()
        self.kind.invalidate_recordset(["default_struct_id"])
        self.assertEqual(self.kind.id, original_type_id)
        self.assertFalse(self.kind.default_struct_id)
        self.assertEqual(self.rule.struct_id.id, original_structure_id)
        self.assertTrue(self.structure.exists())
        self.kind.flush_recordset(["default_struct_id"])
        self.env.cr.execute("SELECT default_struct_id FROM hr_payroll_structure_type WHERE id=%s", [self.kind.id])
        self.assertIsNone(self.env.cr.fetchone()[0])

    def test_each_account_property_protects_all_original_company_slots_on_unlink(self):
        for field_index, field in enumerate(("account_debit", "account_credit")):
            accounts = self.scope["account.account"]
            for index, company in enumerate(self.companies):
                account = self.account(company, "9496%s%s" % (field_index, index))
                accounts |= account
                self.rule.with_company(company).write({field: account.id})
            before = self.property_snapshot()
            for account in accounts:
                with self.assertRaises(UserError), self.env.cr.savepoint():
                    account.unlink()
                self.assertTrue(account.exists())
                self.assertEqual(self.property_snapshot(), before)

    def test_unreferenced_account_unlink_remains_available_without_erasing_properties(self):
        before = self.property_snapshot()
        account = self.account(self.companies[0], "949699")
        ident = account.id
        account.unlink()
        self.assertFalse(self.scope["account.account"].browse(ident).exists())
        self.assertEqual(self.property_snapshot(), before)
