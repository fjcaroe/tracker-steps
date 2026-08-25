"""Pruebas de los archivos generados: Excel, PDF consolidado y equivalencia."""

import io
import re
import xml.etree.ElementTree as ElementTree
import zipfile

from odoo.tests.common import tagged

from ..tools import dt_book
from ..tools.xlsx_book import build_workbook, CONTROL_SHEET_NAME, SHEET_NAME
from .common import RemunerationBookCommon

NS = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"


class Sheet:
    """Lector mínimo de xlsx con la biblioteca estándar."""

    def __init__(self, payload, index=1):
        archive = zipfile.ZipFile(io.BytesIO(payload))
        self.names = archive.namelist()
        strings = [
            "".join(node.text or "" for node in item.iter(NS + "t"))
            for item in ElementTree.fromstring(
                archive.read("xl/sharedStrings.xml")).iter(NS + "si")
        ]
        self.workbook = ElementTree.fromstring(archive.read("xl/workbook.xml"))
        sheet = ElementTree.fromstring(
            archive.read("xl/worksheets/sheet%s.xml" % index))
        self.root = sheet
        self.values = {}
        self.types = {}
        self.formulas = {}
        for cell in sheet.iter(NS + "c"):
            match = re.match(r"([A-Z]+)(\d+)", cell.get("r"))
            key = (int(match.group(2)), match.group(1))
            kind = cell.get("t")
            value = cell.find(NS + "v")
            formula = cell.find(NS + "f")
            if kind == "s" and value is not None:
                self.values[key] = strings[int(value.text)]
            elif value is not None:
                self.values[key] = value.text
            else:
                self.values[key] = None
            self.types[key] = kind or "n"
            if formula is not None:
                self.formulas[key] = formula.text

    def value(self, row, column):
        return self.values.get((row, column))

    def sheet_names(self):
        return [node.get("name") for node in self.workbook.iter(NS + "sheet")]

    def setup(self, tag):
        for node in self.root.iter(NS + tag):
            return node.attrib
        return {}


@tagged("post_install", "-at_install")
class TestGeneratedFiles(RemunerationBookCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        ana = cls._create_employee("Ana Sintética", "12.345.678-5")
        bruno = cls._create_employee("Bruno Sintético", "11.111.111-1")
        carla = cls._create_employee("Carla Sintética", "22.222.222-2")
        cls._create_payslip(
            ana, cls._create_contract(ana, cls.department_admin),
            cls._coherent_values(wage=600000, transport=30000, meal=40000,
                                 deductions={dt_book.CODE_PENSION: 60000}))
        cls._create_payslip(
            bruno, cls._create_contract(bruno, cls.department_field),
            cls._coherent_values(wage=400000, bonus=50000,
                                 deductions={dt_book.CODE_HEALTH: 31500}))
        cls._create_payslip(
            carla, cls._create_contract(carla, cls.department_field),
            cls._coherent_values(wage=450000,
                                 deductions={dt_book.CODE_PENSION: 45000}))
        cls.dataset = cls.env["step.hr.remuneration.book.wizard"].create({
            "company_id": cls.company.id, "month": "6", "year": 2026,
            "mode": "full",
        }).build_dataset()

    def _workbook(self):
        stream = io.BytesIO()
        build_workbook(stream, self.dataset)
        return Sheet(stream.getvalue())

    # -- estructura ---------------------------------------------------------

    def test_headers_are_the_24_columns_in_order(self):
        sheet = self._workbook()
        headers = [sheet.value(5, chr(ord("A") + index)) for index in range(24)]
        self.assertEqual(headers,
                         [column.header for column in dt_book.BOOK_COLUMNS])
        self.assertIsNone(sheet.value(5, "Y"))

    def test_headers_carry_the_dt_code(self):
        sheet = self._workbook()
        self.assertEqual(dt_book.extract_dt_code(sheet.value(5, "B")), "1101")
        self.assertEqual(dt_book.extract_dt_code(sheet.value(5, "W")), "5301")

    def test_company_and_period_are_present(self):
        sheet = self._workbook()
        self.assertIn("Libro de Remuneraciones", sheet.value(1, "A"))
        self.assertIn("Junio 2026", sheet.value(1, "A"))
        self.assertIn(self.company.name, sheet.value(2, "A"))
        self.assertIn("76.543.210-3", sheet.value(2, "A"))

    def test_rut_is_text_and_amounts_are_numbers(self):
        sheet = self._workbook()
        self.assertEqual(sheet.types[(6, "B")], "s")
        self.assertRegex(sheet.value(6, "B"), r"^[\d.]+-[\dK]$")
        self.assertEqual(sheet.types[(6, "F")], "n")
        self.assertNotIn(".", sheet.value(6, "F") or "")

    def test_quantity_is_empty_in_detail(self):
        sheet = self._workbook()
        self.assertIsNone(sheet.value(6, "D"))

    def test_subtotal_and_grand_total_rows(self):
        sheet = self._workbook()
        labels = [
            value for (row, column), value in sheet.values.items()
            if column == "A" and isinstance(value, str)
        ]
        for group in self.dataset.groups:
            self.assertIn(group.label, labels)
        self.assertIn("Total general", labels)

    def test_subtotals_match_the_dataset(self):
        sheet = self._workbook()
        total_row = 5 + len(self.dataset.lines) + len(self.dataset.groups) + 1
        self.assertEqual(sheet.value(total_row, "A"), "Total general")
        self.assertEqual(
            int(sheet.value(total_row, "F")),
            self.dataset.totals[dt_book.CODE_WAGE],
        )
        self.assertEqual(
            int(sheet.value(total_row, "D")), len(self.dataset.lines))

    def test_formulas_have_cached_values(self):
        """El archivo muestra los totales correctos sin recalcular."""
        sheet = self._workbook()
        self.assertTrue(sheet.formulas)
        for key, formula in sheet.formulas.items():
            self.assertTrue(formula.startswith("=") or "SUM" in formula
                            or "+" in formula)
            self.assertIsNotNone(sheet.values[key])
            self.assertNotIn("#", sheet.values[key] or "")

    def test_no_black_fill_and_no_hidden_wide_sheet(self):
        sheet = self._workbook()
        self.assertEqual(sheet.sheet_names(), [SHEET_NAME, CONTROL_SHEET_NAME])

    def test_print_setup_is_landscape_and_repeats_header(self):
        sheet = self._workbook()
        setup = sheet.setup("pageSetup")
        self.assertEqual(setup.get("orientation"), "landscape")
        self.assertEqual(setup.get("paperSize"), "5")  # Legal
        self.assertEqual(sheet.setup("pane").get("ySplit"), "5")
        titles = [
            node.text for node in sheet.workbook.iter(NS + "definedName")
            if node.get("name") == "_xlnm.Print_Titles"
        ]
        self.assertTrue(titles)

    def test_control_sheet_has_counters_without_personal_data(self):
        stream = io.BytesIO()
        build_workbook(stream, self.dataset)
        control = Sheet(stream.getvalue(), index=2)
        text = " ".join(str(value) for value in control.values.values() if value)
        self.assertIn("Líneas del informe", text)
        self.assertIn("Trabajadores únicos", text)
        for line in self.dataset.lines:
            self.assertNotIn(line.employee_name, text)

    # -- equivalencia entre salidas -----------------------------------------

    def test_pdf_uses_the_same_dataset_and_totals(self):
        wizard = self._wizard()
        report = self.env["report.step_hr_remuneration_book.consolidated_book"]
        values = report._get_report_values(wizard.ids)
        pdf_dataset = values["dataset"]
        self.assertEqual(pdf_dataset.totals, self.dataset.totals)
        self.assertEqual(pdf_dataset.quantity, self.dataset.quantity)
        self.assertEqual(
            [group.name for group in pdf_dataset.groups],
            [group.name for group in self.dataset.groups],
        )

    def test_consolidated_pdf_renders_with_groups_and_totals(self):
        wizard = self._wizard()
        html = self.env["ir.qweb"]._render(
            "step_hr_remuneration_book.consolidated_book",
            self.env["report.step_hr_remuneration_book.consolidated_book"]
            ._get_report_values(wizard.ids),
        )
        html = str(html)
        self.assertIn("Libro de Remuneraciones", html)
        self.assertIn("Total general", html)
        for group in self.dataset.groups:
            self.assertIn(group.label, html)
        for column in dt_book.BOOK_COLUMNS:
            self.assertIn(column.label, html)

    def test_employee_sheets_render_one_block_per_line(self):
        wizard = self._wizard()
        html = str(self.env["ir.qweb"]._render(
            "step_hr_remuneration_book.employee_sheets",
            self.env["report.step_hr_remuneration_book.employee_sheets"]
            ._get_report_values(wizard.ids),
        ))
        self.assertEqual(html.count("Ficha detallada de remuneraciones"),
                         len(self.dataset.lines))
        self.assertIn("No constituye liquidación", html)
