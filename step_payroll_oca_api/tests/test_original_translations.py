"""Real OCA masters, language fallback and PostgreSQL literal conversion."""
import json
from unittest.mock import patch

from odoo import api, Command
from odoo.exceptions import AccessError, ValidationError
from odoo.tests import TransactionCase, tagged
from psycopg2 import sql

from .. import translation_storage
from ..translation_storage import (
    TranslationStorageError, _convert_input_name_column, _convert_literal_column,
    original_input_name_literal, original_translation_payload,
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
        self.assertFalse(self.input_type._fields["name"].translate)
        self.assertFalse(self.scope["hr.payslip.line"]._fields["note"].translate)
        self.env.cr.execute("""SELECT table_name,data_type FROM information_schema.columns WHERE table_schema='public'
            AND column_name='note' AND table_name IN ('hr_salary_rule','hr_payslip_line') ORDER BY table_name""")
        self.assertEqual(self.env.cr.fetchall(), [("hr_payslip_line", "text"), ("hr_salary_rule", "jsonb")])
        self.env.cr.execute("SELECT data_type FROM information_schema.columns WHERE table_schema='public' AND table_name='hr_payslip_input_type' AND column_name='name'")
        self.assertEqual(self.env.cr.fetchone(), ("character varying",))
        # Sanitized Html uses a callable term translator in official Odoo.
        # Its ordinary write edits the source; authorized translations use the
        # actual public API with source terms, not a language-only setter.
        self.rule.update_field_translations("note", {
            "es_CL": {"Texto original": "Nota chilena explícita"}}, source_lang="en_US")
        stored = self._raw(self.rule, "note")
        self.assertEqual(stored["en_US"], "<p>Texto original</p>")
        self.assertEqual(stored["es_CL"], "<p>Nota chilena explícita</p>")
        self.assertEqual(self.rule.with_context(lang="fr_FR").note, "<p>Texto original</p>")
        self.assertNotIn("fr_FR", stored)
        self.assertEqual(self._raw(self.rule, "note"), stored)

    def test_original_scalar_name_plan_is_one_literal_in_every_language(self):
        before = self._raw(self.input_type, "name")
        audit = self.input_type.read(["id", "write_uid", "write_date"])
        self.assertEqual(before, "Etiqueta original")
        self.assertEqual(self.input_type._step_original_name_literal(before), before)
        self.assertEqual(self.input_type._step_original_name_literal({"en_US": before}), before)
        self.assertEqual(self.input_type._step_original_name_translations("Etiqueta original"), before)
        self.assertEqual(self.input_type.with_context(lang="fr_FR").name, "Etiqueta original")
        self.assertEqual(self.input_type.with_context(lang="es_CL").name, "Etiqueta original")
        self.assertEqual(self._raw(self.input_type, "name"), before)
        self.assertEqual(self.input_type.read(["id", "write_uid", "write_date"]), audit)
        for values in ({"en_US": before, "es_CL": before}, {"en_US": before, "es_CL": "Otro idioma"}):
            with self.assertRaises(ValidationError):
                self.input_type._step_original_name_literal(values)
            with self.assertRaises(ValidationError):
                self.input_type._step_original_name_translations(values)
        # A normal write from another language updates the one real literal;
        # no invisible JSON language slot is introduced by the ORM.
        self.input_type.with_context(lang="es_CL").name = "Nombre único autorizado"
        self.assertEqual(self.input_type.with_context(lang="en_US").name, "Nombre único autorizado")
        self.assertEqual(self._raw(self.input_type, "name"), "Nombre único autorizado")

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
                (self.input_type, "step_payroll_oca_api.model_hr_payslip_input_type", "_step_original_name_translations", "Etiqueta original"),
                (self.input_type, "step_payroll_oca_api.model_hr_payslip_input_type", "_step_original_name_literal", "Etiqueta original")):
            hidden = self.env["ir.rule"].create({"name": "Private hidden translation master", "model_id": self.env.ref(model_xmlid).id,
                "domain_force": "[('id','!=',%d)]" % record.id})
            with self.assertRaises(AccessError):
                getattr(record.sudo() if record._name == "hr.payslip.input.type" else record, method)(source)
            hidden.unlink()
        with patch.object(self.input_type._fields["name"], "groups", "base.group_system"):
            for method in ("_step_original_name_literal", "_step_original_name_translations"):
                with self.assertRaises(AccessError):
                    getattr(self.input_type.sudo(), method)("Etiqueta original")

    def test_postgresql_legacy_text_conversion_preserves_literal_null_and_empty_values(self):
        self.env.cr.execute("CREATE TEMP TABLE step_literal_translation_test (id integer PRIMARY KEY,note text,name varchar NOT NULL) ON COMMIT DROP")
        values = [(1, None, "Original"), (2, "", ""), (3, '<p>Literal &amp; ñ</p>', '{"fr_FR":"texto literal"}')]
        self.env.cr.executemany("INSERT INTO step_literal_translation_test VALUES (%s,%s,%s)", values)
        first = _convert_literal_column(self.env.cr, "step_literal_translation_test", "note")
        name = _convert_input_name_column(self.env.cr, "step_literal_translation_test")
        self.assertTrue(first["converted"])
        self.assertFalse(name["converted"])
        self.env.cr.execute("SELECT id,note,name FROM step_literal_translation_test ORDER BY id")
        self.assertEqual(self.env.cr.fetchall(), [(ident, None if note is None else {"en_US": note}, label) for ident, note, label in values])
        again = _convert_literal_column(self.env.cr, "step_literal_translation_test", "note")
        self.assertFalse(again["converted"])
        self.assertEqual(again["literal_projection_sha256"], first["literal_projection_sha256"])
        self.env.cr.execute("SELECT attnotnull FROM pg_attribute WHERE attrelid='step_literal_translation_test'::regclass AND attname='name'")
        self.assertTrue(self.env.cr.fetchone()[0])

    def test_real_json_columns_are_idempotent_and_existing_language_objects_remain_exact(self):
        self.rule.update_field_translations("note", {
            "es_CL": {"Texto original": "Nota explícita"}}, source_lang="en_US")
        before = self._raw(self.rule, "note"), self._raw(self.input_type, "name")
        self.assertEqual(before[0]["en_US"], "<p>Texto original</p>")
        self.assertEqual(before[0]["es_CL"], "<p>Nota explícita</p>")
        audit = self.rule.read(["id", "write_uid", "write_date"]), self.input_type.read(["id", "write_uid", "write_date"])
        first = prepare_original_translation_storage(self.env.cr)
        second = prepare_original_translation_storage(self.env.cr)
        self.assertEqual(first, second)
        self.assertEqual(migrate_original_translation_storage(self.env.cr), first)
        self.assertTrue(all(not value["converted"] for value in first["columns"].values()))
        self.assertFalse(first["historical_lines_changed"])
        self.assertEqual((self._raw(self.rule, "note"), self._raw(self.input_type, "name")), before)
        self.assertEqual((self.rule.read(["id", "write_uid", "write_date"]), self.input_type.read(["id", "write_uid", "write_date"])), audit)

    def test_literal_input_name_payload_rejects_extra_languages_and_conflicts(self):
        for value in (None, "", "Texto literal ñ & <tag>", '{"fr_FR":"literal, no traducción"}'):
            self.assertEqual(original_input_name_literal(value), value)
            self.assertEqual(original_input_name_literal(value, existing=value), value)
            if value is not None:
                self.assertEqual(original_input_name_literal({"en_US": value}, existing=value), value)
        invalid = (False, True, 0, [], {}, {"es_CL": "sin base"}, {"en_US": None},
            {"en_US": False}, {"en_US": "igual", "es_CL": "igual"}, {"en_US": "base", "fr_FR": "traducción"})
        for value in invalid:
            with self.assertRaises(TranslationStorageError):
                original_input_name_literal(value)
        for source, current in ((None, ""), ("", None), ("nuevo", "original")):
            with self.assertRaises(TranslationStorageError):
                original_input_name_literal(source, existing=current)

    def test_postgresql_input_name_json_to_scalar_preserves_ids_null_empty_and_unicode(self):
        self.env.cr.execute("CREATE TEMP TABLE step_input_name_json_test (id integer PRIMARY KEY,name jsonb,marker varchar) ON COMMIT DROP")
        rows = [(1, None, "a"), (2, {"en_US": ""}, "b"),
            (3, {"en_US": "Literal ñ & <tag>"}, "c"), (4, {"en_US": '{"fr_FR":"texto literal"}'}, "d")]
        self.env.cr.executemany("INSERT INTO step_input_name_json_test VALUES (%s,%s::jsonb,%s)",
            [(ident, None if value is None else json.dumps(value), marker) for ident, value, marker in rows])
        before = [(ident, None if value is None else value["en_US"], marker) for ident, value, marker in rows]
        first = _convert_input_name_column(self.env.cr, "step_input_name_json_test")
        self.assertTrue(first["converted"])
        self.assertEqual(first["source_type"], "jsonb")
        self.assertEqual(first["target_type"], "varchar")
        self.assertFalse(first["extra_languages_discarded"])
        self.env.cr.execute("SELECT id,name,marker FROM step_input_name_json_test ORDER BY id")
        self.assertEqual(self.env.cr.fetchall(), before)
        again = _convert_input_name_column(self.env.cr, "step_input_name_json_test")
        self.assertFalse(again["converted"])
        self.assertEqual(again["literal_projection_sha256"], first["literal_projection_sha256"])
        self.env.cr.execute("SELECT attnotnull,atthasdef FROM pg_attribute WHERE attrelid='step_input_name_json_test'::regclass AND attname='name'")
        self.assertEqual(self.env.cr.fetchone(), (False, False))
        self.env.cr.execute("CREATE TEMP TABLE step_input_name_required_test (id integer PRIMARY KEY,name jsonb NOT NULL) ON COMMIT DROP")
        self.env.cr.execute("INSERT INTO step_input_name_required_test VALUES (1,%s::jsonb)", (json.dumps({"en_US": "Required"}),))
        _convert_input_name_column(self.env.cr, "step_input_name_required_test")
        self.env.cr.execute("SELECT attnotnull FROM pg_attribute WHERE attrelid='step_input_name_required_test'::regclass AND attname='name'")
        self.assertEqual(self.env.cr.fetchone(), (True,))
        self.env.cr.execute("CREATE TEMP TABLE step_input_name_text_test (id integer PRIMARY KEY,name text) ON COMMIT DROP")
        self.env.cr.execute("INSERT INTO step_input_name_text_test VALUES (1,NULL),(2,''),(3,%s)", ('{"fr_FR":"literal"}',))
        converted = _convert_input_name_column(self.env.cr, "step_input_name_text_test")
        self.assertTrue(converted["converted"])
        self.assertEqual(converted["source_type"], "text")
        self.env.cr.execute("SELECT id,name FROM step_input_name_text_test ORDER BY id")
        self.assertEqual(self.env.cr.fetchall(), [(1, None), (2, ""), (3, '{"fr_FR":"literal"}')])

    def test_postgresql_input_name_extra_languages_malformed_json_and_defaults_abort_without_ddl(self):
        self.env.cr.execute("CREATE TEMP TABLE step_input_name_reject_test (id integer PRIMARY KEY,name jsonb,marker varchar) ON COMMIT DROP")
        self.env.cr.execute("INSERT INTO step_input_name_reject_test VALUES (1,%s::jsonb,'preserved')", (json.dumps({"en_US": "Valid"}),))
        invalid = (None, False, True, 12, "scalar", [], {}, {"es_CL": "sin base"},
            {"en_US": None}, {"en_US": 5}, {"en_US": "same", "es_CL": "same"},
            {"en_US": "base", "fr_FR": "translated"})
        for value in invalid:
            self.env.cr.execute("INSERT INTO step_input_name_reject_test VALUES (2,%s::jsonb,'invalid')", (json.dumps(value),))
            self.env.cr.execute("SELECT id,name,marker FROM step_input_name_reject_test ORDER BY id")
            before = self.env.cr.fetchall()
            with self.assertRaises(TranslationStorageError):
                _convert_input_name_column(self.env.cr, "step_input_name_reject_test")
            self.env.cr.execute("SELECT id,name,marker FROM step_input_name_reject_test ORDER BY id")
            self.assertEqual(self.env.cr.fetchall(), before)
            self.env.cr.execute("SELECT typname FROM pg_attribute a JOIN pg_type t ON t.oid=a.atttypid WHERE a.attrelid='step_input_name_reject_test'::regclass AND a.attname='name'")
            self.assertEqual(self.env.cr.fetchone(), ("jsonb",))
            self.env.cr.execute("DELETE FROM step_input_name_reject_test WHERE id=2")
        self.env.cr.execute("ALTER TABLE step_input_name_reject_test ALTER COLUMN name SET DEFAULT '{}'::jsonb")
        with self.assertRaisesRegex(TranslationStorageError, "sql-default"):
            _convert_input_name_column(self.env.cr, "step_input_name_reject_test")
        self.env.cr.execute("SELECT atthasdef FROM pg_attribute WHERE attrelid='step_input_name_reject_test'::regclass AND attname='name'")
        self.assertEqual(self.env.cr.fetchone(), (True,))
        self.env.cr.execute("SELECT id,name,marker FROM step_input_name_reject_test ORDER BY id")
        self.assertEqual(self.env.cr.fetchall(), [(1, {"en_US": "Valid"}, "preserved")])
        self.env.cr.execute("CREATE TEMP TABLE step_input_name_default_test (id integer PRIMARY KEY,name varchar DEFAULT 'not approved') ON COMMIT DROP")
        self.env.cr.execute("INSERT INTO step_input_name_default_test VALUES (1,'Original')")
        with self.assertRaisesRegex(TranslationStorageError, "sql-default"):
            _convert_input_name_column(self.env.cr, "step_input_name_default_test")
        self.env.cr.execute("SELECT name FROM step_input_name_default_test")
        self.assertEqual(self.env.cr.fetchone(), ("Original",))
        self.env.cr.execute("CREATE TEMP TABLE step_input_name_rollback_test (id integer PRIMARY KEY,name jsonb) ON COMMIT DROP")
        self.env.cr.execute("INSERT INTO step_input_name_rollback_test VALUES (1,%s::jsonb)", (json.dumps({"en_US": "Original"}),))
        # A caller may catch a verification failure. Exercise the actual DDL
        # and queries; inject only a late fingerprint mismatch, never a result
        # for the payroll provider or the stored name values.
        real_projection = translation_storage._input_name_projection
        def mismatched_projection(cursor, table, translated):
            count, fingerprint = real_projection(cursor, table, translated)
            return count, fingerprint if translated else "unexpected-fingerprint"
        with patch.object(translation_storage, "_input_name_projection", side_effect=mismatched_projection):
            with self.assertRaisesRegex(TranslationStorageError, "literal-projection-changed"):
                _convert_input_name_column(self.env.cr, "step_input_name_rollback_test")
        self.env.cr.execute("SELECT typname FROM pg_attribute a JOIN pg_type t ON t.oid=a.atttypid WHERE a.attrelid='step_input_name_rollback_test'::regclass AND attname='name'")
        self.assertEqual(self.env.cr.fetchone(), ("jsonb",))
        self.env.cr.execute("SELECT id,name FROM step_input_name_rollback_test")
        self.assertEqual(self.env.cr.fetchall(), [(1, {"en_US": "Original"})])

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
