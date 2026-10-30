"""Official unlimited NUMERIC storage, catalog refusal and real OCA fixtures."""
from decimal import Decimal
from unittest import TestCase
from unittest.mock import patch

from odoo.exceptions import AccessError, UserError
from odoo.tests import TransactionCase, tagged
from odoo.addons.step_payroll_contracts.testing import PayrollContractMixin

from ..input_storage import (
    InputStorageError, admit_input_amount_contract, admit_original_input_storage,
    input_amount_table_admission, inspect_input_amount_storage,
)


@tagged("post_install", "-at_install")
class OriginalInputStorageCase(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        class FixtureRoot:
            @classmethod
            def setUpClass(cls):
                pass
        class Fixture(PayrollContractMixin, FixtureRoot):
            payroll_group = "payroll.group_payroll_manager"
            oca = True
        Fixture.env = cls.env
        Fixture.setUpClass()
        cls.case = Fixture()

    def _row(self, literal="0"):
        slip = self.case.slip(amount=0)
        slip.number = "PRIVATE/NUMERIC/INPUT"
        row = slip.input_line_ids
        row.flush_recordset()
        self.env.cr.execute("UPDATE hr_payslip_input SET amount=%s::numeric WHERE id=%s", (literal, row.id))
        row.invalidate_recordset(["amount"])
        return slip, row

    def _stored(self, rows):
        rows.flush_recordset()
        self.env.cr.execute("SELECT id,amount::text,write_uid,write_date,contract_id,input_type_id FROM hr_payslip_input WHERE id=ANY(%s) ORDER BY id", (rows.ids,))
        return self.env.cr.fetchall()

    def test_actual_float_field_uses_unlimited_numeric_nullable_without_default_or_extra_rounding(self):
        model = self.case.scope["hr.payslip.input"]
        field = model._fields["amount"]
        self.assertEqual(field.type, "float")
        self.assertEqual(field.column_type, ("numeric", "numeric"))
        self.assertIs(field.get_digits(model.env), False)
        self.assertIsNone(field.default)
        self.assertFalse(field.required)
        column = inspect_input_amount_storage(self.env.cr)
        self.assertEqual(column, {"type": "numeric", "type_kind": "b", "typmod": -1,
            "not_null": False, "has_default": False})
        slip, row = self._row("12.34567890123456789")
        self.assertIsInstance(row.amount, float)
        self.assertTrue(slip._step_check_saved_input_values())
        self.assertEqual(self._stored(row)[0][1], "12.34567890123456789")

    def test_exact_sql_precision_null_zero_and_negative_survive_normal_reads_without_backfill(self):
        for literal in (None, "0", "-25.12345678901234567890123456789", "12345678901234567890.12345678901234567890"):
            slip, row = self._row(literal)
            before = self._stored(row)
            row.read(["amount", "code", "contract_id", "input_type_id"])
            row.mapped("amount")
            self.assertEqual(self._stored(row), before)
            if literal is None:
                self.assertEqual(row.amount, 0.0)
                with TestCase.assertRaisesRegex(self, UserError, "Complete the amount"):
                    slip._step_check_saved_input_values()
            else:
                self.assertTrue(slip._step_check_saved_input_values())
                self.env.cr.execute("SELECT amount FROM hr_payslip_input WHERE id=%s", (row.id,))
                self.assertEqual(self.env.cr.fetchone(), (Decimal(literal),))
            self.assertEqual(self._stored(row), before)

    def test_real_closed_fixture_and_synthetic_paid_flag_keep_numeric_bytes_under_catalog_rechecks(self):
        slip, row = self._row("123.123456789012345678901234567890")
        original = self._stored(row)
        slip.compute_sheet()
        slip.prevent_compute_on_confirm = True
        slip.action_payslip_done()
        self.assertEqual(slip.state, "done")
        self.assertTrue(slip.move_id)
        self.assertEqual(self._stored(row), original)
        # This is an own newly closed fixture, not a payment workflow. Mirror
        # the sealed upgrade fixture's explicit synthetic paid-history marker.
        self.env.cr.execute("UPDATE hr_payslip SET paid=true WHERE id=%s AND state='done' AND step_history_locked=true AND paid IS NOT TRUE", (slip.id,))
        self.assertEqual(self.env.cr.rowcount, 1)
        slip.invalidate_recordset(["paid"])
        self.assertTrue(slip.paid)
        before = self._stored(row)
        self.case.contract.wage = 1200000
        row.read(["amount"])
        first = admit_original_input_storage(self.env.cr)
        second = admit_original_input_storage(self.env.cr)
        self.assertEqual(first, second)
        self.assertFalse(first["ddl_executed"])
        self.assertFalse(first["stored_amounts_read"])
        self.assertFalse(first["code_or_contract_materialized"])
        self.assertEqual(self._stored(row), before)
        with TestCase.assertRaises(self, UserError):
            row.sudo().write({"amount": 0.0})
        self.assertEqual(self._stored(row), before)

    def test_normal_amount_acl_and_hidden_rows_remain_authoritative_with_warm_sudo_cache(self):
        slip, row = self._row("0")
        before = self._stored(row)
        row.sudo().read(["amount"])
        hidden = self.env["ir.rule"].create({"name": "Private numeric input visibility",
            "model_id": self.env["ir.model"]._get_id("hr.payslip.input"), "domain_force": "[('id','!=',%d)]" % row.id})
        with TestCase.assertRaises(self, AccessError):
            slip.sudo()._step_check_saved_input_values()
        with TestCase.assertRaises(self, AccessError):
            row.sudo().write({"amount": 0.0})
        hidden.unlink()
        with patch.object(row._fields["amount"], "groups", "base.group_system"):
            with TestCase.assertRaises(self, AccessError):
                slip.sudo()._step_check_saved_input_values()
            with TestCase.assertRaises(self, AccessError):
                row.sudo().write({"amount": 0.0})
        self.assertEqual(self._stored(row), before)

    def test_temp_float8_even_empty_and_all_other_unapproved_contracts_are_refused_without_changes(self):
        self.env.cr.execute("CREATE TEMP TABLE step_numeric_input_float (id integer PRIMARY KEY,amount double precision) ON COMMIT DROP")
        for populated in (False, True):
            if populated:
                self.env.cr.execute("INSERT INTO step_numeric_input_float VALUES (1,0.1)")
            with TestCase.assertRaisesRegex(self, InputStorageError, "existing-float8"):
                inspect_input_amount_storage(self.env.cr, ("pg_temp", "step_numeric_input_float"))
            self.env.cr.execute("SELECT typname FROM pg_attribute a JOIN pg_type t ON t.oid=a.atttypid WHERE a.attrelid='step_numeric_input_float'::regclass AND a.attname='amount'")
            self.assertEqual(self.env.cr.fetchone(), ("float8",))
        for name, definition, error in (("fixed", "numeric(16,2)", "fixed-precision"),
                ("required", "numeric NOT NULL", "nullability"), ("default", "numeric DEFAULT 0", "sql-default")):
            table = "step_numeric_input_" + name
            self.env.cr.execute("CREATE TEMP TABLE " + table + " (id integer PRIMARY KEY,amount " + definition + ") ON COMMIT DROP")
            with TestCase.assertRaisesRegex(self, InputStorageError, error):
                inspect_input_amount_storage(self.env.cr, ("pg_temp", table))
        self.env.cr.execute("SELECT amount FROM step_numeric_input_float")
        self.assertEqual(self.env.cr.fetchone(), (0.1,))

    def test_catalog_policy_is_idempotent_and_missing_tables_only_belong_to_real_cold_install(self):
        column = {"type": "numeric", "type_kind": "b", "typmod": -1, "not_null": False, "has_default": False}
        self.assertTrue(admit_input_amount_contract(column))
        for state in ("to install", "installed", "to upgrade"):
            self.assertFalse(input_amount_table_admission(state, True)["input_table_pending_orm"])
        self.assertTrue(input_amount_table_admission("to install", False)["input_table_pending_orm"])
        for state in ("installed", "to upgrade"):
            with TestCase.assertRaisesRegex(self, InputStorageError, "missing-on-upgrade"):
                input_amount_table_admission(state, False)
        for state in (None, "uninstalled", "to remove"):
            with TestCase.assertRaises(InputStorageError):
                input_amount_table_admission(state, True)
        self.assertIsNone(inspect_input_amount_storage(self.env.cr, ("pg_temp", "step_numeric_input_missing")))
        self.env.cr.execute("CREATE TEMP TABLE step_numeric_input_no_amount (id integer) ON COMMIT DROP")
        with TestCase.assertRaisesRegex(self, InputStorageError, "column-missing"):
            inspect_input_amount_storage(self.env.cr, ("pg_temp", "step_numeric_input_no_amount"))
        before = inspect_input_amount_storage(self.env.cr)
        self.assertEqual(inspect_input_amount_storage(self.env.cr), before)
