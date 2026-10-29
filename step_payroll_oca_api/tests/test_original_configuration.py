"""Original configuration storage and fail-closed admission on the real OCA API."""
import json

from odoo import api, Command, fields
from odoo.exceptions import AccessError, UserError
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class OriginalConfigurationCase(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        company = cls.env["res.company"].create({
            "name": "Private original configuration company", "country_id": cls.env.ref("base.cl").id,
            "currency_id": cls.env.ref("base.CLP").id})
        actor = cls.env["res.users"].with_context(no_reset_password=True).create({
            "name": "Private original configuration manager", "login": "private-original-configuration-manager",
            "company_id": company.id, "company_ids": [Command.set(company.ids)],
            "groups_id": [Command.set([cls.env.ref(xmlid).id for xmlid in (
                "base.group_user", "payroll.group_payroll_manager", "account.group_account_manager", "hr.group_hr_manager")])]})
        cls.scope = api.Environment(cls.env.cr, actor.id, dict(cls.env.context, allowed_company_ids=company.ids), su=False)
        cls.company = company
        cls.journal = cls.scope["account.journal"].create({
            "name": "Private original configuration journal", "code": "OCF", "type": "general", "company_id": company.id})
        cls.kind = cls.scope["hr.payroll.structure.type"].create({"name": "Private original configuration type"})
        cls.structure = cls.scope["hr.payroll.structure"].create({
            "name": "Private original configuration", "code": "PRIVATE_ORIGINAL_CONFIG", "parent_id": False,
            "type_id": cls.kind.id, "company_id": company.id, "journal_id": cls.journal.id})
        cls.category = cls.scope["hr.salary.rule.category"].create({
            "name": "Private original configuration category", "code": "PRIVATE_ORIGINAL_CATEGORY", "company_id": company.id})
        cls.rule = cls.scope["hr.salary.rule"].create({
            "name": "Private original configuration rule", "code": "PRIVATE_ORIGINAL_RESULT", "sequence": 1,
            "category_id": cls.category.id, "company_id": company.id, "struct_id": cls.structure.id,
            "condition_select": "none", "amount_select": "fix", "amount_fix": 100.0})
        cls.input_type = cls.scope["hr.payslip.input.type"].create({
            "name": "Private original configuration input", "code": "PRIVATE_ORIGINAL_INPUT",
            "country_id": company.country_id.id, "struct_ids": [Command.set(cls.structure.ids)]})
        cls.partner = cls.scope["res.partner"].create({"name": "Private original rule partner", "company_id": company.id})
        cls.employee = cls.scope["hr.employee"].create({"name": "Private original configuration employee", "company_id": company.id})
        values = {"name": "Private original configuration contract", "employee_id": cls.employee.id,
            "company_id": company.id, "state": "open", "date_start": fields.Date.today().replace(day=1),
            "wage": 100.0, "structure_type_id": cls.kind.id, "struct_id": cls.structure.id, "journal_id": cls.journal.id}
        if "contract_type_id" in cls.scope["hr.contract"]._fields:
            field = cls.scope["hr.contract"]._fields["contract_type_id"]
            values["contract_type_id"] = cls.scope[field.comodel_name].search([], limit=1).id
        cls.contract = cls.scope["hr.contract"].create(values)

    def _slip(self):
        # This suite does not test numbering and must not consume an original
        # salary sequence, including when compute rejects configuration.
        return self.scope["hr.payslip"].create({
            "name": "Private original configuration payslip", "number": "PRIVATE/ORIGINAL/CONFIG",
            "employee_id": self.employee.id, "company_id": self.company.id,
            "contract_id": self.contract.id, "struct_id": self.structure.id,
            "date_from": fields.Date.today().replace(day=1), "date_to": fields.Date.today()})

    def _snapshot(self, slip):
        return (slip.read(["id", "number", "state", "compute_date", "struct_id", "contract_id", "line_ids", "move_id"]),
            slip.line_ids.read(["id", "salary_rule_id", "amount", "quantity", "rate", "total"]))

    def _accounting_snapshot(self):
        moves = self.scope["account.move"].search([("journal_id", "=", self.journal.id)], order="id")
        return (moves.read(["id", "name", "state", "journal_id", "line_ids"]),
            moves.line_ids.read(["id", "move_id", "account_id", "debit", "credit"]))

    def _accounting_rules(self):
        debit = self.scope["account.account"].create({"name": "Private original configuration cost", "code": "940051",
            "account_type": "expense", "company_ids": [Command.set(self.company.ids)]})
        credit = self.scope["account.account"].create({"name": "Private original configuration debt", "code": "940052",
            "account_type": "liability_current", "company_ids": [Command.set(self.company.ids)]})
        self.rule.write({"account_debit": debit.id, "account_credit": credit.id})

    def _other_company_journal(self):
        company = self.env["res.company"].create({"name": "Private other original posting company",
            "country_id": self.company.country_id.id, "currency_id": self.company.currency_id.id})
        self.scope.user.with_env(self.env).write({"company_ids": [Command.link(company.id)]})
        scope = self.scope["hr.payroll.structure"].with_context(allowed_company_ids=(self.company | company).ids).with_company(company).env
        journal = scope["account.journal"].create({"name": "Private other original posting journal",
            "code": "OPJ", "type": "general", "company_id": company.id})
        return scope, journal

    def test_original_fields_match_nullable_storage_relations_and_translations(self):
        expected = {
            "hr.salary.rule": {"condition_other_input_id": "many2one", "amount_other_input_id": "many2one",
                "partner_id": "many2one", "not_computed_in_net": "boolean", "split_move_lines": "boolean"},
            "hr.payroll.structure": {"active": "boolean", "hide_basic_on_pdf": "boolean", "payslip_name": "char",
                "report_id": "many2one", "journal_id": "many2one"},
        }
        relations = {"condition_other_input_id": "hr.payslip.input.type", "amount_other_input_id": "hr.payslip.input.type",
            "partner_id": "res.partner", "report_id": "ir.actions.report", "journal_id": "account.journal"}
        for model_name, names in expected.items():
            model = self.scope[model_name]
            for name, kind in names.items():
                field = model._fields[name]
                self.assertEqual(field.type, kind)
                self.assertTrue(field.store)
                self.assertFalse(field.required)
                self.assertFalse(field.readonly)
                self.assertFalse(field.related)
                self.assertEqual(bool(field.translate), name == "payslip_name")
                if name in relations:
                    self.assertEqual(field.comodel_name, relations[name])
                    self.assertEqual(field.ondelete, "set null")
            self.env.cr.execute("""SELECT a.attname,a.attnotnull,t.typname FROM pg_attribute a
                JOIN pg_type t ON t.oid=a.atttypid WHERE a.attrelid=%s::regclass
                AND a.attname=ANY(%s) AND NOT a.attisdropped""", (model._table, list(names)))
            rows = self.env.cr.fetchall()
            self.assertEqual({name for name, required, kind in rows}, set(names))
            self.assertFalse(any(required for name, required, kind in rows))
            for name, required, kind in rows:
                self.assertEqual(kind, "jsonb" if name in {"payslip_name", "journal_id"}
                    else "bool" if names[name] == "boolean" else "int4")
        self.assertTrue(self.structure._fields["journal_id"].company_dependent)
        self.assertTrue(self.structure.active)

    def test_original_direct_foreign_keys_keep_set_null_policy(self):
        for model_name, names in {
            "hr.salary.rule": ["condition_other_input_id", "amount_other_input_id", "partner_id"],
            "hr.payroll.structure": ["report_id"],
        }.items():
            model = self.scope[model_name]
            self.env.cr.execute("""SELECT a.attname,c.confrelid::regclass::text,c.confdeltype,c.convalidated
                FROM pg_constraint c JOIN pg_attribute a ON a.attrelid=c.conrelid
                    AND c.conkey=ARRAY[a.attnum]::smallint[]
                WHERE c.conrelid=%s::regclass AND c.contype='f' AND a.attname=ANY(%s)""", (model._table, names))
            rows = self.env.cr.fetchall()
            self.assertEqual({row[0] for row in rows}, set(names))
            for name, table, policy, validated in rows:
                self.assertEqual(table, self.scope[model._fields[name].comodel_name]._table)
                self.assertEqual(policy, "n")
                self.assertTrue(validated)

    def test_original_company_journal_preserves_all_json_slots_after_reads(self):
        other = self.env["res.company"].create({"name": "Private second original configuration company",
            "country_id": self.company.country_id.id, "currency_id": self.company.currency_id.id})
        self.scope.user.with_env(self.env).write({"company_ids": [Command.link(other.id)]})
        scope = self.scope["hr.payroll.structure"].with_context(allowed_company_ids=(self.company | other).ids).env
        journal = scope["account.journal"].with_company(other).create({
            "name": "Private second original configuration journal", "code": "OCO", "type": "general", "company_id": other.id})
        structure = scope["hr.payroll.structure"].create({
            "name": "Private original global journals", "code": "PRIVATE_ORIGINAL_JOURNALS", "company_id": False, "parent_id": False})
        structure.with_company(self.company).journal_id = self.journal
        structure.with_company(other).journal_id = journal
        structure.flush_recordset(["journal_id"])
        self.env.cr.execute("SELECT journal_id FROM hr_payroll_structure WHERE id=%s", (structure.id,))
        before = self.env.cr.fetchone()[0]
        self.assertEqual(before, {str(self.company.id): self.journal.id, str(other.id): journal.id})
        structure.invalidate_recordset(["journal_id"])
        self.assertEqual(structure.with_company(self.company).journal_id, self.journal)
        self.assertEqual(structure.with_company(other).journal_id, journal)
        self.assertFalse(structure.company_id)
        structure.flush_recordset(["journal_id"])
        self.env.cr.execute("SELECT journal_id FROM hr_payroll_structure WHERE id=%s", (structure.id,))
        self.assertEqual(self.env.cr.fetchone()[0], before)

    def test_original_sql_nulls_survive_normal_configuration_read(self):
        rule_fields = ["condition_other_input_id", "amount_other_input_id", "partner_id", "not_computed_in_net", "split_move_lines"]
        structure_fields = ["hide_basic_on_pdf", "payslip_name", "report_id", "journal_id"]
        self.rule.flush_recordset(rule_fields)
        self.structure.flush_recordset(structure_fields)
        self.env.cr.execute("""UPDATE hr_salary_rule SET condition_other_input_id=NULL,amount_other_input_id=NULL,
            partner_id=NULL,not_computed_in_net=NULL,split_move_lines=NULL WHERE id=%s""", (self.rule.id,))
        self.env.cr.execute("""UPDATE hr_payroll_structure SET hide_basic_on_pdf=NULL,payslip_name=NULL,
            report_id=NULL,journal_id=NULL WHERE id=%s""", (self.structure.id,))
        self.rule.invalidate_recordset(rule_fields)
        self.structure.invalidate_recordset(structure_fields)
        self.assertFalse(any(self.rule.read(rule_fields)[0][name] for name in rule_fields))
        self.assertFalse(any(self.structure.read(structure_fields)[0][name] for name in structure_fields))
        self.env.flush_all()
        self.env.cr.execute("""SELECT condition_other_input_id,amount_other_input_id,partner_id,not_computed_in_net,split_move_lines
            FROM hr_salary_rule WHERE id=%s""", (self.rule.id,))
        self.assertEqual(self.env.cr.fetchone(), (None,) * 5)
        self.env.cr.execute("SELECT hide_basic_on_pdf,payslip_name,report_id,journal_id FROM hr_payroll_structure WHERE id=%s", (self.structure.id,))
        self.assertEqual(self.env.cr.fetchone(), (None,) * 4)

    def test_original_defaults_retain_actual_engine_rule_and_stored_result(self):
        slip = self._slip()
        self.assertTrue(slip._step_check_original_configuration())
        slip.compute_sheet()
        self.assertEqual(slip.line_ids.salary_rule_id, self.rule)
        self.assertEqual(slip._get_line_values([self.rule.code])[self.rule.code][slip.id]["total"], 100.0)
        before = self._snapshot(slip)
        self.assertTrue(slip._step_check_original_configuration(operation="account"))
        self.assertEqual(self._snapshot(slip), before)

    def test_archived_original_structure_rejects_all_calculation_entry_points_before_changes(self):
        slip = self._slip()
        slip.compute_sheet()
        before = self._snapshot(slip)
        self.structure.active = False
        for operation in (slip.compute_sheet, slip.get_lines_dict, slip.action_payslip_done,
                lambda: slip._get_payslip_lines(self.contract.ids, slip.id),
                lambda: slip._step_check_original_configuration(operation="account")):
            with self.assertRaisesRegex(UserError, "archived"):
                operation()
            self.assertEqual(self._snapshot(slip), before)

    def test_archived_parent_rejects_real_contract_fallback_without_assigning_structure(self):
        parent = self.scope["hr.payroll.structure"].create({
            "name": "Private archived original parent", "code": "PRIVATE_ARCHIVED_PARENT", "parent_id": False,
            "company_id": self.company.id, "active": False})
        self.structure.parent_id = parent
        slip = self._slip()
        slip.struct_id = False
        before = self._snapshot(slip)
        with self.assertRaisesRegex(UserError, "archived"):
            slip.compute_sheet()
        with self.assertRaisesRegex(UserError, "archived"):
            slip.get_lines_dict()
        self.assertFalse(slip.struct_id)
        self.assertEqual(slip.contract_id, self.contract)
        self.assertEqual(self._snapshot(slip), before)

    def test_unsupported_original_refs_and_flags_reject_before_calculation_and_posting(self):
        slip = self._slip()
        slip.compute_sheet()
        before = self._snapshot(slip)
        for name, value in (("condition_other_input_id", self.input_type.id),
                ("amount_other_input_id", self.input_type.id), ("partner_id", self.partner.id),
                ("not_computed_in_net", True), ("split_move_lines", True)):
            self.rule[name] = value
            for operation in (slip.compute_sheet, slip.get_lines_dict,
                    lambda: slip.with_context(without_compute_sheet=True).action_payslip_done(),
                    lambda: slip._step_check_original_configuration(operation="account")):
                with self.assertRaisesRegex(UserError, "certified Community"):
                    operation()
                self.assertEqual(self._snapshot(slip), before)
            self.rule[name] = False

    def test_archived_split_flag_is_preserved_and_not_enabled_implicitly(self):
        self.rule.split_move_lines = True
        self.structure.active = False
        self.assertTrue(self.rule.read(["split_move_lines"])[0]["split_move_lines"])
        self.assertFalse(self.structure.read(["active"])[0]["active"])
        self.assertNotIn(self.structure, self.scope["hr.payroll.structure"].search([("id", "=", self.structure.id)]))
        self.assertIn(self.structure, self.scope["hr.payroll.structure"].with_context(active_test=False).search([("id", "=", self.structure.id)]))
        slip = self._slip()
        with self.assertRaisesRegex(UserError, "archived"):
            slip._step_check_original_configuration()
        self.structure.active = True
        with self.assertRaisesRegex(UserError, "certified Community"):
            slip._step_check_original_configuration()
        self.assertTrue(self.rule.split_move_lines)

    def test_unsupported_original_calculation_modes_fail_closed_without_evaluation(self):
        slip = self._slip()
        for column, original in (("condition_select", "none"), ("amount_select", "fix")):
            self.rule.flush_recordset([column])
            # Controlled new fixture: a raw configuration import must not bypass
            # admission simply because ORM selection validation was not used.
            self.env.cr.execute("UPDATE hr_salary_rule SET " + column + "='input' WHERE id=%s", (self.rule.id,))
            self.rule.invalidate_recordset([column])
            before = self._snapshot(slip)
            with self.assertRaisesRegex(UserError, "mode is not supported"):
                slip.compute_sheet()
            self.assertEqual(self._snapshot(slip), before)
            self.env.cr.execute("UPDATE hr_salary_rule SET " + column + "=%s WHERE id=%s", (original, self.rule.id))
            self.rule.invalidate_recordset([column])

    def test_normal_access_to_rule_and_linked_masters_is_required_with_warm_cache(self):
        slip = self._slip()
        before = self._snapshot(slip)
        for name, record, model_xmlid in (
                ("condition_other_input_id", self.input_type, "step_payroll_oca_api.model_hr_payslip_input_type"),
                ("partner_id", self.partner, "base.model_res_partner")):
            self.rule[name] = record
            self.rule.read([name])
            hidden = self.env["ir.rule"].create({"name": "Private hidden original reference",
                "model_id": self.env.ref(model_xmlid).id, "domain_force": "[('id','!=',%d)]" % record.id})
            with self.assertRaises(AccessError):
                slip._step_check_original_configuration()
            self.assertEqual(self._snapshot(slip), before)
            hidden.unlink()
            self.rule[name] = False
        self.rule.read(["active", "struct_id", "company_id"])
        self.env["ir.rule"].create({"name": "Private hidden original salary rule",
            "model_id": self.env.ref("payroll.model_hr_salary_rule").id,
            "domain_force": "[('id','!=',%d)]" % self.rule.id})
        with self.assertRaises(AccessError):
            slip._step_check_original_configuration()
        self.assertEqual(self._snapshot(slip), before)

    def test_closed_stored_results_remain_readable_after_original_configuration_changes(self):
        slip = self._slip()
        slip.compute_sheet()
        slip.state = "done"
        self.structure.active = False
        self.rule.split_move_lines = True
        before = self._snapshot(slip)
        self.assertEqual(slip._get_line_values([self.rule.code])[self.rule.code][slip.id]["total"], 100.0)
        self.assertEqual(slip.get_salary_line_total(self.rule.code), 100.0)
        self.assertFalse(slip.struct_id.active)
        for operation in ("calculate", "account"):
            with self.assertRaisesRegex(UserError, "Closed payroll"):
                slip._step_check_original_configuration(operation=operation)
        with self.assertRaisesRegex(UserError, "Closed payroll"):
            slip.action_payslip_done()
        self.assertEqual(self._snapshot(slip), before)

    def test_posting_matching_structure_property_uses_actual_oca_move(self):
        self._accounting_rules()
        slip = self._slip()
        slip.compute_sheet()
        before = slip.line_ids.read(["id", "salary_rule_id", "amount", "quantity", "rate", "total"])
        # Exercise OCA's genuine already-calculated confirmation route. The
        # posting admission must not rely on compute_sheet being called again.
        slip.with_context(without_compute_sheet=True).action_payslip_done()
        self.assertEqual(slip.state, "done")
        self.assertTrue(slip.move_id)
        self.assertEqual(slip.move_id.state, "posted")
        self.assertEqual(slip.move_id.journal_id, self.journal)
        self.assertEqual(slip.move_id.company_id, self.company)
        self.assertEqual(sum(slip.move_id.line_ids.mapped("balance")), 0.0)
        self.assertEqual(sum(slip.move_id.line_ids.mapped("debit")), 100.0)
        self.assertEqual(slip.line_ids.read(["id", "salary_rule_id", "amount", "quantity", "rate", "total"]), before)

    def test_posting_null_structure_property_keeps_real_contract_fallback_and_null(self):
        self._accounting_rules()
        self.structure.flush_recordset(["journal_id"])
        self.env.cr.execute("UPDATE hr_payroll_structure SET journal_id=NULL WHERE id=%s", (self.structure.id,))
        self.structure.invalidate_recordset(["journal_id"])
        slip = self._slip()
        slip.compute_sheet()
        self.assertFalse(self.structure.with_company(self.company).journal_id)
        self.assertEqual(slip.journal_id, self.contract.journal_id)
        slip.action_payslip_done()
        self.assertEqual(slip.move_id.journal_id, self.journal)
        self.assertEqual(slip.move_id.state, "posted")
        self.structure.flush_recordset(["journal_id"])
        self.env.cr.execute("SELECT journal_id FROM hr_payroll_structure WHERE id=%s", (self.structure.id,))
        self.assertIsNone(self.env.cr.fetchone()[0])

    def test_posting_mismatched_or_foreign_property_fails_before_state_or_moves(self):
        self._accounting_rules()
        slip = self._slip()
        slip.compute_sheet()
        before = self._snapshot(slip), self._accounting_snapshot()
        alternate = self.scope["account.journal"].create({"name": "Private mismatched original journal",
            "code": "OMJ", "type": "general", "company_id": self.company.id})
        self.structure.with_company(self.company).journal_id = alternate
        with self.assertRaisesRegex(UserError, "structure salary journal differs"):
            slip.action_payslip_done()
        self.assertEqual((self._snapshot(slip), self._accounting_snapshot()), before)
        scope, foreign_journal = self._other_company_journal()
        self.env["ir.default"].set("hr.payroll.structure", "journal_id", self.journal.id, company_id=self.company.id)
        for incomplete in ({}, {str(scope.company.id): foreign_journal.id},
                {str(self.company.id): None}, {str(self.company.id): False},
                {str(self.company.id): 0}, {str(self.company.id): 2**31},
                {str(self.company.id): str(self.journal.id)}):
            self.structure.flush_recordset(["journal_id"])
            self.env.cr.execute("UPDATE hr_payroll_structure SET journal_id=%s::jsonb WHERE id=%s",
                (json.dumps(incomplete), self.structure.id))
            self.structure.invalidate_recordset(["journal_id"])
            if str(self.company.id) not in incomplete:
                # A real ORM default can make the visible journal appear
                # compatible even though the original company key is absent.
                self.assertEqual(self.structure.with_company(self.company).journal_id, self.journal)
            with self.assertRaisesRegex(UserError, "property is incomplete"):
                slip.with_context(without_compute_sheet=True).action_payslip_done()
            self.assertEqual((self._snapshot(slip), self._accounting_snapshot()), before)
            self.structure.flush_recordset(["journal_id"])
            self.env.cr.execute("SELECT journal_id FROM hr_payroll_structure WHERE id=%s", (self.structure.id,))
            self.assertEqual(self.env.cr.fetchone()[0], incomplete)
        caller = slip.with_env(scope).with_company(self.company)
        self.structure.with_env(caller.env).with_company(self.company).journal_id = foreign_journal
        with self.assertRaisesRegex(UserError, "structure salary journal must belong"):
            caller.action_payslip_done()
        self.assertEqual((self._snapshot(slip), self._accounting_snapshot()), before)
        self.assertEqual(self.structure.with_env(caller.env).with_company(self.company).journal_id, foreign_journal)

    def test_posting_rechecks_normal_journal_access_even_with_warm_related_cache(self):
        self._accounting_rules()
        slip = self._slip()
        slip.compute_sheet()
        self.assertEqual(slip.journal_id, self.journal)
        self.assertEqual(self.structure.journal_id, self.journal)
        before = self._snapshot(slip), self._accounting_snapshot()
        self.env["ir.rule"].create({"name": "Private hidden original salary journal",
            "model_id": self.env.ref("account.model_account_journal").id,
            "domain_force": "[('id','!=',%d)]" % self.journal.id})
        with self.assertRaises(AccessError):
            slip.with_context(without_compute_sheet=True).action_payslip_done()
        self.assertEqual((self._snapshot(slip), self._accounting_snapshot()), before)

    def test_posting_rejects_wrong_company_and_mixed_batch_before_compatible_fallback(self):
        self._accounting_rules()
        slip = self._slip()
        slip.compute_sheet()
        scope, journal = self._other_company_journal()
        employee = scope["hr.employee"].create({"name": "Private other posting employee", "company_id": scope.company.id})
        other = scope["hr.payslip"].create({"name": "Private other company draft payroll", "number": "PRIVATE/OTHER/CONFIG",
            "employee_id": employee.id, "company_id": scope.company.id, "contract_id": False, "struct_id": False,
            "date_from": fields.Date.today().replace(day=1), "date_to": fields.Date.today()})
        own = slip.with_env(scope).with_company(self.company)
        before = self._snapshot(own), self._snapshot(other), self._accounting_snapshot()
        with self.assertRaisesRegex(UserError, "original company context"):
            slip.with_env(scope).action_payslip_done()
        with self.assertRaisesRegex(UserError, "original company context"):
            (own | other.with_env(own.env)).action_payslip_done()
        self.assertEqual((self._snapshot(own), self._snapshot(other), self._accounting_snapshot()), before)
        self.structure.with_env(own.env).with_company(scope.company).journal_id = journal
        # A different company's configured slot must not replace the actual
        # company's compatible journal; only explicit with_company is allowed.
        own.action_payslip_done()
        self.assertEqual(own.move_id.journal_id, self.journal)
        self.assertEqual(own.move_id.state, "posted")
        self.assertEqual(self._snapshot(other), before[1])
