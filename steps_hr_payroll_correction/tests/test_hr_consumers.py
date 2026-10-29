"""Functional consumer flows on the installed, actual payroll provider."""
from datetime import date, datetime, time
import hashlib
import json
import logging
from unittest.mock import patch

import pytz

from odoo import api, Command
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests import TransactionCase, tagged


_logger = logging.getLogger(__name__)


@tagged("post_install", "-at_install", "hr_consumers")
class HrConsumersCase(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # Native reference aliases retain role IDs. An alias is not evidence
        # that the OCA engine itself was installed or the source was converted.
        cls.oca = bool(cls.env["ir.module.module"].search_count([
            ("name", "=", "payroll"), ("state", "=", "installed")]))
        payroll_group = "payroll.group_payroll_manager" if cls.oca else "hr_payroll.group_hr_payroll_manager"
        company = cls.env["res.company"].create({"name": "Private HR consumer fixture",
            "country_id": cls.env.ref("base.cl").id, "currency_id": cls.env.ref("base.CLP").id})
        groups = [cls.env.ref(name).id for name in ("base.group_user", payroll_group,
            "hr.group_hr_manager", "account.group_account_manager",
            "steps_hr_payroll_correction.group_payroll_correction")]
        for name in ("group_contract_management_view", "group_severance_calc"):
            group = cls.env.ref("step_hr_contract_lifecycle." + name, raise_if_not_found=False)
            if group:
                groups.append(group.id)
        user = cls.env["res.users"].with_context(no_reset_password=True).create({
            "name": "Private HR consumer manager", "login": "private-hr-consumer-manager", "tz": "UTC",
            "email": "private-hr-consumer@example.invalid",
            "company_id": company.id, "company_ids": [Command.set(company.ids)], "groups_id": [Command.set(groups)]})
        cls.scope = api.Environment(cls.env.cr, user.id, dict(cls.env.context, allowed_company_ids=company.ids), su=False)
        cls.company, cls.actor = company, user
        scope = cls.scope
        cls.kind = scope["hr.payroll.structure.type"].create({"name": "Private consumer structure type"})
        values = {"name": "Private consumer structure", "code": "PRIVATE_CONSUMER", "type_id": cls.kind.id}
        for name, value in (("company_id", company.id), ("parent_id", False), ("use_worked_day_lines", False)):
            if name in scope["hr.payroll.structure"]._fields:
                values[name] = value
        cls.structure = scope["hr.payroll.structure"].create(values)
        journal = scope["account.journal"].create({"name": "Private consumer payroll journal", "code": "HRC",
            "type": "general", "company_id": company.id})
        if "journal_id" in cls.structure._fields:
            cls.structure.journal_id = journal
        debit = scope["account.account"].create({"name": "Private consumer payroll cost", "code": "940004",
            "account_type": "expense", "company_ids": [Command.set(company.ids)]})
        credit = scope["account.account"].create({"name": "Private consumer payroll debt", "code": "940005",
            "account_type": "liability_current", "company_ids": [Command.set(company.ids)]})
        cls.rule = scope["hr.salary.rule"].create({"name": "Private consumer actual rule", "code": "PRIVATE_HR_AMOUNT",
            "sequence": 1, "struct_id": cls.structure.id,
            "category_id": scope["hr.salary.rule.category"].create({"name": "Private consumer category", "code": "PRIVATE_HR"}).id,
            "condition_select": "none", "amount_select": "code", "quantity": "1.0",
            "amount_python_compute": "result = contract.wage", "account_debit": debit.id, "account_credit": credit.id})
        cls.calendar = scope["resource.calendar"].create({"name": "Private consumer calendar", "company_id": company.id,
            "tz": "UTC", "attendance_ids": [Command.clear()] + [Command.create({"name": "Private shift",
                "dayofweek": str(day), "hour_from": 8, "hour_to": 16, "day_period": "morning"}) for day in range(5)]})
        cls.employee = scope["hr.employee"].create({"name": "Private consumer employee", "company_id": company.id,
            "resource_calendar_id": cls.calendar.id})
        values = {"name": "Private consumer contract", "employee_id": cls.employee.id, "company_id": company.id,
            "state": "open", "date_start": date(2026, 10, 1), "wage": 800000, "structure_type_id": cls.kind.id,
            "resource_calendar_id": cls.calendar.id}
        if "struct_id" in scope["hr.contract"]._fields:
            values["struct_id"] = cls.structure.id
        if "contract_type_id" in scope["hr.contract"]._fields:
            model = scope["hr.contract"]._fields["contract_type_id"].comodel_name
            values["contract_type_id"] = scope[model].search([], limit=1).id
        if "journal_id" in scope["hr.contract"]._fields:
            values["journal_id"] = journal.id
        cls.contract_values = values
        cls.contract = scope["hr.contract"].create(values)
        cls.work_type = scope["hr.work.entry.type"].create({"name": "Private consumer worked time", "code": "PRIVATE_HR_WORK"})
        if "use_work_entries" in cls.structure._fields:
            cls.structure.use_work_entries = True
            cls.structure.out_of_contract_work_entry_type_id = scope["hr.work.entry.type"].create({
                "name": "Private consumer out of contract", "code": "PRIVATE_HR_OUT"})
        cls.env["ir.sequence"].create({"name": "Private consumer slips", "code": "salary.slip",
            "company_id": company.id, "prefix": "PRIVATE-HR/"})

    def slip(self):
        return self.scope["hr.payslip"].create({"name": "Private consumer payslip", "employee_id": self.employee.id,
            "company_id": self.company.id, "contract_id": self.contract.id, "struct_id": self.structure.id,
            "date_from": date(2026, 10, 1), "date_to": date(2026, 10, 31)})

    def entry(self, day=5):
        return self.scope["hr.work.entry"].create({"name": "Private consumer work", "employee_id": self.employee.id,
            "contract_id": self.contract.id, "company_id": self.company.id, "work_entry_type_id": self.work_type.id,
            "date_start": datetime(2026, 10, day, 8), "date_stop": datetime(2026, 10, day, 16)})

    def wizard(self):
        return self.scope["hr.termination.correction.wizard"].create({"employee_id": self.employee.id,
            "actual_termination_date": date(2026, 10, 7), "confirm": True})

    def stored(self, slip):
        self.env.flush_all()
        self.env.cr.execute("SELECT to_jsonb(s) FROM hr_payslip s WHERE id=%s", (slip.id,))
        result = self.env.cr.fetchall()
        self.env.cr.execute("SELECT to_jsonb(l) FROM hr_payslip_line l WHERE slip_id=%s ORDER BY id", (slip.id,))
        return result, self.env.cr.fetchall()

    def test_closed_history_blocks_contract_work_entries_and_amounts(self):
        self.entry()
        extra = self.entry(9)
        slip = self.slip()
        slip.compute_sheet()
        slip.state = "done"
        original = self.stored(slip)
        wizard = self.wizard()
        self.assertEqual(wizard.blocked_payslip_ids, slip)
        self.assertFalse(wizard.payslip_ids)
        with self.assertRaises(UserError):
            wizard.action_apply()
        self.assertFalse(self.contract.date_end)
        self.assertTrue(extra.exists())
        self.assertEqual(self.stored(slip), original)

    def _assert_flag_protected(self, field):
        if field not in self.scope["hr.payslip"]._fields:
            self.skipTest("The installed real engine has no " + field + " flag")
        self.entry()
        extra = self.entry(9)
        slip = self.slip()
        slip.compute_sheet()
        if field == "step_history_locked":
            slip.action_payslip_done()
            self.assertTrue(slip.step_history_locked)
            # An isolated import fixture represents an original lock retained
            # on an open legacy state. No RPC can set this flag. The real
            # engine created the snapshot/lock above; only this fixture's
            # state is changed and the TransactionCase rolls it all back.
            self.assertTrue(self.env.cr.dbname.startswith(("COMMUNITY_PAYROLL_API_", "MANAGEMENT_QA_CERRO_PAYROLL_API_")))
            self.env.flush_all()
            self.env.cr.execute("UPDATE hr_payslip SET state='draft' WHERE id=%s", (slip.id,))
            slip.invalidate_recordset(["state"])
        else:
            slip.write({field: True})
        original = self.stored(slip)
        with self.assertRaises(UserError):
            self.wizard().action_apply()
        self.assertFalse(self.contract.date_end)
        self.assertTrue(extra.exists())
        self.assertEqual(self.stored(slip), original)

    def test_open_paid_flag_is_not_recomputed(self):
        self._assert_flag_protected("paid")

    def test_open_history_lock_is_not_recomputed(self):
        self._assert_flag_protected("step_history_locked")

    def test_apply_rechecks_a_preview_validated_in_another_session(self):
        self.entry()
        slip = self.slip()
        slip.compute_sheet()
        wizard = self.wizard()
        self.assertEqual(wizard.payslip_ids, slip)
        slip.state = "done"
        original = self.stored(slip)
        with self.assertRaises(UserError):
            wizard.action_apply()
        self.assertEqual(self.stored(slip), original)
        self.assertFalse(self.contract.date_end)

    def test_rpc_requires_correction_group(self):
        user = self.env["res.users"].with_context(no_reset_password=True).create({"name": "Private HR unauthorized",
            "login": "private-hr-unauthorized", "company_id": self.company.id, "company_ids": [Command.set(self.company.ids)],
            "groups_id": [Command.set(self.env.ref("base.group_user").ids)]})
        with self.assertRaises(AccessError):
            self.wizard().with_user(user).action_apply()
        self.assertFalse(self.contract.date_end)

    def test_correction_cannot_cross_allowed_companies(self):
        foreign = self.env["res.company"].create({"name": "Private foreign HR company"})
        employee = self.env["hr.employee"].create({"name": "Private foreign HR employee", "company_id": foreign.id})
        wizard = self.scope["hr.termination.correction.wizard"].sudo().create({"employee_id": employee.id,
            "actual_termination_date": date(2026, 10, 7), "confirm": True})
        with self.assertRaises(AccessError):
            wizard.with_env(self.scope).action_apply()

    def test_open_correction_uses_actual_engine_and_preserves_input_identity(self):
        if "default_work_entry_type_id" in self.kind._fields:
            # The native provider consolidates ordinary attendance under its
            # structure type's configured master. Keep that real relation
            # coherent with the two original fixture work entries.
            self.kind.default_work_entry_type_id = self.work_type
        if not self.oca:
            # The shared fixture disables native day lines for unrelated API
            # cases. This operational flow must ask the real provider to use
            # its actual work entries instead of omitting those lines.
            self.structure.use_worked_day_lines = True
        kept, removed = self.entry(), self.entry(9)
        (kept | removed).action_validate()
        self.assertEqual(set((kept | removed).mapped("state")), {"validated"})
        expected_hours = kept.duration
        self.assertGreater(expected_hours, 0)
        slip = self.slip()
        kind = self.scope["hr.payslip.input.type"].create({"name": "Private consumer original input", "code": "PRIVATE_HR_INPUT",
            "struct_ids": [Command.set(self.structure.ids)]})
        self.scope["hr.payslip.input"].create({"name": "Private consumer original input", "payslip_id": slip.id,
            "contract_id": self.contract.id, "input_type_id": kind.id, "amount": 321})
        actual_before = self.contract.get_work_hours(slip.date_from, slip.date_to)
        self.assertAlmostEqual(actual_before.get(self.work_type.id, 0), sum((kept | removed).mapped("duration")))
        if not self.oca:
            if "edited" in slip._fields:
                slip.edited = False
            # The native UI/onchange explicitly refreshes day lines. Payroll
            # compute_sheet alone consumes the existing rows; reproduce that
            # real provider step, as action_apply itself does after correction.
            slip._compute_worked_days_line_ids()
            rows = slip._get_worked_day_lines()
            values = slip._get_worked_day_lines_values()
            origins = {name: [{"class": cls.__name__, "module": cls.__module__}
                              for cls in type(slip).__mro__ if name in cls.__dict__]
                       for name in ("_get_worked_day_lines", "_get_worked_day_lines_values", "_compute_worked_days_line_ids")}
            _logger.info("HR_CONSUMER_NATIVE_REFRESH %s", {
                "synthetic_slip_id": slip.id, "synthetic_structure_id": self.structure.id,
                "actual_slip_structure_id": slip.struct_id.id,
                "structure_default_work_type_id": self.kind.default_work_entry_type_id.id,
                "actual_employee_id": slip.employee_id.id, "synthetic_employee_id": self.employee.id,
                "actual_contract_id": slip.contract_id.id, "synthetic_contract_id": self.contract.id,
                "actual_calendar_id": slip.contract_id.resource_calendar_id.id, "synthetic_calendar_id": self.calendar.id,
                "actual_structure_type_id": slip.contract_id.structure_type_id.id,
                "date_from": str(slip.date_from), "date_to": str(slip.date_to),
                "contract_date_start": str(slip.contract_id.date_start), "contract_date_end": str(slip.contract_id.date_end),
                "work_entry_source": slip.contract_id.work_entry_source if "work_entry_source" in slip.contract_id._fields else None,
                "structure_uses_worked_days": self.structure.use_worked_day_lines,
                "slip_uses_worked_days": slip.use_worked_day_lines,
                "edited": slip.edited if "edited" in slip._fields else None,
                "state": slip.state, "validated_synthetic_entries": len(kept | removed),
                "work_type_id": self.work_type.id, "actual_hours": actual_before[self.work_type.id],
                "stored_day_rows": len(slip.worked_days_line_ids), "provider_day_rows": len(rows),
                "provider_rows": [{key: row.get(key) for key in ("work_entry_type_id", "number_of_hours", "number_of_days")} for row in rows],
                "provider_value_rows": [{key: row.get(key) for key in ("work_entry_type_id", "number_of_hours", "number_of_days")} for row in values],
                "method_origins": origins,
                "provider_day_rows_sha256": hashlib.sha256(json.dumps(rows, sort_keys=True, default=str).encode()).hexdigest(),
            })
        slip.compute_sheet()
        before = slip.worked_days_line_ids.filtered(lambda line: line.work_entry_type_id == self.work_type)
        self.assertAlmostEqual(sum(before.mapped("number_of_hours")), actual_before[self.work_type.id])
        inputs = slip.input_line_ids.read(["id", "code", "amount"])
        action = self.wizard().action_apply()
        self.assertEqual(self.contract.date_end, date(2026, 10, 7))
        self.assertTrue(kept.exists())
        self.assertFalse(removed.exists())
        self.assertIn(slip.id, action["domain"][0][2])
        self.assertIn(slip.state, ("draft", "verify"))
        self.assertEqual(slip.input_line_ids.read(["id", "code", "amount"]), inputs)
        self.assertTrue(slip.line_ids)
        worked = slip.worked_days_line_ids.filtered(lambda line: line.work_entry_type_id == self.work_type)
        actual_after = self.contract.get_work_hours(slip.date_from, slip.date_to)
        self.assertAlmostEqual(actual_after.get(self.work_type.id, 0), expected_hours)
        self.assertAlmostEqual(sum(worked.mapped("number_of_hours")), expected_hours)

    def test_engine_failure_rolls_back_contract_and_work_entry_changes(self):
        self.entry()
        extra = self.entry(9)
        slip = self.slip()
        slip.compute_sheet()
        original = self.stored(slip)
        with patch.object(type(slip), "compute_sheet", side_effect=UserError("Private technical failure")):
            with self.assertRaises(UserError):
                self.wizard().action_apply()
        self.assertFalse(self.contract.date_end)
        self.assertTrue(extra.exists())
        self.assertEqual(self.stored(slip), original)

    def test_calendar_termination_cutoff_uses_local_day(self):
        self.calendar.tz = "America/Santiago"
        wizard = self.wizard()
        zone = pytz.timezone("America/Santiago")
        expected = zone.localize(datetime.combine(date(2026, 10, 7), time.max)).astimezone(pytz.UTC).replace(tzinfo=None)
        self.assertEqual(wizard._cutoff_datetime(), expected)

    def test_crossing_work_entry_requires_real_hour_review(self):
        entry = self.entry()
        entry.write({"date_start": datetime(2026, 10, 7, 22), "date_stop": datetime(2026, 10, 8, 6)})
        before = entry.read(["date_start", "date_stop", "state"])
        with self.assertRaises(UserError):
            self.wizard().action_apply()
        self.assertFalse(self.contract.date_end)
        self.assertEqual(entry.read(["date_start", "date_stop", "state"]), before)

    def test_existing_relation_tables_and_acl_ownership_remain(self):
        fields = self.scope["hr.termination.correction.wizard"]._fields
        for name in ("payslip_ids", "blocked_payslip_ids"):
            self.assertFalse(fields[name].store)
            self.assertIsNone(fields[name].relation)
            self.assertEqual(fields[name].comodel_name, "hr.payslip")
        # The original declarations name relations, but nonstored computed
        # fields never created those tables. Preserve that actual contract.
        self.env.cr.execute("SELECT to_regclass('hr_termination_correction_payslip_rel'), to_regclass('hr_termination_correction_blocked_rel')")
        self.assertEqual(self.env.cr.fetchone(), (None, None))
        action = self.env.ref("steps_hr_payroll_correction.action_hr_termination_correction_from_employee")
        self.assertIn(self.env.ref("steps_hr_payroll_correction.group_payroll_correction"), action.groups_id)
        self.assertTrue(self.scope["hr.termination.correction.wizard"].get_view(view_type="form")["arch"])

    def test_community_refuses_theoretical_days_before_mutation(self):
        if not self.oca:
            self.skipTest("The native engine uses its real worked-day refresh")
        extra = self.entry(9)
        self.slip()
        self.structure.use_work_entries = False
        with self.assertRaises(UserError):
            self.wizard().action_apply()
        self.assertFalse(self.contract.date_end)
        self.assertTrue(extra.exists())

    def test_lifecycle_has_real_city_payslip_relations_views_and_menus(self):
        if "hr.severance" not in self.scope:
            self.skipTest("Lifecycle is not installed in this consumer-only database")
        self.assertEqual(self.scope["hr.contract"]._fields["work_commune_id"].comodel_name, "res.city")
        self.assertIn("res.city", self.scope)
        self.assertEqual(self.scope["hr.severance"]._fields["last_payslip_ids"].comodel_name, "hr.payslip")
        for xmlid in ("menu_hr_severance", "menu_hr_contract_lifecycle_termino", "menu_hr_labor_document"):
            menu = self.env.ref("step_hr_contract_lifecycle." + xmlid)
            self.assertTrue(menu.parent_id)
        self.assertTrue(self.scope["hr.contract"].get_view(view_type="form")["arch"])
        self.assertTrue(self.scope["hr.severance"].get_view(view_type="form")["arch"])

    def test_lifecycle_preserves_paid_severance_and_worker_identity(self):
        if "hr.severance" not in self.scope:
            self.skipTest("Lifecycle is not installed in this consumer-only database")
        cause = self.env["step.hr.termination.cause"].create({"name": "Private consumer cause", "code": "PRIVATE_HR_CONSUMER"})
        slip = self.slip()
        severance = self.scope["hr.severance"].create({"contract_id": self.contract.id, "company_id": self.company.id,
            "causal_id": cause.id, "date_termino": date(2026, 10, 7), "last_payslip_ids": [Command.set(slip.ids)]})
        severance.state = "paid"
        original = severance.read(["state", "renta_base", "total_a_pagar", "last_payslip_ids"])
        with self.assertRaises(UserError):
            severance.action_prevalidate()
        self.assertEqual(severance.read(["state", "renta_base", "total_a_pagar", "last_payslip_ids"]), original)
        foreign_employee = self.scope["hr.employee"].create({"name": "Private second employee", "company_id": self.company.id})
        foreign_contract = self.scope["hr.contract"].create(dict(self.contract_values, employee_id=foreign_employee.id))
        foreign_slip = slip.copy({"employee_id": foreign_employee.id, "contract_id": foreign_contract.id})
        with self.assertRaises(ValidationError), self.env.cr.savepoint():
            severance.last_payslip_ids = foreign_slip

    def test_transition_uses_actual_payroll_manager_and_keeps_review_on_missing_masters(self):
        if "step_payroll_migration_review" not in self.contract._fields:
            self.skipTest("Transition is not installed in this consumer-only database")
        self.contract.step_payroll_migration_review = True
        with self.assertRaises(UserError):
            self.contract.action_confirm_payroll_migration()
        self.assertTrue(self.contract.step_payroll_migration_review)
        self.assertFalse(self.contract.employee_id.hr_commune)

    def test_transition_preserves_structure_and_forbids_old_engine_recalculation(self):
        if "step_legacy_payroll" not in self.structure._fields:
            self.skipTest("Transition is not installed in this consumer-only database")
        slip = self.slip()
        self.structure.step_legacy_payroll = True
        original = self.stored(slip)
        with self.assertRaises(UserError):
            slip.compute_sheet()
        self.assertEqual(self.stored(slip), original)

    def test_weekly_hours_feed_all_contract_consumers_without_changing_the_schedule(self):
        if "hr.severance" not in self.scope:
            self.skipTest("Lifecycle is not installed in this consumer-only database")
        from odoo.addons.step_hr_contract_lifecycle.models.dt_contract_field_catalog import DT_CONTRACT_COLUMNS
        from odoo.addons.step_hr_contract_lifecycle.models.hr_labor_template import TEMPLATE_VARIABLES
        self.assertEqual(self.contract.adequacy_state, "adequate")
        self.calendar.attendance_ids.filtered(lambda row: row.dayofweek == "4").hour_to = 20
        original = self.calendar.attendance_ids.read(["id", "hour_from", "hour_to"])
        self.assertEqual(self.calendar._steps_contract_weekly_hours(), 44)
        self.assertEqual(float(dict(DT_CONTRACT_COLUMNS)["DURACION_JORNADA"](self.contract)), 44)
        self.assertEqual(float(TEMPLATE_VARIABLES["contrato.jornada_semanal"](self.contract)), 44)
        self.assertEqual(self.contract.adequacy_state, "exception")
        transition = self.scope["hr.legal.workweek.calendar"].create({"date_from": date(2035, 1, 1),
            "max_weekly_hours": 36, "company_id": self.company.id})
        batch = self.scope["hr.contract.adequacy.batch"].create({"calendar_id": transition.id, "company_id": self.company.id})
        batch.action_simulate()
        self.assertEqual(batch.line_ids.contract_id, self.contract)
        self.assertEqual(batch.line_ids.current_weekly_hours, 44)
        simulator = self.scope["hr.legal.calendar.simulator"].create({"calendar_id": transition.id, "company_id": self.company.id})
        self.assertEqual(simulator.affected_contract_ids, self.contract)
        self.assertEqual(simulator.total_hours_to_reduce, 8)
        transition._apply_transition()
        log = self.scope["hr.legal.calendar.execution.log"].search([("calendar_id", "=", transition.id),
            ("contract_id", "=", self.contract.id)])
        self.assertEqual(log.old_hours, 44)
        self.assertTrue(log.is_exception)
        self.assertEqual(self.calendar.attendance_ids.read(["id", "hour_from", "hour_to"]), original)

    def test_hidden_work_entries_cannot_be_deleted_through_the_correction_role(self):
        extra = self.entry(9)
        original = extra.read(["id", "date_start", "date_stop", "state"])
        messages = self.contract.message_ids.ids
        wizard = self.wizard()
        self.env["ir.rule"].create({"name": "Private hidden correction work entry",
            "model_id": self.env["ir.model"]._get_id("hr.work.entry"),
            "domain_force": "[('id','!=',%d)]" % extra.id})
        with self.assertRaises(AccessError):
            wizard.action_apply()
        self.assertFalse(self.contract.date_end)
        self.assertEqual(extra.sudo().read(["id", "date_start", "date_stop", "state"]), original)
        self.assertEqual(self.contract.message_ids.ids, messages)
