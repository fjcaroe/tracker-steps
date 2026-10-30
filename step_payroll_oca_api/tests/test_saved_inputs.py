"""Six saved-row admission cases with the actual OCA input model and actor."""
import json
import math
from unittest.mock import patch

from lxml import etree
from psycopg2.errors import FeatureNotSupported

from odoo import api, Command, fields
from odoo.exceptions import AccessError, UserError
from odoo.tests import TransactionCase, tagged
from odoo.tools import json_default


@tagged("post_install", "-at_install")
class SavedInputValuesCase(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env["res.company"].create({"name": "Private saved-input company",
            "country_id": cls.env.ref("base.cl").id, "currency_id": cls.env.ref("base.CLP").id})
        actor = cls.env["res.users"].with_context(no_reset_password=True).create({
            "name": "Private saved-input manager", "login": "private-saved-input-manager",
            "company_id": cls.company.id, "company_ids": [Command.set(cls.company.ids)],
            "groups_id": [Command.set([cls.env.ref(name).id for name in (
                "base.group_user", "payroll.group_payroll_manager", "hr.group_hr_manager", "account.group_account_manager")])]})
        cls.scope = api.Environment(cls.env.cr, actor.id, dict(cls.env.context, allowed_company_ids=cls.company.ids), su=False)
        cls.journal = cls.scope["account.journal"].create({"name": "Private saved-input journal", "code": "PSI",
            "type": "general", "company_id": cls.company.id})
        kind = cls.scope["hr.payroll.structure.type"].create({"name": "Private saved-input structure type"})
        cls.structure = cls.scope["hr.payroll.structure"].create({"name": "Private saved-input structure",
            "code": "PRIVATE_SAVED", "type_id": kind.id, "company_id": cls.company.id, "parent_id": False})
        category = cls.scope["hr.salary.rule.category"].create({"name": "Private saved-input category", "code": "PRIVATE_SAVED_CAT"})
        cls.rule = cls.scope["hr.salary.rule"].create({"name": "Private saved-input rule", "code": "PRIVATE_SAVED_RESULT",
            "company_id": cls.company.id, "struct_id": cls.structure.id, "category_id": category.id,
            "condition_select": "none", "amount_select": "code", "amount_python_compute": "result = inputs['PRIVATE_SAVED_INPUT'].amount"})
        cls.input_type = cls.scope["hr.payslip.input.type"].create({"name": "Private saved-input type",
            "code": "PRIVATE_SAVED_INPUT", "country_id": cls.company.country_id.id, "struct_ids": [Command.set(cls.structure.ids)]})
        employee = cls.scope["hr.employee"].create({"name": "Private saved-input employee", "company_id": cls.company.id})
        values = {"name": "Private saved-input contract", "employee_id": employee.id, "company_id": cls.company.id,
            "state": "open", "date_start": fields.Date.today().replace(day=1), "wage": 100,
            "structure_type_id": kind.id, "struct_id": cls.structure.id, "journal_id": cls.journal.id}
        if "contract_type_id" in cls.scope["hr.contract"]._fields:
            field = cls.scope["hr.contract"]._fields["contract_type_id"]
            values["contract_type_id"] = cls.scope[field.comodel_name].search([], limit=1).id
        cls.contract = cls.scope["hr.contract"].create(values)

    def _slip(self):
        return self.scope["hr.payslip"].create({"name": "Private saved-input payslip", "number": "PRIVATE/SAVED/INPUT",
            "employee_id": self.contract.employee_id.id, "company_id": self.company.id,
            "contract_id": self.contract.id, "struct_id": self.structure.id,
            "date_from": fields.Date.today().replace(day=1), "date_to": fields.Date.today()})

    def _input(self, slip, amount=0, kind=None, omitted=False):
        values = {"payslip_id": slip.id, "contract_id": self.contract.id,
            "input_type_id": (kind if kind is not None else self.input_type).id}
        if not omitted:
            values["amount"] = amount
        return self.scope["hr.payslip.input"].create(values)

    def _snapshot(self, slip):
        self.scope.flush_all()
        result = []
        for table, predicate, args in (("hr_payslip", "id=%s", (slip.id,)),
                ("hr_payslip_input", "payslip_id=%s", (slip.id,)),
                ("hr_payslip_line", "slip_id=%s", (slip.id,))):
            self.env.cr.execute("SELECT to_jsonb(t) FROM " + table + " t WHERE " + predicate + " ORDER BY id", args)
            result.append(self.env.cr.fetchall())
        return result

    def test_saved_zero_and_repeated_same_type_are_admitted_without_writes_and_real_view(self):
        slip = self._slip()
        first = self._input(slip, 0)
        second = self._input(slip, 12.5)
        before = self._snapshot(slip)
        self.assertFalse(slip.env.su)
        self.assertTrue(slip._step_check_saved_input_values())
        self.assertEqual(self._snapshot(slip), before)
        self.env.cr.execute("SELECT amount FROM hr_payslip_input WHERE id=%s", (first.id,))
        self.assertEqual(self.env.cr.fetchone(), (0.0,))
        slip.compute_sheet()
        self.assertTrue(slip.line_ids)
        self.assertEqual(slip.input_line_ids, first | second)
        self.assertTrue(slip._step_check_saved_input_values())
        arch = etree.fromstring(slip.get_view(view_id=self.scope.ref("payroll.hr_payslip_view_form").id, view_type="form")["arch"])
        for node in ("list", "form"):
            relation = arch.xpath("//field[@name='input_line_ids']/" + node)[0]
            typed = relation.xpath(".//field[@name='input_type_id']")[0]
            self.assertIn("no_create", typed.get("options"))
            self.assertTrue(relation.xpath(".//field[@name='code'][@readonly='input_type_id != False']"))
        json.dumps(slip.get_view(view_type="form"), default=json_default)

    def test_missing_amount_is_sql_null_despite_zero_cache_and_nonfinite_values_are_rejected(self):
        slip = self._slip()
        row = self._input(slip, omitted=True)
        self.assertEqual(row.amount, 0.0)
        before = self._snapshot(slip)
        self.env.cr.execute("SELECT amount FROM hr_payslip_input WHERE id=%s", (row.id,))
        self.assertEqual(self.env.cr.fetchone(), (None,))
        with self.assertRaisesRegex(UserError, "Complete the amount"):
            slip.sudo()._step_check_saved_input_values()
        self.assertEqual(self._snapshot(slip), before)
        row.write({"name": "Private input still awaiting an amount"})
        row.flush_recordset()
        self.assertEqual(row.amount, 0.0)
        self.env.cr.execute("SELECT amount FROM hr_payslip_input WHERE id=%s", (row.id,))
        self.assertEqual(self.env.cr.fetchone(), (None,), "An unrelated write cannot acknowledge a missing amount")
        # Model.write is the explicit saved-value RPC contract. Verify the
        # physical zero rather than accepting Float's NULL-to-zero cache view.
        row.write({"amount": 0.0})
        row.flush_recordset(["amount"])
        self.env.cr.execute("SELECT amount FROM hr_payslip_input WHERE id=%s", (row.id,))
        self.assertEqual(self.env.cr.fetchone(), (0.0,))
        self.assertTrue(slip._step_check_saved_input_values())
        for value in (float("nan"), float("inf"), float("-inf")):
            attempted_before = self._snapshot(slip)
            try:
                # PostgreSQL 12 NUMERIC cannot store Infinity. Later versions
                # may accept it; then the actual admission must reject it.
                with self.env.cr.savepoint(flush=False):
                    self.env.cr.execute("UPDATE hr_payslip_input SET amount=%s WHERE id=%s", (value, row.id))
            except FeatureNotSupported as error:
                self.assertEqual(error.pgcode, "0A000")
                self.assertTrue(math.isinf(value), "NaN storage is supported and must exercise the API guard")
                self.env.cr.execute("SELECT t.typname FROM pg_attribute a JOIN pg_type t ON t.oid=a.atttypid WHERE a.attrelid='hr_payslip_input'::regclass AND a.attname='amount'")
                self.assertEqual(self.env.cr.fetchone(), ("numeric",))
                self.assertEqual(self._snapshot(slip), attempted_before, "Rejected nonfinite storage changed the saved rows")
                continue
            row.invalidate_recordset(["amount"])
            before = self._snapshot(slip)
            with self.assertRaisesRegex(UserError, "finite"):
                slip._step_check_saved_input_values()
            self.assertEqual(self._snapshot(slip), before)

    def test_hidden_saved_input_type_descriptor_and_structure_block_warm_sudo_without_partial_rows(self):
        slip = self._slip()
        other = self.structure.copy({"name": "Private linked saved-input structure", "code": "PRIVATE_SAVED_LINKED", "rule_ids": [Command.clear()]})
        self.input_type.struct_ids = self.structure | other
        row = self._input(slip, 25)
        descriptor = self.scope["hr.rule.input"].create({"name": "Private saved-input descriptor", "code": self.input_type.code, "input_id": self.rule.id})
        row.read(["amount", "input_type_id"])
        self.input_type.read(["code", "struct_ids"])
        descriptor.read(["code"])
        for record in (slip, row, self.input_type, descriptor, other):
            before = self._snapshot(slip)
            restriction = self.env["ir.rule"].create({"name": "Private hidden saved-input reference",
                "model_id": self.env["ir.model"]._get_id(record._name), "domain_force": "[('id','!=',%d)]" % record.id})
            with self.assertRaises(AccessError):
                slip.sudo()._step_check_saved_input_values()
            if record._name in ("hr.payslip", "hr.payslip.input"):
                with self.assertRaises(AccessError):
                    row.sudo().write({"amount": 0.0})
            restriction.unlink()
            self.assertEqual(self._snapshot(slip), before)

    def test_field_access_is_checked_before_sql_values_even_with_warm_cache_and_sudo(self):
        slip = self._slip()
        row = self._input(slip, 25)
        descriptor = self.scope["hr.rule.input"].create({"name": "Private field-access input descriptor", "code": self.input_type.code, "input_id": self.rule.id})
        self.assertTrue(slip._step_check_saved_input_values())
        before = self._snapshot(slip)
        protected = [slip._fields["input_line_ids"], row._fields["amount"], row._fields["code"],
            row._fields["contract_id"], self.input_type._fields["country_id"], self.input_type._fields["struct_ids"],
            descriptor._fields["code"], descriptor._fields["input_id"]]
        for field in protected:
            with patch.object(field, "groups", "base.group_system"), self.assertRaises(AccessError):
                slip.sudo()._step_check_saved_input_values()
            self.assertEqual(self._snapshot(slip), before)
        with patch.object(row._fields["amount"], "groups", "base.group_system"), self.assertRaises(AccessError):
            row.sudo().write({"amount": 0.0})
        self.assertEqual(self._snapshot(slip), before)

    def test_configured_type_coverage_uses_saved_fk_and_legacy_codes_must_be_unambiguous(self):
        slip = self._slip()
        self.scope["hr.payslip.input.type"].create({"name": "Private unused global input", "code": "PRIVATE_UNUSED_GLOBAL"})
        with self.assertRaisesRegex(UserError, "every configured"):
            slip._step_check_saved_input_values()
        self._input(slip, 10)
        self.assertTrue(slip._step_check_saved_input_values())
        kind = self.scope["hr.payslip.input.type"].create({"name": "Private second configured input", "code": "PRIVATE_SAVED_SECOND",
            "struct_ids": [Command.set(self.structure.ids)]})
        with self.assertRaisesRegex(UserError, "every configured"):
            slip._step_check_saved_input_values()
        self._input(slip, 0, kind=kind)
        descriptor = self.scope["hr.rule.input"].create({"name": "Private exact input descriptor", "code": self.input_type.code, "input_id": self.rule.id})
        self.assertTrue(slip._step_check_saved_input_values())
        duplicate = descriptor.copy({"name": "Private ambiguous descriptor"})
        with self.assertRaisesRegex(UserError, "unambiguous exact code"):
            slip._step_check_saved_input_values()
        duplicate.unlink()
        descriptor.code = "PRIVATE_MISSING_ORIGINAL_INPUT"
        with self.assertRaisesRegex(UserError, "unambiguous exact code"):
            slip._step_check_saved_input_values()
        self.assertEqual(set(slip.input_line_ids.input_type_id.ids), set((self.input_type | kind).ids))

    def test_untyped_wrong_contract_code_country_company_and_closed_history_are_never_repaired(self):
        slip = self._slip()
        row = self._input(slip, 25)
        legacy = self.scope["hr.payslip.input"].create({"name": "Private untyped legacy input", "code": "PRIVATE_UNTYPED",
            "payslip_id": slip.id, "contract_id": self.contract.id, "amount": 0})
        with self.assertRaisesRegex(UserError, "untyped legacy"):
            slip._step_check_saved_input_values()
        self.assertFalse(legacy.input_type_id)
        legacy.unlink()
        # Full contract duplication reads sensitive HR fields. Provision this
        # private master as fixture author; every tested operation stays normal.
        other_contract = self.contract.with_env(self.env).copy({
            "name": "Private other saved-input contract", "state": "draft"}).with_env(self.scope)
        for column, bad, original in (("code", "PRIVATE_WRONG_CODE", row.code), ("contract_id", other_contract.id, self.contract.id)):
            self.env.cr.execute("UPDATE hr_payslip_input SET " + column + "=%s WHERE id=%s", (bad, row.id))
            before = self._snapshot(slip)
            with self.assertRaises(UserError):
                slip._step_check_saved_input_values()
            self.assertEqual(self._snapshot(slip), before)
            self.env.cr.execute("UPDATE hr_payslip_input SET " + column + "=%s WHERE id=%s", (original, row.id))
            row.invalidate_recordset([column])
        self.env.cr.execute("UPDATE hr_payslip_input_type SET country_id=%s WHERE id=%s", (self.env.ref("base.fr").id, self.input_type.id))
        self.input_type.invalidate_recordset(["country_id"])
        before = self._snapshot(slip)
        # The original country record rule hides this master before the
        # business-country checker; preserve that earlier permission boundary.
        with self.assertRaises(AccessError):
            slip._step_check_saved_input_values()
        self.assertEqual(self._snapshot(slip), before)
        self.env.cr.execute("UPDATE hr_payslip_input_type SET country_id=%s WHERE id=%s", (self.company.country_id.id, self.input_type.id))
        self.input_type.invalidate_recordset(["country_id"])
        other_company = self.env["res.company"].create({"name": "Private other saved-input company", "country_id": self.company.country_id.id})
        self.scope.user.with_env(self.env).write({"company_ids": [Command.link(other_company.id)]})
        with self.assertRaises(UserError):
            slip.with_company(other_company).sudo()._step_check_saved_input_values()
        debit, credit = self.scope["account.account"].create([
            {"name": "Private saved-input cost", "code": "948651", "account_type": "expense", "company_ids": [Command.set(self.company.ids)]},
            {"name": "Private saved-input debt", "code": "948652", "account_type": "liability_current", "company_ids": [Command.set(self.company.ids)]}])
        self.rule.write({"account_debit": debit.id, "account_credit": credit.id})
        slip.compute_sheet()
        slip.prevent_compute_on_confirm = True
        slip.action_payslip_done()
        closed = self._snapshot(slip)
        with self.assertRaisesRegex(UserError, "Closed payroll"):
            slip._step_check_saved_input_values()
        with self.assertRaises(UserError):
            row.sudo().write({"amount": 0.0})
        self.assertEqual(self._snapshot(slip), closed)
