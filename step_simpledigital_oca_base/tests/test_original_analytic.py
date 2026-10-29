"""Actual OCA posting and transactional admission of original analytic storage."""
import json
from unittest.mock import patch

from odoo import api, Command, fields
from odoo.exceptions import AccessError, UserError
from odoo.tests import TransactionCase, tagged

from ..analytic_storage import AnalyticStorageError, prepare_original_analytic_storage


@tagged("post_install", "-at_install")
class OriginalAnalyticCase(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env["res.company"].create({"name": "Private original analytic company",
            "country_id": cls.env.ref("base.cl").id, "currency_id": cls.env.ref("base.CLP").id})
        actor = cls.env["res.users"].with_context(no_reset_password=True).create({
            "name": "Private original analytic manager", "login": "private-original-analytic-manager",
            "company_id": cls.company.id, "company_ids": [Command.set(cls.company.ids)],
            "groups_id": [Command.set([cls.env.ref(xmlid).id for xmlid in (
                "base.group_user", "payroll.group_payroll_manager", "account.group_account_manager", "hr.group_hr_manager")]) ]})
        cls.scope = api.Environment(cls.env.cr, actor.id, dict(cls.env.context, allowed_company_ids=cls.company.ids), su=False)
        cls.journal = cls.scope["account.journal"].create({"name": "Private analytic salary journal", "code": "OAN",
            "type": "general", "company_id": cls.company.id})
        kind = cls.scope["hr.payroll.structure.type"].create({"name": "Private original analytic type"})
        cls.structure = cls.scope["hr.payroll.structure"].create({"name": "Private original analytic structure",
            "code": "PRIVATE_ORIGINAL_ANALYTIC", "type_id": kind.id, "company_id": cls.company.id,
            "parent_id": False, "journal_id": cls.journal.id})
        category = cls.scope["hr.salary.rule.category"].create({"name": "Private analytic category",
            "code": "PRIVATE_ANALYTIC_CATEGORY", "company_id": cls.company.id})
        cls.rule = cls.scope["hr.salary.rule"].create({"name": "Private original analytic rule", "code": "PRIVATE_ANALYTIC_RESULT",
            "sequence": 1, "category_id": category.id, "company_id": cls.company.id, "struct_id": cls.structure.id,
            "condition_select": "none", "amount_select": "fix", "amount_fix": 100.0})
        debit = cls.scope["account.account"].create({"name": "Private analytic expense", "code": "940061",
            "account_type": "expense", "company_ids": [Command.set(cls.company.ids)]})
        credit = cls.scope["account.account"].create({"name": "Private analytic liability", "code": "940062",
            "account_type": "liability_current", "company_ids": [Command.set(cls.company.ids)]})
        cls.rule.write({"account_debit": debit.id, "account_credit": credit.id})
        # Configuration masters are provisioned by the fixture author. The
        # actual payroll actor receives no additional analytic creation role.
        plan = cls.env["account.analytic.plan"].create({"name": "Private original salary plan", "default_applicability": "optional"})
        cls.analytic = cls.env["account.analytic.account"].create({"name": "Private original salary analytic",
            "company_id": cls.company.id, "plan_id": plan.id}).with_env(cls.scope)
        cls.alternate = cls.env["account.analytic.account"].create({"name": "Private original contract analytic",
            "company_id": cls.company.id, "plan_id": plan.id}).with_env(cls.scope)
        (cls.analytic | cls.alternate).check_access("read")
        employee = cls.scope["hr.employee"].create({"name": "Private original analytic employee", "company_id": cls.company.id})
        values = {"name": "Private original analytic contract", "employee_id": employee.id, "company_id": cls.company.id,
            "state": "open", "date_start": fields.Date.today().replace(day=1), "wage": 100.0,
            "structure_type_id": kind.id, "struct_id": cls.structure.id, "journal_id": cls.journal.id}
        if "contract_type_id" in cls.scope["hr.contract"]._fields:
            field = cls.scope["hr.contract"]._fields["contract_type_id"]
            values["contract_type_id"] = cls.scope[field.comodel_name].search([], limit=1).id
        cls.contract = cls.scope["hr.contract"].create(values)

    def _slip(self):
        return self.scope["hr.payslip"].create({"name": "Private original analytic payslip", "number": "PRIVATE/ORIGINAL/ANALYTIC",
            "employee_id": self.contract.employee_id.id, "company_id": self.company.id, "contract_id": self.contract.id,
            "struct_id": self.structure.id, "date_from": fields.Date.today().replace(day=1), "date_to": fields.Date.today()})

    def _snapshot(self, slip):
        moves = self.scope["account.move"].search([("journal_id", "=", self.journal.id)])
        return (slip.read(["id", "state", "number", "compute_date", "line_ids", "move_id"]),
            slip.line_ids.read(["id", "salary_rule_id", "amount", "quantity", "rate", "total", "analytic_account_id"]),
            moves.read(["id", "state", "line_ids"]), moves.line_ids.read(["id", "debit", "credit", "analytic_distribution"]))

    def _raw_property(self, value):
        self.rule.flush_recordset(["analytic_account_id"])
        self.env.cr.execute("UPDATE hr_salary_rule SET analytic_account_id=%s::jsonb WHERE id=%s",
            (json.dumps(value) if value is not None else None, self.rule.id))
        self.rule.invalidate_recordset(["analytic_account_id"])

    def _other_analytic(self):
        company = self.env["res.company"].create({"name": "Private other analytic company",
            "country_id": self.company.country_id.id, "currency_id": self.company.currency_id.id})
        self.scope.user.with_env(self.env).write({"company_ids": [Command.link(company.id)]})
        scope = self.scope["account.analytic.account"].with_context(allowed_company_ids=(self.company | company).ids).with_company(company).env
        other = self.env["account.analytic.account"].with_company(company).create({"name": "Private other company analytic",
            "company_id": company.id, "plan_id": self.analytic.plan_id.id}).with_env(scope)
        other.check_access("read")
        return scope, other

    def _assert_posted(self, slip, account):
        self.assertEqual(slip.state, "done")
        self.assertEqual(slip.move_id.state, "posted")
        self.assertEqual(slip.move_id.company_id, self.company)
        self.assertEqual(sum(slip.move_id.line_ids.mapped("balance")), 0.0)
        self.assertEqual(sum(slip.move_id.line_ids.mapped("debit")), 100.0)
        if account:
            self.assertEqual(slip.move_id.line_ids.mapped("analytic_distribution"), [{str(account.id): 100.0}] * 2)
        else:
            self.assertTrue(all(not line.analytic_distribution for line in slip.move_id.line_ids))

    def test_rule_json_metadata_and_line_scalar_remain_independent(self):
        # Trusted module-data/fixture author, context A, explicit owner B.
        # With no analytic property the provider's ordinary create policy is
        # authoritative; the adapter must not invent a company slot/context.
        other_company = self.env["res.company"].create({"name": "Private NULL analytic rule owner"})
        other_category = self.env["hr.salary.rule.category"].with_company(other_company).create({
            "name": "Private other-owner analytic category", "code": "PRIVATE_OTHER_ANALYTIC_CATEGORY", "company_id": other_company.id})
        author = self.env["hr.salary.rule"].with_company(self.company)
        other_rule = author.create({"name": "Private other-owner NULL analytic rule", "code": "PRIVATE_OTHER_NULL_ANALYTIC",
            "sequence": 1, "category_id": other_category.id, "company_id": other_company.id})
        other_rule.flush_recordset(["company_id", "analytic_account_id"])
        self.env.cr.execute("SELECT company_id,analytic_account_id,analytic_account_id IS NULL FROM hr_salary_rule WHERE id=%s", (other_rule.id,))
        self.assertEqual(self.env.cr.fetchone(), (other_company.id, None, True))
        rule_field = self.rule._fields["analytic_account_id"]
        line_field = self.scope["hr.payslip.line"]._fields["analytic_account_id"]
        self.assertTrue(rule_field.company_dependent)
        self.assertFalse(rule_field.copy)
        self.assertFalse(line_field.company_dependent)
        self.assertTrue(line_field.copy)
        self.assertEqual(rule_field.ondelete, "set null")
        self.assertEqual(rule_field.comodel_name, "account.analytic.account")
        self.rule.analytic_account_id = self.analytic
        slip = self._slip()
        slip.compute_sheet()
        self.assertEqual(slip.line_ids.salary_rule_id, self.rule)
        self.env.cr.execute("""SELECT c.relname,t.typname FROM pg_attribute a JOIN pg_class c ON c.oid=a.attrelid
            JOIN pg_type t ON t.oid=a.atttypid WHERE c.oid=ANY(ARRAY['hr_salary_rule'::regclass,'hr_payslip_line'::regclass])
            AND a.attname='analytic_account_id' AND NOT a.attisdropped""")
        self.assertEqual(dict(self.env.cr.fetchall()), {"hr_salary_rule": "jsonb", "hr_payslip_line": "int4"})
        slip.line_ids.analytic_account_id = self.alternate
        self.assertEqual(self.rule.analytic_account_id, self.analytic)
        self.assertEqual(slip.line_ids.analytic_account_id, self.alternate)

    def test_real_posting_uses_exact_rule_company_property_and_keeps_stored_lines(self):
        self.rule.analytic_account_id = self.analytic
        slip = self._slip()
        slip.compute_sheet()
        before = slip.line_ids.read(["id", "salary_rule_id", "amount", "quantity", "rate", "total", "analytic_account_id"])
        slip.with_context(without_compute_sheet=True).action_payslip_done()
        self._assert_posted(slip, self.analytic)
        self.assertEqual(slip.line_ids.read(["id", "salary_rule_id", "amount", "quantity", "rate", "total", "analytic_account_id"]), before)
        shared = self.env["account.analytic.account"].create({"name": "Private shared salary analytic",
            "company_id": False, "plan_id": self.analytic.plan_id.id}).with_env(self.scope)
        shared.check_access("read")
        self.rule.analytic_account_id = shared
        other = self._slip()
        other.compute_sheet()
        other.with_context(without_compute_sheet=True).action_payslip_done()
        self._assert_posted(other, shared)
        self._assert_posted(slip, self.analytic)

    def test_contract_priority_is_real_and_unused_hidden_rule_account_is_not_read(self):
        self.rule.analytic_account_id = self.analytic
        self.contract.analytic_account_id = self.alternate
        slip = self._slip()
        slip.compute_sheet()
        self.env["ir.rule"].create({"name": "Private unused hidden rule analytic", "model_id": self.env.ref("analytic.model_account_analytic_account").id,
            "domain_force": "[('id','!=',%d)]" % self.analytic.id})
        slip.with_context(without_compute_sheet=True).action_payslip_done()
        self._assert_posted(slip, self.alternate)

    def test_null_property_stays_null_and_no_unapproved_default_is_posted(self):
        for value in (None, {str(self.company.id): None}):
            self._raw_property(value)
            original = self._slip()
            original.compute_sheet()
            original.with_context(without_compute_sheet=True).action_payslip_done()
            self._assert_posted(original, self.scope["account.analytic.account"])
            self.env.cr.execute("SELECT analytic_account_id FROM hr_salary_rule WHERE id=%s", (self.rule.id,))
            self.assertEqual(self.env.cr.fetchone()[0], value)
        # Python False remains the ordinary ORM clear operation. It must be
        # normalized by the real provider, not stored as a JSON boolean M2O.
        self.rule.analytic_account_id = self.analytic
        self.rule.analytic_account_id = False
        self.rule.flush_recordset(["analytic_account_id"])
        self.env.cr.execute("SELECT analytic_account_id,analytic_account_id IS NULL FROM hr_salary_rule WHERE id=%s", (self.rule.id,))
        cleared, sql_null = self.env.cr.fetchone()
        if sql_null:
            self.assertIsNone(cleared)
        else:
            self.assertIsInstance(cleared, dict)
            self.assertIn(str(self.company.id), cleared)
            self.assertIsNone(cleared[str(self.company.id)])
        self.assertFalse(self.rule.analytic_account_id)
        cleared_slip = self._slip()
        cleared_slip.compute_sheet()
        cleared_slip.with_context(without_compute_sheet=True).action_payslip_done()
        self._assert_posted(cleared_slip, self.scope["account.analytic.account"])
        self._raw_property(None)
        slip = self._slip()
        slip.compute_sheet()
        self.env["ir.default"].set("hr.salary.rule", "analytic_account_id", self.analytic.id, company_id=self.company.id)
        before = self._snapshot(slip)
        with self.assertRaisesRegex(UserError, "implicit payroll analytic default"):
            slip.with_context(without_compute_sheet=True).action_payslip_done()
        self.assertEqual(self._snapshot(slip), before)
        self.env.cr.execute("SELECT analytic_account_id FROM hr_salary_rule WHERE id=%s", (self.rule.id,))
        self.assertIsNone(self.env.cr.fetchone()[0])

    def test_empty_missing_malformed_and_foreign_slots_fail_before_mutations(self):
        slip = self._slip()
        slip.compute_sheet()
        scope, foreign = self._other_analytic()
        caller = slip.with_env(scope).with_company(self.company)
        before = self._snapshot(slip)
        for value in ({}, {str(scope.company.id): foreign.id}, {str(self.company.id): "wrong"},
                {str(self.company.id): 0}, {str(self.company.id): 2**31}, {str(self.company.id): False},
                {str(self.company.id): True}, {str(self.company.id): foreign.id}):
            self._raw_property(value)
            with self.assertRaises(UserError):
                caller.with_context(without_compute_sheet=True).action_payslip_done()
            self.assertEqual(self._snapshot(slip), before)
            self.env.cr.execute("SELECT analytic_account_id FROM hr_salary_rule WHERE id=%s", (self.rule.id,))
            self.assertEqual(self.env.cr.fetchone()[0], value)

    def test_rule_and_contract_accounts_enforce_normal_actor_acl_even_with_sudo_and_warm_cache(self):
        for contract_priority in (False, True):
            self.rule.analytic_account_id = self.analytic
            self.contract.analytic_account_id = self.alternate if contract_priority else False
            slip = self._slip()
            slip.compute_sheet()
            target = self.alternate if contract_priority else self.analytic
            self.assertTrue(target.name)
            before = self._snapshot(slip)
            restriction = self.env["ir.rule"].create({"name": "Private hidden original analytic", "model_id": self.env.ref("analytic.model_account_analytic_account").id,
                "domain_force": "[('id','!=',%d)]" % target.id})
            with self.assertRaises(AccessError):
                slip.sudo().with_context(without_compute_sheet=True).action_payslip_done()
            self.assertEqual(self._snapshot(slip), before)
            restriction.unlink()

    def test_field_acl_and_hidden_existing_salary_line_block_posting_before_changes(self):
        self.rule.analytic_account_id = self.analytic
        slip = self._slip()
        slip.compute_sheet()
        before = self._snapshot(slip)
        for field in (self.rule._fields["analytic_account_id"], self.analytic._fields["company_id"]):
            with patch.object(field, "groups", "base.group_system"), self.assertRaises(AccessError):
                slip.sudo().with_context(without_compute_sheet=True).action_payslip_done()
            self.assertEqual(self._snapshot(slip), before)
        self.env["ir.rule"].create({"name": "Private hidden original analytic salary line",
            "model_id": self.env.ref("payroll.model_hr_payslip_line").id, "domain_force": "[('id','not in',%r)]" % slip.line_ids.ids})
        with self.assertRaises(AccessError):
            slip.with_context(without_compute_sheet=True).action_payslip_done()
        # Fixture author reads its original owned lines only for comparison.
        self.assertEqual(self._snapshot(slip.sudo()), before)

    def test_writes_reject_wrong_company_or_hidden_accounts_atomically(self):
        scope, foreign = self._other_analytic()
        rule = self.rule.with_env(scope).with_company(self.company)
        rule.analytic_account_id = self.analytic
        with self.assertRaisesRegex(UserError, "payslip company or be shared"):
            rule.analytic_account_id = foreign
        self.assertEqual(rule.analytic_account_id, self.analytic)
        self.env["ir.rule"].create({"name": "Private hidden analytic assignment", "model_id": self.env.ref("analytic.model_account_analytic_account").id,
            "domain_force": "[('id','!=',%d)]" % self.alternate.id})
        with self.assertRaises(AccessError):
            rule.sudo().analytic_account_id = self.alternate
        self.assertEqual(rule.analytic_account_id, self.analytic)
        with self.assertRaises(AccessError):
            self.scope["hr.salary.rule"].create({"name": "Private rejected analytic rule", "code": "PRIVATE_REJECTED_ANALYTIC",
                "sequence": 1, "category_id": self.rule.category_id.id, "company_id": self.company.id,
                "analytic_account_id": self.alternate.id})
        self.assertFalse(self.scope["hr.salary.rule"].search([("code", "=", "PRIVATE_REJECTED_ANALYTIC")]))

    def test_multi_company_slots_and_closed_history_are_not_reassigned_or_recomputed(self):
        scope, foreign = self._other_analytic()
        self.rule.company_id = False
        scoped = self.rule.with_env(scope)
        scoped.with_company(self.company).analytic_account_id = self.analytic
        scoped.with_company(scope.company).analytic_account_id = foreign
        self.assertEqual(scoped.with_company(self.company)._step_original_analytic_account(), self.analytic.with_env(scope))
        self.assertEqual(scoped.with_company(scope.company)._step_original_analytic_account(), foreign)
        slip = self._slip()
        slip.compute_sheet()
        slip.with_context(without_compute_sheet=True).action_payslip_done()
        before = self._snapshot(slip)
        self.rule.analytic_account_id = self.alternate
        self.structure.active = False
        with patch.object(type(slip), "compute_sheet", side_effect=AssertionError("Closed payroll cannot be recomputed")):
            self.assertEqual(slip._get_line_values([self.rule.code])[self.rule.code][slip.id]["total"], 100.0)
            self.assertEqual(self._snapshot(slip), before)
        with self.assertRaisesRegex(UserError, "Closed payroll"):
            slip.with_context(without_compute_sheet=True).action_payslip_done()
        self.assertEqual(self._snapshot(slip), before)


@tagged("post_install", "-at_install")
class OriginalAnalyticStorageCase(TransactionCase):
    """Real PostgreSQL DDL on rollback-only temporary fixtures, no business rows."""
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env["res.company"].create({"name": "Private analytic migration company"})
        cls.other = cls.env["res.company"].create({"name": "Private other analytic migration company"})
        plan = cls.env["account.analytic.plan"].create({"name": "Private analytic migration plan"})
        cls.account = cls.env["account.analytic.account"].create({"name": "Private analytic migration account",
            "company_id": cls.company.id, "plan_id": plan.id})
        cls.env.flush_all()

    def _temporary_rules(self, kind="integer", default=""):
        # pg_temp shadows only SQL in this test transaction, then rollback
        # removes it. There is no persistent parallel payroll model/master.
        self.env.cr.execute("CREATE TEMP TABLE account_analytic_account(id integer PRIMARY KEY,company_id integer) ON COMMIT DROP")
        self.env.cr.execute("INSERT INTO account_analytic_account VALUES(%s,%s)", (self.account.id, self.company.id))
        self.env.cr.execute("CREATE TEMP TABLE hr_salary_rule(id integer PRIMARY KEY,company_id integer,analytic_account_id " + kind + default + ") ON COMMIT DROP")

    def test_scalar_conversion_keeps_null_and_exact_owner_account_ids_and_other_schema(self):
        self._temporary_rules()
        self.env.cr.execute("ALTER TABLE hr_salary_rule ADD CONSTRAINT private_analytic_fk FOREIGN KEY(analytic_account_id) REFERENCES account_analytic_account(id) ON DELETE SET NULL")
        self.env.cr.execute("INSERT INTO hr_salary_rule VALUES(1,NULL,NULL),(2,%s,%s)", (self.company.id, self.account.id))
        result = prepare_original_analytic_storage(self.env.cr)
        self.assertEqual(result, {"storage": "jsonb", "converted": 1})
        self.env.cr.execute("SELECT id,company_id,analytic_account_id FROM hr_salary_rule ORDER BY id")
        self.assertEqual(self.env.cr.fetchall(), [(1, None, None), (2, self.company.id, {str(self.company.id): self.account.id})])
        self.env.cr.execute("SELECT contype FROM pg_constraint WHERE conrelid='hr_salary_rule'::regclass")
        self.assertEqual(self.env.cr.fetchall(), [("p",)])
        self.env.cr.execute("SELECT data_type FROM information_schema.columns WHERE table_schema='public' AND table_name='hr_payslip_line' AND column_name='analytic_account_id'")
        self.assertEqual(self.env.cr.fetchone(), ("integer",))

    def test_ambiguous_owner_or_foreign_reference_aborts_without_ddl_or_partial_rows(self):
        self._temporary_rules()
        for owner in (None, self.other.id):
            self.env.cr.execute("DELETE FROM hr_salary_rule")
            self.env.cr.execute("INSERT INTO hr_salary_rule VALUES(1,%s,%s),(2,%s,%s)", (self.company.id, self.account.id, owner, self.account.id))
            with self.assertRaises(AnalyticStorageError):
                prepare_original_analytic_storage(self.env.cr)
            self.env.cr.execute("SELECT id,company_id,analytic_account_id FROM hr_salary_rule ORDER BY id")
            self.assertEqual(self.env.cr.fetchall(), [(1, self.company.id, self.account.id), (2, owner, self.account.id)])
            self.env.cr.execute("SELECT atttypid::regtype::text FROM pg_attribute WHERE attrelid='hr_salary_rule'::regclass AND attname='analytic_account_id'")
            self.assertEqual(self.env.cr.fetchone(), ("integer",))

    def test_existing_json_is_idempotent_and_preserves_null_empty_and_explicit_clear(self):
        self._temporary_rules("jsonb")
        value = {str(self.company.id): self.account.id, str(self.other.id): None}
        self.env.cr.execute("INSERT INTO hr_salary_rule VALUES(1,NULL,NULL),(2,NULL,%s::jsonb),(3,NULL,'{}'::jsonb),(4,NULL,%s::jsonb)",
            (json.dumps(value), json.dumps({str(self.company.id): None})))
        self.env.cr.execute("SELECT id,company_id,analytic_account_id FROM hr_salary_rule ORDER BY id")
        before = self.env.cr.fetchall()
        self.assertEqual(prepare_original_analytic_storage(self.env.cr), {"storage": "jsonb", "converted": 0})
        self.env.cr.execute("SELECT id,company_id,analytic_account_id FROM hr_salary_rule ORDER BY id")
        self.assertEqual(self.env.cr.fetchall(), before)
        for malformed in ("[]", "null", "true", "123"):
            self.env.cr.execute("UPDATE hr_salary_rule SET analytic_account_id=%s::jsonb WHERE id=3", (malformed,))
            with self.assertRaises(AnalyticStorageError):
                prepare_original_analytic_storage(self.env.cr)
        for boolean in (False, True):
            value = {str(self.company.id): boolean}
            self.env.cr.execute("UPDATE hr_salary_rule SET analytic_account_id=%s::jsonb WHERE id=3", (json.dumps(value),))
            with self.assertRaises(AnalyticStorageError):
                prepare_original_analytic_storage(self.env.cr)
            self.env.cr.execute("SELECT analytic_account_id FROM hr_salary_rule WHERE id=3")
            self.assertEqual(self.env.cr.fetchone()[0], value)

    def test_unapproved_column_default_aborts_without_rewriting_null(self):
        self._temporary_rules(default=" DEFAULT 0")
        self.env.cr.execute("INSERT INTO hr_salary_rule VALUES(1,NULL,NULL)")
        with self.assertRaises(AnalyticStorageError):
            prepare_original_analytic_storage(self.env.cr)
        self.env.cr.execute("SELECT analytic_account_id FROM hr_salary_rule WHERE id=1")
        self.assertIsNone(self.env.cr.fetchone()[0])
        # Metadata-only temporary fixture: the actual providers remain loaded;
        # no installed module row is changed to exercise these admission gates.
        self.env.cr.execute("CREATE TEMP TABLE ir_module_module(name text,state text,license text) ON COMMIT DROP")
        self.env.cr.execute("INSERT INTO ir_module_module VALUES('payroll','installed','LGPL-3'),('payroll_account','installed','LGPL-3')")
        for module in ("hr_payroll", "hr_payroll_account", "private_enterprise_provider"):
            for state in ("installed", "to install", "to upgrade", "to remove"):
                self.env.cr.execute("INSERT INTO ir_module_module VALUES(%s,%s,'OEEL-1')", (module, state))
                with self.assertRaisesRegex(AnalyticStorageError, "retire Enterprise"):
                    prepare_original_analytic_storage(self.env.cr)
                self.env.cr.execute("DELETE FROM ir_module_module WHERE name=%s", (module,))
        self.env.cr.execute("UPDATE ir_module_module SET state='uninstalled' WHERE name='payroll_account'")
        with self.assertRaisesRegex(AnalyticStorageError, "actual OCA"):
            prepare_original_analytic_storage(self.env.cr)
