"""Adaptador Previred del motor Blueminds (`l10n_cl_hr`).

Este bridge **sí** depende del addon del proveedor: es el único punto del
sistema que lo importa. El core (`step_hr_previred`) no conoce este motor.

Reutiliza el asistente `wizard.export.csv.previred` que ya está en producción,
de modo que los importes de los 105 campos siguen siendo los que la empresa
concilia hoy. Lo que **no** hereda son sus defectos de alcance: el core
selecciona por su cuenta las liquidaciones elegibles y descarta las filas que
el asistente emite de más.
"""

import base64
import logging

from odoo import _

from odoo.addons.step_hr_previred.models import previred_adapter as adapters
from odoo.addons.step_hr_previred.tools import previred

from . import field_matrix

_logger = logging.getLogger(__name__)

#: Notas de revisión por posición, contrastadas con la especificación v98.
MATRIX_NOTES = {
    12: "El motor fija «0» (activo no pensionado) en vez de leer el tipo de "
        "trabajador de la tabla N°5; el campo existe en el contrato.",
    14: "Fijo en «00». Correcto para este motor: no tiene modelo de "
        "movimientos múltiples, así que no hay anexas que informar.",
    24: "Reintegro de cargas familiares siempre en cero.",
    25: "Subsidio trabajador joven siempre «N» (tabla N°9, uso futuro).",
    64: "Renta imponible IPS sólo cuando la institución de salud es «07» "
        "(Fonasa).",
    90: "Cotización a CCAF de no afiliados a Isapre: se calcula como renta "
        "imponible CCAF x tasa del indicador del período.",
    93: "El motor emite «0»; el core lo reemplaza por 1 (completa) o 2 "
        "(parcial) desde la jornada semanal del contrato.",
    94: "El motor la deja en cero; en v98 el core calcula 1,00% sobre la "
        "renta imponible AFP ya conciliada.",
    95: "El motor la deja en blanco; en v98 el core calcula 0,90% sobre la "
        "renta imponible AFP para remuneraciones desde agosto de 2026.",
    105: "Centro de costos: el motor envía el **nombre** de la cuenta "
         "analítica; la especificación admite 20 caracteres y el validador "
         "rechaza el registro si se excede.",
}


class BluemindsAdapter(adapters.EngineAdapter):
    """Motor Blueminds: asistente `wizard.export.csv.previred`."""

    key = "l10n_cl_hr"
    label = "Nómina Chilena Blueminds (l10n_cl_hr)"
    module = "l10n_cl_hr"
    generator = "wizard.export.csv.previred.action_generate_csv"

    #: El flujo de este motor confirma la liquidación al cerrarla: `done` y
    #: `paid` son las validadas. `verify` es «calculada, sin confirmar» y no
    #: debe declararse ante las instituciones previsionales.
    eligible_states = ("done", "paid")
    eligible_states_note = (
        "En el flujo Blueminds una liquidación queda validada al confirmarse "
        "(«done») y sigue válida al pagarse («paid»). «verify» es una "
        "liquidación calculada pero no confirmada, así que no se exporta. El "
        "generador del proveedor no filtraba por estado y exportaba también "
        "borradores: esta lista corrige ese defecto."
    )

    #: `l10n_cl_hr` guarda el movimiento de personal en un único campo
    #: Selection de `hr.payslip` (`movimientos_personal`), que ya viaja en el
    #: campo 15 de la línea principal. **No existe** un modelo de movimientos
    #: múltiples, así que no hay dato que justifique una línea anexa.
    supports_annexes = False
    annexes_note = (
        "Este motor no tiene modelo de movimientos de personal múltiples: "
        "`hr.payslip.movimientos_personal` es un solo código que ya se informa "
        "en el campo 15 de la línea principal. No se generan líneas 01/02/03 "
        "porque no hay datos que las respalden; inventarlas declararía "
        "movimientos inexistentes ante las instituciones previsionales."
    )

    @classmethod
    def field_matrix(cls):
        return field_matrix.field_sources(MATRIX_NOTES)

    @classmethod
    def generate_rows(cls, env, company, date_from, date_to, payslips):
        model = env.get("wizard.export.csv.previred")
        if model is None:
            return [], [cls.missing_engine_issue(cls.label)]

        # El asistente del proveedor busca por `date_from` sin acotar
        # compañía. Se ejecuta con el contexto de la compañía pedida y el core
        # descarta después lo que no corresponda.
        wizard = model.with_company(company).with_context(
            allowed_company_ids=company.ids,
        ).create({
            "date_from": date_from,
            "date_to": date_to,
            "in_all": True,
        })
        wizard.action_generate_csv()
        if not wizard.file_data:
            return [], [previred.Issue(
                previred.SEVERITY_WARNING, "engine_empty",
                _("El generador de %s no devolvió ninguna línea para el "
                  "período solicitado.", cls.label))]

        raw = base64.b64decode(wizard.file_data)
        text = raw.decode(previred.ENCODING, errors="replace")
        return cls.split_text(text), []


adapters.register(BluemindsAdapter)
