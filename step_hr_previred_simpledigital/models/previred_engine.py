"""Adaptador Previred del motor SimpleDigital.

Este bridge **sí** depende del addon del proveedor: es el único punto del
sistema que lo importa. El core (`step_hr_previred`) no conoce este motor.

Reutiliza el generador `/hr_payroll/previred/txt` que ya está en producción en
Demo-SyS, incluidas sus líneas anexas por movimiento de personal, de modo que
los importes siguen siendo los que la empresa concilia hoy. Lo que **no**
hereda es su control de acceso: el core valida permiso, compañía y período en
servidor antes de invocarlo, y el controlador de este bridge cierra además la
ruta pública.
"""

import logging

from odoo import _

from odoo.addons.step_hr_previred.models import previred_adapter as adapters
from odoo.addons.step_hr_previred.tools import previred

from . import field_matrix

_logger = logging.getLogger(__name__)

#: Notas de revisión por posición, contrastadas con la especificación v98.
MATRIX_NOTES = {
    8: "Tipo de pago fijo en «01» (remuneraciones del mes, tabla N°3).",
    13: "El generador declara `_get_real_worked_days_from_payslip`, que en "
        "esta base es `hr.payslip._dias_trabajados_previred()` («30 − "
        "ausencias», con «Fuera de contrato» contando como ausencia). El "
        "núcleo NO usa ese valor: recalcula el campo 13 desde la línea de "
        "días trabajados de tipo «Asistencia» (código WORK100, o Tipo y "
        "Descripción «Asistencia»), que es lo que pide el documento funcional. "
        "El valor se escribe también en las líneas anexas.",
    14: "El generador emite «0» donde la tabla N°6 declara «00»; el core lo "
        "serializa de forma canónica como «00».",
    23: "Asignación familiar retroactiva en blanco; sólo aplica a empresas "
        "adheridas a CCAF.",
    76: "Número de FUN fijo en «00000000».",
    86: "El generador nombra la variable `codigo_ex_caja_regimen_ips` pero la "
        "posición 86 de la especificación es «Descuento Dental CCAF».",
    88: "La variable se llama `renta_imponible_ips_ex_caja` y transporta "
        "`total_ccaf_seguro`, que es lo que la posición 88 pide "
        "(«Descuentos por seguro de vida»).",
    90: "La variable se llama `codigo_accidente_trabajo_isl` y transporta "
        "`cotizacion_ccaf_fonasa`, que es lo que la posición 90 pide "
        "(«Cotización a CCAF de no afiliados a Isapres»).",
    92: "Renta imponible del mes anterior a la licencia (RIMA).",
    93: "El motor usa «0» para jornada parcial; el core lo normaliza a «2» "
        "según la tabla N°22.",
    95: "El motor la deja en blanco; en v98 el core calcula 0,90% sobre la "
        "renta imponible AFP desde agosto de 2026.",
    105: "Centro de costos: el motor envía el **código** de la cuenta "
         "analítica recortado a 20 caracteres, que es lo que pide la "
         "especificación.",
}


class SimpleDigitalAdapter(adapters.EngineAdapter):
    """Motor SimpleDigital: controlador `/hr_payroll/previred/txt`."""

    key = "simpledigital"
    label = "Nómina Chilena Simpledigital"
    module = "l10n_cl_simpledigital_payroll"
    generator = "/hr_payroll/previred/txt"

    #: SimpleDigital sí admite `verify`: en su flujo la liquidación se calcula
    #: y queda «por verificar» hasta el cierre del mes, y la declaración
    #: previsional se prepara antes de ese cierre. Es el comportamiento que
    #: Demo-SyS tiene hoy y se conserva **de forma explícita y configurable**,
    #: no como una lista global heredada.
    eligible_states = ("verify", "done", "paid")
    eligible_states_note = (
        "El generador de SimpleDigital exporta «verify», «done» y «paid». En "
        "su flujo la liquidación calculada («verify») ya es la que se declara "
        "a las instituciones previsionales, y el cierre contable ocurre "
        "después. Se conserva ese criterio para no cambiar lo que Demo-SyS "
        "declara hoy, pero queda editable en el perfil. «draft» y «cancel» "
        "están excluidos siempre."
    )

    #: SimpleDigital sí tiene modelo de movimientos: `hr.payslip.
    #: previred_movement_ids`, y el generador ya emite una línea anexa por
    #: cada uno, inmediatamente después de la principal.
    supports_annexes = True
    annexes_note = (
        "Las anexas provienen de `hr.payslip.previred_movement_ids`: el "
        "generador emite una línea por movimiento real, con su código y sus "
        "fechas, justo después de la línea principal. El módulo no crea "
        "ninguna anexa adicional y valida los condicionales que la "
        "especificación exige (fecha desde/hasta obligatorias según el código "
        "de movimiento, y datos del afiliado voluntario en las líneas 03)."
    )

    @classmethod
    def field_matrix(cls):
        return field_matrix.field_sources(MATRIX_NOTES)

    @classmethod
    def generate_rows(cls, env, company, date_from, date_to, payslips):
        try:
            from odoo.addons.l10n_cl_simpledigital_payroll.controllers import (
                previred_txt as vendor,
            )
        except ImportError:
            return [], [cls.missing_engine_issue(cls.label)]

        from odoo.http import request
        if not request:
            return [], [previred.Issue(
                previred.SEVERITY_ERROR, "engine_needs_request",
                _("El generador de %s sólo puede ejecutarse desde una "
                  "petición web. Use el asistente desde la interfaz.",
                  cls.label))]

        controller = vendor.PreviredExportController()
        response = controller.download_previred_txt(
            period=date_from.strftime("%m%Y"), company_id=str(company.id))
        data = getattr(response, "data", b"") or b""
        text = data if isinstance(data, str) \
            else data.decode(previred.ENCODING, errors="replace")
        if not text.strip():
            return [], [previred.Issue(
                previred.SEVERITY_WARNING, "engine_empty",
                _("El generador de %s no devolvió ninguna línea para el "
                  "período solicitado.", cls.label))]

        rows = cls.split_text(text)
        row_meta, meta_issues = cls._contract_meta(env, company, date_from,
                                                   rows)
        if row_meta is None:
            return rows, meta_issues
        return rows, meta_issues, row_meta

    @classmethod
    def _contract_meta(cls, env, company, date_from, rows):
        """Correlación explícita línea principal → contrato.

        El generador del proveedor recorre `hr.payslip` del período (rango de
        `date_from`, estados `verify/done/paid`, compañía) en orden de
        trabajador y emite **una línea principal por liquidación**. Aquí se
        reconstruye esa misma lista y se asocia, RUT por RUT y en el mismo
        orden, cada línea principal con el contrato de su liquidación.

        Devuelve `(row_meta, issues)`. Si la correlación no es fiable
        (recuentos que no cuadran) devuelve `(None, issues)` y el núcleo cae
        al respaldo de unicidad por compañía + período + RUT.
        """
        import calendar as _calendar

        period_start = date_from.replace(day=1)
        period_end = date_from.replace(
            day=_calendar.monthrange(date_from.year, date_from.month)[1])
        vendor_payslips = env["hr.payslip"].sudo().search([
            ("date_from", ">=", period_start),
            ("date_from", "<=", period_end),
            ("state", "in", ["verify", "done", "paid"]),
            ("company_id", "=", company.id),
        ], order="employee_id")

        by_rut = {}
        for payslip in vendor_payslips:
            key = previred.rut_key(payslip.employee_id.identification_id)
            by_rut.setdefault(key, []).append(payslip)

        principals = [row for row in rows
                      if previred.normalize_line_type(
                          row[previred.F_LINE_TYPE - 1])
                      == previred.LINE_PRINCIPAL]
        if len(principals) != len(vendor_payslips):
            return None, [previred.Issue(
                previred.SEVERITY_WARNING, "engine_contract_meta_unavailable",
                _("El generador de %(engine)s emitió %(p)s línea(s) principal(es) "
                  "y el período tiene %(s)s liquidación(es); no se puede "
                  "correlacionar contrato por contrato y la unicidad usará el "
                  "respaldo por RUT.",
                  engine=cls.label, p=len(principals),
                  s=len(vendor_payslips)))]

        seen = {}
        row_meta = []
        for row in principals:
            key = previred.rut_key(
                (row[previred.F_RUT - 1] or "") + (row[previred.F_DV - 1] or ""))
            bucket = by_rut.get(key) or []
            position = seen.get(key, 0)
            seen[key] = position + 1
            payslip = bucket[position] if position < len(bucket) else None
            row_meta.append({
                "contract_id": payslip.contract_id.id
                if payslip and payslip.contract_id else None,
                "payslip_id": payslip.id if payslip else None,
            })
        return row_meta, []


adapters.register(SimpleDigitalAdapter)
