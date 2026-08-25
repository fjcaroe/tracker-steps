"""Registro de adaptadores de origen externo del Libro de Remuneraciones.

Un adaptador es la **única** manera de que un código DT tome su valor desde
algo que no es la propia liquidación. No existe ningún mecanismo para escribir
un modelo, un campo o un dominio Odoo desde la interfaz: cada adaptador está
declarado aquí, en código, con

* un modelo permitido y uno solo,
* un campo de importe permitido y uno solo,
* un conjunto cerrado de parámetros seleccionables,
* y un dominio **construido por el servidor** a partir de la liquidación, el
  trabajador, el contrato, el período y la compañía.

De este modo un Administrador de Nómina puede asignar un perfil aprobado a su
empresa, pero no puede programar una consulta sobre otro modelo, otro campo u
otra compañía.

Todos los adaptadores devuelven ``{payslip_id: entero}`` para el conjunto
completo de liquidaciones: se consulta una vez por lote y no una vez por
liquidación, para evitar el N+1.
"""

import logging

from odoo import _

_logger = logging.getLogger(__name__)


class BookAdapter:
    """Contrato común de los adaptadores."""

    #: Clave técnica seleccionable desde la línea de perfil.
    key = ""
    #: Etiqueta mostrada en la interfaz.
    label = ""
    #: Único modelo Odoo que este adaptador puede leer.
    model = ""
    #: Único campo numérico que este adaptador puede sumar.
    amount_field = ""
    #: Parámetros admitidos: tuplas ``(valor, etiqueta)``. Vacío = sin parámetro.
    params = ()
    #: Motivo acotado por el que el adaptador necesita elevación, o ``None``.
    sudo_reason = None

    # -- utilidades ---------------------------------------------------------

    @classmethod
    def allowed_params(cls):
        return [value for value, label in cls.params]

    @classmethod
    def is_installed(cls, env):
        return env.get(cls.model) is not None

    @classmethod
    def check_param(cls, param):
        """Devuelve un mensaje de error si el parámetro no es admisible."""
        param = (param or "").strip()
        if not cls.params:
            return None
        if param not in cls.allowed_params():
            return _(
                "El adaptador «%(label)s» no admite el parámetro «%(param)s». "
                "Valores admitidos: %(allowed)s.",
                label=cls.label, param=param or "-",
                allowed=", ".join(cls.allowed_params()),
            )
        return None

    @classmethod
    def _scoped(cls, env, payslips):
        """Modelo del adaptador restringido a las compañías del informe.

        Se aplica siempre ``allowed_company_ids``; el filtro por ``company_id``
        del modelo se aplica además dentro de cada adaptador cuando el modelo
        tiene ese campo.
        """
        companies = payslips.mapped("company_id")
        model = env[cls.model].with_context(
            allowed_company_ids=companies.ids
        ).with_company(companies[:1])
        if cls.sudo_reason:
            model = model.sudo()
        return model

    # -- API ----------------------------------------------------------------

    @classmethod
    def values(cls, env, payslips, param):
        raise NotImplementedError


class _PayslipRuleCodesAdapter(BookAdapter):
    """Base de los adaptadores que terminan sumando líneas de la liquidación.

    Es la forma más segura de leer un concepto del proveedor: los importes ya
    están en la liquidación, así que no se sale del registro que el usuario
    tiene derecho a leer y no hay riesgo de mezclar trabajadores, períodos ni
    compañías.
    """

    @classmethod
    def rule_codes(cls, env, payslips, param):
        raise NotImplementedError

    @classmethod
    def values(cls, env, payslips, param):
        codes = set(cls.rule_codes(env, payslips, param))
        if not codes:
            return {}
        result = {}
        for payslip in payslips:
            total = 0.0
            for line in payslip.line_ids:
                if line.code in codes:
                    total += line.total
            if total:
                result[payslip.id] = int(round(total))
        return result


class MovementTypeRulesAdapter(_PayslipRuleCodesAdapter):
    """Conceptos que SimpleDigital materializa como reglas ``MOV_<id>``.

    Cada ``hr.employee.movement.type`` genera su propia regla salarial, y esa
    regla ya suma sus montos dentro de la liquidación. El adaptador resuelve
    qué códigos de regla corresponden al concepto pedido -leyendo sólo el
    modelo de CONFIGURACIÓN, que no contiene datos personales- y después suma
    las líneas de la propia liquidación.
    """

    key = "sd_movement_type_rules"
    label = "SimpleDigital: reglas de tipos de movimiento"
    model = "hr.employee.movement.type"
    #: Se suma ``hr.payslip.line.total``; el modelo del adaptador sólo aporta
    #: los códigos de regla, nunca importes.
    amount_field = "total"
    params = (
        ("bono_ok", "Tipos marcados como Bono"),
        ("comision_ok", "Tipos marcados como Comisión"),
        ("aguinaldo_ok", "Tipos marcados como Aguinaldo"),
        ("movilizacion_ok", "Tipos marcados como Movilización"),
        ("otros_descuentos_ok", "Tipos marcados como Otros descuentos"),
        ("anticipo_prestamo", "Tipos de anticipo o préstamo"),
    )
    sudo_reason = (
        "Sólo se leen el nombre y la regla salarial del catálogo de tipos de "
        "movimiento, que es configuración y no contiene datos personales."
    )

    #: Palabras clave del catálogo para el parámetro que no es un booleano.
    _KEYWORDS = {"anticipo_prestamo": ("anticipo", "prestamo", "préstamo")}

    @classmethod
    def rule_codes(cls, env, payslips, param):
        types = cls._scoped(env, payslips)
        keywords = cls._KEYWORDS.get(param)
        if keywords:
            domain = ["|"] * (len(keywords) - 1)
            domain += [("name", "ilike", word) for word in keywords]
        else:
            domain = [(param, "=", True)]
        records = types.with_context(active_test=False).search(domain)
        return [
            record.salary_rule_id.code
            for record in records
            if record.salary_rule_id and record.salary_rule_id.code
        ]


class MovementLinesAdapter(BookAdapter):
    """Movimientos del trabajador que no llegaron a la liquidación.

    El dominio lo construye el servidor: trabajador de la liquidación, fecha
    del movimiento dentro del período de la liquidación y compañía del
    movimiento igual a la de la liquidación. La configuración sólo elige el
    tipo de concepto entre los declarados aquí.
    """

    key = "sd_movement_lines"
    label = "SimpleDigital: líneas de movimiento del trabajador"
    model = "hr.employee.movement.line"
    amount_field = "amount"
    params = (
        ("bono_ok", "Tipos marcados como Bono"),
        ("comision_ok", "Tipos marcados como Comisión"),
        ("aguinaldo_ok", "Tipos marcados como Aguinaldo"),
        ("otros_descuentos_ok", "Tipos marcados como Otros descuentos"),
    )
    sudo_reason = (
        "El modelo del proveedor no declara reglas de registro por trabajador; "
        "el adaptador acota el dominio a los trabajadores, períodos y "
        "compañías de las liquidaciones del informe y verifica cada registro."
    )

    @classmethod
    def values(cls, env, payslips, param):
        employees = payslips.mapped("employee_id")
        if not employees:
            return {}
        model = cls._scoped(env, payslips)
        dates = list(payslips.mapped("date_from")) + list(payslips.mapped("date_to"))
        records = model.search([
            ("employee_id", "in", employees.ids),
            ("movement_id.date", ">=", min(dates)),
            ("movement_id.date", "<=", max(dates)),
            ("movement_id.company_id", "in", payslips.mapped("company_id").ids),
            ("movement_type_id.%s" % param, "=", True),
        ])
        by_employee = {}
        for record in records:
            by_employee.setdefault(record.employee_id.id, []).append(record)
        result = {}
        for payslip in payslips:
            total = 0.0
            for record in by_employee.get(payslip.employee_id.id, ()):
                movement = record.movement_id
                # Verificación explícita: el registro debe pertenecer a ESTE
                # trabajador, a ESTE período y a ESTA compañía.
                if movement.company_id.id != payslip.company_id.id:
                    continue
                if not movement.date:
                    continue
                if not (payslip.date_from <= movement.date <= payslip.date_to):
                    continue
                total += record.amount or 0.0
            if total:
                result[payslip.id] = int(round(total))
        return result


class CcafDeductionAdapter(BookAdapter):
    """Descuentos CCAF vigentes del trabajador en el período.

    El modelo del proveedor no tiene compañía: la pertenencia se comprueba a
    través del trabajador de la liquidación, nunca por un dominio configurable.
    """

    key = "sd_ccaf_deduction"
    label = "SimpleDigital: descuentos CCAF"
    model = "hr.ccaf.deduction"
    amount_field = "installment_amount"
    params = (
        ("credit", "Crédito social"),
        ("insurance", "Seguro"),
        ("other", "Otros"),
    )
    sudo_reason = (
        "El modelo del proveedor no declara reglas de registro; el adaptador "
        "lo acota a los trabajadores de las liquidaciones del informe."
    )

    @classmethod
    def values(cls, env, payslips, param):
        employees = payslips.mapped("employee_id")
        if not employees:
            return {}
        model = cls._scoped(env, payslips)
        records = model.search([
            ("employee_id", "in", employees.ids),
            ("deduction_type", "=", param),
        ])
        by_employee = {}
        for record in records:
            by_employee.setdefault(record.employee_id.id, []).append(record)
        result = {}
        for payslip in payslips:
            total = 0.0
            for record in by_employee.get(payslip.employee_id.id, ()):
                if record.employee_id.company_id.id != payslip.company_id.id:
                    continue
                start = record.start_date
                end = record.end_date
                if start and start > payslip.date_to:
                    continue
                if end and end < payslip.date_from:
                    continue
                total += record.installment_amount or 0.0
            if total:
                result[payslip.id] = int(round(total))
        return result


#: Registro cerrado. Añadir un origen externo exige tocar este archivo, pasar
#: por revisión de código y desplegar: no se puede improvisar desde la interfaz.
ADAPTERS = {
    adapter.key: adapter
    for adapter in (
        MovementTypeRulesAdapter,
        MovementLinesAdapter,
        CcafDeductionAdapter,
    )
}


def adapter_selection():
    return [(key, adapter.label) for key, adapter in ADAPTERS.items()]


def get_adapter(key):
    return ADAPTERS.get(key)
