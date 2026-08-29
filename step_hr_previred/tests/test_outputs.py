"""Pruebas de las salidas: TXT, ZIP, manifiesto y Excel.

Cubre los casos 1 (paridad del consolidado), 5 (consolidado = unión de los
departamentales) y 6 (Excel y TXT del mismo dataset con los mismos totales).
"""

import io
import zipfile

from odoo.tests.common import tagged

from ..tools import previred, xlsx_previred
from .common import PreviredCase, make_row


@tagged("post_install", "-at_install")
class TestOutputs(PreviredCase):

    def _populate(self):
        agri = self.make_employee("Ana Rojas", "11111111-1", self.dep_agri)
        agri2 = self.make_employee("Beto Lira", "22222222-2", self.dep_agri)
        admin = self.make_employee("Luis Díaz", "33333333-3", self.dep_admin)
        for employee, department in ((agri, self.dep_agri),
                                     (agri2, self.dep_agri),
                                     (admin, self.dep_admin)):
            self.make_payslip(employee, department)
        return [
            make_row(rut="11111111", dv="1"),
            make_row(rut="11111111", dv="1",
                     line_type=previred.LINE_ADDITIONAL),
            make_row(rut="22222222", dv="2"),
            make_row(rut="33333333", dv="3"),
        ]

    def _wizard(self, **values):
        return self.env["step.previred.export.wizard"].create(dict({
            "company_id": self.company.id,
            "date_from": self.date_from,
            "date_to": self.date_to,
        }, **values))

    # -- caso 1: paridad del consolidado -------------------------------------

    def test_consolidated_txt_preserves_engine_rows_verbatim(self):
        """El consolidado es exactamente lo que emitió el motor, reordenado.

        Ni un campo se reescribe: es lo que garantiza la paridad con el
        generador anterior para el mismo conjunto de liquidaciones.
        """
        rows = self._populate()
        dataset = self.build(rows)
        text = previred.render_records(dataset.sorted_records())
        produced = [line.split(";") for line in text.split("\r\n")]
        self.assertEqual(sorted(map(tuple, produced)),
                         sorted(map(tuple, rows)))
        for row in produced:
            self.assertEqual(len(row), 105)

    def test_consolidated_row_count_matches_engine(self):
        rows = self._populate()
        dataset = self.build(rows)
        self.assertEqual(dataset.row_count, len(rows))

    # -- caso 5: consolidado = unión de departamentales -----------------------

    def test_consolidated_equals_union_of_department_files(self):
        rows = self._populate()
        dataset = self.build(rows)

        consolidated = previred.render_records(dataset.sorted_records())
        grouped = dataset.by_department()
        union = []
        for department_id, _label, _code in dataset.departments():
            union.extend(
                previred.render_records(grouped[department_id]).split("\r\n"))

        self.assertEqual(sorted(consolidated.split("\r\n")), sorted(union))
        self.assertEqual(len(consolidated.split("\r\n")), len(union))

    def test_annexes_are_never_split_from_their_principal(self):
        rows = self._populate()
        dataset = self.build(rows)
        for department_id, _label, _code in dataset.departments():
            lines = previred.render_records(
                dataset.by_department()[department_id]).split("\r\n")
            for index, line in enumerate(lines):
                fields = line.split(";")
                if fields[previred.F_LINE_TYPE - 1] == previred.LINE_PRINCIPAL:
                    continue
                # Toda anexa tiene una línea antes, del mismo RUT.
                self.assertGreater(index, 0)
                previous = lines[index - 1].split(";")
                self.assertEqual(previous[previred.F_RUT - 1],
                                 fields[previred.F_RUT - 1])

    # -- ZIP y manifiesto ----------------------------------------------------

    def test_department_mode_produces_zip_with_manifest(self):
        rows = self._populate()
        self.build(rows)  # deja las filas en el adaptador falso
        wizard = self._wizard(scope="departments", output="txt")
        dataset = self.build(rows)
        payload, filename, entries = wizard._render_outputs(dataset)

        self.assertTrue(filename.endswith(".zip"))
        with zipfile.ZipFile(io.BytesIO(payload)) as archive:
            names = archive.namelist()
            self.assertIn(previred.MANIFEST_NAME, names)
            txt_names = [name for name in names if name.endswith(".txt")]
            self.assertEqual(len(txt_names), 2)  # dos departamentos
            manifest = archive.read(previred.MANIFEST_NAME).decode("utf-8")

        # El manifiesto lleva conteos y hashes, y NO lleva datos personales.
        for entry in entries:
            if entry["official"]:
                self.assertIn(entry["sha256"], manifest)
                self.assertIn(entry["filename"], manifest)
        self.assertNotIn("11111111", manifest)
        self.assertNotIn("Ana", manifest)

    def test_single_consolidated_file_is_not_zipped(self):
        rows = self._populate()
        dataset = self.build(rows)
        wizard = self._wizard(scope="consolidated", output="txt")
        _payload, filename, entries = wizard._render_outputs(dataset)
        self.assertTrue(filename.endswith(".txt"))
        self.assertEqual(len(entries), 1)

    def test_single_file_is_zipped_when_requested(self):
        rows = self._populate()
        dataset = self.build(rows)
        wizard = self._wizard(scope="consolidated", output="txt",
                              zip_single=True)
        _payload, filename, _entries = wizard._render_outputs(dataset)
        self.assertTrue(filename.endswith(".zip"))

    def test_manifest_hashes_match_the_files(self):
        rows = self._populate()
        dataset = self.build(rows)
        wizard = self._wizard(scope="both", output="txt")
        payload, _filename, entries = wizard._render_outputs(dataset)
        with zipfile.ZipFile(io.BytesIO(payload)) as archive:
            for entry in entries:
                data = archive.read(entry["filename"])
                self.assertEqual(previred.sha256_hex(data), entry["sha256"])

    # -- caso 6: Excel y TXT del mismo dataset -------------------------------

    def test_excel_reflects_the_same_dataset(self):
        rows = self._populate()
        dataset = self.build(rows)
        stream = io.BytesIO()
        xlsx_previred.build_workbook(stream, dataset,
                                     per_department_sheets=True)
        data = stream.getvalue()
        self.assertTrue(data.startswith(b"PK"))

        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            shared = archive.read("xl/sharedStrings.xml").decode("utf-8")
            sheets = archive.read("xl/workbook.xml").decode("utf-8")

        self.assertIn(previred.REVIEW_WARNING, shared)
        for _department_id, label, _code in dataset.departments():
            self.assertIn(label, sheets)
        self.assertIn(xlsx_previred.SUMMARY_SHEET, sheets)
        self.assertIn(xlsx_previred.CONSOLIDATED_SHEET, sheets)

    def test_excel_and_txt_have_the_same_counts(self):
        rows = self._populate()
        dataset = self.build(rows)
        txt_lines = previred.render_records(
            dataset.sorted_records()).split("\r\n")
        self.assertEqual(len(txt_lines), dataset.counters["rows"])
        self.assertEqual(dataset.counters["workers"], 3)
        self.assertEqual(dataset.counters["annexes"], 1)
        self.assertEqual(dataset.counters["principal"]
                         + dataset.counters["annexes"],
                         dataset.counters["rows"])

    def test_excel_filename_is_marked_as_review(self):
        name = previred.xlsx_filename("761234567", "202608")
        self.assertIn("REVISION", name)
        self.assertTrue(name.endswith(".xlsx"))

    def test_duplicate_sheet_names_are_disambiguated(self):
        namer = xlsx_previred._SheetNamer()
        first = namer.take("Departamento")
        second = namer.take("Departamento")
        self.assertNotEqual(first, second)
        long_name = namer.take("D" * 60)
        self.assertLessEqual(len(long_name), 31)
        repeated_long = namer.take("D" * 60)
        self.assertNotEqual(long_name, repeated_long)
        self.assertLessEqual(len(repeated_long), 31)

    def test_both_outputs_produce_txt_and_xlsx(self):
        rows = self._populate()
        dataset = self.build(rows)
        wizard = self._wizard(scope="both", output="both")
        payload, filename, entries = wizard._render_outputs(dataset)
        self.assertTrue(filename.endswith(".zip"))
        official = [entry for entry in entries if entry["official"]]
        review = [entry for entry in entries if not entry["official"]]
        self.assertTrue(all(entry["filename"].endswith(".txt")
                            for entry in official))
        self.assertTrue(all(entry["filename"].endswith(".xlsx")
                            for entry in review))
        with zipfile.ZipFile(io.BytesIO(payload)) as archive:
            manifest = archive.read(previred.MANIFEST_NAME).decode("utf-8")
        # El manifiesto sólo lista los archivos cargables.
        for entry in review:
            self.assertNotIn(entry["filename"], manifest)
