"""Actual OCA draft deletion; never a native history or payroll calculation."""
from unittest.mock import patch
from psycopg2 import IntegrityError

from odoo import api, Command, fields
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests import TransactionCase, tagged
from odoo.tools import mute_logger
from odoo.addons.step_payroll_oca_api.models.original_history_deletion import _admit_original_company_storage


@tagged("post_install", "-at_install")
class OriginalHistoryDeletionCase(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env["res.company"].create({"name": "Private original deletion company",
            "country_id": cls.env.ref("base.cl").id})
        cls.actor = cls.env["res.users"].with_context(no_reset_password=True).create({
            "name": "Private original deletion manager", "login": "private-original-deletion-manager",
            "company_id": cls.company.id, "company_ids": [Command.set(cls.company.ids)],
            "groups_id": [Command.set([cls.env.ref(name).id for name in (
                "base.group_user", "payroll.group_payroll_manager", "hr.group_hr_manager", "account.group_account_manager")])]})
        cls.scope = api.Environment(cls.env.cr, cls.actor.id, dict(cls.env.context,
            allowed_company_ids=cls.company.ids), su=False)
        cls.journal = cls.scope["account.journal"].create({"name": "Private deletion journal", "code": "DEL",
            "type": "general", "company_id": cls.company.id})
        kind = cls.scope["hr.payroll.structure.type"].create({"name": "Private deletion structure type"})
        cls.structure = cls.scope["hr.payroll.structure"].create({"name": "Private deletion structure",
            "code": "PRIVATE_DELETE", "type_id": kind.id, "company_id": cls.company.id, "parent_id": False})
        category = cls.scope["hr.salary.rule.category"].create({"name": "Private deletion category", "code": "PRIVATE_DELETE_CAT"})
        cls.rule = cls.scope["hr.salary.rule"].create({"name": "Private deletion rule", "code": "PRIVATE_DELETE_RULE",
            "company_id": cls.company.id, "struct_id": cls.structure.id, "category_id": category.id,
            "condition_select": "none", "amount_select": "fix", "amount_fix": 0})
        cls.input_type = cls.scope["hr.payslip.input.type"].create({"name": "Private deletion input type",
            "code": "PRIVATE_DELETE_INPUT", "country_id": cls.company.country_id.id,
            "struct_ids": [Command.set(cls.structure.ids)]})
        cls.employee = cls.scope["hr.employee"].create({"name": "Private deletion employee", "company_id": cls.company.id})
        values = {"name": "Private deletion contract", "employee_id": cls.employee.id, "company_id": cls.company.id,
            "state": "open", "date_start": fields.Date.today().replace(day=1), "wage": 100,
            "structure_type_id": kind.id, "struct_id": cls.structure.id, "journal_id": cls.journal.id}
        if "contract_type_id" in cls.scope["hr.contract"]._fields:
            field = cls.scope["hr.contract"]._fields["contract_type_id"]
            values["contract_type_id"] = cls.scope[field.comodel_name].search([], limit=1).id
        cls.contract = cls.scope["hr.contract"].create(values)
        cls.entry_type = cls.env["hr.work.entry.type"].create({"name": "Private deletion worked type", "code": "PRIVATE_DELETE_DAY"})

    def _batch(self, children=True):
        run = self.scope["hr.payslip.run"].create({"name": "Private original deletion batch", "company_id": self.company.id})
        slip = self.scope["hr.payslip"].create({"name": "Private original deletion slip", "number": "PRIVATE/DELETE/" + str(run.id),
            "employee_id": self.employee.id, "company_id": self.company.id, "contract_id": self.contract.id,
            "struct_id": self.structure.id, "journal_id": self.journal.id, "payslip_run_id": run.id,
            "date_from": run.date_start, "date_to": run.date_end})
        if children:
            self.scope["hr.payslip.input"].create({"payslip_id": slip.id, "contract_id": self.contract.id,
                "input_type_id": self.input_type.id, "amount": 0})
            self.scope["hr.payslip.worked_days"].create({"name": "Private saved day", "payslip_id": slip.id,
                "contract_id": self.contract.id, "work_entry_type_id": self.entry_type.id,
                "number_of_days": 0, "number_of_hours": 0})
            self.scope["hr.payslip.line"].create({"name": "Private stored draft line", "code": self.rule.code,
                "slip_id": slip.id, "salary_rule_id": self.rule.id, "employee_id": self.employee.id,
                "contract_id": self.contract.id, "amount": 0, "quantity": 1, "rate": 100})
        return run, slip

    def _snapshot(self, runs):
        self.env.flush_all()
        self.env.cr.execute("SELECT id FROM hr_payslip WHERE payslip_run_id=ANY(%s) ORDER BY id", (runs.ids,))
        ids = [row[0] for row in self.env.cr.fetchall()]
        result = {}
        for table, column, values in (("hr_payslip_run", "id", runs.ids), ("hr_payslip", "id", ids),
                ("hr_payslip_input", "payslip_id", ids), ("hr_payslip_worked_days", "payslip_id", ids),
                ("hr_payslip_line", "slip_id", ids)):
            self.env.cr.execute("SELECT to_jsonb(t) FROM " + table + " t WHERE " + column + "=ANY(%s) ORDER BY id", (values,))
            result[table] = self.env.cr.fetchall()
        return result

    def _hide(self, model, ident):
        return self.env["ir.rule"].create({"name": "Private deletion hidden row",
            "model_id": self.env["ir.model"]._get_id(model), "domain_force": "[('id', '!=', %s)]" % ident})

    def test_real_draft_delete_uses_normal_child_unlinks_and_preserves_original_fk_contracts(self):
        run, slip = self._batch()
        descendants = [slip.line_ids, slip.input_line_ids, slip.worked_days_line_ids]
        self.assertFalse(self.scope.su)
        company = slip._fields["company_id"]
        self.assertTrue(company.required)
        self.assertEqual(company.ondelete, "restrict")
        self.assertEqual(slip._fields["payslip_run_id"].ondelete, "cascade")
        self.env.cr.execute("SELECT a.attname,c.confdeltype,c.convalidated FROM pg_constraint c "
            "JOIN pg_attribute a ON a.attrelid=c.conrelid AND c.conkey=ARRAY[a.attnum]::smallint[] "
            "WHERE c.contype='f' AND c.conrelid='hr_payslip'::regclass AND a.attname IN ('company_id','payslip_run_id') ORDER BY a.attname")
        self.assertEqual(self.env.cr.fetchall(), [("company_id", "r", True), ("payslip_run_id", "c", True)])
        self.env.cr.execute("SELECT attnotnull FROM pg_attribute WHERE attrelid='hr_payslip'::regclass AND attname='company_id'")
        self.assertEqual(self.env.cr.fetchone(), (True,))
        called = []
        def wrapper(original):
            def unlink(records):
                self.assertFalse(records.env.su)
                self.assertEqual(records.env.uid, self.actor.id)
                called.append((records._name, records.ids))
                return original(records)
            return unlink
        with patch.object(type(descendants[0]), "unlink", wrapper(type(descendants[0]).unlink)), \
                patch.object(type(descendants[1]), "unlink", wrapper(type(descendants[1]).unlink)), \
                patch.object(type(descendants[2]), "unlink", wrapper(type(descendants[2]).unlink)), \
                patch.object(type(slip), "compute_sheet", side_effect=AssertionError("No payroll calculation during deletion")):
            self.assertTrue(run.unlink())
        self.assertEqual({name for name, ids in called}, {records._name for records in descendants})
        self.assertFalse(run.exists() or slip.exists() or any(records.exists() for records in descendants))

    def test_closed_refund_and_calculated_history_is_rejected_before_any_delete(self):
        variants = (("run", {"state": "close"}), ("run", {"credit_note": True}),
            ("slip", {"state": "verify"}), ("slip", {"state": "done"}), ("slip", {"state": "paid"}),
            ("slip", {"state": "cancel"}), ("slip", {"paid": True}),
            ("slip", {"credit_note": True}), ("slip", {"compute_date": fields.Date.today()}))
        for target, values in variants:
            run, slip = self._batch()
            (run if target == "run" else slip).write(values)
            before = self._snapshot(run)
            with self.subTest(target=target, values=values), self.assertRaises(UserError):
                run.sudo().unlink()
            self.assertEqual(self._snapshot(run), before)

    def test_account_move_reference_and_missing_company_are_not_deleted_or_repaired(self):
        run, slip = self._batch()
        move = self.scope["account.move"].create({"name": "PRIVATE/DELETE/MOVE", "journal_id": self.journal.id,
            "move_type": "entry", "company_id": self.company.id})
        slip.move_id = move
        before = self._snapshot(run)
        with self.assertRaises(UserError):
            run.unlink()
        self.assertEqual(self._snapshot(run), before)
        self.assertTrue(move.exists())
        with mute_logger("odoo.sql_db"), self.assertRaises((ValidationError, UserError, IntegrityError)):
            with self.env.cr.savepoint():
                slip.company_id = False
        self.assertEqual(slip.company_id, self.company)
        # Primitive PostgreSQL storage witness, not a replacement payslip
        # model. Existing NULL must be rejected before any default initializer.
        self.env.cr.execute("CREATE TEMP TABLE step_private_original_company_policy (id integer,company_id integer)")
        self.env.cr.execute("INSERT INTO step_private_original_company_policy VALUES (1,NULL)")
        with self.assertRaisesRegex(UserError, "no owner"):
            _admit_original_company_storage(self.env.cr, "step_private_original_company_policy")
        self.env.cr.execute("SELECT id,company_id FROM step_private_original_company_policy")
        self.assertEqual(self.env.cr.fetchall(), [(1, None)])
        self.env.cr.execute("DELETE FROM step_private_original_company_policy")
        _admit_original_company_storage(self.env.cr, "step_private_original_company_policy")
        self.env.cr.execute("INSERT INTO step_private_original_company_policy VALUES (2,%s)", (self.company.id,))
        _admit_original_company_storage(self.env.cr, "step_private_original_company_policy")
        self.env.cr.execute("SELECT id,company_id FROM step_private_original_company_policy")
        self.assertEqual(self.env.cr.fetchall(), [(2, self.company.id)])

    def test_mixed_companies_reject_the_entire_normal_or_sudo_request(self):
        run, slip = self._batch()
        other = self.env["res.company"].create({"name": "Private other deletion company"})
        self.actor.with_env(self.env).write({"company_ids": [Command.link(other.id)]})
        scope = self.scope["hr.payslip.run"].with_context(allowed_company_ids=(self.company | other).ids)
        foreign = scope.with_company(other).create({"name": "Private foreign deletion batch", "company_id": other.id})
        batches = (scope.browse(run.id) | scope.browse(foreign.id))
        before = self._snapshot(batches)
        for records in (batches, batches.sudo()):
            with self.assertRaises(UserError):
                records.unlink()
            self.assertEqual(self._snapshot(batches), before)

    def test_hidden_run_and_actor_without_unlink_cannot_use_cached_or_sudo_requests(self):
        run, slip = self._batch()
        self.assertEqual(run.sudo().slip_ids, slip.sudo())
        self._hide("hr.payslip.run", run.id)
        before = self._snapshot(run)
        for records in (run, run.sudo()):
            with self.assertRaises(AccessError):
                records.unlink()
        internal = self.env["res.users"].with_context(no_reset_password=True).create({
            "name": "Private deletion denied user", "login": "private-deletion-denied-user",
            "company_id": self.company.id, "company_ids": [Command.set(self.company.ids)],
            "groups_id": [Command.set(self.env.ref("base.group_user").ids)]})
        with self.assertRaises(AccessError):
            run.with_user(internal).sudo().unlink()
        self.assertEqual(self._snapshot(run), before)

    def test_one_hidden_payslip_prevents_partial_deletion_of_the_visible_sibling(self):
        run, slip = self._batch()
        second = slip.copy({"number": "PRIVATE/DELETE/SECOND", "payslip_run_id": run.id})
        self.assertEqual(set(run.sudo().slip_ids.ids), {slip.id, second.id})
        self._hide("hr.payslip", second.id)
        before = self._snapshot(run)
        for records in (run, run.sudo()):
            with self.assertRaises(AccessError):
                records.unlink()
            self.assertEqual(self._snapshot(run), before)

    def test_hidden_descendant_and_field_acl_are_checked_before_all_child_deletes(self):
        run, slip = self._batch()
        for children in (slip.line_ids, slip.input_line_ids, slip.worked_days_line_ids):
            self.assertTrue(children)
            before = self._snapshot(run)
            with self.env.cr.savepoint() as point:
                self._hide(children._name, children[0].id)
                for records in (run, run.sudo()):
                    with self.assertRaises(AccessError):
                        records.unlink()
                    self.assertEqual(self._snapshot(run), before)
                point.rollback()
        for model, name in (("hr.payslip", "paid"), ("hr.payslip.run", "state"), ("hr.payslip.input", "payslip_id")):
            before = self._snapshot(run)
            with patch.object(self.scope[model]._fields[name], "groups", "base.group_system"), self.assertRaises(AccessError):
                run.sudo().unlink()
            self.assertEqual(self._snapshot(run), before)

    def test_late_actual_provider_failure_rolls_back_all_real_child_deletions(self):
        run, slip = self._batch()
        before = self._snapshot(run)
        provider = next(base for base in type(run).__mro__ if base.__module__ == "odoo.addons.payroll.models.hr_payslip_run")
        called = []
        def late(records):
            self.assertFalse(records.env.su)
            self.assertFalse(slip.exists())
            result = super(provider, records).unlink()
            self.assertTrue(result)
            self.assertFalse(records.exists())
            called.append(True)
            raise UserError("Private late real provider deletion failure")
        with patch.object(provider, "unlink", late, create=True), self.assertRaisesRegex(UserError, "Private late"):
            run.unlink()
        self.assertEqual(called, [True])
        self.assertEqual(self._snapshot(run), before)
