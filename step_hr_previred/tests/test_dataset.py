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

    def test_workday_type_part_time_under_40_hours_is_partial(self):
        """Ticket EMCA 2026-08, RUT 12588103-3: un horario cuyo «Tiempo
        completo de la empresa» es inferior a 40 h semanales es jornada
        parcial (campo 93 = 2), aunque no tenga `previred_workday_type`."""
        employee = self.make_employee("Karen Flies", "12588103-3",
                                      self.dep_agri)
        payslip = self.make_payslip(employee, self.dep_agri)
        calendar = payslip.contract_id.resource_calendar_id
        calendar.previred_workday_type = False
        calendar.full_time_required_hours = 24

        dataset = self.build([make_row(rut="12588103", dv="3")],
                             spec_version="98")

        self.assertEqual(
            dataset.records[0].principal[previred.F_WORKDAY_TYPE - 1], "2")

    def test_part_time_hours_override_stale_full_time_configuration(self):
        """Una migración antigua no debe convertir 24 h en jornada completa."""
        employee = self.make_employee("Karen Flies migrada", "12588103-3",
                                      self.dep_agri)
        payslip = self.make_payslip(employee, self.dep_agri)
        calendar = payslip.contract_id.resource_calendar_id
        calendar.previred_workday_type = "1"
        calendar.full_time_required_hours = 24

        dataset = self.build([make_row(rut="12588103", dv="3")],
                             spec_version="98")

        self.assertEqual(
            dataset.records[0].principal[previred.F_WORKDAY_TYPE - 1], "2")

    def test_mutual_contribution_uses_taxable_and_company_rate(self):
        """Ticket #15: 438.229 × 0,93 % = 4.076, no 4.159."""
        if "rate_base" not in self.company._fields:
            self.skipTest("La localización no aporta las tasas Mutual")
        self.company.rate_base = 0.93
        if "rate_additional" in self.company._fields:
            self.company.rate_additional = 0
        employee = self.make_employee("Celestina Peñaloza", "12359103-8",
                                      self.dep_agri)
        self.make_payslip(employee, self.dep_agri)
        row = make_row(rut="12359103", dv="8", overrides={
            previred.F_MUTUAL_CODE: "01",
            previred.F_MUTUAL_TAXABLE: "438229",
            previred.F_MUTUAL_CONTRIBUTION: "4159",
        })

        dataset = self.build([row], spec_version="98")

        self.assertEqual(
            dataset.records[0].principal[
                previred.F_MUTUAL_CONTRIBUTION - 1],
            "4076",
        )
        self.assertIn("mutual_contribution_normalized",
                      [issue.code for issue in dataset.issues])

    def test_workday_type_40_hours_is_full(self):
        """40 h semanales o más es jornada completa (campo 93 = 1): Previred
        exige el sueldo mínimo legal en el campo 27."""
        employee = self.make_employee("Jornada Completa", "12345678-9",
                                      self.dep_agri)
        payslip = self.make_payslip(employee, self.dep_agri)
        calendar = payslip.contract_id.resource_calendar_id
        calendar.previred_workday_type = False
        calendar.full_time_required_hours = 40

        dataset = self.build([make_row()], spec_version="98")

        self.assertEqual(
            dataset.records[0].principal[previred.F_WORKDAY_TYPE - 1], "1")

    def test_workday_type_is_propagated_to_annex_lines(self):
        """Ticket EMCA 2026-08: las líneas 01/02/03 deben repetir el campo
        93 de su línea principal 00, aunque el motor entregue otro valor."""
        employee = self.make_employee("Filomena Munoz", "12358793-6",
                                      self.dep_agri)
        payslip = self.make_payslip(employee, self.dep_agri)
        payslip.contract_id.resource_calendar_id.previred_workday_type = "1"
        rows = [
            make_row(rut="12358793", dv="6",
                     line_type=previred.LINE_PRINCIPAL,
                     overrides={previred.F_WORKDAY_TYPE: "1"}),
            make_row(rut="12358793", dv="6",
                     line_type=previred.LINE_ADDITIONAL,
                     overrides={previred.F_WORKDAY_TYPE: "2"}),
            make_row(rut="12358793", dv="6",
                     line_type=previred.LINE_SECOND_CONTRACT,
                     overrides={previred.F_WORKDAY_TYPE: "2"}),
            make_row(rut="12358793", dv="6",
                     line_type=previred.LINE_VOLUNTARY,
                     overrides={previred.F_WORKDAY_TYPE: "2"}),
        ]

        dataset = self.build(rows, spec_version="98")

        self.assertEqual(
            [row[previred.F_WORKDAY_TYPE - 1]
             for row in dataset.records[0].rows],
            ["1", "1", "1", "1"],
        )

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

    def test_v98_cost_center_strips_accents(self):
        """Ticket PreviRed 2026-08 (Los Lingues / Megafrut): un centro de
        costo con tilde («Administración») se rechazaba con «Error de
        formato en el campo Centro de Costos» porque el archivo UTF-8 se
        releía como Latin-1 («AdministraciÃ³n»). El campo 105 debe quedar en
        ASCII puro."""
        contract_model = self.env["hr.contract"]
        field_name = "analytic_account_id" if "analytic_account_id" in \
            contract_model._fields else "cost_center_id"
        if field_name not in contract_model._fields:
            self.skipTest("El motor instalado no aporta centro de costo")
        employee = self.make_employee("Centro Costo Tilde", "12345678-9",
                                      self.dep_agri)
        payslip = self.make_payslip(employee, self.dep_agri)
        analytic_model = self.env[contract_model._fields[
            field_name].comodel_name]
        values = {"name": "Administración", "company_id": self.company.id}
        if "plan_id" in analytic_model._fields:
            plan = self.env["account.analytic.plan"].search(
                [("name", "=", "Plan Previred")], limit=1
            ) or self.env["account.analytic.plan"].create({
                "name": "Plan Previred",
            })
            values["plan_id"] = plan.id
        center = analytic_model.create(values)
        payslip.contract_id[field_name] = center

        dataset = self.build([make_row()], spec_version="98")

        value = dataset.records[0].principal[previred.F_COST_CENTER - 1]
        self.assertEqual(value, "Administracion")
        # el valor debe coincidir byte a byte al codificar UTF-8 o Latin-1:
        # ninguna tilde sobrevive para poder divergir entre ambas.
        self.assertEqual(value.encode("utf-8"), value.encode("latin-1"))

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
        """Un solo contrato con dos líneas principales sigue siendo error."""
        employee = self.make_employee("Ana Rojas", "11111111-1",
                                      self.dep_agri)
        self.make_payslip(employee, self.dep_agri)
        dataset = self.build([
            make_row(rut="11111111", dv="1"),
            make_row(rut="11111111", dv="1"),
        ])
        codes = [issue.code for issue in dataset.errors]
        self.assertIn("duplicate_worker", codes)
        self.assertIn("too_many_principal_lines", codes)

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
        # Tasa CEV 0,72 % desde 2026-08 (corte 2): 1.000.000 × 0,72 % = 7.200.
        self.assertEqual(row[previred.F_LIFE_EXPECTANCY - 1], "7200")
        self.assertEqual(row[previred.F_PROTECTED_RETURN - 1], "9000")
        self.assertFalse(dataset.errors)

    def test_without_ccaf_moves_afp_family_allowance_to_field_73(self):
        """Ticket S&S #19: la condición es «empresa Sin CCAF», incluso si la
        trabajadora está afiliada a AFP como Valentina en el caso real."""
        employee = self.make_employee("Ana AFP", "18656818-4", self.dep_admin)
        self.make_payslip(employee, self.dep_admin)
        row = make_row(rut="18656818", dv="4", overrides={
            previred.F_PENSION_REGIME: "AFP",
            previred.F_FAMILY_ALLOWANCE: "27812",
            previred.F_FAMILY_ALLOWANCE_IPS: "0",
            previred.F_CCAF_CODE: "0",
        })
        dataset = self.build([row], spec_version="98")
        principal = dataset.records[0].principal
        self.assertEqual(principal[previred.F_FAMILY_ALLOWANCE - 1], "0")
        self.assertEqual(
            principal[previred.F_FAMILY_ALLOWANCE_IPS - 1], "27812")
        self.assertIn("family_allowance_moved_to_ips",
                      [issue.code for issue in dataset.issues])
        self.assertFalse(dataset.errors)

    def test_with_ccaf_keeps_family_allowance_in_field_22(self):
        """Una empresa adherida a CCAF conserva el campo 22, sea cual sea el
        régimen previsional individual del trabajador."""
        employee = self.make_employee("Caro AFP CCAF", "18656818-4",
                                      self.dep_admin)
        self.make_payslip(employee, self.dep_admin)
        row = make_row(rut="18656818", dv="4", overrides={
            previred.F_PENSION_REGIME: "AFP",
            previred.F_FAMILY_ALLOWANCE: "27812",
            previred.F_CCAF_CODE: "5",
        })
        dataset = self.build([row], spec_version="98")
        principal = dataset.records[0].principal
        self.assertEqual(principal[previred.F_FAMILY_ALLOWANCE - 1], "27812")
        self.assertEqual(principal[previred.F_FAMILY_ALLOWANCE_IPS - 1], "0")
        self.assertNotIn("family_allowance_moved_to_ips",
                         [issue.code for issue in dataset.issues])

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

    def test_medical_leave_rebases_employer_contributions_on_rima(self):
        """Ticket Somed 2026-09, RUT 17.932.663-9: mes completo de licencia
        médica; el motor informa la RIMA (campo 92) y el imponible del mes es
        0. Las cotizaciones de cargo del empleador se recalculan sobre
        imponible + RIMA con la tasa estatutaria, contra los valores que
        confirmó el cliente."""
        employee = self.make_employee("Carolina Medel", "17932663-9",
                                      self.dep_admin)
        self.make_payslip(employee, self.dep_admin)
        row = make_row(rut="17932663", dv="9", overrides={
            previred.F_WORKED_DAYS: "0",
            previred.F_AFP_CODE: "34",
            previred.F_AFP_TAXABLE: "0",
            previred.F_RIMA: "1205761",
            previred.F_SIS_CONTRIBUTION: "22178",
            previred.F_LIFE_EXPECTANCY: "8681",
            previred.F_PROTECTED_RETURN: "0",
            previred.F_MUTUAL_CODE: "00",
            # El motor real deja el campo 71 en 0 en licencia de mes completo
            # (empleador ISL «Sin Mutual»); debe recalcularse igual.
            previred.F_ISL_ACCIDENT: "0",
            previred.F_UNEMPLOYMENT_TAXABLE: "1205761",
            previred.F_UNEMPLOYMENT_EMPLOYER: "29903",
        })
        dataset = self.build([row], spec_version="98")
        principal = dataset.records[0].principal
        self.assertEqual(principal[previred.F_SIS_CONTRIBUTION - 1], "21463")
        self.assertEqual(principal[previred.F_LIFE_EXPECTANCY - 1], "8681")
        self.assertEqual(principal[previred.F_PROTECTED_RETURN - 1], "10852")
        self.assertEqual(principal[previred.F_ISL_ACCIDENT - 1], "11214")
        self.assertEqual(
            principal[previred.F_UNEMPLOYMENT_TAXABLE - 1], "1205761")
        self.assertEqual(
            principal[previred.F_UNEMPLOYMENT_EMPLOYER - 1], "28938")
        self.assertIn("medical_leave_bases_rebased",
                      [issue.code for issue in dataset.issues])
        self.assertFalse(dataset.errors)

    def test_medical_leave_partial_month_rebases_taxable_plus_rima(self):
        """Ticket Serv. Bienestar 2026-09, RUT 18.656.818-4: mes parcial (con
        imponible propio) más RIMA informada por el motor. La base es la suma
        y las cotizaciones patronales usan esa base; la mutualidad no."""
        employee = self.make_employee("Valentina Parada", "18656818-4",
                                      self.dep_admin)
        self.make_payslip(employee, self.dep_admin)
        row = make_row(rut="18656818", dv="4", overrides={
            previred.F_WORKED_DAYS: "11",
            previred.F_AFP_CODE: "29",
            previred.F_AFP_TAXABLE: "192500",
            previred.F_RIMA: "350000",
            previred.F_MUTUAL_CODE: "",
            previred.F_ISL_ACCIDENT: "1790",
            previred.F_MUTUAL_CONTRIBUTION: "0",
        })
        dataset = self.build([row], spec_version="98")
        principal = dataset.records[0].principal
        # base = 192.500 + 350.000 = 542.500
        self.assertEqual(principal[previred.F_SIS_CONTRIBUTION - 1], "9657")
        self.assertEqual(principal[previred.F_LIFE_EXPECTANCY - 1], "3906")
        self.assertEqual(principal[previred.F_PROTECTED_RETURN - 1], "4883")
        self.assertEqual(principal[previred.F_ISL_ACCIDENT - 1], "5045")
        self.assertEqual(
            principal[previred.F_UNEMPLOYMENT_TAXABLE - 1], "542500")
        self.assertEqual(
            principal[previred.F_UNEMPLOYMENT_EMPLOYER - 1], "13020")
        self.assertEqual(principal[previred.F_MUTUAL_CONTRIBUTION - 1], "0")

    def test_medical_leave_isl_employer_zeroes_mutual_fields(self):
        """Ticket Serv. Bienestar: quien cotiza en INP/ISL (campo 96 vacío) no
        lleva mutualidad — el motor deja el campo 97 con monto y debe quedar
        en 0, y el campo 71 se recalcula sobre imponible + RIMA."""
        employee = self.make_employee("INP Parada", "18656818-4",
                                      self.dep_admin)
        self.make_payslip(employee, self.dep_admin)
        row = make_row(rut="18656818", dv="4", overrides={
            previred.F_WORKED_DAYS: "11",
            previred.F_AFP_CODE: "29",
            previred.F_AFP_TAXABLE: "192500",
            previred.F_RIMA: "350000",
            previred.F_MUTUAL_CODE: "",
            previred.F_ISL_ACCIDENT: "0",
            previred.F_MUTUAL_TAXABLE: "192500",
            previred.F_MUTUAL_CONTRIBUTION: "1790",
        })
        dataset = self.build([row], spec_version="98")
        principal = dataset.records[0].principal
        self.assertEqual(principal[previred.F_ISL_ACCIDENT - 1], "5045")
        self.assertEqual(principal[previred.F_MUTUAL_TAXABLE - 1], "0")
        self.assertEqual(principal[previred.F_MUTUAL_CONTRIBUTION - 1], "0")

    def test_medical_leave_without_motor_rima_warns_and_keeps_fields(self):
        """Licencia médica, el motor no informó la RIMA y tampoco se puede
        calcular (sin sueldo base en el contrato): no se recalcula nada y
        queda un aviso trazable."""
        employee = self.make_employee("Sin RIMA", "18656818-4", self.dep_admin)
        payslip = self.make_payslip(employee, self.dep_admin)
        payslip.contract_id.wage = 0
        payslip.worked_days_line_ids.unlink()
        self._add_worked_days(payslip, "LIC", 30, is_leave=True)
        row = make_row(rut="18656818", dv="4", overrides={
            previred.F_WORKED_DAYS: "0",
            previred.F_AFP_CODE: "29",
            previred.F_AFP_TAXABLE: "0",
            previred.F_RIMA: "0",
            previred.F_SIS_CONTRIBUTION: "3427",
        })
        dataset = self.build([row], spec_version="98")
        principal = dataset.records[0].principal
        self.assertEqual(principal[previred.F_SIS_CONTRIBUTION - 1], "3427")
        self.assertIn("medical_leave_rima_missing",
                      [issue.code for issue in dataset.issues])
        self.assertNotIn("medical_leave_bases_rebased",
                         [issue.code for issue in dataset.issues])

    def test_medical_leave_computes_rima_from_contract_when_motor_omits_it(self):
        """Ticket #18, RUT 18.656.818-4: el motor no informa la RIMA. La
        extracción la calcula = (sueldo base 420.000 + gratificación 105.000)
        / 30 × 20 días de licencia = 350.000, y rebasa las cotizaciones sobre
        192.500 + 350.000 = 542.500. Verificado contra la liquidación real de
        SyS (agosto 2026)."""
        employee = self.make_employee("Valentina Parada", "18656818-4",
                                      self.dep_admin)
        payslip = self.make_payslip(employee, self.dep_admin)
        payslip.contract_id.wage = 420000
        payslip.worked_days_line_ids.unlink()
        self._add_worked_days(payslip, "WORK100", 11)
        self._add_worked_days(payslip, "LIC", 20, is_leave=True)
        row = make_row(rut="18656818", dv="4", overrides={
            previred.F_AFP_CODE: "29",
            previred.F_AFP_TAXABLE: "192500",
            previred.F_RIMA: "0",
            previred.F_MUTUAL_CODE: "",
            previred.F_ISL_ACCIDENT: "1790",
        })
        dataset = self.build([row], spec_version="98")
        principal = dataset.records[0].principal
        self.assertEqual(principal[previred.F_RIMA - 1], "350000")
        self.assertEqual(principal[previred.F_SIS_CONTRIBUTION - 1], "9657")
        self.assertEqual(principal[previred.F_ISL_ACCIDENT - 1], "5045")
        self.assertEqual(principal[previred.F_LIFE_EXPECTANCY - 1], "3906")
        self.assertEqual(principal[previred.F_PROTECTED_RETURN - 1], "4883")
        self.assertEqual(
            principal[previred.F_UNEMPLOYMENT_TAXABLE - 1], "542500")
        self.assertEqual(
            principal[previred.F_UNEMPLOYMENT_EMPLOYER - 1], "13020")
        self.assertIn("medical_leave_bases_rebased",
                      [issue.code for issue in dataset.issues])

    def test_medical_leave_additional_line_zeroes_13_71_and_92(self):
        """Ticket #18 revisión 2: la línea 01 de Valentina no replica días
        trabajados, accidente ISL ni RIMA; el resto de sus campos se conserva.
        """
        employee = self.make_employee("Valentina Parada", "18656818-4",
                                      self.dep_admin)
        payslip = self.make_payslip(employee, self.dep_admin)
        payslip.contract_id.wage = 420000
        payslip.worked_days_line_ids.unlink()
        self._add_worked_days(payslip, "WORK100", 11)
        self._add_worked_days(payslip, "LIC", 20, is_leave=True)
        principal = make_row(rut="18656818", dv="4", overrides={
            previred.F_AFP_CODE: "29",
            previred.F_AFP_TAXABLE: "192500",
            previred.F_RIMA: "0",
            previred.F_MUTUAL_CODE: "",
            previred.F_ISL_ACCIDENT: "1790",
        })
        annex = make_row(
            rut="18656818", dv="4",
            line_type=previred.LINE_ADDITIONAL,
            overrides={
                previred.F_WORKED_DAYS: "11",
                previred.F_ISL_ACCIDENT: "1790",
                previred.F_RIMA: "350000",
                previred.F_WORKDAY_TYPE: "2",
            })

        dataset = self.build([principal, annex], spec_version="98")

        record = dataset.records[0]
        self.assertEqual(record.principal[previred.F_WORKED_DAYS - 1], "11")
        self.assertEqual(record.principal[previred.F_RIMA - 1], "350000")
        self.assertEqual(record.principal[previred.F_ISL_ACCIDENT - 1], "5045")
        self.assertEqual(record.annexes[0][previred.F_WORKED_DAYS - 1], "0")
        self.assertEqual(record.annexes[0][previred.F_ISL_ACCIDENT - 1], "0")
        self.assertEqual(record.annexes[0][previred.F_RIMA - 1], "0")
        # Un campo ajeno a la revisión mantiene la normalización general.
        self.assertEqual(record.annexes[0][previred.F_WORKDAY_TYPE - 1], "1")
        self.assertIn("medical_leave_annex_zeroed",
                      [issue.code for issue in dataset.issues])

    def test_medical_leave_full_month_computes_rima_capped_by_imm(self):
        """Ticket #17, RUT 17.932.663-9: mes completo de licencia, sin RIMA
        del motor. gratificación = min(25 % de 986.646, 4,75 × 553.553 / 12)
        = 219.114; RIMA = (986.646 + 219.114) / 30 × 30 = 1.205.761.
        Verificado contra la liquidación real de SyS."""
        employee = self.make_employee("Carolina Medel", "17932663-9",
                                      self.dep_admin)
        payslip = self.make_payslip(employee, self.dep_admin)
        payslip.contract_id.wage = 986646
        payslip.worked_days_line_ids.unlink()
        self._add_worked_days(payslip, "LIC", 30, is_leave=True)
        row = make_row(rut="17932663", dv="9", overrides={
            previred.F_AFP_CODE: "34",
            previred.F_AFP_TAXABLE: "0",
            previred.F_RIMA: "0",
            previred.F_MUTUAL_CODE: "",
            previred.F_ISL_ACCIDENT: "362",
        })
        dataset = self.build([row], spec_version="98")
        principal = dataset.records[0].principal
        self.assertEqual(principal[previred.F_RIMA - 1], "1205761")
        self.assertEqual(principal[previred.F_SIS_CONTRIBUTION - 1], "21463")
        self.assertEqual(principal[previred.F_LIFE_EXPECTANCY - 1], "8681")
        self.assertEqual(principal[previred.F_PROTECTED_RETURN - 1], "10852")
        self.assertEqual(principal[previred.F_ISL_ACCIDENT - 1], "11214")
        self.assertEqual(
            principal[previred.F_UNEMPLOYMENT_EMPLOYER - 1], "28938")

    def test_medical_leave_without_imm_table_entry_warns(self):
        """Sin IMM del período en la tabla no se calcula la RIMA: aviso
        trazable, sin recálculo."""
        employee = self.make_employee("Sin IMM", "17932663-9", self.dep_admin)
        payslip = self.make_payslip(employee, self.dep_admin)
        payslip.contract_id.wage = 986646
        payslip.worked_days_line_ids.unlink()
        self._add_worked_days(payslip, "LIC", 30, is_leave=True)
        row = make_row(rut="17932663", dv="9", overrides={
            previred.F_AFP_CODE: "34",
            previred.F_AFP_TAXABLE: "0",
            previred.F_RIMA: "0",
            previred.F_SIS_CONTRIBUTION: "22178",
        })
        original = dict(previred.MINIMUM_WAGE_BY_PERIOD)
        previred.MINIMUM_WAGE_BY_PERIOD.clear()
        try:
            dataset = self.build([row], spec_version="98")
        finally:
            previred.MINIMUM_WAGE_BY_PERIOD.update(original)
        principal = dataset.records[0].principal
        self.assertEqual(principal[previred.F_SIS_CONTRIBUTION - 1], "22178")
        self.assertIn("medical_leave_rima_missing",
                      [issue.code for issue in dataset.issues])

    def test_no_rima_leaves_employer_contributions_untouched(self):
        """Sin RIMA y con días trabajados normales: el recálculo de licencia
        médica no toca ningún campo ni emite avisos."""
        employee = self.make_employee("Sin Licencia", "12345678-9",
                                      self.dep_agri)
        self.make_payslip(employee, self.dep_agri)
        row = make_row(overrides={
            previred.F_AFP_CODE: "8",
            previred.F_AFP_TAXABLE: "800000",
            previred.F_SIS_CONTRIBUTION: "11111",
            previred.F_ISL_ACCIDENT: "7440",
        })
        dataset = self.build([row], spec_version="98")
        principal = dataset.records[0].principal
        self.assertEqual(principal[previred.F_SIS_CONTRIBUTION - 1], "11111")
        self.assertEqual(principal[previred.F_ISL_ACCIDENT - 1], "7440")
        self.assertFalse(any(
            issue.code in ("medical_leave_bases_rebased",
                           "medical_leave_rima_missing")
            for issue in dataset.issues))

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
