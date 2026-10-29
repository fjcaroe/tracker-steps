"""Regression contracts for narrowly admitted metadata, including translations."""
from copy import deepcopy
from unittest import TestCase, main
from unittest.mock import patch

from hr_consumer_metadata import EXPECTED, MODEL, PREVIOUS, source_contract, verify


class ConsumerMetadataCase(TestCase):
    def setUp(self):
        self.before = [{"id": ident, "model": MODEL, "name": name, "ttype": "boolean" if name == "confirm" else "many2many",
                        "required": False, "modules": "steps_hr_payroll_correction",
                        **{prop: {"en_US": text, "es_CL": "Referencia conservada " + name + prop}
                           for prop, text in properties.items()}}
                       for ident, (name, properties) in enumerate(PREVIOUS.items(), 20)]
        self.before.append({"id": 99, "model": "hr.employee", "name": "name", "ttype": "char", "required": True})
        self.after = deepcopy(self.before)
        for row in self.after:
            if row["model"] == MODEL:
                for prop, text in EXPECTED[row["name"]].items():
                    row[prop]["en_US"] = text

    def test_exact_source_messages_preserve_all_original_properties_and_other_languages(self):
        audit = verify({"ir_model_fields": self.before}, {"ir_model_fields": self.after})
        self.assertEqual(len(audit["fields"]), 3)
        self.assertEqual(audit["original_field_count"], 4)
        self.assertEqual(audit["source"]["messages"], EXPECTED)
        for row in audit["fields"]:
            for prop in row["properties"]:
                self.assertEqual(row["before"][prop]["es_CL"], row["after"][prop]["es_CL"])

    def test_already_upgraded_metadata_is_idempotent(self):
        self.assertEqual(len(verify(self.after, self.after)["fields"]), 3)

    def test_unexpected_original_message_is_not_licensed_for_replacement(self):
        self.before[0]["help"]["en_US"] = "Unapproved custom help"
        with self.assertRaises(AssertionError):
            verify(self.before, self.after)

    def test_changed_removed_or_added_translation_is_rejected(self):
        for operation in (lambda data: data[0]["help"].update(es_CL="Changed"),
                          lambda data: data[0]["help"].pop("es_CL"),
                          lambda data: data[0]["help"].update(fr_FR="Added")):
            with self.subTest(operation=operation):
                changed = deepcopy(self.after)
                operation(changed)
                with self.assertRaises(AssertionError):
                    verify(self.before, changed)

    def test_other_field_properties_and_ids_remain_exact(self):
        for index, prop, value in ((0, "required", True), (1, "ttype", "char"), (2, "modules", "another_owner"),
                                  (0, "id", 777), (3, "name", "changed")):
            with self.subTest(property=prop):
                changed = deepcopy(self.after)
                changed[index][prop] = value
                with self.assertRaises(AssertionError):
                    verify(self.before, changed)

    def test_duplicate_ids_and_missing_original_fields_are_rejected(self):
        with self.assertRaises(AssertionError):
            verify(self.before, self.after + [self.after[0]])
        with self.assertRaises(AssertionError):
            verify(self.before, self.after[1:])
        with self.assertRaises(AssertionError):
            verify(self.before, self.after + [dict(self.after[0], id=777)])

    def test_existing_source_language_must_match_the_declared_new_literal(self):
        changed = deepcopy(self.after)
        changed[1]["field_description"]["en_US"] = "Some presentation difference"
        with self.assertRaises(AssertionError):
            verify(self.before, changed)

    def test_declared_allowlist_cannot_drift_from_source_ast(self):
        changed = deepcopy(EXPECTED)
        changed["confirm"]["help"] = "Undeclared helper text"
        with patch("hr_consumer_metadata.EXPECTED", changed):
            with self.assertRaises(AssertionError):
                source_contract()


if __name__ == "__main__":
    main()
