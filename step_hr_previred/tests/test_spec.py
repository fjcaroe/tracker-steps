"""Pruebas de la especificación: 105 campos, tipos, tablas y render.

Corresponde al caso 7 (RUT con K, ceros, acentos, montos y fechas límite) y al
caso 8 (campo obligatorio ausente, código inválido, período manipulado).
"""

from odoo.tests.common import tagged  # noqa: F401
from odoo.tests.common import TransactionCase

from ..tools import previred
from .common import make_row


@tagged("post_install", "-at_install")
class TestSpec(TransactionCase):

    def test_field_table_has_105_entries(self):
        self.assertEqual(len(previred.FIELD_NAMES), 105)
        self.assertEqual(previred.FIELD_COUNT, 105)

    def test_valid_row_has_no_issues(self):
        self.assertEqual(previred.validate_row(make_row()), [])

    def test_missing_field_is_rejected(self):
        """La especificación prohíbe omitir cualquiera de los 105 campos."""
        row = make_row()[:-1]
        codes = [issue.code for issue in previred.validate_row(row)]
        self.assertIn("field_count", codes)

    def test_missing_mandatory_value_is_rejected(self):
        row = make_row(overrides={previred.F_SEX: ""})
        codes = [issue.code for issue in previred.validate_row(row)]
        self.assertIn("missing_mandatory", codes)

    def test_invalid_code_is_rejected(self):
        for position, value, code in (
                (previred.F_SEX, "X", "bad_sex"),
                (previred.F_FAMILY_BRACKET, "Z", "bad_family_bracket"),
                (previred.F_LINE_TYPE, "99", "bad_line_type"),
                (previred.F_PENSION_REGIME, "XXX", "bad_pension_regime")):
            row = make_row(overrides={position: value})
            codes = [issue.code for issue in previred.validate_row(row)]
            self.assertIn(code, codes, "campo %d" % position)

    def test_manipulated_period_is_rejected(self):
        for value in ("2026-08", "132026", "0820261", "agosto"):
            row = make_row(overrides={previred.F_PERIOD_FROM: value})
            codes = [issue.code for issue in previred.validate_row(row)]
            self.assertIn("bad_period", codes, value)

    def test_worked_days_upper_bound(self):
        self.assertEqual(
            previred.validate_row(
                make_row(overrides={previred.F_WORKED_DAYS: "30"})), [])
        codes = [issue.code for issue in previred.validate_row(
            make_row(overrides={previred.F_WORKED_DAYS: "31"}))]
        self.assertIn("worked_days_range", codes)

    def test_amounts_must_be_integers(self):
        """Previred exige enteros sin decimales en los campos numéricos."""
        codes = [issue.code for issue in previred.validate_row(
            make_row(overrides={previred.F_AFP_TAXABLE: "1234567.89"}))]
        self.assertIn("not_numeric", codes)
        codes = [issue.code for issue in previred.validate_row(
            make_row(overrides={previred.F_AFP_TAXABLE: "-500"}))]
        self.assertIn("not_numeric", codes)
        self.assertEqual(previred.validate_row(
            make_row(overrides={previred.F_AFP_TAXABLE: "1234567"})), [])

    def test_separator_inside_a_value_is_rejected(self):
        """Un «;» dentro de un valor desplazaría todos los campos siguientes."""
        codes = [issue.code for issue in previred.validate_row(
            make_row(last_name="PEREZ;SOTO"))]
        self.assertIn("separator_in_value", codes)

    def test_cost_center_length(self):
        codes = [issue.code for issue in previred.validate_row(
            make_row(cost_center="X" * 21))]
        self.assertIn("cost_center_length", codes)
        self.assertEqual(previred.validate_row(
            make_row(cost_center="X" * 20)), [])

    # -- RUT -----------------------------------------------------------------

    def test_rut_with_k_sorts_and_matches(self):
        """El DV «K» debe compararse y ordenarse, nunca reescribirse."""
        self.assertEqual(previred.rut_key("9.999.999-K"),
                         previred.rut_key("9999999K"))
        self.assertEqual(previred.rut_key("9999999k"),
                         previred.rut_key("9999999K"))
        # 9.999.999 va antes que 10.000.000 aunque como texto sea al revés.
        self.assertLess(previred.rut_key("9999999K"),
                        previred.rut_key("100000001"))

    def test_rut_leading_zeros_are_preserved_in_the_file(self):
        """La normalización es sólo para comparar: el archivo lleva el original."""
        row = make_row(rut="00123456", dv="7")
        text = previred.render_rows([row])
        self.assertTrue(text.startswith("00123456;7;"))

    def test_accents_are_transliterated(self):
        self.assertEqual(previred.strip_accents("MUÑOZ ÁVILA"), "MUNOZ AVILA")
        self.assertEqual(previred.strip_accents(""), "")

    # -- render --------------------------------------------------------------

    def test_render_uses_semicolon_and_crlf_without_trailing_newline(self):
        text = previred.render_rows([make_row(), make_row(rut="8888888")])
        self.assertEqual(text.count("\r\n"), 1)
        self.assertFalse(text.endswith("\r\n"))
        self.assertEqual(len(text.split("\r\n")[0].split(";")), 105)

    def test_output_has_no_bom(self):
        data = previred.txt_bytes(previred.render_rows([make_row()]))
        self.assertFalse(data.startswith(b"\xef\xbb\xbf"))
        self.assertFalse(previred.USE_BOM)

    # -- nombres de archivo --------------------------------------------------

    def test_filenames_are_safe_and_deterministic(self):
        name = previred.txt_filename("76.123.456-7", "202608", "Agrícola/../x")
        self.assertEqual(name, "PREVIRED_761234567_202608_AGRICOLA_X.txt")
        for forbidden in ("/", "\\", "..", " "):
            self.assertNotIn(forbidden, name)
        self.assertEqual(name, previred.txt_filename(
            "76.123.456-7", "202608", "Agrícola/../x"))

    def test_company_rut_separators_are_stripped_not_replaced(self):
        """«76.123.456-7» debe quedar «761234567», no «76_123_456_7»."""
        self.assertEqual(previred.vat_code("76.123.456-7"), "761234567")
        self.assertEqual(previred.vat_code("CL 76.123.456-7"), "CL761234567")
        self.assertEqual(previred.vat_code(""), "EMPRESA")

    def test_filename_without_department_is_the_consolidated_one(self):
        self.assertEqual(previred.txt_filename("761234567", "202608"),
                         "PREVIRED_761234567_202608.txt")

    # -- condicionales de las líneas anexas (condición 1 del encargo) --------

    def test_annex_01_without_movement_is_rejected(self):
        """Una línea 01 existe para informar un movimiento: sin él sobra."""
        row = make_row(line_type=previred.LINE_ADDITIONAL,
                       overrides={previred.F_MOVEMENT_CODE: "0"})
        codes = [issue.code
                 for issue in previred.validate_annex_conditions(row)]
        self.assertIn("annex_without_movement", codes)

    def test_movement_requiring_dates_is_enforced(self):
        """Los movimientos 1,3,4,5,6,7,8,11 exigen fecha desde y hasta."""
        for code in ("1", "3", "5", "7", "11"):
            row = make_row(
                line_type=previred.LINE_ADDITIONAL,
                overrides={previred.F_MOVEMENT_CODE: code,
                           previred.F_MOVEMENT_FROM: "00/00/0000",
                           previred.F_MOVEMENT_TO: "00/00/0000"})
            codes = [issue.code
                     for issue in previred.validate_annex_conditions(row)]
            self.assertIn("movement_date_from_required", codes, code)
            self.assertIn("movement_date_to_required", codes, code)

    def test_movement_with_dates_passes(self):
        row = make_row(
            line_type=previred.LINE_ADDITIONAL,
            overrides={previred.F_MOVEMENT_CODE: "3",
                       previred.F_MOVEMENT_FROM: "01-08-2026",
                       previred.F_MOVEMENT_TO: "15-08-2026"})
        self.assertEqual(previred.validate_annex_conditions(row), [])

    def test_movement_without_dates_is_fine_when_none_declared(self):
        """El movimiento «0» (sin movimiento) no exige fechas."""
        row = make_row(overrides={previred.F_MOVEMENT_CODE: "0"})
        self.assertEqual(previred.validate_annex_conditions(row), [])

    def test_voluntary_line_requires_its_own_rut(self):
        """La línea 03 sólo informa al afiliado voluntario, y debe hacerlo."""
        row = make_row(line_type=previred.LINE_VOLUNTARY,
                       overrides={previred.F_MOVEMENT_CODE: "10"})
        codes = [issue.code
                 for issue in previred.validate_annex_conditions(row)]
        self.assertIn("voluntary_rut_missing", codes)

    def test_voluntary_line_only_admits_movement_10(self):
        row = make_row(line_type=previred.LINE_VOLUNTARY,
                       overrides={previred.F_MOVEMENT_CODE: "3",
                                  previred.F_VOLUNTARY_RUT: "12345678"})
        codes = [issue.code
                 for issue in previred.validate_annex_conditions(row)]
        self.assertIn("voluntary_movement_code", codes)

    def test_valid_voluntary_line_passes(self):
        row = make_row(line_type=previred.LINE_VOLUNTARY,
                       overrides={previred.F_MOVEMENT_CODE: "10",
                                  previred.F_VOLUNTARY_RUT: "12345678"})
        self.assertEqual(previred.validate_annex_conditions(row), [])

    # -- normalización del tipo de línea -------------------------------------

    def test_single_digit_line_type_is_normalized_for_comparison(self):
        """SimpleDigital emite «0» donde la tabla N°6 dice «00»."""
        self.assertEqual(previred.normalize_line_type("0"), "00")
        self.assertEqual(previred.normalize_line_type("1"), "01")
        self.assertEqual(previred.normalize_line_type("00"), "00")
        self.assertEqual(previred.normalize_line_type(""), "")

    def test_single_digit_line_type_is_accepted_by_the_validator(self):
        self.assertEqual(
            previred.validate_row(make_row(line_type="0")), [])

    def test_single_digit_line_type_is_written_canonically(self):
        fields = previred.render_rows(
            [make_row(line_type="0")]).split(";")
        self.assertEqual(fields[previred.F_LINE_TYPE - 1], "00")

    def test_workday_type_only_accepts_official_table(self):
        codes = [issue.code for issue in previred.validate_row(
            make_row(overrides={previred.F_WORKDAY_TYPE: "0"}))]
        self.assertIn("bad_workday_type", codes)

    def test_reform_rate_schedule(self):
        self.assertEqual(previred.life_expectancy_rate("202607"), "0.90")
        self.assertEqual(previred.life_expectancy_rate("202608"), "1.00")
        self.assertEqual(previred.protected_return_rate("202607"), "0")
        self.assertEqual(previred.protected_return_rate("202608"), "0.90")
        self.assertEqual(previred.protected_return_rate("202708"), "1.50")
        self.assertEqual(previred.protected_return_rate("204509"), "1.35")
        self.assertEqual(previred.protected_return_rate("205409"), "0")
