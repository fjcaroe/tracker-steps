"""Actual monthly day payment, original M2M custody and closed ledger snapshots."""
from unittest import TestCase
from unittest.mock import patch

from odoo import Command, fields
from odoo.exceptions import AccessError, UserError
from odoo.tests import TransactionCase, tagged
from odoo.addons.step_payroll_contracts.unpaid_testing import UnpaidRelationFixture

from ..models.original_unpaid import PAYMENT_DEPENDENCIES


@tagged("post_install", "-at_install")
class OriginalUnpaidCase(UnpaidRelationFixture, TransactionCase):
    payroll_group = "payroll.group_payroll_manager"

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.structures.parent_id = False
        cls.structures.country_id = cls.company.country_id
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
        view = self.scope['hr.payroll.structure'].get_view(
            view_id=self.scope.ref('payroll.hr_payroll_structure_view_form').id, view_type='form')
        self.assertIn('name="unpaid_work_entry_type_ids"', view['arch'])
        days = self.scope["hr.payslip.worked_days"]
        for name in ("is_paid", "amount"):
            field = days._fields[name]
            self.assertTrue(field.store)
            self.assertEqual(field.compute, "_compute_payment")
            self.assertEqual(set(field.get_depends(days)[0]), set(PAYMENT_DEPENDENCIES))
            self.assertEqual(set(self.scope.registry.field_depends[field]), set(PAYMENT_DEPENDENCIES))
            self.assertNotIn("work_entry_type_id.unpaid_structure_ids", self.scope.registry.field_depends[field])

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

    def test_real_unsaved_preview_checks_normal_policy_without_rows_or_closed_origin_override(self):
        original_formula = self.rule.amount_python_compute
        self.rule.amount_python_compute = 'result = 1 / 0'
        preview = self.scope['hr.payslip'].new({'name': 'Private actual ORM payroll preview',
            'employee_id': self.contract.employee_id.id, 'company_id': self.company.id,
            'contract_id': self.contract.id, 'struct_id': self.structure.id,
            'date_from': fields.Date.today().replace(day=1), 'date_to': fields.Date.today(),
            'worked_days_line_ids': [Command.create({'name': 'Private real typed preview day',
                'contract_id': self.contract.id, 'work_entry_type_id': self.entry_type.id,
                'code': self.entry_type.code, 'number_of_days': 2, 'number_of_hours': 16})]})
        self.assertFalse(preview._origin)
        self.scope.flush_all()
        self.env.cr.execute('SELECT (SELECT count(*) FROM hr_payslip),(SELECT count(*) FROM hr_payslip_worked_days)')
        before = self.env.cr.fetchone()
        self.assertTrue(preview._step_check_original_configuration(operation='calculate'))
        # Odoo's AccessError assertion deliberately clears the entire cache,
        # which erases unsaved ORM values. This guard is strictly read-only;
        # use unittest's assertion without a savepoint/cache-reset wrapper.
        with patch.object(self.entry_type._fields['country_id'], 'groups', 'base.group_system'), TestCase.assertRaises(self, AccessError):
            preview.sudo()._step_check_original_configuration(operation='calculate')
        self.env.cr.execute('SELECT (SELECT count(*) FROM hr_payslip),(SELECT count(*) FROM hr_payslip_worked_days)')
        self.assertEqual(self.env.cr.fetchone(), before)
        foreign = self.env['res.company'].create({'name': 'Private preview foreign country', 'country_id': self.env.ref('base.fr').id})
        self.scope.user.with_env(self.env).write({'company_ids': [Command.link(foreign.id)]})
        original_country = self.entry_type.country_id
        self.entry_type.with_env(self.env).country_id = foreign.country_id
        with TestCase.assertRaisesRegex(self, UserError, 'country boundaries'):
            preview.with_context(allowed_company_ids=(self.company | foreign).ids)._step_check_original_configuration(operation='calculate')
        self.entry_type.with_env(self.env).country_id = original_country
        self.env.cr.execute('SELECT (SELECT count(*) FROM hr_payslip),(SELECT count(*) FROM hr_payslip_worked_days)')
        self.assertEqual(self.env.cr.fetchone(), before)
        saved = self._slip()
        self._day(saved)
        self.scope.flush_all()
        saved_before = self._stored(saved)
        draft_preview = self.scope['hr.payslip'].new({'state': 'draft',
            'employee_id': self.contract.employee_id.id, 'company_id': self.company.id,
            'contract_id': self.contract.id, 'struct_id': self.structure.id,
            'date_from': saved.date_from, 'date_to': saved.date_to,
            'worked_days_line_ids': [Command.create({'name': 'Private typed draft-origin preview day',
                'contract_id': self.contract.id, 'work_entry_type_id': self.entry_type.id,
                'code': self.entry_type.code, 'number_of_days': 2, 'number_of_hours': 16})]}, origin=saved)
        self.assertTrue(draft_preview.worked_days_line_ids)
        with patch.object(draft_preview._fields['worked_days_line_ids'], 'groups', 'base.group_system'), TestCase.assertRaises(self, AccessError):
            draft_preview.sudo()._step_check_original_configuration(operation='calculate')
        self.assertEqual(self._stored(saved), saved_before)
        # Admission never evaluated the intentionally invalid synthetic rule.
        # Only this fresh saved fixture now follows the actual closing workflow.
        self.rule.amount_python_compute = original_formula
        saved.compute_sheet()
        saved.with_context(without_compute_sheet=True).action_payslip_done()
        self.env.flush_all()
        stored = self._stored(saved)
        masquerade = self.scope['hr.payslip'].new({'state': 'draft', 'paid': False, 'step_history_locked': False,
            'employee_id': self.contract.employee_id.id, 'company_id': self.company.id,
            'contract_id': self.contract.id, 'struct_id': self.structure.id,
            'date_from': saved.date_from, 'date_to': saved.date_to}, origin=saved)
        with TestCase.assertRaisesRegex(self, UserError, 'Closed payroll'):
            masquerade._step_check_original_configuration(operation='calculate')
        self.assertEqual(self._stored(saved), stored)

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

    def test_global_type_does_not_read_foreign_neighbours_but_type_mutation_protects_all_its_pairs(self):
        foreign_company = self.env["res.company"].create({"name": "Private inaccessible unpaid relation company",
            "country_id": self.env.ref("base.fr").id})
        foreign = self.env["hr.payroll.structure"].create({"name": "Private inaccessible unpaid relation structure",
            "code": "PRIVATE_INACCESSIBLE_UNPAID", "type_id": self.kind.id, "company_id": foreign_company.id,
            "country_id": foreign_company.country_id.id, "parent_id": False, "active": False})
        self.entry_type.country_id = False
        self.entry_type.with_env(self.env).unpaid_structure_ids = [Command.set([self.structure.id, foreign.id])]
        # A real draft day in B is intentionally outside A's permissions. A's
        # relation edit must not enqueue and try to recompute B through a global
        # type dependency. Provision it with the fixture author's real company.
        author = self.env["hr.contract"].with_company(foreign_company).env
        foreign_kind = author["hr.payroll.structure.type"].create({
            "name": "Private inaccessible unpaid payroll type", "country_id": foreign_company.country_id.id})
        foreign.type_id = foreign_kind
        journal = author["account.journal"].create({"name": "Private inaccessible unpaid salary journal",
            "code": "UPB", "type": "general", "company_id": foreign_company.id})
        employee = author["hr.employee"].create({"name": "Private inaccessible unpaid employee", "company_id": foreign_company.id})
        values = {"name": "Private inaccessible unpaid contract", "employee_id": employee.id,
            "company_id": foreign_company.id, "state": "open", "date_start": fields.Date.today().replace(day=1),
            "wage": 750000, "schedule_pay": "monthly", "struct_id": foreign.id,
            "structure_type_id": foreign_kind.id, "journal_id": journal.id}
        field = author["hr.contract"]._fields.get("contract_type_id")
        if field:
            values["contract_type_id"] = author[field.comodel_name].search([], limit=1).id
        contract = author["hr.contract"].create(values)
        foreign_slip = author["hr.payslip"].create({"name": "Private inaccessible unpaid salary slip",
            "number": "PRIVATE/UNPAID/B", "company_id": foreign_company.id, "employee_id": employee.id,
            "contract_id": contract.id, "struct_id": foreign.id,
            "date_from": fields.Date.today().replace(day=1), "date_to": fields.Date.today()})
        foreign_day = author["hr.payslip.worked_days"].create({"name": "Private inaccessible real typed day",
            "payslip_id": foreign_slip.id, "contract_id": contract.id, "work_entry_type_id": self.entry_type.id,
            "number_of_days": 3, "number_of_hours": 24})
        self.assertFalse(foreign_day.is_paid)
        author.flush_all()
        self.env.cr.execute("SELECT to_jsonb(t) FROM hr_payslip_worked_days t WHERE id=%s", (foreign_day.id,))
        foreign_before = self.env.cr.fetchone()
        with self.assertRaises(AccessError):
            foreign.with_env(self.scope).read(["id"])
        slip = self._slip()
        day = self._day(slip)
        self.assertEqual(day.amount, 0)
        self.assertFalse(day.is_paid)
        copied = self.structure.copy({"name": "Private independent unpaid policy copy", "code": "PRIVATE_INDEPENDENT_UNPAID"})
        self.assertEqual(copied.unpaid_work_entry_type_ids, self.entry_type)
        self.env.cr.execute("""SELECT hr_payroll_structure_id,hr_work_entry_type_id
            FROM hr_payroll_structure_hr_work_entry_type_rel WHERE hr_work_entry_type_id=%s ORDER BY 1""", (self.entry_type.id,))
        before = self.env.cr.fetchall()
        for operation in (
            lambda: self.entry_type.write({"unpaid_structure_ids": [Command.set(self.structure.ids)]}),
            lambda: self.entry_type.copy({"name": "Private forbidden global type copy", "code": "PRIVATE_FORBIDDEN_UNPAID"}),
            lambda: self.entry_type.unlink(),
        ):
            with self.assertRaises(AccessError):
                operation()
            self.env.cr.execute("""SELECT hr_payroll_structure_id,hr_work_entry_type_id
                FROM hr_payroll_structure_hr_work_entry_type_rel WHERE hr_work_entry_type_id=%s ORDER BY 1""", (self.entry_type.id,))
            self.assertEqual(self.env.cr.fetchall(), before)
        # This edit owns A's membership only, and must not authorize or inspect
        # the unrelated archived/foreign B configuration behind the global type.
        self.structure.unpaid_work_entry_type_ids = [Command.clear()]
        self.scope.flush_all()
        self.assertTrue(day.is_paid)
        expected = self.company.currency_id.round(self.contract.wage / 30.0 * day.number_of_days)
        self.assertEqual(day.amount, expected)
        slip.compute_sheet()
        self.assertEqual(slip.line_ids.total, expected)
        self.env.cr.execute("""SELECT hr_payroll_structure_id FROM hr_payroll_structure_hr_work_entry_type_rel
            WHERE hr_work_entry_type_id=%s ORDER BY 1""", (self.entry_type.id,))
        self.assertEqual([row[0] for row in self.env.cr.fetchall()], sorted([foreign.id, copied.id]))
        self.env.cr.execute("SELECT to_jsonb(t) FROM hr_payslip_worked_days t WHERE id=%s", (foreign_day.id,))
        self.assertEqual(self.env.cr.fetchone(), foreign_before)

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
        # Fresh draft totals are genuine pending computed defaults. Store them
        # before taking the preservation baseline, not during its comparison.
        scope.flush_all()
        before = self._stored(slip)
        with self.assertRaisesRegex(UserError, "country boundaries"):
            slip.compute_sheet()
        self.assertEqual(self._stored(slip), before)
        # Even a real OCA default owner is not native-country provenance.
        # Unknown setup country is stored pending, rather than reassigned or
        # treated as a certified policy. Use still requires the real company.
        pending = scope["hr.payroll.structure"].create({"name": "Private unresolved default-owner unpaid structure",
            "code": "PRIVATE_DEFAULT_OWNER_UNPAID", "company_id": self.company.id, "country_id": False,
            "type_id": self.kind.id, "unpaid_work_entry_type_ids": [Command.link(foreign.id)]})
        pending_slip = self._slip(pending).with_env(scope)
        scope.flush_all()
        pending_before = self._stored(pending_slip)
        with self.assertRaisesRegex(UserError, "country boundaries"):
            pending_slip.compute_sheet()
        self.assertEqual(self._stored(pending_slip), pending_before)
        self.assertEqual(pending.company_id.id, self.company.id)
        self.assertFalse(pending.country_id)
        # An isolated synthetic SQL pair represents pre-existing bad policy;
        # no original master or amount is changed to manufacture this case.
        self.env.cr.execute("""INSERT INTO hr_payroll_structure_hr_work_entry_type_rel
            (hr_payroll_structure_id,hr_work_entry_type_id) VALUES (%s,%s)""", (structure.id, foreign.id))
        structure.invalidate_recordset(["unpaid_work_entry_type_ids"])
        foreign.invalidate_recordset(["unpaid_structure_ids"])
        structure.unpaid_work_entry_type_ids = [Command.unlink(foreign.id)]
        self.assertFalse(structure.unpaid_work_entry_type_ids)
        self.assertEqual(global_structure.unpaid_work_entry_type_ids, foreign)
