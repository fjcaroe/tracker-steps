"""Real OCA optional configuration and explicit original-adoption admission."""
from psycopg2 import IntegrityError

from odoo import api, Command, fields
from odoo.exceptions import AccessError, UserError
from odoo.tests import TransactionCase, tagged
from odoo.tools import mute_logger

from ..nullable_storage import (
    NullableStorageError, _check_original_type_names, original_type_name_table_admission,
)


@tagged("post_install", "-at_install")
class OriginalNullableCase(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env["res.company"].create({"name": "Private required contract company",
            "country_id": cls.env.ref("base.cl").id, "currency_id": cls.env.ref("base.CLP").id})
        actor = cls.env["res.users"].with_context(no_reset_password=True).create({
            "name": "Private required contract manager", "login": "private-required-contract-manager",
            "company_id": cls.company.id, "company_ids": [Command.set(cls.company.ids)],
            "groups_id": [Command.set([cls.env.ref(xmlid).id for xmlid in (
                "base.group_user", "payroll.group_payroll_manager", "hr.group_hr_manager", "account.group_account_manager")])]})
        cls.scope = api.Environment(cls.env.cr, actor.id, dict(cls.env.context, allowed_company_ids=cls.company.ids), su=False)
        cls.kind = cls.scope["hr.payroll.structure.type"].create({"name": "Private required contract type"})
        cls.structure = cls.scope["hr.payroll.structure"].create({
            "name": "Private required contract structure", "code": "PRIVATE_REQUIRED_STRUCTURE",
            "company_id": cls.company.id, "parent_id": False, "type_id": cls.kind.id})
        cls.category = cls.scope["hr.salary.rule.category"].create({
            "name": "Private required contract category", "code": "PRIVATE_REQUIRED_CATEGORY", "company_id": cls.company.id})
        cls.rule = cls.scope["hr.salary.rule"].create({
            "name": "Private required contract rule", "code": "PRIVATE_REQUIRED_RULE", "sequence": 1,
            "category_id": cls.category.id, "company_id": cls.company.id, "struct_id": cls.structure.id,
            "condition_select": "none", "amount_select": "fix", "amount_fix": 100.0})
        journal = cls.scope["account.journal"].create({"name": "Private required contract journal", "code": "RQD",
            "type": "general", "company_id": cls.company.id})
        employee = cls.scope["hr.employee"].create({"name": "Private required contract employee", "company_id": cls.company.id})
        values = {"name": "Private required contract", "company_id": cls.company.id, "employee_id": employee.id,
            "state": "open", "date_start": fields.Date.today().replace(day=1), "wage": 100,
            "struct_id": cls.structure.id, "structure_type_id": cls.kind.id, "journal_id": journal.id}
        field = cls.scope["hr.contract"]._fields.get("contract_type_id")
        if field:
            values["contract_type_id"] = cls.scope[field.comodel_name].search([], limit=1).id
        cls.contract = cls.scope["hr.contract"].create(values)

    def _slip(self):
        return self.scope["hr.payslip"].create({"name": "Private required contract payslip",
            "number": "PRIVATE/REQUIRED/CONTRACT", "company_id": self.company.id,
            "employee_id": self.contract.employee_id.id, "contract_id": self.contract.id,
            "struct_id": self.structure.id, "date_from": fields.Date.today().replace(day=1), "date_to": fields.Date.today()})

    def _snapshot(self, scope=None):
        scope = scope if scope is not None else self.scope
        return (self.structure.with_env(scope).read(["id", "type_id", "company_id", "country_id", "rule_ids", "write_date"]),
            self.rule.with_env(scope).read(["id", "code", "struct_id", "category_id", "active", "write_date"]),
            self.category.with_env(scope).read(["id", "code", "parent_id", "write_date"]),
            self.kind.with_env(scope).read(["id", "name", "write_date"]))

    def test_required_type_name_and_independent_rule_line_delete_metadata(self):
        self.assertTrue(self.kind._fields["name"].required)
        for model_name, name in (("hr.payroll.structure", "type_id"), ("hr.salary.rule", "struct_id"),
                ("hr.salary.rule", "code"), ("hr.salary.rule", "category_id"), ("hr.salary.rule.category", "code")):
            self.assertFalse(self.scope[model_name]._fields[name].required)
        self.assertEqual(self.rule._fields["category_id"].ondelete, "restrict")
        line_field = self.scope["hr.payslip.line"]._fields["category_id"]
        self.assertFalse(line_field.required)
        self.assertTrue(line_field.store)
        self.assertFalse(line_field.related)
        self.assertEqual(line_field.ondelete, "set null")
        self.env.cr.execute("SELECT attnotnull FROM pg_attribute WHERE attrelid='hr_payroll_structure_type'::regclass AND attname='name'")
        self.assertEqual(self.env.cr.fetchone(), (True,))
        self.env.cr.execute("""SELECT c.conrelid::regclass::text,c.confdeltype,c.convalidated
            FROM pg_constraint c JOIN pg_attribute a ON a.attrelid=c.conrelid AND a.attnum=c.conkey[1]
            WHERE c.contype='f' AND c.conrelid IN ('hr_salary_rule'::regclass,'hr_payslip_line'::regclass)
            AND a.attname='category_id' ORDER BY 1""")
        self.assertEqual(self.env.cr.fetchall(), [("hr_payslip_line", "n", True), ("hr_salary_rule", "r", True)])
        before = self.kind.read(["id", "name", "write_date"])
        with self.assertRaises(IntegrityError), mute_logger("odoo.sql_db"), self.env.cr.savepoint():
            self.env.cr.execute("UPDATE hr_payroll_structure_type SET name=NULL WHERE id=%s", (self.kind.id,))
        self.assertEqual(self.kind.read(["id", "name", "write_date"]), before)

    def test_referenced_master_category_is_restricted_but_draft_line_boundary_is_unchanged(self):
        slip = self._slip()
        slip.compute_sheet()
        self.assertEqual(slip.line_ids.salary_rule_id, self.rule)
        before = slip.line_ids.read(["id", "code", "salary_rule_id", "amount", "quantity", "rate", "total"])
        self.category.check_access("unlink")
        with self.assertRaises(IntegrityError), mute_logger("odoo.sql_db"), self.env.cr.savepoint():
            self.category.unlink()
        self.assertTrue(self.category.exists())
        self.assertEqual(self.rule.category_id, self.category)
        self.assertEqual(slip.line_ids.read(["id", "code", "salary_rule_id", "amount", "quantity", "rate", "total"]), before)
        # Only the private draft fixture now references the category. Preserve
        # OCA's existing stored-line policy instead of inheriting master RESTRICT.
        self.rule.category_id = False
        self.category.unlink()
        slip.line_ids.invalidate_recordset(["category_id"])
        self.assertFalse(slip.line_ids.category_id)
        self.assertEqual(slip.line_ids.read(["id", "code", "salary_rule_id", "amount", "quantity", "rate", "total"]), before)

    def test_original_admission_is_read_only_and_includes_archived_configuration(self):
        self.assertFalse(self.scope.su)
        before = self._snapshot()
        self.assertTrue(self.structure._step_check_original_required_contract())
        self.assertEqual(self._snapshot(), before)
        self.rule.active = False
        self.rule.code = False
        before = self._snapshot()
        with self.assertRaisesRegex(UserError, "original code"):
            self.structure._step_check_original_required_contract()
        self.assertEqual(self._snapshot(), before)

    def test_each_optional_oca_value_blocks_original_adoption_without_backfill(self):
        for record, name in ((self.structure, "type_id"), (self.rule, "struct_id"),
                (self.rule, "category_id"), (self.rule, "code"), (self.category, "code")):
            original = record[name]
            record[name] = False
            if record == self.rule and name == "struct_id":
                self.structure.rule_ids = [Command.link(self.rule.id)]
            before = self._snapshot()
            with self.assertRaises(UserError):
                self.structure._step_check_original_required_contract()
            self.assertEqual(self._snapshot(), before)
            record[name] = original.id if hasattr(original, "id") else original
        self.assertTrue(self.structure._step_check_original_required_contract())

    def test_real_oca_optional_rule_and_category_still_calculate(self):
        self.rule.struct_id = False
        self.category.code = False
        self.structure.rule_ids = [Command.link(self.rule.id)]
        slip = self._slip()
        slip.compute_sheet()
        self.assertEqual(slip.line_ids.salary_rule_id, self.rule)
        self.assertEqual(slip.line_ids.total, self.company.currency_id.round(100))
        before = slip.line_ids.read(["id", "amount", "quantity", "rate", "total", "code", "category_id"])
        with self.assertRaises(UserError):
            self.structure._step_check_original_required_contract()
        self.assertEqual(slip.line_ids.read(["id", "amount", "quantity", "rate", "total", "code", "category_id"]), before)
        # Upstream also permits no category, rather than a manufactured one.
        self.rule.category_id = False
        slip.compute_sheet()
        self.assertEqual(slip.line_ids.salary_rule_id, self.rule)
        self.assertFalse(slip.line_ids.category_id)
        self.assertEqual(slip.line_ids.total, self.company.currency_id.round(100))
        # OCA's real provider supports a missing master-rule code. StepBase's
        # existing native line.code NOT NULL contract separately prevents
        # persisting that incomplete line; do not relax it in this boundary.
        optional = self.scope["hr.salary.rule"].create({
            "name": "Private OCA provider rule without code", "code": False, "sequence": 2,
            "category_id": False, "company_id": self.company.id, "struct_id": False,
            "condition_select": "none", "amount_select": "fix", "amount_fix": 100.0})
        self.structure.rule_ids = [Command.set(optional.ids)]
        unpersisted = self._slip()
        before = slip.line_ids.read(["id", "amount", "quantity", "rate", "total"])
        result = unpersisted.get_lines_dict()
        values = list(result.values())
        self.assertEqual(len(values), 1)
        self.assertEqual(values[0]["salary_rule_id"], optional.id)
        self.assertFalse(values[0]["code"])
        self.assertEqual(values[0]["total"], self.company.currency_id.round(100))
        self.assertFalse(unpersisted.line_ids)
        self.assertEqual(slip.line_ids.read(["id", "amount", "quantity", "rate", "total"]), before)

    def test_warm_cache_hidden_rule_or_category_and_foreign_type_are_not_admitted(self):
        self.rule.read(["code", "struct_id", "category_id"])
        self.category.read(["code"])
        for model_xmlid, record in (("payroll.model_hr_salary_rule", self.rule),
                ("payroll.model_hr_salary_rule_category", self.category)):
            restriction = self.env["ir.rule"].create({"name": "Private hidden original required reference",
                "model_id": self.env.ref(model_xmlid).id, "global": True, "domain_force": "[('id','!=',%d)]" % record.id})
            with self.assertRaises(AccessError):
                self.structure._step_check_original_required_contract()
            restriction.unlink()
        self.kind.country_id = self.env.ref("base.fr")
        # Authorize the foreign country in this fixture's company context so
        # the type is deliberately visible. The tested actor keeps its roles;
        # this isolates the actual country-scope rejection from a read ACL.
        foreign_company = self.env["res.company"].create({"name": "Private visible foreign required-type company",
            "country_id": self.env.ref("base.fr").id})
        self.scope.user.with_env(self.env).write({"company_ids": [Command.link(foreign_company.id)]})
        scope = self.structure.with_context(allowed_company_ids=(self.company | foreign_company).ids).env
        self.assertFalse(scope.su)
        self.kind.with_env(scope).check_access("read")
        before = self._snapshot(scope)
        with self.assertRaisesRegex(UserError, "country scope"):
            self.structure.with_env(scope)._step_check_original_required_contract()
        self.assertEqual(self._snapshot(scope), before)

    def test_pre_orm_null_admission_aborts_without_backfill_or_ownership_changes(self):
        self.assertTrue(original_type_name_table_admission("to install", False)["type_table_pending_orm"])
        for state in ("installed", "to upgrade"):
            with self.assertRaises(NullableStorageError):
                original_type_name_table_admission(state, False)
        self.env.cr.execute("CREATE TEMP TABLE private_required_type_names (id INTEGER PRIMARY KEY,name VARCHAR) ON COMMIT DROP")
        self.env.cr.execute("INSERT INTO private_required_type_names VALUES (1,NULL),(2,'Private literal preserved')")
        with self.assertRaisesRegex(NullableStorageError, "no-backfill"):
            _check_original_type_names(self.env.cr, ("pg_temp", "private_required_type_names"))
        self.env.cr.execute("SELECT id,name FROM private_required_type_names ORDER BY id")
        self.assertEqual(self.env.cr.fetchall(), [(1, None), (2, "Private literal preserved")])
        self.env.cr.execute("DELETE FROM private_required_type_names WHERE id=1")
        self.assertEqual(_check_original_type_names(self.env.cr, ("pg_temp", "private_required_type_names")),
            {"rows": 1, "null_names": 0, "names_changed": False})
