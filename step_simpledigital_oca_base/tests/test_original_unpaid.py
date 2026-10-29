"""Actual monthly day payment, original M2M custody and closed ledger snapshots."""
from unittest.mock import patch

from odoo import Command, fields
from odoo.exceptions import AccessError, UserError
from odoo.tests import TransactionCase, tagged
from odoo.addons.step_payroll_contracts.unpaid_testing import UnpaidRelationFixture


@tagged("post_install", "-at_install")
class OriginalUnpaidCase(UnpaidRelationFixture, TransactionCase):
    payroll_group = "payroll.group_payroll_manager"

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.structures.parent_id = False
        cls.structure.use_worked_day_lines = True
        cls.journal = cls.scope["account.journal"].create({"name": "Private unpaid salary journal", "code": "UPD",
            "type": "general", "company_id": cls.company.id})
        debit, credit = cls.scope["account.account"].create([
            {"name": "Private unpaid salary cost", "code": "949731", "account_type": "expense", "company_ids": [Command.set(cls.company.ids)]},
            {"name": "Private unpaid salary debt", "code": "949732", "account_type": "liability_current", "company_ids": [Command.set(cls.company.ids)]},
        ])
        category = cls.scope["hr.salary.rule.category"].create({"name": "Private unpaid salary category",
            "code": "PRIVATE_UNPAID_CATEGORY", "company_id": cls.company.id})
        cls.rule = cls.scope["hr.salary.rule"].create({"name": "Private real paid-day rule", "code": "PRIVATE_PAID_DAYS",
            "struct_id": cls.structure.id, "company_id": cls.company.id, "category_id": category.id,
            "condition_select": "none", "amount_select": "code", "amount_python_compute": "result = payslip.paid_amount",
            "account_debit": debit.id, "account_credit": credit.id})
        employee = cls.scope["hr.employee"].create({"name": "Private unpaid salary employee", "company_id": cls.company.id})
        values = {"name": "Private unpaid salary contract", "employee_id": employee.id, "company_id": cls.company.id,
            "state": "open", "date_start": fields.Date.today().replace(day=1), "wage": 900000,
            "struct_id": cls.structure.id, "structure_type_id": cls.kind.id, "journal_id": cls.journal.id, "schedule_pay": "monthly"}
        field = cls.scope["hr.contract"]._fields.get("contract_type_id")
        if field:
            values["contract_type_id"] = cls.scope[field.comodel_name].search([], limit=1).id
        cls.contract = cls.scope["hr.contract"].create(values)

    def _slip(self, structure=None):
        structure = structure if structure is not None else self.structure
        return self.scope["hr.payslip"].create({"name": "Private unpaid salary slip", "number": "PRIVATE/UNPAID/SALARY",
            "employee_id": self.contract.employee_id.id, "company_id": self.company.id,
            "contract_id": self.contract.id, "struct_id": structure.id,
            "date_from": fields.Date.today().replace(day=1), "date_to": fields.Date.today()})

    def _day(self, slip):
        return self.scope["hr.payslip.worked_days"].create({"name": "Private actual typed days", "payslip_id": slip.id,
            "contract_id": self.contract.id, "work_entry_type_id": self.entry_type.id,
            "number_of_days": 2, "number_of_hours": 16})

    def _stored(self, slip):
        result = []
        for table, predicate, values in (
            ("hr_payslip", "id=%s", (slip.id,)),
            ("hr_payslip_worked_days", "payslip_id=%s", (slip.id,)),
            ("hr_payslip_line", "slip_id=%s", (slip.id,)),
            ("account_move", "id=%s", (slip.move_id.id or 0,)),
            ("account_move_line", "move_id=%s", (slip.move_id.id or 0,)),
        ):
            self.env.cr.execute("SELECT to_jsonb(t) FROM " + table + " t WHERE " + predicate + " ORDER BY id", values)
            result.append(self.env.cr.fetchall())
        return result

    def test_real_unpaid_relation_metadata_inverse_and_raw_pairs(self):
        self.case_real_unpaid_relation_metadata_inverse_and_raw_pairs()

    def test_archived_pairs_and_default_copy_keep_both_original_endpoints(self):
        self.case_real_unpaid_relation_keeps_archived_original_pairs()
        before = self.unpaid_pairs()
        copied_structure = self.structure.copy({"name": "Private copied unpaid structure", "code": "PRIVATE_UNPAID_COPY"})
        self.assertEqual(copied_structure.with_context(active_test=False).unpaid_work_entry_type_ids, self.entry_type)
        copied_type = self.entry_type.copy({"name": "Private copied unpaid entry", "code": "PRIVATE_UNPAID_COPY_TYPE"})
        self.assertEqual(set(copied_type.with_context(active_test=False).unpaid_structure_ids.ids),
            set((self.structures | copied_structure).ids))
        self.assertEqual(self.unpaid_pairs(), before)

    def test_inverse_policy_recomputes_actual_draft_days_without_replacing_identity(self):
        slip = self._slip()
        day = self._day(slip)
        expected = self.company.currency_id.round(self.contract.wage / 30.0 * day.number_of_days)
        self.assertEqual(day.amount, expected)
        self.assertTrue(day.is_paid)
        original_id = day.id
        self.structure.unpaid_work_entry_type_ids = [Command.link(self.entry_type.id)]
        self.assertEqual(day.amount, 0)
        self.assertFalse(day.is_paid)
        self.entry_type.unpaid_structure_ids = [Command.unlink(self.structure.id)]
        self.assertEqual(day.amount, expected)
        self.assertTrue(day.is_paid)
        self.contract.wage = 1200000
        self.assertEqual(day.amount, self.company.currency_id.round(self.contract.wage / 30.0 * day.number_of_days))
        self.assertEqual(day.id, original_id)

    def test_real_closed_workflow_keeps_days_lines_and_ledger_exact_after_policy_change(self):
        slip = self._slip()
        day = self._day(slip)
        slip.compute_sheet()
        slip.with_context(without_compute_sheet=True).action_payslip_done()
        self.assertTrue(slip.step_history_locked)
        self.assertTrue(slip.move_id)
        self.assertEqual(slip.move_id.state, "posted")
        self.env.flush_all()
        before = self._stored(slip)
        original = day.read(["id", "amount", "is_paid"])
        self.contract.wage = 1200000
        self.structure.unpaid_work_entry_type_ids = [Command.link(self.entry_type.id)]
        self.entry_type.active = False
        self.env["ir.rule"].create({"name": "Private hidden future unpaid type",
            "model_id": self.env.ref("hr_work_entry.model_hr_work_entry_type").id,
            "domain_force": "[('id','!=',%d)]" % self.entry_type.id})
        self.env.flush_all()
        day.invalidate_recordset(["amount", "is_paid"])
        self.assertEqual(day.read(["id", "amount", "is_paid"]), original)
        self.assertEqual(self._stored(slip), before)

    def test_hidden_component_cannot_be_cleared_copied_or_deleted(self):
        self.entry_type.unpaid_structure_ids = [Command.set(self.structures.ids)]
        self.other_structure.active = False
        self.structure.with_context(active_test=False).unpaid_work_entry_type_ids.read(["name"])
        before = self.unpaid_pairs()
        self.env["ir.rule"].create({"name": "Private hidden unpaid structure neighbour",
            "model_id": self.env.ref("payroll.model_hr_payroll_structure").id,
            "domain_force": "[('id','!=',%d)]" % self.other_structure.id})
        for operation in (
            lambda: self.structure.write({"unpaid_work_entry_type_ids": [Command.clear()]}),
            lambda: self.entry_type.write({"unpaid_structure_ids": [Command.clear()]}),
            lambda: self.structure.copy({"name": "Private forbidden hidden copy"}),
            lambda: self.entry_type.unlink(),
        ):
            with self.assertRaises(AccessError):
                operation()
            self.assertEqual(self.unpaid_pairs(), before)

    def test_field_acl_is_enforced_before_calculation_and_stored_payment_compute(self):
        slip = self._slip()
        day = self._day(slip)
        self.structure.unpaid_work_entry_type_ids = [Command.link(self.entry_type.id)]
        self.env.flush_all()
        before = self._stored(slip)
        for field in (self.structure._fields["unpaid_work_entry_type_ids"],
                self.entry_type._fields["unpaid_structure_ids"], self.entry_type._fields["country_id"]):
            # A real field ACL is restricted temporarily; no successful engine
            # or accounting response is mocked and the tested actor gains no role.
            with patch.object(field, "groups", "base.group_system"):
                with self.assertRaises(AccessError):
                    slip.sudo().compute_sheet()
                with self.assertRaises(AccessError):
                    day.sudo()._compute_payment()
            self.assertEqual(self._stored(slip), before)

    def test_country_policy_uses_real_company_for_global_structure_and_visible_legacy_pair_can_be_removed(self):
        foreign_company = self.env["res.company"].create({"name": "Private foreign unpaid policy company",
            "country_id": self.env.ref("base.fr").id})
        self.scope.user.with_env(self.env).write({"company_ids": [Command.link(foreign_company.id)]})
        scope = self.structure.with_context(allowed_company_ids=(self.company | foreign_company).ids).env
        foreign = scope["hr.work.entry.type"].create({"name": "Private foreign unpaid entry",
            "code": "PRIVATE_UNPAID_FOREIGN", "country_id": foreign_company.country_id.id})
        structure = self.structure.with_env(scope)
        with self.assertRaisesRegex(UserError, "country boundaries"):
            structure.unpaid_work_entry_type_ids = [Command.link(foreign.id)]
        self.assertFalse(structure.unpaid_work_entry_type_ids)
        global_structure = scope["hr.payroll.structure"].create({"name": "Private global unresolved unpaid structure",
            "code": "PRIVATE_GLOBAL_UNPAID", "company_id": False, "country_id": False, "type_id": self.kind.id,
            "unpaid_work_entry_type_ids": [Command.link(foreign.id)]})
        self.assertFalse(global_structure.company_id)
        self.assertFalse(global_structure.country_id)
        slip = self._slip(global_structure).with_env(scope)
        before = self._stored(slip)
        with self.assertRaisesRegex(UserError, "country boundaries"):
            slip.compute_sheet()
        self.assertEqual(self._stored(slip), before)
        # An isolated synthetic SQL pair represents pre-existing bad policy;
        # no original master or amount is changed to manufacture this case.
        self.env.cr.execute("""INSERT INTO hr_payroll_structure_hr_work_entry_type_rel
            (hr_payroll_structure_id,hr_work_entry_type_id) VALUES (%s,%s)""", (structure.id, foreign.id))
        structure.invalidate_recordset(["unpaid_work_entry_type_ids"])
        foreign.invalidate_recordset(["unpaid_structure_ids"])
        structure.unpaid_work_entry_type_ids = [Command.unlink(foreign.id)]
        self.assertFalse(structure.unpaid_work_entry_type_ids)
        self.assertEqual(global_structure.unpaid_work_entry_type_ids, foreign)
