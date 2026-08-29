"""Pruebas del dataset canónico.

Cubre los casos 2 (dos departamentos y trabajador con líneas 00/01/02/03),
3 (trabajador sin departamento), 4 (departamentos homónimos en dos compañías)
y 11 (un único dataset por acción).
"""

from odoo.tests.common import tagged

from ..tools import previred
from .common import PreviredCase, make_row


@tagged("post_install", "-at_install")
class TestDataset(PreviredCase):

    def _add_worked_days(self, payslip, code, days, is_leave=False):
        entry_type = self.env["hr.work.entry.type"].search(
            [("code", "=", code)], limit=1
        )
        if not entry_type:
            entry_type = self.env["hr.work.entry.type"].create({
                "name": "Tipo %s" % code,
                "code": code,
                "is_leave": is_leave,
            })
        return self.env["hr.payslip.worked_days"].create({
            "name": entry_type.name,
            "payslip_id": payslip.id,
            "work_entry_type_id": entry_type.id,
            "number_of_days": days,
            "number_of_hours": days * 8,
        })

    def test_v98_uses_only_attendance_for_worked_days(self):
        """Caso real: 1 día de asistencia + 30 de licencia informa 1."""
        employee = self.make_employee("Marcelo Soto", "12345678-9",
                                      self.dep_agri)
        payslip = self.make_payslip(employee, self.dep_agri)
        payslip.worked_days_line_ids.unlink()
        self._add_worked_days(payslip, "WORK100", 1)
        self._add_worked_days(payslip, "LIC_TEST", 30, is_leave=True)

        dataset = self.build([make_row()], spec_version="84")

        row = dataset.records[0].principal
        self.assertEqual(row[previred.F_WORKED_DAYS - 1], "1")

    def test_v98_workday_type_comes_from_calendar_configuration(self):
        employee = self.make_employee("Jornada Parcial", "12345678-9",
                                      self.dep_agri)
        payslip = self.make_payslip(employee, self.dep_agri)
        payslip.contract_id.resource_calendar_id.previred_workday_type = "2"

        dataset = self.build([make_row()], spec_version="98")

        self.assertEqual(
            dataset.records[0].principal[previred.F_WORKDAY_TYPE - 1], "2")

    def test_v98_cost_center_uses_code_or_name_from_contract(self):
        contract_model = self.env["hr.contract"]
        field_name = "analytic_account_id" if "analytic_account_id" in \
            contract_model._fields else "cost_center_id"
        if field_name not in contract_model._fields:
            self.skipTest("El motor instalado no aporta centro de costo")
        employee = self.make_employee("Centro Costo", "12345678-9",
                                      self.dep_agri)
        payslip = self.make_payslip(employee, self.dep_agri)
        analytic_model = self.env[contract_model._fields[
            field_name].comodel_name]
        values = {"name": "Maquinarias", "company_id": self.company.id}
        if "plan_id" in analytic_model._fields:
            plan = self.env["account.analytic.plan"].create({
                "name": "Plan Previred",
            })
            values["plan_id"] = plan.id
        center = analytic_model.create(values)
        payslip.contract_id[field_name] = center

        dataset = self.build([make_row()], spec_version="98")

        self.assertEqual(
            dataset.records[0].principal[previred.F_COST_CENTER - 1],
            "Maquinarias")

    def test_annexes_stay_with_their_principal(self):
        """Caso 2: un trabajador con líneas 00/01/02/03 forma UN registro."""
        employee = self.make_employee("Ana Rojas", "11111111-1",
                                      self.dep_agri)
        self.make_payslip(employee, self.dep_agri)
        rows = [
            make_row(rut="11111111", dv="1",
                     line_type=previred.LINE_PRINCIPAL),
            make_row(rut="11111111", dv="1",
                     line_type=previred.LINE_ADDITIONAL),
            make_row(rut="11111111", dv="1",
                     line_type=previred.LINE_SECOND_CONTRACT),
            make_row(rut="11111111", dv="1",
                     line_type=previred.LINE_VOLUNTARY),
        ]
        dataset = self.build(rows)
        self.assertEqual(len(dataset.records), 1)
        record = dataset.records[0]
        self.assertEqual(len(record.annexes), 3)
        self.assertEqual(record.department, "Agrícola")
        self.assertEqual(
            [row[previred.F_LINE_TYPE - 1] for row in record.rows],
            ["00", "01", "02", "03"])
        self.assertEqual(dataset.counters["rows"], 4)
        self.assertEqual(dataset.counters["workers"], 1)

    def test_two_departments_are_separated(self):
        agri = self.make_employee("Ana Rojas", "11111111-1", self.dep_agri)
        admin = self.make_employee("Luis Díaz", "22222222-2", self.dep_admin)
        self.make_payslip(agri, self.dep_agri)
        self.make_payslip(admin, self.dep_admin)
        dataset = self.build([
            make_row(rut="11111111", dv="1"),
            make_row(rut="22222222", dv="2"),
        ])
        grouped = dataset.by_department()
        self.assertEqual(sorted(grouped), sorted([
            self.dep_admin.id, self.dep_agri.id]))
        self.assertEqual(len(grouped[self.dep_agri.id]), 1)
        self.assertEqual(len(grouped[self.dep_admin.id]), 1)

    def test_homonymous_departments_in_same_company_are_separated_by_id(self):
        duplicate = self.env["hr.department"].create({
            "name": "Agrícola", "company_id": self.company.id})
        first = self.make_employee("Primero", "10111111-3", self.dep_agri)
        second = self.make_employee("Segundo", "10222222-9", duplicate)
        self.make_payslip(first, self.dep_agri)
        self.make_payslip(second, duplicate)
        dataset = self.build([
            make_row(rut="10111111", dv="3"),
            make_row(rut="10222222", dv="9"),
        ])
        self.assertEqual(len(dataset.departments()), 2)
        self.assertEqual(set(dataset.by_department()),
                         {self.dep_agri.id, duplicate.id})
        selected = self.build([
            make_row(rut="10111111", dv="3"),
            make_row(rut="10222222", dv="9"),
        ], departments=duplicate)
        self.assertEqual(len(selected.records), 1)
        self.assertEqual(selected.records[0].department_id, duplicate.id)

    def test_worker_without_department_blocks_by_default(self):
        """Caso 3: por defecto bloquea; sólo una opción explícita lo permite."""
        employee = self.make_employee("Sin Depto", "33333333-3")
        self.make_payslip(employee)
        rows = [make_row(rut="33333333", dv="3")]

        dataset = self.build(rows)
        self.assertIn("without_department",
                      [issue.code for issue in dataset.errors])

        allowed = self.build(rows, allow_without_department=True)
        self.assertNotIn("without_department",
                         [issue.code for issue in allowed.errors])
        self.assertEqual(allowed.records[0].department_label,
                         previred.NO_DEPARTMENT_LABEL)
        self.assertEqual(allowed.records[0].department_code,
                         previred.NO_DEPARTMENT_CODE)

    def test_homonymous_departments_do_not_collide(self):
        """Caso 4: «Agrícola» de dos compañías produce códigos distintos."""
        here = self.make_employee("Ana Rojas", "11111111-1", self.dep_agri)
        self.make_payslip(here, self.dep_agri)
        there = self.make_employee("Otro Ana", "44444444-4",
                                   self.dep_agri_other,
                                   company=self.other_company)
        self.make_payslip(there, self.dep_agri_other,
                          company=self.other_company)

        mine = self.build([make_row(rut="11111111", dv="1")])
        theirs = self.build([make_row(rut="44444444", dv="4")],
                            company=self.other_company)

        self.assertEqual(mine.records[0].department, "Agrícola")
        self.assertEqual(theirs.records[0].department, "Agrícola")
        self.assertNotEqual(mine.records[0].department_code,
                            theirs.records[0].department_code)
        self.assertNotEqual(
            previred.txt_filename("A", "202608",
                                  mine.records[0].department_code),
            previred.txt_filename("A", "202608",
                                  theirs.records[0].department_code))

    def test_other_company_rows_are_dropped(self):
        """Corrección deliberada: el motor no filtraba compañía, el core sí.

        El generador de Blueminds busca por fecha y devuelve liquidaciones de
        cualquier empresa. El core descarta lo que no corresponde a la
        compañía del lote, porque Previred es un archivo **por empresa**.
        """
        outsider = self.make_employee("Ajeno", "55555555-5",
                                      self.dep_agri_other,
                                      company=self.other_company)
        self.make_payslip(outsider, self.dep_agri_other,
                          company=self.other_company)
        dataset = self.build([make_row(rut="55555555", dv="5")])
        self.assertEqual(dataset.records, [])
        self.assertIn("dropped_not_eligible",
                      [issue.code for issue in dataset.warnings])
        self.assertEqual(dataset.dropped_count, 1)

    # -- estados exportables (condición 3 del encargo) -----------------------

    def test_draft_payslips_are_never_exported(self):
        """Un borrador no está calculado: no puede declararse."""
        employee = self.make_employee("Borrador", "66666666-6", self.dep_agri)
        self.make_payslip(employee, self.dep_agri, state="draft")
        dataset = self.build([make_row(rut="66666666", dv="6")])
        self.assertEqual(dataset.records, [])
        self.assertIn("dropped_not_eligible",
                      [issue.code for issue in dataset.warnings])

    def test_cancelled_payslips_are_never_exported(self):
        employee = self.make_employee("Anulada", "77777777-7", self.dep_agri)
        self.make_payslip(employee, self.dep_agri, state="cancel")
        dataset = self.build([make_row(rut="77777777", dv="7")])
        self.assertEqual(dataset.records, [])

    def test_forbidden_states_are_stripped_even_if_requested(self):
        """Pedir «draft» explícitamente no lo habilita."""
        employee = self.make_employee("Borrador", "66666666-6", self.dep_agri)
        self.make_payslip(employee, self.dep_agri, state="draft")
        dataset = self.build([make_row(rut="66666666", dv="6")],
                             states=("draft", "done"))
        self.assertEqual(dataset.records, [])

    def test_verify_is_exported_only_when_the_engine_admits_it(self):
        """El estado elegible lo decide el motor, no una lista global."""
        employee = self.make_employee("Calculada", "88888888-8", self.dep_agri)
        self.make_payslip(employee, self.dep_agri, state="verify")
        rows = [make_row(rut="88888888", dv="8")]

        included = self.build(rows, states=("verify", "done", "paid"))
        self.assertEqual(len(included.records), 1)

        excluded = self.build(rows, states=("done", "paid"))
        self.assertEqual(excluded.records, [])

    def test_eligible_states_are_recorded_in_the_dataset(self):
        employee = self.make_employee("Ana Rojas", "11111111-1", self.dep_agri)
        self.make_payslip(employee, self.dep_agri)
        dataset = self.build([make_row(rut="11111111", dv="1")],
                             states=("done", "paid"))
        self.assertEqual(dataset.eligible_states, ("done", "paid"))
        self.assertEqual(dataset.eligible_payslip_count, 1)

    def test_department_precedence_contract_over_employee(self):
        """Precedencia documentada: contrato gana al trabajador."""
        employee = self.make_employee("Ana Rojas", "11111111-1",
                                      self.dep_admin)
        self.make_payslip(employee, self.dep_agri)
        dataset = self.build([make_row(rut="11111111", dv="1")])
        self.assertEqual(dataset.records[0].department, "Agrícola")
        self.assertNotIn("department_from_employee",
                         [issue.code for issue in dataset.warnings])

    def test_department_fallback_below_contract_warns(self):
        """Sin departamento en el contrato se cae al siguiente nivel, avisando.

        En Odoo 18 `hr.payslip.department_id` es un campo relacionado del
        trabajador, así que en la práctica el nivel que responde es el de la
        liquidación; lo que importa es que el departamento se resuelva y que
        quede constancia de que **no** vino del contrato, que es la fuente
        que manda.
        """
        employee = self.make_employee("Ana Rojas", "11111111-1",
                                      self.dep_admin)
        self.make_payslip(employee, department=None)
        dataset = self.build([make_row(rut="11111111", dv="1")])
        self.assertEqual(dataset.records[0].department, "Administración")
        codes = [issue.code for issue in dataset.warnings]
        self.assertTrue(
            {"department_from_payslip", "department_from_employee"}
            & set(codes),
            "Se esperaba una advertencia de departamento no tomado del "
            "contrato y llegaron: %s" % codes)

    def test_orphan_annex_is_reported(self):
        employee = self.make_employee("Ana Rojas", "11111111-1",
                                      self.dep_agri)
        self.make_payslip(employee, self.dep_agri)
        dataset = self.build([
            make_row(rut="11111111", dv="1",
                     line_type=previred.LINE_ADDITIONAL),
        ])
        self.assertIn("orphan_annex",
                      [issue.code for issue in dataset.errors])

    def test_duplicate_principal_is_reported(self):
        employee = self.make_employee("Ana Rojas", "11111111-1",
                                      self.dep_agri)
        self.make_payslip(employee, self.dep_agri)
        dataset = self.build([
            make_row(rut="11111111", dv="1"),
            make_row(rut="11111111", dv="1"),
        ])
        self.assertIn("duplicate_worker",
                      [issue.code for issue in dataset.errors])
        self.assertIn("ambiguous_engine_rows",
                      [issue.code for issue in dataset.errors])

    def test_v98_enriches_reform_fields_from_taxable_income(self):
        employee = self.make_employee("Reforma", "19191919-K", self.dep_agri)
        self.make_payslip(employee, self.dep_agri)
        dataset = self.build([make_row(
            rut="19191919", dv="K",
            overrides={previred.F_AFP_CODE: "33",
                       previred.F_AFP_TAXABLE: "1000000",
                       previred.F_WORKDAY_TYPE: "0",
                       previred.F_LIFE_EXPECTANCY: "",
                       previred.F_PROTECTED_RETURN: ""})], spec_version="98")
        row = dataset.records[0].principal
        self.assertEqual(row[previred.F_WORKDAY_TYPE - 1], "1")
        self.assertEqual(row[previred.F_LIFE_EXPECTANCY - 1], "10000")
        self.assertEqual(row[previred.F_PROTECTED_RETURN - 1], "9000")
        self.assertFalse(dataset.errors)

    def test_department_filter_narrows_the_batch(self):
        agri = self.make_employee("Ana Rojas", "11111111-1", self.dep_agri)
        admin = self.make_employee("Luis Díaz", "22222222-2", self.dep_admin)
        self.make_payslip(agri, self.dep_agri)
        self.make_payslip(admin, self.dep_admin)
        dataset = self.build(
            [make_row(rut="11111111", dv="1"),
             make_row(rut="22222222", dv="2")],
            departments=self.dep_agri)
        self.assertEqual(len(dataset.records), 1)
        self.assertEqual(dataset.records[0].department, "Agrícola")
        self.assertIn("scope_filtered",
                      [issue.code for issue in dataset.warnings])

    def test_sort_order_is_deterministic(self):
        for rut, dv, department in (("9999999", "3", self.dep_agri),
                                    ("10000000", "8", self.dep_agri),
                                    ("11111111", "1", self.dep_admin)):
            employee = self.make_employee("T %s" % rut, "%s-%s" % (rut, dv),
                                          department)
            self.make_payslip(employee, department)
        rows = [make_row(rut="11111111", dv="1"),
                make_row(rut="10000000", dv="8"),
                make_row(rut="9999999", dv="3")]
        first = self.build(rows).sorted_records()
        second = self.build(rows).sorted_records()
        order = [record.rut for record in first]
        self.assertEqual(order, [record.rut for record in second])
        # Administración antes que Agrícola; dentro, el RUT menor primero.
        self.assertEqual(order, ["11111111", "9999999", "10000000"])
