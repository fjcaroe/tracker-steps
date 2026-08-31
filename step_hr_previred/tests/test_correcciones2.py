"""Correcciones 2 al TXT PreviRed (documento funcional 2026-08-29).

Cubre las dos causas de los 11 errores que impedían generar el archivo:

* **Campo 13 «Días Trabajados»**: debe salir de la línea de asistencia de la
  liquidación (código estable `WORK100`, o Tipo y Descripción «Asistencia»),
  nunca de la suma genérica de todas las líneas ni de «30 − ausencias»; y debe
  ir en **todas** las filas del trabajador, también las anexas.
* **Trabajador con más de un contrato**: se admiten tantas líneas principales
  (código `00`) como contratos elegibles tenga en la compañía y período; dos
  líneas del mismo contrato siguen siendo error.
"""

from odoo.tests.common import tagged

from ..tools import previred
from .common import PreviredCase, make_row


@tagged("post_install", "-at_install")
class TestCampo13(PreviredCase):
    """Corrección 1 — origen y formato del campo 13."""

    def _worked(self, payslip, code, days, name=None, is_leave=False):
        entry_type = self.env["hr.work.entry.type"].search(
            [("code", "=", code)], limit=1)
        if not entry_type:
            entry_type = self.env["hr.work.entry.type"].create({
                "name": name or ("Tipo %s" % code),
                "code": code,
                "is_leave": is_leave,
            })
        return self.env["hr.payslip.worked_days"].create({
            "name": name or entry_type.name,
            "payslip_id": payslip.id,
            "work_entry_type_id": entry_type.id,
            "number_of_days": days,
            "number_of_hours": days * 8,
        })

    def _one(self, worked, field13_override=None, annexes=0):
        """Un trabajador con su liquidación y `worked` líneas de días.

        `worked` es una lista de tuplas `(code, days[, name, is_leave])`.
        Devuelve el dataset ya construido.
        """
        employee = self.make_employee("Maria Riquelme", "10339402-3",
                                      self.dep_agri)
        payslip = self.make_payslip(employee, self.dep_agri)
        payslip.worked_days_line_ids.unlink()
        for spec in worked:
            self._worked(payslip, *spec)
        overrides = {}
        if field13_override is not None:
            overrides[previred.F_WORKED_DAYS] = field13_override
        rows = [make_row(rut="10339402", dv="3", overrides=overrides)]
        for _ in range(annexes):
            rows.append(make_row(rut="10339402", dv="3",
                                 line_type=previred.LINE_ADDITIONAL,
                                 overrides={previred.F_WORKED_DAYS: "",
                                            previred.F_MOVEMENT_CODE: "2"}))
        return self.build(rows)

    # -- casos del documento ----------------------------------------------

    def test_attendance_six_plus_out_of_contract_twelve_gives_six(self):
        """SLIP/491: Asistencia 6 + Fuera de contrato 12 exporta «6»."""
        dataset = self._one([("WORK100", 6, "Asistencia"),
                             ("OUT", 12, "Fuera de contrato")])
        self.assertEqual(
            dataset.records[0].principal[previred.F_WORKED_DAYS - 1], "6")
        codes = [i.code for i in dataset.errors]
        self.assertNotIn("worked_days_source_missing", codes)
        self.assertNotIn("worked_days_fraction", codes)

    def test_several_attendance_lines_are_added_only_among_themselves(self):
        dataset = self._one([("WORK100", 6, "Asistencia"),
                             ("WORK100", 4, "Asistencia"),
                             ("OUT", 12, "Fuera de contrato"),
                             ("LIC", 5, "Licencia Médica", True)])
        self.assertEqual(
            dataset.records[0].principal[previred.F_WORKED_DAYS - 1], "10")

    def test_leaves_permits_absences_vacations_are_excluded(self):
        dataset = self._one([
            ("WORK100", 8, "Asistencia"),
            ("LIC", 5, "Licencia Médica", True),
            ("PERM", 2, "Permiso", True),
            ("AUS", 3, "Ausencia", True),
            ("LEAVE100", 4, "Vacaciones", True),
            ("OUT", 8, "Fuera de contrato"),
        ])
        self.assertEqual(
            dataset.records[0].principal[previred.F_WORKED_DAYS - 1], "8")
        self.assertFalse(dataset.errors)

    def test_positive_line_without_attendance_code_does_not_leak_in(self):
        """Corrección 1.5: se elimina el respaldo genérico."""
        dataset = self._one([("OUT", 12, "Fuera de contrato"),
                             ("LIC", 6, "Licencia", True)],
                            field13_override="")
        field13 = dataset.records[0].principal[previred.F_WORKED_DAYS - 1]
        self.assertNotIn(field13, ("12", "18", "6"))
        self.assertIn("worked_days_source_missing",
                      [i.code for i in dataset.errors])

    def test_no_valid_attendance_line_blocks_with_a_functional_error(self):
        dataset = self._one([("OUT", 20, "Fuera de contrato")],
                            field13_override="")
        self.assertTrue(dataset.errors,
                        "Sin línea de asistencia no debe generarse el TXT.")
        self.assertIn("worked_days_source_missing",
                      [i.code for i in dataset.errors])

    def test_six_point_zero_serialises_as_six(self):
        dataset = self._one([("WORK100", 6.0, "Asistencia")])
        self.assertEqual(
            dataset.records[0].principal[previred.F_WORKED_DAYS - 1], "6")

    def test_non_representable_fraction_is_reported_not_truncated(self):
        dataset = self._one([("WORK100", 6.5, "Asistencia")],
                            field13_override="")
        codes = [i.code for i in dataset.errors]
        self.assertIn("worked_days_fraction", codes)
        field13 = dataset.records[0].principal[previred.F_WORKED_DAYS - 1]
        self.assertNotIn(field13, ("6", "7"),
                         "La fracción no debe truncarse en silencio.")

    def test_same_value_in_principal_and_annex_rows(self):
        """Paridad: el campo 13 va idéntico en principal y anexas."""
        dataset = self._one([("WORK100", 6, "Asistencia"),
                             ("OUT", 12, "Fuera de contrato")],
                            annexes=2)
        record = dataset.records[0]
        values = {row[previred.F_WORKED_DAYS - 1] for row in record.rows}
        self.assertEqual(values, {"6"})

    def test_value_is_consistent_across_txt_and_department_partition(self):
        dataset = self._one([("WORK100", 6, "Asistencia"),
                             ("OUT", 12, "Fuera de contrato")])
        record = dataset.records[0]
        consolidated = previred.render_records(dataset.sorted_records())
        by_dep = dataset.by_department()[record.department_id]
        department = previred.render_records(by_dep)
        field = consolidated.split(previred.LINE_ENDING)[0].split(
            previred.SEPARATOR)[previred.F_WORKED_DAYS - 1]
        field_dep = department.split(previred.LINE_ENDING)[0].split(
            previred.SEPARATOR)[previred.F_WORKED_DAYS - 1]
        self.assertEqual(field, "6")
        self.assertEqual(field_dep, "6")


@tagged("post_install", "-at_install")
class TestMultiplesContratos(PreviredCase):
    """Corrección 2 — multiplicidad de líneas principales por contrato."""

    def _two_contract_employee(self, identification="10339402-3",
                               states=("done", "done")):
        """Trabajador con dos contratos elegibles en el mismo período.

        Como en los datos reales (María Riquelme en Demo-SyS): dos contratos
        que **no se solapan** —uno cerrado a mitad de mes y otro que arranca
        después—, cada uno con su liquidación del mes completo.
        """
        employee = self.make_employee("Maria Riquelme", identification,
                                      self.dep_agri)
        first = self.make_payslip(
            employee, self.dep_agri, state=states[0],
            contract_date_start="2026-08-01", contract_date_end="2026-08-15",
            contract_state="close")
        second = self.make_payslip(
            employee, self.dep_agri, state=states[1],
            contract_date_start="2026-08-16", contract_state="open")
        return employee, first, second

    def _rows(self, count, line_type=previred.LINE_PRINCIPAL, rut="10339402",
             dv="3"):
        return [make_row(rut=rut, dv=dv, line_type=line_type)
                for _ in range(count)]

    def test_two_contracts_two_principals_is_valid(self):
        _e, first, second = self._two_contract_employee()
        dataset = self.build(
            self._rows(2),
            row_meta=[{"contract_id": first.contract_id.id},
                      {"contract_id": second.contract_id.id}])
        codes = [i.code for i in dataset.errors]
        self.assertNotIn("duplicate_worker", codes)
        self.assertNotIn("too_many_principal_lines", codes)
        self.assertEqual(len(dataset.records), 2)
        self.assertEqual(
            {r.contract_id for r in dataset.records},
            {first.contract_id.id, second.contract_id.id})

    def test_one_contract_two_principals_is_an_error(self):
        employee = self.make_employee("Ana Rojas", "11111111-1", self.dep_agri)
        payslip = self.make_payslip(employee, self.dep_agri)
        dataset = self.build(
            self._rows(2, rut="11111111", dv="1"),
            row_meta=[{"contract_id": payslip.contract_id.id},
                      {"contract_id": payslip.contract_id.id}])
        codes = [i.code for i in dataset.errors]
        self.assertIn("too_many_principal_lines", codes)
        self.assertIn("duplicate_worker", codes)

    def test_two_contracts_three_principals_is_an_error(self):
        _e, first, second = self._two_contract_employee()
        dataset = self.build(
            self._rows(3),
            row_meta=[{"contract_id": first.contract_id.id},
                      {"contract_id": second.contract_id.id},
                      {"contract_id": first.contract_id.id}])
        self.assertIn("too_many_principal_lines",
                      [i.code for i in dataset.errors])

    def test_annexes_do_not_count_as_extra_contracts(self):
        _e, first, second = self._two_contract_employee()
        rows = [
            make_row(rut="10339402", dv="3"),
            make_row(rut="10339402", dv="3",
                     line_type=previred.LINE_ADDITIONAL,
                     overrides={previred.F_MOVEMENT_CODE: "2"}),
            make_row(rut="10339402", dv="3"),
            make_row(rut="10339402", dv="3",
                     line_type=previred.LINE_ADDITIONAL,
                     overrides={previred.F_MOVEMENT_CODE: "2"}),
        ]
        dataset = self.build(
            rows,
            row_meta=[{"contract_id": first.contract_id.id},
                      {"contract_id": second.contract_id.id}])
        codes = [i.code for i in dataset.errors]
        self.assertNotIn("too_many_principal_lines", codes)
        self.assertNotIn("duplicate_worker", codes)
        self.assertEqual(dataset.counters["principal"], 2)
        self.assertEqual(dataset.counters["annexes"], 2)
        for record in dataset.records:
            self.assertEqual(len(record.annexes), 1)

    def test_same_rut_in_two_companies_is_validated_separately(self):
        emp_a = self.make_employee("Doble A", "33333333-3", self.dep_agri)
        self.make_payslip(emp_a, self.dep_agri)
        other_employee = self.env["hr.employee"].create({
            "name": "Doble B", "identification_id": "33333333-3",
            "company_id": self.other_company.id})
        self.make_payslip(other_employee, self.dep_agri_other,
                          company=self.other_company)
        dataset = self.build([make_row(rut="33333333", dv="3")])
        self.assertEqual(len(dataset.records), 1)
        self.assertNotIn("duplicate_worker",
                         [i.code for i in dataset.errors])

    def test_payslip_in_another_period_does_not_add_a_principal(self):
        employee = self.make_employee("Otro Periodo", "44444444-4",
                                      self.dep_agri)
        current = self.make_payslip(employee, self.dep_agri)
        # Mismo contrato, liquidación de otro mes: no debe sumar principal.
        self.make_payslip(employee, self.dep_agri,
                          contract=current.contract_id,
                          date_from="2026-07-01", date_to="2026-07-31")
        dataset = self.build([make_row(rut="44444444", dv="4")])
        self.assertEqual(len(dataset.records), 1)
        self.assertNotIn("too_many_principal_lines",
                         [i.code for i in dataset.errors])

    def test_cancelled_payslip_does_not_enable_an_extra_principal(self):
        _e, done, cancelled = self._two_contract_employee(
            states=("done", "cancel"))
        dataset = self.build(
            self._rows(2),
            row_meta=[{"contract_id": done.contract_id.id},
                      {"contract_id": cancelled.contract_id.id}])
        self.assertIn("too_many_principal_lines",
                      [i.code for i in dataset.errors])

    def test_ambiguous_contract_correlation_is_an_explicit_error(self):
        """Sin metadata de contrato y con dos liquidaciones: no se adivina."""
        self._two_contract_employee()
        dataset = self.build(self._rows(2))  # row_meta=None
        self.assertIn("ambiguous_contract_correlation",
                      [i.code for i in dataset.errors])
