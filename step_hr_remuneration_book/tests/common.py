"""Fixture sintético del Libro de Remuneraciones.

Todos los datos son inventados. No se usan RUT, nombres ni remuneraciones
reales de ninguna empresa.
"""

from odoo import fields
from odoo.tests.common import HttpCase, TransactionCase

from ..tools import dt_book

#: Códigos de regla salarial propios del fixture, para no depender de ninguna
#: localización concreta durante las pruebas.
RULE_CODES = {
    dt_book.CODE_WAGE: "TST_SUELDO",
    dt_book.CODE_BONUS: "TST_BONO",
    dt_book.CODE_GRATIFICATION: "TST_GRAT",
    dt_book.CODE_TOTAL_TAXABLE: "TST_TOTIM",
    dt_book.CODE_TRANSPORT: "TST_MOV",
    dt_book.CODE_MEAL: "TST_COL",
    dt_book.CODE_FAMILY: "TST_ASIG",
    dt_book.CODE_TOTAL_INCOME: "TST_HAB",
    dt_book.CODE_PENSION: "TST_AFP",
    dt_book.CODE_HEALTH: "TST_SALUD",
    dt_book.CODE_HEALTH_EXTRA: "TST_ADI",
    dt_book.CODE_UNEMPLOYMENT: "TST_AFC",
    dt_book.CODE_INCOME_TAX: "TST_IMP",
    dt_book.CODE_CCAF: "TST_CCAF",
    dt_book.CODE_ADVANCES: "TST_ANT",
    dt_book.CODE_OTHER_DEDUCTIONS: "TST_OTROS",
    dt_book.CODE_APVI: "TST_APV",
    dt_book.CODE_TOTAL_DEDUCTIONS: "TST_TDE",
    dt_book.CODE_NET: "TST_LIQ",
}

FULL_GROUP = "step_hr_remuneration_book.group_remuneration_book_full"
TECHNICAL_GROUP = "step_hr_remuneration_book.group_remuneration_book_technical"


class RemunerationBookCommon(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env["res.company"].create({
            "name": "Sintética Steps SpA",
            "vat": "CL76543210-3",
        })
        cls.other_company = cls.env["res.company"].create({
            "name": "Otra Empresa Sintética SpA",
        })
        cls.env.user.company_ids |= cls.company | cls.other_company
        cls.env.user.company_id = cls.company
        # El usuario del fixture necesita el permiso de exportación completa:
        # las pruebas de permisos usan usuarios dedicados y explícitos.
        cls.env.user.groups_id |= (
            cls.env.ref(FULL_GROUP) | cls.env.ref(TECHNICAL_GROUP)
        )

        cls.department_admin = cls.env["hr.department"].create({
            "name": "Administración Sintética", "company_id": cls.company.id,
        })
        cls.department_field = cls.env["hr.department"].create({
            "name": "Campo Sintético", "company_id": cls.company.id,
        })

        cls.structure_type = cls.env["hr.payroll.structure.type"].create({
            "name": "Estructura sintética",
        })
        cls.structure = cls.env["hr.payroll.structure"].create({
            "name": "Nómina sintética",
            "type_id": cls.structure_type.id,
        })
        cls.category = cls.env["hr.salary.rule.category"].create({
            "name": "Sintética", "code": "TSTCAT",
        })
        cls.rules = {}
        for sequence, (dt_code, code) in enumerate(RULE_CODES.items(), start=1):
            cls.rules[dt_code] = cls.env["hr.salary.rule"].create({
                "name": "Regla %s" % code,
                "code": code,
                "sequence": sequence,
                "category_id": cls.category.id,
                "struct_id": cls.structure.id,
                "amount_select": "fix",
                "amount_fix": 0.0,
            })
        cls.work_entry_type = cls.env["hr.work.entry.type"].search(
            [("code", "=", "WORK100")], limit=1
        ) or cls.env["hr.work.entry.type"].create({
            "name": "Asistencia sintética", "code": "WORK100",
        })

        cls.profile = cls.env["step.remuneration.book.profile"].create({
            "name": "Perfil sintético",
            "code": "tst_sintetico",
            "company_id": cls.company.id,
            "detector_rule_codes": "TST_HAB,TST_TDE,TST_LIQ",
            "line_ids": [
                (0, 0, {"dt_code": dt_book.CODE_RUT,
                        "source_type": "employee_rut"}),
                (0, 0, {"dt_code": dt_book.CODE_DAYS,
                        "source_type": "worked_days",
                        "rule_codes": "WORK100"}),
            ] + [
                (0, 0, {"dt_code": dt_code, "source_type": "rule",
                        "rule_codes": code})
                for dt_code, code in RULE_CODES.items()
            ],
        })
        cls.profile.action_activate()
        cls.company.remuneration_book_profile_id = cls.profile

    # -- helpers ------------------------------------------------------------

    @classmethod
    def _create_employee(cls, name, rut, department=None, company=None):
        return cls.env["hr.employee"].create({
            "name": name,
            "identification_id": rut,
            "department_id": department.id if department else False,
            "company_id": (company or cls.company).id,
        })

    @classmethod
    def _contract_type(cls):
        """Tipo de contrato sintético.

        Algunas localizaciones -entre ellas la del proveedor chileno- hacen
        obligatorio `contract_type_id`. El fixture lo resuelve sólo si el campo
        existe, para que la misma suite corra igual en una base con y sin ese
        addon.
        """
        model = cls.env.get("hr.contract.type")
        if model is None:
            return None
        existing = model.search([("name", "=", "Tipo sintético Steps")], limit=1)
        return existing or model.create({"name": "Tipo sintético Steps"})

    @classmethod
    def _create_contract(cls, employee, department=None, wage=500000.0):
        values = {
            "name": "Contrato %s" % employee.name,
            "employee_id": employee.id,
            "department_id": department.id if department else False,
            "structure_type_id": cls.structure_type.id,
            "date_start": fields.Date.to_date("2026-01-01"),
            "wage": wage,
            "state": "open",
            "company_id": employee.company_id.id,
        }
        if "contract_type_id" in cls.env["hr.contract"]._fields:
            contract_type = cls._contract_type()
            if contract_type:
                values["contract_type_id"] = contract_type.id
        # La localización SimpleDigital declara este campo obligatorio, pero
        # su override de ``create`` no conserva siempre el valor por defecto
        # al ejecutar tests de módulos dependientes. Mantener el fixture
        # portable evita acoplar la prueba a que esa localización esté o no
        # instalada en la base.
        if "income_tax_type" in cls.env["hr.contract"]._fields:
            values["income_tax_type"] = "1"
        return cls.env["hr.contract"].create(values)

    @classmethod
    def _create_payslip(cls, employee, contract, values, company=None,
                        date_from="2026-06-01", date_to="2026-06-30",
                        days=30, state="done"):
        """Crea una liquidación con líneas ya valorizadas.

        ``values`` es un diccionario código DT -> importe. Se escriben como
        líneas de liquidación, es decir, como valores ya calculados por el
        motor de nómina: el módulo nunca los recalcula.
        """
        company = company or cls.company
        payslip = cls.env["hr.payslip"].create({
            "name": "Liquidación sintética %s" % employee.name,
            "employee_id": employee.id,
            "contract_id": contract.id,
            "struct_id": cls.structure.id,
            "date_from": fields.Date.to_date(date_from),
            "date_to": fields.Date.to_date(date_to),
            "company_id": company.id,
        })
        # El motor de nómina puebla días trabajados al crear: se reemplazan
        # por los del fixture para controlar el escenario.
        payslip.worked_days_line_ids.unlink()
        cls.env["hr.payslip.worked_days"].create({
            "payslip_id": payslip.id,
            "name": "Días trabajados",
            "work_entry_type_id": cls.work_entry_type.id,
            "number_of_days": days,
            "number_of_hours": days * 8,
        })
        for dt_code, amount in values.items():
            rule = cls.rules[dt_code]
            cls.env["hr.payslip.line"].create({
                "slip_id": payslip.id,
                "salary_rule_id": rule.id,
                "code": rule.code,
                "category_id": cls.category.id,
                "name": rule.name,
                "sequence": rule.sequence,
                "quantity": 1.0,
                "rate": 100.0,
                "amount": amount,
                # `total` se almacena sin cálculo automático en este modelo.
                "total": amount,
            })
        payslip.state = state
        return payslip

    @classmethod
    def _coherent_values(cls, wage=500000, bonus=0, gratification=0,
                         transport=0, meal=0, family=0, deductions=None):
        deductions = deductions or {}
        taxable = wage + bonus + gratification
        income = taxable + transport + meal + family
        total_deductions = sum(deductions.values())
        values = {
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

    def _wizard(self, company=None, month="6", year=2026, mode="full"):
        return self.env["step.hr.remuneration.book.wizard"].create({
            "company_id": (company or self.company).id,
            "month": month,
            "year": year,
            "mode": mode,
        })


class RemunerationBookHttpCommon(RemunerationBookCommon, HttpCase):
    """Mismo fixture sintético, con servidor HTTP para probar las rutas."""
