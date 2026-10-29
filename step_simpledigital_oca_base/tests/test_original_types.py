"""Four independent cases for real type policies, onchanges and generated work."""
from datetime import timedelta

from lxml import etree

from odoo import api, Command, fields
from odoo.exceptions import AccessError, UserError
from odoo.tests import TransactionCase, tagged
from odoo.tools import mute_logger
from psycopg2 import IntegrityError


@tagged("post_install", "-at_install")
class OriginalTypeCase(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env["res.company"].create({"name": "Private original type company",
            "country_id": cls.env.ref("base.cl").id, "currency_id": cls.env.ref("base.CLP").id})
        actor = cls.env["res.users"].with_context(no_reset_password=True).create({
            "name": "Private original type manager", "login": "private-original-type-manager",
            "company_id": cls.company.id, "company_ids": [Command.set(cls.company.ids)],
            "groups_id": [Command.set([cls.env.ref(xmlid).id for xmlid in (
                "base.group_user", "payroll.group_payroll_manager", "hr.group_hr_manager", "account.group_account_manager")])]})
        cls.scope = api.Environment(cls.env.cr, actor.id, dict(cls.env.context, allowed_company_ids=cls.company.ids), su=False)
        cls.calendar = cls.scope["resource.calendar"].create({"name": "Private original type calendar", "tz": "UTC",
            "company_id": cls.company.id, "attendance_ids": [Command.clear()] + [Command.create({
                "name": "Private original shift", "dayofweek": str(day), "hour_from": 8, "hour_to": 16,
                "day_period": "morning"}) for day in range(5)]})
        cls.entry_type = cls.scope["hr.work.entry.type"].create({"name": "Private original attendance", "code": "PRIVATE_ORIGINAL_TYPE"})
        cls.kind = cls.scope["hr.payroll.structure.type"].create({"name": "Private original payroll type",
            "country_id": cls.company.country_id.id, "default_schedule_pay": "monthly", "wage_type": "monthly",
            "sequence": 10, "default_work_entry_type_id": cls.entry_type.id, "default_resource_calendar_id": cls.calendar.id})
        cls.structure = cls.scope["hr.payroll.structure"].create({"name": "Private original type structure",
            "code": "PRIVATE_ORIGINAL_TYPE_STRUCT", "type_id": cls.kind.id, "company_id": cls.company.id, "parent_id": False})
        cls.kind.default_struct_id = cls.structure
        category = cls.scope["hr.salary.rule.category"].create({"name": "Private original type category", "code": "PRIVATE_OT_CATEGORY"})
        cls.rule = cls.scope["hr.salary.rule"].create({"name": "Private original type rule", "code": "PRIVATE_OT_RESULT",
            "sequence": 1, "struct_id": cls.structure.id, "category_id": category.id, "condition_select": "none", "amount_select": "fix", "amount_fix": 100.0})
        cls.employee = cls.scope["hr.employee"].create({"name": "Private original type employee", "company_id": cls.company.id,
            "resource_calendar_id": cls.calendar.id})
        cls.employee.resource_id.tz = "UTC"
        cls.contract = cls.scope["hr.contract"].create({"name": "Private original type contract", "employee_id": cls.employee.id,
            "company_id": cls.company.id, "state": "open", "date_start": fields.Date.today().replace(day=1),
            "wage": 100.0, "structure_type_id": cls.kind.id, "struct_id": cls.structure.id, "resource_calendar_id": cls.calendar.id})
        cls.contract.resource_calendar_id = cls.calendar
        cls.employee.resource_calendar_id = cls.calendar

    def _slip(self):
        return self.scope["hr.payslip"].create({"name": "Private original type payslip", "number": "PRIVATE/ORIGINAL/TYPE",
            "employee_id": self.employee.id, "company_id": self.company.id, "contract_id": self.contract.id,
            "struct_id": self.structure.id, "date_from": fields.Date.today().replace(day=1), "date_to": fields.Date.today()})

    def test_original_type_metadata_preserves_explicit_values_and_restrict_foreign_key(self):
        expected = {"default_schedule_pay": ("selection", False), "default_work_entry_type_id": ("many2one", True),
            "sequence": ("integer", False), "wage_type": ("selection", True)}
        for name, (kind, required) in expected.items():
            field = self.kind._fields[name]
            self.assertEqual(field.type, kind)
            self.assertEqual(field.required, required)
            self.assertTrue(field.store)
            self.assertFalse(field.related)
            self.assertFalse(field.readonly)
            self.assertFalse(field.translate)
        self.assertEqual({key for key, label in self.kind._fields["default_schedule_pay"]._description_selection(self.scope)},
            {"annually", "semi-annually", "quarterly", "bi-monthly", "monthly", "semi-monthly", "bi-weekly", "weekly", "daily"})
        self.kind.flush_recordset(list(expected))
        self.env.cr.execute("SELECT default_schedule_pay,default_work_entry_type_id,sequence,wage_type FROM hr_payroll_structure_type WHERE id=%s", (self.kind.id,))
        self.assertEqual(self.env.cr.fetchone(), ("monthly", self.entry_type.id, 10, "monthly"))
        self.env.cr.execute("""SELECT c.confdeltype,c.convalidated FROM pg_constraint c JOIN pg_attribute a
            ON a.attrelid=c.conrelid AND c.conkey=ARRAY[a.attnum]::smallint[]
            WHERE c.conrelid='hr_payroll_structure_type'::regclass AND c.contype='f' AND a.attname='default_work_entry_type_id'""")
        self.assertEqual(self.env.cr.fetchall(), [("r", True)])
        normal = self.scope["hr.payroll.structure.type"].create({"name": "Private normal payroll type"})
        self.assertEqual(normal.default_work_entry_type_id, self.env.ref("hr_work_entry.work_entry_type_attendance"))
        self.assertEqual(normal.wage_type, "monthly")
        self.assertFalse(normal.default_schedule_pay)
        form = self.scope.ref("step_payroll_oca_api.payroll_structure_type_original_form")
        self.assertEqual(form.model, "hr.payroll.structure.type")
        self.assertFalse(form.inherit_id)
        arch = etree.fromstring(self.scope["hr.payroll.structure.type"].get_view(view_id=form.id, view_type="form")["arch"])
        for name in expected:
            nodes = arch.xpath("//field[@name=$name]", name=name)
            self.assertTrue(nodes, name)
            if expected[name][1]:
                self.assertTrue(all(node.get("required") in ("1", "True") for node in nodes), name)
        self.assertEqual(arch.xpath("//field[@name='sequence']/@readonly"), ["1"])
        officer = self.env["res.users"].with_context(no_reset_password=True).create({
            "name": "Private original type officer", "login": "private-original-type-officer",
            "company_id": self.company.id, "company_ids": [Command.set(self.company.ids)],
            "groups_id": [Command.set([self.env.ref(xmlid).id for xmlid in ("base.group_user", "payroll.group_payroll_user")])]})
        self.assertFalse(officer.has_group("payroll.group_payroll_manager"))
        officer_arch = etree.fromstring(self.scope["hr.payroll.structure.type"].with_user(officer).get_view(view_id=form.id, view_type="form")["arch"])
        for name in expected:
            self.assertFalse(officer_arch.xpath("//field[@name=$name]", name=name), name)

    def test_real_onchanges_preserve_calendar_and_structure_chain_and_apply_supported_policy(self):
        other = self.calendar.copy({"name": "Private pre-onchange calendar"})
        self.contract.write({"resource_calendar_id": other.id, "struct_id": False, "schedule_pay": "weekly", "wage_type": "hourly"})
        self.contract._onchange_structure_type_id()
        self.contract._onchange_simpledigital_structure_type()
        self.assertEqual(self.contract.resource_calendar_id, self.calendar)
        self.assertEqual(self.contract.struct_id, self.structure)
        self.assertEqual(self.contract.schedule_pay, "monthly")
        self.assertEqual(self.contract.wage_type, "monthly")
        slip = self._slip()
        slip.compute_sheet()
        self.assertEqual(slip.line_ids.salary_rule_id, self.rule)
        self.assertEqual(slip._get_line_values([self.rule.code])[self.rule.code][slip.id]["total"], 100.0)

    def test_unsupported_type_policies_are_stored_but_rejected_before_onchange_or_calculation(self):
        slip = self._slip()
        slip.compute_sheet()
        contract_fields = ["resource_calendar_id", "struct_id", "schedule_pay", "wage_type"]
        before_contract = self.contract.read(contract_fields)
        before_slip = slip.read(["state", "number", "line_ids", "compute_date"])
        before_lines = slip.line_ids.read(["id", "salary_rule_id", "amount", "quantity", "rate", "total"])
        for name, value, message in (("default_schedule_pay", "daily", "schedule policy"),
                ("default_schedule_pay", "semi-monthly", "schedule policy"), ("wage_type", "hourly", "hourly payroll type policy")):
            self.kind[name] = value
            for action in (self.contract._onchange_structure_type_id,
                    self.contract._onchange_simpledigital_structure_type, slip.compute_sheet, slip.get_lines_dict):
                with self.assertRaisesRegex(UserError, message):
                    action()
                self.assertEqual(self.contract.read(contract_fields), before_contract)
                self.assertEqual(slip.read(["state", "number", "line_ids", "compute_date"]), before_slip)
                self.assertEqual(slip.line_ids.read(["id", "salary_rule_id", "amount", "quantity", "rate", "total"]), before_lines)
            self.kind[name] = "monthly"

    def test_actual_work_entry_generation_uses_original_type_without_stale_cache_or_acl_bypass(self):
        first = self.contract.date_start
        self.assertEqual(self.contract._get_default_work_entry_type_id(), self.entry_type.id)
        self.contract.generate_work_entries(first, first + timedelta(days=6))
        entries = self.scope["hr.work.entry"].search([("contract_id", "=", self.contract.id)])
        self.assertTrue(entries)
        self.assertEqual(entries.work_entry_type_id, self.entry_type)
        self.assertGreater(sum(entries.mapped("duration")), 0)
        before = entries.read(["id", "contract_id", "work_entry_type_id", "date_start", "date_stop", "duration"])
        future = self.scope["hr.work.entry.type"].create({"name": "Private future original attendance", "code": "PRIVATE_OT_FUTURE"})
        self.kind.default_work_entry_type_id = future
        self.assertEqual(self.contract._get_default_work_entry_type_id(), future.id)
        self.assertEqual(entries.read(["id", "contract_id", "work_entry_type_id", "date_start", "date_stop", "duration"]), before)
        with mute_logger("odoo.sql_db"), self.assertRaises(IntegrityError), self.env.cr.savepoint():
            future.unlink()
        self.assertEqual(self.kind.default_work_entry_type_id, future)
        self.env["ir.rule"].create({"name": "Private hidden original work entry type", "model_id": self.env.ref("hr_work_entry.model_hr_work_entry_type").id,
            "domain_force": "[('id','!=',%d)]" % future.id})
        with self.assertRaises(AccessError):
            self.contract._get_default_work_entry_type_id()
        self.assertEqual(entries.read(["id", "contract_id", "work_entry_type_id", "date_start", "date_stop", "duration"]), before)
