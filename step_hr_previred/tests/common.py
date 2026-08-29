"""Fixtures sintéticas para las pruebas de Previred.

Las pruebas **nunca** usan datos reales: construyen sus propias compañías,
trabajadores y liquidaciones. El motor de nómina se sustituye por un
adaptador falso que devuelve filas de 105 campos controladas por la prueba,
de modo que las suites corren igual en los tres ambientes y no dependen de
qué addon previsional esté instalado.
"""

from odoo import fields
from odoo.exceptions import ValidationError
from odoo.tests.common import TransactionCase

from ..models import previred_adapter as adapters
from ..tools import previred


def make_row(rut="12345678", dv="9", last_name="PEREZ", mother_name="SOTO",
             names="JUAN ANDRES", line_type=previred.LINE_PRINCIPAL,
             period="082026", cost_center="", overrides=None):
    """Una fila válida de 105 campos.

    Se parte de un registro que pasa todas las validaciones y la prueba
    modifica sólo el campo que quiere ejercitar, indicándolo por su posición
    oficial (`overrides={27: "0"}`).
    """
    row = ["0"] * previred.FIELD_COUNT
    row[previred.F_RUT - 1] = rut
    row[previred.F_DV - 1] = dv
    row[previred.F_LAST_NAME - 1] = last_name
    row[previred.F_MOTHER_NAME - 1] = mother_name
    row[previred.F_NAMES - 1] = names
    row[previred.F_SEX - 1] = "M"
    row[previred.F_NATIONALITY - 1] = "0"
    row[previred.F_PAYMENT_TYPE - 1] = "1"
    row[previred.F_PERIOD_FROM - 1] = period
    row[previred.F_PERIOD_TO - 1] = period
    row[previred.F_PENSION_REGIME - 1] = "AFP"
    row[previred.F_WORKER_TYPE - 1] = "0"
    row[previred.F_WORKED_DAYS - 1] = "30"
    row[previred.F_LINE_TYPE - 1] = line_type
    row[previred.F_MOVEMENT_CODE - 1] = "0"
    row[previred.F_MOVEMENT_FROM - 1] = "00/00/0000"
    row[previred.F_MOVEMENT_TO - 1] = "00/00/0000"
    row[previred.F_FAMILY_BRACKET - 1] = "D"
    row[previred.F_WORKDAY_TYPE - 1] = "1"
    row[previred.F_COST_CENTER - 1] = cost_center
    for position, value in (overrides or {}).items():
        row[position - 1] = value
    return row


class FakeAdapter(adapters.EngineAdapter):
    """Adaptador de motor controlado por la prueba.

    Existe para que el core pueda probarse sin ningún addon de proveedor: las
    suites corren igual en Desarrollo (Blueminds) y en Demo-SyS
    (SimpleDigital).
    """

    key = "fake"
    label = "Motor de prueba"
    module = "hr_payroll"
    generator = "tests.FakeAdapter"
    eligible_states = ("verify", "done", "paid")
    eligible_states_note = "Motor de prueba: admite los tres estados."
    supports_annexes = True
    annexes_note = "Las anexas las controla cada prueba."

    rows = []
    issues = []

    @classmethod
    def is_available(cls, env):
        return True

    @classmethod
    def field_matrix(cls):
        return [adapters.FieldSource(position, "constant", "fixture")
                for position in range(1, previred.FIELD_COUNT + 1)]

    @classmethod
    def generate_rows(cls, env, company, date_from, date_to, payslips):
        return [list(row) for row in cls.rows], list(cls.issues)


class PreviredCase(TransactionCase):

    @classmethod
    def _create_company(cls, name):
        """Crea una compañía rellenando lo que otros addons exijan.

        Varios addons del stack declaran campos `required=True` en
        `res.company`; alguno además llega a la base con un NOT NULL que el
        `create` no rellena. La fixture no debe depender de qué addons estén
        instalados donde corre la suite, así que se pasa un valor **explícito**
        para todo campo obligatorio y almacenado: el de su default si lo tiene
        y, si no, el primero admisible.
        """
        model = cls.env["res.company"]
        values = {"name": name}
        defaults = model.default_get(list(model._fields))
        for field_name, field in model._fields.items():
            if field_name in values or not field.required:
                continue
            if field.compute or field.related or not field.store:
                continue
            default = defaults.get(field_name)
            if default not in (None, False):
                values[field_name] = default
                continue
            if field.type == "selection":
                options = field.get_values(cls.env)
                if options:
                    values[field_name] = options[0]
            elif field.type in ("char", "text"):
                values[field_name] = "test"
        return model.create(values)

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls._create_company("Agrícola Prueba")
        # RUT sintético con DV válido. Si la base tiene una validación de
        # VAT más estricta, el lote funciona igual sin él.
        try:
            cls.company.partner_id.vat = "CL76123456-0"
        except ValidationError:
            cls.company.partner_id.sudo().write({"vat": False})
        cls.other_company = cls._create_company("Otra Prueba")

        cls.env.user.write({
            "company_ids": [(4, cls.company.id), (4, cls.other_company.id)],
            "company_id": cls.company.id,
        })

        cls.dep_agri = cls.env["hr.department"].create({
            "name": "Agrícola", "company_id": cls.company.id})
        cls.dep_admin = cls.env["hr.department"].create({
            "name": "Administración", "company_id": cls.company.id})
        # Departamento homónimo en OTRA compañía: no debe mezclarse nunca.
        cls.dep_agri_other = cls.env["hr.department"].create({
            "name": "Agrícola", "company_id": cls.other_company.id})

        cls.date_from = fields.Date.to_date("2026-08-01")
        cls.date_to = fields.Date.to_date("2026-08-31")
        cls.period = "082026"

        cls.structure = cls._payroll_structure()

    @classmethod
    def _payroll_structure(cls):
        structure_type = cls.env["hr.payroll.structure.type"].create({
            "name": "Prueba Previred"})
        return cls.env["hr.payroll.structure"].create({
            "name": "Estructura Prueba Previred",
            "type_id": structure_type.id,
        })

    @classmethod
    def make_employee(cls, name, identification, department=None,
                      company=None):
        company = company or cls.company
        employee = cls.env["hr.employee"].create({
            "name": name,
            "identification_id": identification,
            "company_id": company.id,
            "department_id": department.id if department else False,
        })
        return employee

    @classmethod
    def make_payslip(cls, employee, department=None, company=None,
                     date_from=None, date_to=None, state="done"):
        """Liquidación con contrato, que es de donde sale el departamento.

        Nace en `done` porque el extractor sólo exporta liquidaciones
        validadas; las pruebas que quieren ejercitar el filtro pasan otro
        estado explícitamente.
        """
        company = company or cls.company
        date_from = date_from or cls.date_from
        date_to = date_to or cls.date_to
        contract_values = {
            "name": "Contrato %s" % employee.name,
            "employee_id": employee.id,
            "company_id": company.id,
            "date_start": "2024-01-01",
            "wage": 800000,
            "structure_type_id": cls.structure.type_id.id,
            "department_id": department.id if department else False,
            "state": "open",
        }
        # SimpleDigital materializa este campo como NOT NULL aunque en otras
        # bases/motores no exista. La fixture usa el maestro real disponible
        # para probar el core sin depender del proveedor instalado.
        contract_model = cls.env["hr.contract"]
        contract_type_field = contract_model._fields.get("contract_type_id")
        if contract_type_field:
            contract_type = cls.env[
                contract_type_field.comodel_name].search([], limit=1)
            if contract_type:
                contract_values["contract_type_id"] = contract_type.id
        contract = contract_model.create(contract_values)
        payslip = cls.env["hr.payslip"].create({
            "name": "Liquidación %s" % employee.name,
            "employee_id": employee.id,
            "contract_id": contract.id,
            "company_id": company.id,
            "struct_id": cls.structure.id,
            "date_from": date_from,
            "date_to": date_to,
        })
        if state and payslip.state != state:
            payslip.state = state
        return payslip

    def build(self, rows, issues=(), departments=None,
              allow_without_department=False, company=None, states=None,
              spec_version="84"):
        """Atajo: construye el dataset con el adaptador falso."""
        FakeAdapter.rows = rows
        FakeAdapter.issues = list(issues)
        return self.env["step.previred.extractor"].build_dataset(
            company=company or self.company,
            date_from=self.date_from,
            date_to=self.date_to,
            adapter=FakeAdapter,
            states=states,
            departments=departments,
            allow_without_department=allow_without_department,
            profile_name="Perfil de prueba",
            spec_version=spec_version,
            spec_effective_from="2025-08" if spec_version == "84" else "2026-08",
        )
