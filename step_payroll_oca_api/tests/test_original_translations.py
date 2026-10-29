"""Real OCA masters, language fallback and PostgreSQL literal conversion."""
from odoo import api, Command
from odoo.exceptions import AccessError, ValidationError
from odoo.tests import TransactionCase, tagged
from psycopg2 import sql

from ..translation_storage import (
    TranslationStorageError, _convert_literal_column, original_translation_payload,
    migrate_original_translation_storage, original_translation_table_admission, prepare_original_translation_storage,
)


@tagged("post_install", "-at_install")
class OriginalTranslationCase(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        for code in ("es_CL", "fr_FR"):
            cls.env["res.lang"]._activate_lang(code)
        company = cls.env["res.company"].create({"name": "Private translation company", "country_id": cls.env.ref("base.cl").id})
        actor = cls.env["res.users"].with_context(no_reset_password=True).create({
            "name": "Private payroll translation manager", "login": "private-payroll-translation-manager",
            "company_id": company.id, "company_ids": [Command.set(company.ids)],
            "groups_id": [Command.set([cls.env.ref(xmlid).id for xmlid in ("base.group_user", "payroll.group_payroll_manager", "hr.group_hr_manager")])]})
        cls.scope = api.Environment(cls.env.cr, actor.id, dict(cls.env.context, lang="en_US", allowed_company_ids=company.ids), su=False)
        cls.category = cls.scope["hr.salary.rule.category"].create({"name": "Private translation category", "code": "PRIVATE_TRANSLATION_CAT"})
        cls.rule = cls.scope["hr.salary.rule"].create({"name": "Private translated rule", "code": "PRIVATE_TRANSLATION_RULE",
            "category_id": cls.category.id, "struct_id": False, "condition_select": "none", "amount_select": "fix", "amount_fix": 1,
            "note": "<p>Texto original</p>"})
        cls.input_type = cls.scope["hr.payslip.input.type"].create({"name": "Etiqueta original", "code": "PRIVATE_TRANSLATION_INPUT"})

    def _raw(self, record, field):
        record.flush_recordset([field])
        self.env.cr.execute(sql.SQL("SELECT {} FROM {} WHERE id=%s").format(
            sql.Identifier(field), sql.Identifier(record._table)), (record.id,))
        return self.env.cr.fetchone()[0]

    def test_real_note_translations_and_missing_language_fallback_do_not_touch_lines(self):
        self.assertTrue(self.rule._fields["note"].translate)
        self.assertTrue(self.input_type._fields["name"].translate)
        self.assertFalse(self.scope["hr.payslip.line"]._fields["note"].translate)
        self.env.cr.execute("""SELECT table_name,data_type FROM information_schema.columns WHERE table_schema='public'
            AND column_name='note' AND table_name IN ('hr_salary_rule','hr_payslip_line') ORDER BY table_name""")
        self.assertEqual(self.env.cr.fetchall(), [("hr_payslip_line", "text"), ("hr_salary_rule", "jsonb")])
        self.rule.with_context(lang="es_CL").note = "<p>Nota chilena explícita</p>"
        stored = self._raw(self.rule, "note")
        self.assertEqual(stored["en_US"], "<p>Texto original</p>")
        self.assertEqual(stored["es_CL"], "<p>Nota chilena explícita</p>")
        self.assertEqual(self.rule.with_context(lang="fr_FR").note, "<p>Texto original</p>")
        self.assertNotIn("fr_FR", stored)
        self.assertEqual(self._raw(self.rule, "note"), stored)

    def test_original_scalar_name_plan_keeps_all_existing_community_translations(self):
        self.input_type.with_context(lang="es_CL").name = "Etiqueta chilena autorizada"
        before = self._raw(self.input_type, "name")
        audit = self.input_type.read(["id", "write_uid", "write_date"])
        self.assertEqual(self.input_type._step_original_name_translations("Etiqueta original"), before)
        self.assertEqual(self.input_type.with_context(lang="fr_FR").name, "Etiqueta original")
        self.assertNotIn("fr_FR", before)
        self.assertEqual(self._raw(self.input_type, "name"), before)
        self.assertEqual(self.input_type.read(["id", "write_uid", "write_date"]), audit)

    def test_original_null_and_conflicting_values_never_clear_or_replace_masters(self):
        before = self._raw(self.rule, "note"), self._raw(self.input_type, "name")
        with self.assertRaises(ValidationError):
            self.rule._step_original_note_translations(None)
        with self.assertRaises(ValidationError):
            self.input_type._step_original_name_translations("Otro literal")
        self.assertEqual((self._raw(self.rule, "note"), self._raw(self.input_type, "name")), before)
        empty = self.scope["hr.salary.rule"].create({"name": "Private null note", "code": "PRIVATE_NULL_NOTE",
            "category_id": self.category.id, "struct_id": False, "condition_select": "none", "amount_select": "fix"})
        self.assertIsNone(empty._step_original_note_translations(None))
        self.assertFalse(empty.note)
        self.assertIsNone(self._raw(empty, "note"))
        literal = '{"es_CL":"literal, no traducción"}'
        self.assertEqual(original_translation_payload(literal), {"en_US": literal})
        self.assertEqual(original_translation_payload(""), {"en_US": ""})
        for invalid in (False, 1, [], {"es_CL": "sin base"}):
            with self.assertRaises(TranslationStorageError):
                original_translation_payload(invalid)

    def test_preparation_requires_normal_record_access_with_warm_cache(self):
        self.rule.read(["note"])
        self.input_type.read(["name"])
        for record, model_xmlid, method, source in (
                (self.rule, "payroll.model_hr_salary_rule", "_step_original_note_translations", "<p>Texto original</p>"),
                (self.input_type, "step_payroll_oca_api.model_hr_payslip_input_type", "_step_original_name_translations", "Etiqueta original")):
            hidden = self.env["ir.rule"].create({"name": "Private hidden translation master", "model_id": self.env.ref(model_xmlid).id,
                "domain_force": "[('id','!=',%d)]" % record.id})
            with self.assertRaises(AccessError):
                getattr(record, method)(source)
            hidden.unlink()

    def test_postgresql_legacy_text_conversion_preserves_literal_null_and_empty_values(self):
        self.env.cr.execute("CREATE TEMP TABLE step_literal_translation_test (id integer PRIMARY KEY,note text,name varchar NOT NULL) ON COMMIT DROP")
        values = [(1, None, "Original"), (2, "", ""), (3, '<p>Literal &amp; ñ</p>', '{"fr_FR":"texto literal"}')]
        self.env.cr.executemany("INSERT INTO step_literal_translation_test VALUES (%s,%s,%s)", values)
        first = _convert_literal_column(self.env.cr, "step_literal_translation_test", "note")
        name = _convert_literal_column(self.env.cr, "step_literal_translation_test", "name")
        self.assertTrue(first["converted"])
        self.assertTrue(name["converted"])
        self.env.cr.execute("SELECT id,note,name FROM step_literal_translation_test ORDER BY id")
        self.assertEqual(self.env.cr.fetchall(), [(ident, None if note is None else {"en_US": note}, {"en_US": label}) for ident, note, label in values])
        again = _convert_literal_column(self.env.cr, "step_literal_translation_test", "note")
        self.assertFalse(again["converted"])
        self.assertEqual(again["literal_projection_sha256"], first["literal_projection_sha256"])
        self.env.cr.execute("SELECT attnotnull FROM pg_attribute WHERE attrelid='step_literal_translation_test'::regclass AND attname='name'")
        self.assertTrue(self.env.cr.fetchone()[0])

    def test_real_json_columns_are_idempotent_and_existing_language_objects_remain_exact(self):
        self.input_type.with_context(lang="es_CL").name = "Nombre explícito"
        self.rule.with_context(lang="es_CL").note = "<p>Nota explícita</p>"
        before = self._raw(self.rule, "note"), self._raw(self.input_type, "name")
        audit = self.rule.read(["id", "write_uid", "write_date"]), self.input_type.read(["id", "write_uid", "write_date"])
        first = prepare_original_translation_storage(self.env.cr)
        second = prepare_original_translation_storage(self.env.cr)
        self.assertEqual(first, second)
        self.assertEqual(migrate_original_translation_storage(self.env.cr), first)
        self.assertTrue(all(not value["converted"] for value in first["columns"].values()))
        self.assertFalse(first["historical_lines_changed"])
        self.assertEqual((self._raw(self.rule, "note"), self._raw(self.input_type, "name")), before)
        self.assertEqual((self.rule.read(["id", "write_uid", "write_date"]), self.input_type.read(["id", "write_uid", "write_date"])), audit)

    def test_cold_input_table_admission_never_hides_a_missing_upgrade_table(self):
        # Pure admission over the same facts queried from PostgreSQL: no real
        # application table is dropped or renamed to manufacture this scenario.
        cold = original_translation_table_admission("to install", {"hr_salary_rule"})
        self.assertEqual(cold, {"existing_tables": ["hr_salary_rule"], "input_table_pending_orm": True})
        complete = {"hr_salary_rule", "hr_payslip_input_type"}
        for state in ("to install", "installed", "to upgrade"):
            self.assertFalse(original_translation_table_admission(state, complete)["input_table_pending_orm"])
        for state in ("installed", "to upgrade"):
            with self.assertRaisesRegex(TranslationStorageError, "missing-on-upgrade"):
                original_translation_table_admission(state, {"hr_salary_rule"})
        with self.assertRaisesRegex(TranslationStorageError, "actual-oca-rule-table-required"):
            original_translation_table_admission("to install", set())
        for state in (None, "uninstalled", "to remove"):
            with self.assertRaisesRegex(TranslationStorageError, "state-not-admitted"):
                original_translation_table_admission(state, complete)
