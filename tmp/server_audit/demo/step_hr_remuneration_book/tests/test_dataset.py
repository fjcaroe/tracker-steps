"""Extracción desde liquidaciones sintéticas: mapeo, departamento y totales."""

from odoo.exceptions import UserError
from odoo.tests.common import tagged

from ..tools import dt_book
from .common import RemunerationBookCommon


@tagged("post_install", "-at_install")
class TestExtraction(RemunerationBookCommon):
    def test_single_payslip_per_worker(self):
        employee = self._create_employee("Ana Sintética", "12.345.678-5")
        contract = self._create_contract(employee, self.department_admin)
        self._create_payslip(employee, contract, self._coherent_values(
            wage=600000, deductions={dt_book.CODE_PENSION: 60000}))

        dataset = self._wizard().build_dataset()
        self.assertEqual(dataset.quantity, 1)
        line = dataset.lines[0]
        self.assertEqual(line.value(dt_book.CODE_WAGE), 600000)
        self.assertEqual(line.value(dt_book.CODE_DAYS), 30)
        self.assertEqual(line.cell(dataset.columns[1]), "12.345.678-5")
        self.assertEqual(line.department, self.department_admin.name)
        self.assertFalse(dataset.errors)

    def test_two_payslips_same_worker_same_month(self):
        employee = self._create_employee("Bruno Sintético", "11.111.111-1")
        contract = self._create_contract(employee, self.department_field)
        self._create_payslip(employee, contract,
                             self._coherent_values(wage=300000))
        self._create_payslip(employee, contract,
                             self._coherent_values(wage=200000))

        dataset = self._wizard().build_dataset()
        self.assertEqual(dataset.quantity, 2)
        self.assertEqual(dataset.counters["unique_employees"], 1)
        self.assertEqual(dataset.counters["multiple_payslips"], 1)
        self.assertEqual(dataset.totals[dt_book.CODE_WAGE], 500000)
        group = dataset.groups[0]
        self.assertEqual(group.quantity, 2)
        self.assertEqual(len({line.payslip_id for line in group.lines}), 2)

    def test_department_comes_from_contract_not_from_current_employee(self):
        """El libro histórico no cambia si luego se traslada al trabajador."""
        employee = self._create_employee("Carla Sintética", "22.222.222-2",
                                         self.department_admin)
        contract = self._create_contract(employee, self.department_field)
        self._create_payslip(employee, contract, self._coherent_values())

        employee.department_id = self.department_admin
        dataset = self._wizard().build_dataset()
        self.assertEqual(dataset.lines[0].department, self.department_field.name)

    def test_department_falls_back_with_warning(self):
        employee = self._create_employee("Dario Sintético", "33.333.333-3",
                                         self.department_admin)
        contract = self._create_contract(employee)  # sin departamento
        self._create_payslip(employee, contract, self._coherent_values())

        dataset = self._wizard().build_dataset()
        self.assertEqual(dataset.lines[0].department, self.department_admin.name)
        self.assertTrue([issue for issue in dataset.warnings
                         if issue.code.startswith("department_from_")])

    def test_without_department_goes_to_visible_group(self):
        employee = self._create_employee("Elsa Sintética", "44.444.444-4")
        contract = self._create_contract(employee)
        self._create_payslip(employee, contract, self._coherent_values())

        dataset = self._wizard().build_dataset()
        self.assertEqual(dataset.groups[0].name, dt_book.NO_DEPARTMENT_LABEL)
        self.assertEqual(dataset.counters["without_department"], 1)
        self.assertEqual(dataset.quantity, 1)

    def test_worker_without_rut_is_reported_but_kept(self):
        employee = self._create_employee("Sin RUT Sintético", False,
                                         self.department_admin)
        contract = self._create_contract(employee, self.department_admin)
        self._create_payslip(employee, contract, self._coherent_values())

        dataset = self._wizard().build_dataset()
        self.assertEqual(dataset.quantity, 1)
        self.assertEqual(dataset.counters["without_rut"], 1)
        self.assertTrue([issue for issue in dataset.warnings
                         if issue.code == "line_without_rut"])

    def test_malformed_rut_is_reported(self):
        try:
            employee = self._create_employee(
                "Mal RUT Sintético", "12.345.678-9", self.department_admin)
        except Exception:
            # Hay localizaciones -la del proveedor chileno entre ellas- que
            # impiden guardar un RUT con dígito verificador inválido. En esas
            # bases el escenario no puede construirse y la advertencia del
            # libro nunca se dispara por este motivo.
            self.skipTest(
                "Esta base valida el RUT al crear el trabajador: no es "
                "posible construir el caso.")
        contract = self._create_contract(employee, self.department_admin)
        self._create_payslip(employee, contract, self._coherent_values())

        dataset = self._wizard().build_dataset()
        self.assertTrue([issue for issue in dataset.warnings
                         if issue.code == "invalid_rut"])

    def test_termination_payslip_is_included(self):
        employee = self._create_employee("Fin Sintético", "55.555.555-5")
        contract = self._create_contract(employee, self.department_field)
        contract.date_end = "2026-06-15"
        self._create_payslip(employee, contract,
                             self._coherent_values(wage=250000), days=15)

        dataset = self._wizard().build_dataset()
        self.assertEqual(dataset.quantity, 1)
        self.assertEqual(dataset.lines[0].value(dt_book.CODE_DAYS), 15)

    def test_only_done_or_paid_payslips(self):
        employee = self._create_employee("Draft Sintético", "66.666.666-6")
        contract = self._create_contract(employee, self.department_admin)
        self._create_payslip(employee, contract, self._coherent_values(),
                             state="draft")
        with self.assertRaises(UserError):
            self._wizard().build_dataset()

    def test_other_company_payslips_are_excluded(self):
        employee = self._create_employee("Propio Sintético", "77.777.777-7")
        contract = self._create_contract(employee, self.department_admin)
        self._create_payslip(employee, contract,
                             self._coherent_values(wage=100000))

        foreign_employee = self._create_employee(
            "Ajeno Sintético", "88.888.888-8", company=self.other_company)
        foreign_contract = self._create_contract(foreign_employee)
        self._create_payslip(foreign_employee, foreign_contract,
                             self._coherent_values(wage=999999),
                             company=self.other_company)

        dataset = self._wizard().build_dataset()
        self.assertEqual(dataset.quantity, 1)
        self.assertEqual(dataset.totals[dt_book.CODE_WAGE], 100000)

    def test_official_totals_are_not_recomputed(self):
        """5301 se toma de la fuente aunque no cuadre con las visibles."""
        employee = self._create_employee("Redondeo Sintético", "99.999.999-9")
        contract = self._create_contract(employee, self.department_admin)
        values = self._coherent_values(
            wage=500000, deductions={dt_book.CODE_PENSION: 50000})
        values[dt_book.CODE_TOTAL_DEDUCTIONS] = 50001
        values[dt_book.CODE_NET] = values[dt_book.CODE_TOTAL_INCOME] - 50001
        self._create_payslip(employee, contract, values)

        dataset = self._wizard().build_dataset()
        line = dataset.lines[0]
        self.assertEqual(line.value(dt_book.CODE_TOTAL_DEDUCTIONS), 50001)
        self.assertEqual(line.value(dt_book.CODE_PENSION), 50000)

    def test_missing_dt_code_in_profile_blocks(self):
        employee = self._create_employee("Perfil Sintético", "10.000.001-6")
        contract = self._create_contract(employee, self.department_admin)
        self._create_payslip(employee, contract, self._coherent_values())

        self.profile.line_ids.filtered(
            lambda line: line.dt_code == dt_book.CODE_NET
        ).unlink()
        wizard = self._wizard()
        with self.assertRaises(UserError):
            wizard.generate("xlsx")

    def test_period_is_a_calendar_month(self):
        wizard = self._wizard(month="2", year=2026)
        self.assertEqual(str(wizard.date_from), "2026-02-01")
        self.assertEqual(str(wizard.date_to), "2026-02-28")
        self.assertEqual(wizard.period_label, "Febrero 2026")

    def test_profile_is_autodetected_when_company_has_none(self):
        """Detección por los códigos presentes en ESTAS liquidaciones."""
        employee = self._create_employee("Detecta Sintética", "10.000.002-4")
        contract = self._create_contract(employee, self.department_admin)
        self._create_payslip(employee, contract, self._coherent_values())

        self.company.remuneration_book_profile_id = False
        wizard = self._wizard()
        dataset = wizard.build_dataset()
        self.assertFalse(dataset.errors)
        self.assertEqual(wizard.profile_id, self.profile)
        self.assertEqual(wizard.profile_origin, "detected")
        self.assertEqual(dataset.profile_origin, "detected")
