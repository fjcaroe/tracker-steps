"""Resolución, validación semántica y superficie de configuración del perfil."""

import psycopg2

from odoo.exceptions import UserError, ValidationError
from odoo.tests.common import tagged
from odoo.tools import mute_logger

from ..models import remuneration_book_adapter as adapters
from ..tools import dt_book
from .common import RemunerationBookCommon


@tagged("post_install", "-at_install")
class TestProfileResolution(RemunerationBookCommon):
    """3. Selección y ambigüedad de perfiles."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        employee = cls._create_employee("Resuelve Sintética", "12.345.678-5")
        cls._create_payslip(
            employee, cls._create_contract(employee, cls.department_admin),
            cls._coherent_values(wage=500000))

    def _clone_profile(self, code, detector=None, company=None):
        clone = self.profile.copy({
            "name": "Clon %s" % code,
            "code": code,
            "company_id": company.id if company else False,
        })
        clone.detector_rule_codes = (
            detector if detector is not None else self.profile.detector_rule_codes)
        clone.action_activate()
        return clone

    def test_explicit_profile_wins_and_is_reported_as_assigned(self):
        wizard = self._wizard()
        dataset = wizard.build_dataset()
        self.assertEqual(wizard.profile_id, self.profile)
        self.assertEqual(dataset.profile_origin, "assigned")
        self.assertEqual(dataset.profile_origin_label, "Asignado")

    def test_single_detection_is_reported_as_detected(self):
        self.company.remuneration_book_profile_id = False
        dataset = self._wizard().build_dataset()
        self.assertEqual(dataset.profile_origin, "detected")
        self.assertFalse(dataset.errors)

    def test_zero_matches_blocks_and_explains(self):
        self.company.remuneration_book_profile_id = False
        self.profile.detector_rule_codes = "NO_EXISTE_EN_ESTA_BASE"
        dataset = self._wizard().build_dataset()
        codes = [issue.code for issue in dataset.errors]
        self.assertIn("profile_not_detected", codes)
        self.assertEqual(dataset.quantity, 0)

    def test_ambiguity_blocks_instead_of_taking_the_first(self):
        self.company.remuneration_book_profile_id = False
        self._clone_profile("tst_clon_ambiguo")
        dataset = self._wizard().build_dataset()
        codes = [issue.code for issue in dataset.errors]
        self.assertIn("profile_ambiguous", codes)
        self.assertEqual(dataset.profile_origin, "unconfirmed")

    def test_detection_only_uses_codes_present_in_the_period(self):
        """Una regla que existe en la base pero no en las liquidaciones no
        puede hacer que se elija un perfil de otro motor de nómina."""
        self.company.remuneration_book_profile_id = False
        self.env["hr.salary.rule"].create({
            "name": "Regla de otro motor", "code": "TST_OTRO_MOTOR",
            "category_id": self.category.id, "struct_id": self.structure.id,
            "amount_select": "fix", "amount_fix": 0.0,
        })
        self._clone_profile("tst_otro_motor", detector="TST_OTRO_MOTOR")
        dataset = self._wizard().build_dataset()
        self.assertFalse(dataset.errors)
        self.assertEqual(dataset.profile_origin, "detected")

    def test_a_profile_of_another_company_is_never_chosen(self):
        self.company.remuneration_book_profile_id = False
        self.profile.company_id = self.other_company
        dataset = self._wizard().build_dataset()
        self.assertIn("profile_not_detected",
                      [issue.code for issue in dataset.errors])

    def test_non_active_profile_blocks(self):
        self.profile.action_back_to_draft()
        dataset = self._wizard().build_dataset()
        self.assertIn("profile_not_active",
                      [issue.code for issue in dataset.errors])

    def test_two_companies_with_different_engines(self):
        """Cada empresa resuelve su propio perfil, sin contagio."""
        other_profile = self._clone_profile(
            "tst_otra_empresa", company=self.other_company)
        self.other_company.remuneration_book_profile_id = other_profile
        self.assertEqual(self.company.remuneration_book_profile_id, self.profile)
        self.assertEqual(self.other_company.remuneration_book_profile_id,
                         other_profile)
        self.assertNotEqual(self.company.remuneration_book_profile_id,
                            self.other_company.remuneration_book_profile_id)


@tagged("post_install", "-at_install")
class TestProfileValidation(RemunerationBookCommon):
    """4. Validación semántica y 6. grafo de dependencias."""

    def _draft_clone(self, code="tst_validacion"):
        clone = self.profile.copy({
            "name": "Clon %s" % code, "code": code, "company_id": False})
        clone.action_back_to_draft()
        return clone

    def test_sql_uniqueness_of_profile_and_dt_code(self):
        clone = self._draft_clone("tst_unicidad")
        line = clone.line_ids[0]
        with self.assertRaises(psycopg2.IntegrityError), \
                mute_logger("odoo.sql_db"):
            self.env["step.remuneration.book.profile.line"].create({
                "profile_id": clone.id,
                "dt_code": line.dt_code,
                "source_type": "zero",
            })
            self.env.flush_all()

    def test_missing_required_code_blocks_activation(self):
        clone = self._draft_clone("tst_falta_codigo")
        clone.line_ids.filtered(
            lambda line: line.dt_code == dt_book.CODE_NET).unlink()
        with self.assertRaises(ValidationError):
            clone.action_activate()
        self.assertEqual(clone.state, "draft")

    def test_official_totals_cannot_be_zero(self):
        clone = self._draft_clone("tst_total_cero")
        clone.line_ids.filtered(
            lambda line: line.dt_code == dt_book.CODE_TOTAL_DEDUCTIONS
        ).write({"source_type": "zero", "rule_codes": False})
        errors = clone.validation_errors()
        self.assertTrue([error for error in errors if "5301" in error])
        with self.assertRaises(ValidationError):
            clone.action_activate()

    def test_self_reference_is_rejected(self):
        clone = self._draft_clone("tst_autoreferencia")
        clone.line_ids.filtered(
            lambda line: line.dt_code == dt_book.CODE_TOTAL_INCOME
        ).write({"source_type": "aggregate", "operand_codes": "5201",
                 "rule_codes": False})
        errors = clone.validation_errors()
        self.assertTrue([error for error in errors
                         if "se referencia a sí mismo" in error])

    def test_dependency_cycle_is_detected(self):
        clone = self._draft_clone("tst_ciclo")
        by_code = {line.dt_code: line for line in clone.line_ids}
        by_code[dt_book.CODE_TOTAL_INCOME].write({
            "source_type": "aggregate", "operand_codes": "5501",
            "rule_codes": False})
        by_code[dt_book.CODE_NET].write({
            "source_type": "difference", "operand_codes": "5201,5301",
            "rule_codes": False})
        errors = clone.validation_errors()
        self.assertTrue([error for error in errors if "ciclo" in error])

    def test_long_dependency_chain_resolves_without_fixed_passes(self):
        """Una cadena de seis agregados debe resolverse igual que una de dos."""
        clone = self._draft_clone("tst_cadena")
        by_code = {line.dt_code: line for line in clone.line_ids}
        by_code[dt_book.CODE_TOTAL_TAXABLE].write({
            "source_type": "aggregate", "operand_codes": "2101,2113,2106",
            "rule_codes": False})
        by_code[dt_book.CODE_TOTAL_INCOME].write({
            "source_type": "aggregate",
            "operand_codes": "5210,2302,2301,2311", "rule_codes": False})
        by_code[dt_book.CODE_NET].write({
            "source_type": "difference", "operand_codes": "5201,5301",
            "rule_codes": False})
        self.assertFalse(clone.validation_errors())
        clone.action_activate()
        self.assertEqual(clone.state, "active")

    def test_unresolved_dependency_blocks_instead_of_becoming_zero(self):
        clone = self._draft_clone("tst_sin_resolver")
        clone.line_ids.filtered(
            lambda line: line.dt_code == dt_book.CODE_NET
        ).write({"source_type": "difference", "operand_codes": "5201,9999",
                 "rule_codes": False})
        errors = clone.validation_errors()
        self.assertTrue([error for error in errors if "9999" in error])

    def test_editing_a_validated_profile_returns_it_to_draft(self):
        clone = self._draft_clone("tst_reedicion")
        clone.action_activate()
        self.assertEqual(clone.state, "active")
        clone.detector_rule_codes = "TST_HAB"
        self.assertEqual(clone.state, "draft")


@tagged("post_install", "-at_install")
class TestAdapters(RemunerationBookCommon):
    """5. Adaptadores permitidos y ataques de configuración rechazados."""

    def test_the_configurable_model_and_domain_no_longer_exist(self):
        fields_ = self.env["step.remuneration.book.profile.line"]._fields
        for removed in ("model_name", "model_domain", "amount_field"):
            self.assertNotIn(removed, fields_)

    def test_only_registered_adapters_can_be_selected(self):
        """La selección es cerrada: no se puede nombrar un modelo cualquiera."""
        line = self.profile.line_ids[0]
        # `assertRaises` de Odoo no admite tuplas de excepciones.
        rejected = False
        try:
            line.write({"adapter_key": "modelo_arbitrario"})
            self.env.flush_all()
        except (ValueError, ValidationError):
            rejected = True
        self.assertTrue(rejected)

    def test_unregistered_adapter_is_rejected_on_write(self):
        clone = self.profile.copy({
            "name": "Clon adaptador", "code": "tst_adaptador",
            "company_id": False})
        clone.action_back_to_draft()
        line = clone.line_ids.filtered(
            lambda line: line.dt_code == dt_book.CODE_BONUS)
        with self.assertRaises(ValidationError):
            line.write({"source_type": "adapter", "adapter_key": False})

    def test_adapter_parameter_outside_the_whitelist_is_rejected(self):
        clone = self.profile.copy({
            "name": "Clon parámetro", "code": "tst_parametro",
            "company_id": False})
        clone.action_back_to_draft()
        line = clone.line_ids.filtered(
            lambda line: line.dt_code == dt_book.CODE_BONUS)
        with self.assertRaises(ValidationError):
            line.write({
                "source_type": "adapter",
                "adapter_key": "sd_movement_type_rules",
                "adapter_param": "(1,'=',1) or True",
            })

    def test_every_adapter_declares_one_model_and_one_field(self):
        self.assertTrue(adapters.ADAPTERS)
        for key, adapter in adapters.ADAPTERS.items():
            self.assertTrue(adapter.model, key)
            self.assertTrue(adapter.amount_field, key)
            self.assertTrue(adapter.params, key)
            self.assertIsNone(adapter.check_param(adapter.allowed_params()[0]))
            self.assertIsNotNone(adapter.check_param("otro_modelo"))

    def test_missing_adapter_model_blocks_the_profile(self):
        """Si el módulo del proveedor no está, el perfil no aparenta estar listo."""
        clone = self.profile.copy({
            "name": "Clon proveedor", "code": "tst_proveedor",
            "company_id": False})
        clone.action_back_to_draft()
        clone.line_ids.filtered(
            lambda line: line.dt_code == dt_book.CODE_BONUS
        ).write({
            "source_type": "adapter",
            "adapter_key": "sd_movement_type_rules",
            "adapter_param": "bono_ok",
            "rule_codes": False,
        })
        adapter = adapters.get_adapter("sd_movement_type_rules")
        if adapter.is_installed(self.env):
            self.assertFalse(clone.validation_errors())
        else:
            errors = clone.validation_errors()
            self.assertTrue([error for error in errors
                             if adapter.model in error])
            with self.assertRaises(ValidationError):
                clone.action_activate()
