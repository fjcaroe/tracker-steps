"""Pruebas del núcleo del libro. Datos 100 % sintéticos, sin base de datos."""

from odoo.tests.common import TransactionCase

from ..tools import dt_book


def make_line(payslip_id, name, rut, department, **values):
    return dt_book.BookLine(
        payslip_id=payslip_id,
        employee_id=payslip_id,
        employee_name=name,
        rut=rut,
        department=department,
        values={code: int(amount) for code, amount in values.items()},
    )


def coherent_values(wage=500000, bonus=0, gratification=0, meal=0,
                    transport=0, family=0, deductions=None, days=30):
    """Valores que respetan las identidades oficiales del LRE."""
    deductions = deductions or {}
    taxable = wage + bonus + gratification
    income = taxable + meal + transport + family
    total_deductions = sum(deductions.values())
    values = {
        dt_book.CODE_DAYS: days,
        dt_book.CODE_WAGE: wage,
        dt_book.CODE_BONUS: bonus,
        dt_book.CODE_GRATIFICATION: gratification,
        dt_book.CODE_TOTAL_TAXABLE: taxable,
        dt_book.CODE_TRANSPORT: transport,
        dt_book.CODE_MEAL: meal,
        dt_book.CODE_FAMILY: family,
        dt_book.CODE_TOTAL_INCOME: income,
        dt_book.CODE_TOTAL_DEDUCTIONS: total_deductions,
        dt_book.CODE_NET: income - total_deductions,
    }
    values.update(deductions)
    return values


class TestDtCodeParsing(TransactionCase):
    def test_extract_code_from_provider_header(self):
        self.assertEqual(dt_book.extract_dt_code("Sueldo(2101)"), "2101")
        self.assertEqual(dt_book.extract_dt_code("Días (1115)"), "1115")

    def test_extract_code_ignores_inner_parenthesis(self):
        """La descripción puede traer paréntesis propios: manda el último."""
        header = "Cotización obligatoria previsional (AFP o IPS)(3141)"
        self.assertEqual(dt_book.extract_dt_code(header), "3141")

    def test_description_may_change_without_breaking_mapping(self):
        renamed = "Aporte previsional del trabajador, nueva glosa 2026 (3141)"
        self.assertEqual(dt_book.extract_dt_code(renamed), "3141")

    def test_header_without_code(self):
        self.assertIsNone(dt_book.extract_dt_code("Nombre Trabajador"))
        self.assertIsNone(dt_book.extract_dt_code(""))

    def test_column_order_and_codes(self):
        """Las 24 columnas, en el orden del libro consolidado."""
        self.assertEqual(len(dt_book.BOOK_COLUMNS), 24)
        self.assertEqual(
            [column.order for column in dt_book.BOOK_COLUMNS],
            list(range(1, 25)),
        )
        codes = [column.dt_code for column in dt_book.BOOK_COLUMNS]
        self.assertEqual(codes[:5], [None, "1101", None, None, "1115"])
        # Movilización antes que Colación, como en el libro consolidado.
        self.assertLess(codes.index("2302"), codes.index("2301"))
        self.assertNotIn("2111", codes)
        self.assertIn("2113", codes)

    def test_official_totals_are_declared(self):
        for code in ("5210", "5201", "5301", "5501"):
            self.assertIn(code, dt_book.OFFICIAL_TOTAL_CODES)


class TestRut(TransactionCase):
    """Política de RUT: clave de comparación, validación y presentación.

    Son tres necesidades distintas y por eso son tres funciones distintas. El
    CSV oficial DT no usa ninguna: se entrega tal cual lo genera la fuente.
    """

    def test_display_uses_chilean_format(self):
        self.assertEqual(dt_book.rut_display("12.345.678-5"), "12.345.678-5")
        self.assertEqual(dt_book.rut_display("123456785"), "12.345.678-5")

    def test_display_keeps_k_and_uppercases(self):
        self.assertEqual(dt_book.rut_display("7.654.321-k"), "7.654.321-K")

    def test_display_preserves_leading_zeros(self):
        """El identificador NO se altera de forma irreversible al mostrarlo."""
        formatted = dt_book.rut_display("007.654.321-K")
        self.assertEqual(formatted, "007.654.321-K")
        self.assertIsInstance(formatted, str)

    def test_comparison_key_drops_leading_zeros(self):
        """La CLAVE sí los elimina, para que sea el mismo trabajador."""
        self.assertEqual(dt_book.rut_key("007.654.321-K"),
                         dt_book.rut_key("7654321K"))
        self.assertEqual(dt_book.rut_key("007.654.321-K"), "7654321K")

    def test_display_never_becomes_a_number(self):
        for raw in ("12.345.678-5", "007.654.321-K", "9", "123456785"):
            self.assertIsInstance(dt_book.rut_display(raw), str)

    def test_short_or_odd_values_are_returned_as_text(self):
        self.assertEqual(dt_book.rut_display("9"), "9")
        self.assertEqual(dt_book.rut_display("KK"), "KK")

    def test_empty_rut(self):
        self.assertEqual(dt_book.rut_display(""), "")
        self.assertEqual(dt_book.rut_display(None), "")
        self.assertEqual(dt_book.rut_key("  "), "")

    def test_validation(self):
        self.assertTrue(dt_book.is_valid_rut("12.345.678-5"))
        self.assertFalse(dt_book.is_valid_rut("12.345.678-9"))
        self.assertFalse(dt_book.is_valid_rut("mal formado"))


class TestDataset(TransactionCase):
    def test_groups_subtotals_and_grand_total(self):
        lines = [
            make_line(1, "Ana", "11111111-1", "Aseo",
                      **coherent_values(wage=400000, deductions={"3141": 40000})),
            make_line(2, "Bruno", "22222222-2", "Aseo",
                      **coherent_values(wage=600000, deductions={"3141": 60000})),
            make_line(3, "Carla", "33333333-3", "Administración",
                      **coherent_values(wage=500000, deductions={"3141": 50000})),
        ]
        dataset = dt_book.build_dataset(lines)
        self.assertEqual([group.name for group in dataset.groups],
                         ["Administración", "Aseo"])
        aseo = dataset.groups[1]
        self.assertEqual(aseo.quantity, 2)
        self.assertEqual(aseo.totals[dt_book.CODE_WAGE], 1000000)
        self.assertEqual(dataset.totals[dt_book.CODE_WAGE], 1500000)
        self.assertEqual(dataset.quantity, 3)
        self.assertEqual(dataset.counters["unique_employees"], 3)
        self.assertFalse(dataset.errors)

    def test_quantity_is_empty_in_detail_and_counted_in_totals(self):
        lines = [make_line(1, "Ana", "11111111-1", "Aseo", **coherent_values())]
        dataset = dt_book.build_dataset(lines)
        quantity_column = dataset.columns[3]
        self.assertEqual(quantity_column.key, "quantity")
        self.assertIsNone(dataset.groups[0].lines[0].cell(quantity_column))
        self.assertEqual(dataset.groups[0].cell(quantity_column), 1)
        self.assertEqual(dataset.total_cell(quantity_column), 1)

    def test_two_payslips_same_worker_are_two_lines(self):
        values = coherent_values(wage=300000)
        lines = [
            make_line(1, "Ana", "11111111-1", "Aseo", **values),
            make_line(2, "Ana", "11111111-1", "Aseo", **values),
        ]
        dataset = dt_book.build_dataset(lines)
        self.assertEqual(dataset.quantity, 2)
        self.assertEqual(dataset.groups[0].quantity, 2)
        self.assertEqual(dataset.counters["unique_employees"], 1)
        self.assertEqual(dataset.counters["multiple_payslips"], 1)
        self.assertEqual(dataset.totals[dt_book.CODE_WAGE], 600000)

    def test_missing_department_becomes_visible_group(self):
        lines = [
            make_line(1, "Ana", "11111111-1", "Aseo", **coherent_values()),
            make_line(2, "Bruno", "22222222-2", "", **coherent_values()),
        ]
        dataset = dt_book.build_dataset(lines)
        self.assertEqual(dataset.groups[-1].name, dt_book.NO_DEPARTMENT_LABEL)
        self.assertEqual(dataset.counters["without_department"], 1)
        self.assertTrue(any(issue.code == "missing_department"
                            for issue in dataset.warnings))
        # No se descarta ninguna línea.
        self.assertEqual(dataset.quantity, 2)

    def test_line_without_rut_is_kept(self):
        lines = [make_line(1, "Sin RUT", "", "Aseo", **coherent_values())]
        dataset = dt_book.build_dataset(lines)
        self.assertEqual(dataset.quantity, 1)
        self.assertEqual(dataset.counters["without_rut"], 1)

    def test_department_order_is_stable_with_no_department_last(self):
        lines = [
            make_line(1, "A", "11111111-1", "zeta", **coherent_values()),
            make_line(2, "B", "22222222-2", "", **coherent_values()),
            make_line(3, "C", "33333333-3", "Alfa", **coherent_values()),
        ]
        dataset = dt_book.build_dataset(lines)
        self.assertEqual([group.name for group in dataset.groups],
                         ["Alfa", "zeta", dt_book.NO_DEPARTMENT_LABEL])

    def test_source_order_does_not_change_the_book(self):
        first = [
            make_line(1, "Ana", "11111111-1", "Aseo", **coherent_values(wage=1)),
            make_line(2, "Bruno", "22222222-2", "Aseo", **coherent_values(wage=2)),
        ]
        reversed_lines = list(reversed(first))
        one = dt_book.build_dataset(first)
        other = dt_book.build_dataset(reversed_lines)
        self.assertEqual(
            [line.payslip_id for line in one.lines],
            [line.payslip_id for line in other.lines],
        )
        self.assertEqual(one.totals, other.totals)


class TestReconciliation(TransactionCase):
    def test_official_total_wins_over_visible_sum(self):
        """La diferencia de ±1 advierte, pero no altera el valor oficial."""
        values = coherent_values(wage=500000, deductions={"3141": 50000})
        values[dt_book.CODE_TOTAL_DEDUCTIONS] = 50001
        values[dt_book.CODE_NET] = values[dt_book.CODE_TOTAL_INCOME] - 50001
        line = make_line(1, "Ana", "11111111-1", "Aseo", **values)
        dataset = dt_book.build_dataset([line], tolerance=1)
        self.assertEqual(dataset.totals[dt_book.CODE_TOTAL_DEDUCTIONS], 50001)
        self.assertFalse(dataset.errors)
        # Dentro de la tolerancia: no se emite advertencia de conciliación.
        self.assertFalse([issue for issue in dataset.warnings
                          if issue.code == "recon_5301"])

    def test_difference_beyond_tolerance_warns(self):
        values = coherent_values(wage=500000, deductions={"3141": 50000})
        values[dt_book.CODE_TOTAL_DEDUCTIONS] = 55000
        values[dt_book.CODE_NET] = values[dt_book.CODE_TOTAL_INCOME] - 55000
        line = make_line(1, "Ana", "11111111-1", "Aseo", **values)
        dataset = dt_book.build_dataset([line], tolerance=1)
        self.assertTrue([issue for issue in dataset.warnings
                         if issue.code == "recon_5301"])
        self.assertEqual(dataset.totals[dt_book.CODE_TOTAL_DEDUCTIONS], 55000)

    def test_net_identity_is_reported(self):
        values = coherent_values(wage=500000, deductions={"3141": 50000})
        values[dt_book.CODE_NET] += 7
        line = make_line(1, "Ana", "11111111-1", "Aseo", **values)
        dataset = dt_book.build_dataset([line])
        self.assertTrue([issue for issue in dataset.warnings
                         if issue.code == "recon_5501"])

    def test_zero_and_empty_values_are_accepted(self):
        line = make_line(1, "Ana", "11111111-1", "Aseo",
                         **coherent_values(wage=0))
        dataset = dt_book.build_dataset([line])
        self.assertEqual(dataset.totals[dt_book.CODE_WAGE], 0)
        self.assertFalse(dataset.errors)
