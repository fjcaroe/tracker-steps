"""Saved batch form and real OCA calculation; no generation wizard or mocks."""
import json
from unittest import TestCase
from unittest.mock import patch

from lxml import etree

from odoo import api, Command
from odoo.exceptions import AccessError, UserError
from odoo.tests import TransactionCase, tagged
from odoo.tools import json_default


@tagged("post_install", "-at_install")
class ExistingDraftBatchCase(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env["res.company"].create({"name": "Private saved-batch company",
            "country_id": cls.env.ref("base.cl").id, "currency_id": cls.env.ref("base.CLP").id})
        actor = cls.env["res.users"].with_context(no_reset_password=True).create({
            "name": "Private saved-batch manager", "login": "private-existing-batch-manager", "tz": "UTC",
            "company_id": cls.company.id, "company_ids": [Command.set(cls.company.ids)],
            "groups_id": [Command.set([cls.env.ref(xmlid).id for xmlid in (
                "base.group_user", "payroll.group_payroll_manager", "hr.group_hr_manager", "account.group_account_manager")])]})
        cls.scope = api.Environment(cls.env.cr, actor.id,
            dict(cls.env.context, allowed_company_ids=cls.company.ids, lang="en_US"), su=False)
        cls.kind = cls.scope["hr.payroll.structure.type"].create({"name": "Private saved-batch type"})
        cls.entry_type = cls.scope["hr.work.entry.type"].create({"name": "Private saved-batch attendance", "code": "PRIVATE_SAVED_BATCH_TIME"})
        cls.calendar = cls.scope["resource.calendar"].create({"name": "Private saved-batch calendar", "tz": "UTC",
            "company_id": cls.company.id, "attendance_ids": [Command.clear()] + [Command.create({
                "name": "Private eight-hour shift", "dayofweek": str(day), "hour_from": 8, "hour_to": 16}) for day in range(5)]})
        cls.structure = cls.scope["hr.payroll.structure"].create({"name": "Private saved-batch structure", "code": "PRIVATE_SAVED_BATCH",
            "company_id": cls.company.id, "parent_id": False, "type_id": cls.kind.id, "use_work_entries": True})
        cls.journal = cls.scope["account.journal"].create({"name": "Private saved-batch salary journal", "code": "SBD",
            "type": "general", "company_id": cls.company.id})
        category = cls.scope["hr.salary.rule.category"].create({"name": "Private saved-batch category", "code": "PRIVATE_SAVED_BATCH_CAT"})
        cls.rule = cls.scope["hr.salary.rule"].create({"name": "Private saved-batch calculation", "code": "PRIVATE_SAVED_BATCH_RESULT",
            "company_id": cls.company.id, "struct_id": cls.structure.id, "category_id": category.id,
            "condition_select": "none", "amount_select": "code",
            "amount_python_compute": "result = inputs['PRIVATE_SAVED_BATCH_INPUT'].amount + payslip.paid_amount"})
        cls.input_type = cls.scope["hr.payslip.input.type"].create({"name": "Private saved-batch input", "code": "PRIVATE_SAVED_BATCH_INPUT",
            "country_id": cls.company.country_id.id, "struct_ids": [Command.set(cls.structure.ids)]})

    def _batch(self, count=2):
        run = self.scope["hr.payslip.run"].create({"name": "Private existing drafts", "company_id": self.company.id,
            "date_start": "2026-10-01", "date_end": "2026-10-31", "struct_id": self.structure.id})
        slips = self.scope["hr.payslip"]
        for index in range(count):
            author = self.env["hr.contract"].with_company(self.company).env
            employee = author["hr.employee"].create({"name": "Private saved-batch employee %s" % index, "company_id": self.company.id})
            values = {"name": "Private saved-batch contract %s" % index, "employee_id": employee.id, "company_id": self.company.id,
                "date_start": "2026-10-01", "state": "open", "wage": 900000, "schedule_pay": "monthly", "wage_type": "monthly",
                "resource_calendar_id": self.calendar.id, "struct_id": self.structure.id,
                "structure_type_id": self.kind.id, "journal_id": self.journal.id}
            field = self.scope["hr.contract"]._fields.get("contract_type_id")
            if field:
                values["contract_type_id"] = author[field.comodel_name].search([], limit=1).id
            contract = author["hr.contract"].create(values)
            contract.resource_calendar_id = self.calendar
            employee.resource_calendar_id = self.calendar
            employee.resource_id.tz = "UTC"
            contract = contract.with_env(self.scope)
            self.scope["hr.work.entry"].create({"name": "Private actual saved-batch work", "contract_id": contract.id,
                "employee_id": employee.id, "company_id": self.company.id, "work_entry_type_id": self.entry_type.id,
                "date_start": "2026-10-05 08:00:00", "date_stop": "2026-10-05 16:00:00"})
            slip = self.scope["hr.payslip"].create({"name": "Private existing draft %s" % index,
                "number": "PRIVATE/EXISTING/%s/%s" % (run.id, index), "payslip_run_id": run.id,
                "employee_id": employee.id, "company_id": self.company.id, "contract_id": contract.id,
                "struct_id": self.structure.id, "date_from": run.date_start, "date_to": run.date_end})
            self.scope["hr.payslip.input"].create({"payslip_id": slip.id, "contract_id": contract.id,
                "input_type_id": self.input_type.id, "amount": index * 5})
            self.scope["hr.payslip.worked_days"].create([dict(row, payslip_id=slip.id) for row in slip._get_worked_day_lines()])
            slips |= slip
        return run, slips

    def _snapshot(self, run):
        self.env.flush_all()
        self.env.cr.execute("SELECT id FROM hr_payslip WHERE payslip_run_id=%s ORDER BY id", (run.id,))
        ids = [row[0] for row in self.env.cr.fetchall()]
        result = []
        for table, where, args in (("hr_payslip_run", "id=%s", (run.id,)),
                ("hr_payslip", "id=ANY(%s)", (ids,)), ("hr_payslip_input", "payslip_id=ANY(%s)", (ids,)),
                ("hr_payslip_worked_days", "payslip_id=ANY(%s)", (ids,)), ("hr_payslip_line", "slip_id=ANY(%s)", (ids,)),
                ("hr_work_entry", "contract_id IN (SELECT contract_id FROM hr_payslip WHERE id=ANY(%s))", (ids,))):
            self.env.cr.execute("SELECT to_jsonb(t) FROM " + table + " t WHERE " + where + " ORDER BY id", args)
            result.append(self.env.cr.fetchall())
        return result

    def _hide(self, model, ids):
        return self.env["ir.rule"].create({"name": "Private saved-batch visibility", "model_id": self.env["ir.model"]._get_id(model),
            "domain_force": repr([("id", "not in", ids)])})

    def test_real_two_saved_drafts_use_saved_zero_amounts_and_actual_form(self):
        run, slips = self._batch()
        inputs, days, numbers = slips.input_line_ids.ids, slips.worked_days_line_ids.ids, slips.mapped("number")
        before = self._snapshot(run)
        self.assertFalse(run.env.su)
        result = run.action_step_compute_existing_drafts()
        self.assertEqual(result["res_id"], run.id)
        self.assertEqual(result["res_model"], "hr.payslip.run")
        json.dumps(result, default=json_default)
        self.assertEqual(slips.mapped("state"), ["verify", "verify"])
        self.assertEqual(slips.line_ids.mapped("total"), [30000.0, 30005.0])
        self.assertEqual(slips.input_line_ids.ids, inputs)
        self.assertEqual(slips.worked_days_line_ids.ids, days)
        self.assertEqual(slips.mapped("number"), numbers)
        self.assertEqual(self._snapshot(run)[2], before[2])
        self.assertEqual(self._snapshot(run)[5], before[5])
        arch = etree.fromstring(run.get_view(view_id=self.scope.ref("payroll.hr_payslip_run_view_form").id, view_type="form")["arch"])
        button = arch.xpath("//button[@name='action_step_compute_existing_drafts']")[0]
        self.assertIn("ceros", button.get("confirm"))
        slip_arch = etree.fromstring(slips.get_view(view_id=self.scope.ref("payroll.hr_payslip_view_form").id, view_type="form")["arch"])
        self.assertTrue(slip_arch.xpath("//field[@name='payslip_run_id'][@readonly=\"state != 'draft'\"]"))
        officer = self.env["res.users"].with_context(no_reset_password=True).create({"name": "Private saved-batch officer",
            "login": "private-saved-batch-officer", "company_id": self.company.id, "company_ids": [Command.set(self.company.ids)],
            "groups_id": [Command.set([self.env.ref(name).id for name in ("base.group_user", "payroll.group_payroll_user")])]})
        other = run.with_user(officer)
        # OCA grants this actual batch model only to managers. A missing read
        # right is the real UI boundary, not merely a hidden action button.
        with TestCase.assertRaises(self, AccessError):
            other.get_view(view_type="form")
        with TestCase.assertRaises(self, AccessError):
            other.sudo().action_step_compute_existing_drafts()

    def test_complete_hidden_rows_and_field_acl_reject_warm_sudo_without_changes(self):
        run, slips = self._batch()
        before = self._snapshot(run)
        for model, ids in (("hr.payslip", slips[-1].ids), ("hr.payslip.input", slips[-1].input_line_ids.ids),
                ("hr.payslip.worked_days", slips[-1].worked_days_line_ids.ids), ("hr.work.entry.type", self.entry_type.ids)):
            run.sudo().read(["slip_ids"])
            rule = self._hide(model, ids)
            with TestCase.assertRaises(self, AccessError):
                run.sudo().action_step_compute_existing_drafts()
            self.assertEqual(self._snapshot(run), before)
            rule.unlink()
        with patch.object(self.scope["hr.payslip.input"]._fields["amount"], "groups", "base.group_system"):
            with TestCase.assertRaises(self, AccessError):
                run.sudo().action_step_compute_existing_drafts()
        self.assertEqual(self._snapshot(run), before)

    def test_verify_period_company_legacy_and_review_reject_before_first_calculation(self):
        run, slips = self._batch()
        slips[-1].state = "verify"
        before = self._snapshot(run)
        with TestCase.assertRaisesRegex(self, UserError, "Only existing draft"):
            run.action_step_compute_existing_drafts()
        self.assertEqual(self._snapshot(run), before)
        slips[-1].state = "draft"
        slips[-1].date_to = "2026-10-30"
        before = self._snapshot(run)
        with TestCase.assertRaisesRegex(self, UserError, "batch period"):
            run.action_step_compute_existing_drafts()
        self.assertEqual(self._snapshot(run), before)
        slips[-1].date_to = "2026-10-31"
        other = self.env["res.company"].create({"name": "Private alternate saved-batch context",
            "country_id": self.company.country_id.id, "currency_id": self.company.currency_id.id})
        self.scope.user.with_env(self.env).write({"company_ids": [Command.link(other.id)]})
        before = self._snapshot(run)
        with TestCase.assertRaisesRegex(self, UserError, "original batch company"):
            run.with_context(allowed_company_ids=[other.id, self.company.id]).action_step_compute_existing_drafts()
        self.assertEqual(self._snapshot(run), before)
        self.structure.step_legacy_payroll = True
        before = self._snapshot(run)
        with TestCase.assertRaisesRegex(self, UserError, "Historical payroll"):
            run.action_step_compute_existing_drafts()
        self.assertEqual(self._snapshot(run), before)
        self.structure.step_legacy_payroll = False
        slips[-1].contract_id.step_payroll_migration_review = True
        before = self._snapshot(run)
        with TestCase.assertRaisesRegex(self, UserError, "contract payroll review"):
            run.action_step_compute_existing_drafts()
        self.assertEqual(self._snapshot(run), before)
        slips[0].compute_sheet()
        slips[0].with_context(without_compute_sheet=True).action_payslip_done()
        self.assertEqual(slips[0].state, "done")
        before = self._snapshot(run)
        with TestCase.assertRaisesRegex(self, UserError, "Only existing draft"):
            run.action_step_compute_existing_drafts()
        self.assertEqual(self._snapshot(run), before)

    def test_real_conflicts_and_saved_day_mismatch_block_without_generating_rows(self):
        run, slips = self._batch()
        last = slips[-1]
        conflict = self.scope["hr.work.entry"].create({"name": "Private conflicting saved-batch work",
            "contract_id": last.contract_id.id, "employee_id": last.employee_id.id, "company_id": self.company.id,
            "work_entry_type_id": self.entry_type.id, "date_start": "2026-10-05 10:00:00", "date_stop": "2026-10-05 12:00:00"})
        before = self._snapshot(run)
        with TestCase.assertRaisesRegex(self, UserError, "conflicts|overlapping"):
            run.action_step_compute_existing_drafts()
        self.assertEqual(self._snapshot(run), before)
        # The ordinary tested actor cannot delete work entries. Only fixture
        # cleanup uses its author; the batch action continues as that actor.
        conflict.with_env(self.env).unlink()
        # Conflict state is left untouched by admission. Remove only fixture
        # conflict classification before exercising the separate day mismatch.
        entries = self.scope["hr.work.entry"].search([("contract_id", "in", slips.contract_id.ids)])
        entries.write({"state": "draft"})
        last.worked_days_line_ids.number_of_hours += 1
        before = self._snapshot(run)
        with TestCase.assertRaisesRegex(self, UserError, "Saved worked days"):
            run.action_step_compute_existing_drafts()
        self.assertEqual(self._snapshot(run), before)
        # A real night entry is clipped to the local October boundary, while
        # two conflicts wholly in September remain outside this calculation.
        self.calendar.tz = "America/Santiago"
        night_run, night_slips = self._batch(count=1)
        night = night_slips[0]
        for start, stop in (("2026-09-30 14:00:00", "2026-09-30 16:00:00"),
                ("2026-09-30 14:00:00", "2026-09-30 15:00:00"),
                ("2026-10-01 01:00:00", "2026-10-01 04:00:00")):
            self.scope["hr.work.entry"].create({"name": "Private local boundary work", "contract_id": night.contract_id.id,
                "employee_id": night.employee_id.id, "company_id": self.company.id, "work_entry_type_id": self.entry_type.id,
                "date_start": start, "date_stop": stop})
        actual = night._get_worked_day_lines()
        self.assertEqual(len(actual), 1)
        self.assertEqual(actual[0]["number_of_hours"], 9.0)
        night.worked_days_line_ids.write(actual[0])
        before = self._snapshot(night_run)
        night_run.action_step_compute_existing_drafts()
        self.assertEqual(night.worked_days_line_ids.number_of_hours, 9.0)
        self.assertEqual(self._snapshot(night_run)[5], before[5])

    def test_real_second_rule_error_rolls_back_entire_batch_without_outer_savepoint(self):
        run, slips = self._batch()
        self.rule.amount_python_compute = "result = 100 if payslip.employee_id.id != %s else 1 / 0" % slips[-1].employee_id.id
        before = self._snapshot(run)
        with TestCase.assertRaises(self, UserError):
            run.action_step_compute_existing_drafts()
        self.assertEqual(self._snapshot(run), before)
        self.assertEqual(slips.mapped("state"), ["draft", "draft"])
        self.assertFalse(slips.line_ids)

    def test_sql_null_and_missing_original_input_coverage_block_all_saved_drafts(self):
        run, slips = self._batch()
        row = slips[-1].input_line_ids
        row.flush_recordset(["amount"])
        self.env.cr.execute("UPDATE hr_payslip_input SET amount=NULL WHERE id=%s", (row.id,))
        row.invalidate_recordset(["amount"])
        self.assertEqual(row.amount, 0.0)
        before = self._snapshot(run)
        with TestCase.assertRaisesRegex(self, UserError, "SQL NULL"):
            run.action_step_compute_existing_drafts()
        self.assertEqual(self._snapshot(run), before)
        row.amount = 0.0
        row.unlink()
        before = self._snapshot(run)
        with TestCase.assertRaisesRegex(self, UserError, "every configured original type"):
            run.action_step_compute_existing_drafts()
        self.assertEqual(self._snapshot(run), before)
