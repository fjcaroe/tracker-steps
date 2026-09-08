# -*- coding: utf-8 -*-
"""Deja el catálogo canónico de conceptos de maquinaria tras instalar."""

import logging
import re
import unicodedata

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)

#: Nombre por defecto del plan analítico de cada maestro, usado sólo cuando no
#: se puede deducir del propio maestro ni de sus registros hermanos.
DEFAULT_PLAN_NAMES = {"step.temporada": "Temporada", "step.actividad": "Actividad"}


def post_init_canonical_catalog(env):
    if not isinstance(env, api.Environment):  # compatibilidad con firmas antiguas
        env = api.Environment(env, SUPERUSER_ID, {})
    env["type.service.machinery"]._ensure_canonical_catalog()
    ensure_analytic_masters(env)


def _normalize(value):
    """Compara nombres ignorando tildes, mayúsculas y separadores.

    Así ``T26-27`` reconoce a la cuenta analítica ``T2627`` y ``Mantención de
    campo`` a ``Mantención del campo``.
    """
    text = unicodedata.normalize("NFKD", value or "")
    text = "".join(char for char in text if not unicodedata.combining(char))
    return re.sub(r"[^a-z0-9]", "", text.lower())


def _plan_for(env, records, record):
    """Plan analítico donde debe vivir la cuenta de ``record``.

    Prioridad: el plan declarado en el maestro, el de sus hermanos ya
    configurados y, por último, el plan que lleva el nombre convencional.
    """
    plan = record._fields.get("plan_id") and record.plan_id
    if plan:
        return plan
    siblings = records.filtered(lambda item: item.cost_id).mapped("cost_id.plan_id")
    if siblings:
        return siblings[0]
    return env["account.analytic.plan"].search(
        [("name", "=", DEFAULT_PLAN_NAMES[record._name])], limit=1)


def ensure_analytic_masters(env):
    """Garantiza que Temporada y Actividad tengan su cuenta analítica.

    El comprobante de horas máquina distribuye Temporada, Centro de costos y
    Actividad, y para ello necesita la *cuenta analítica* de cada maestro. Los
    maestros que ya la tienen no se tocan, ni siquiera cuando el nombre no
    coincide: reasignarlos cambiaría analítica ya contabilizada.

    Es idempotente: una segunda pasada no crea ni reasigna nada.
    """
    report = {"vinculadas": [], "creadas": [], "sin_plan": [], "revisar": []}
    Account = env["account.analytic.account"].sudo()
    for model in ("step.temporada", "step.actividad"):
        records = env[model].sudo().search([])
        by_plan = {}
        for record in records:
            if record.cost_id:
                if _normalize(record.cost_id.display_name) != _normalize(record.name):
                    report["revisar"].append(
                        "%s %s -> %s" % (model, record.name, record.cost_id.display_name))
                continue
            plan = _plan_for(env, records, record)
            if not plan:
                report["sin_plan"].append("%s %s" % (model, record.name))
                continue
            if plan.id not in by_plan:
                by_plan[plan.id] = {
                    _normalize(account.name): account
                    for account in Account.search([("plan_id", "=", plan.id)])
                }
            existing = by_plan[plan.id].get(_normalize(record.name))
            if existing:
                record.cost_id = existing
                report["vinculadas"].append(
                    "%s %s -> %s" % (model, record.name, existing.display_name))
                continue
            values = {"name": record.name, "plan_id": plan.id}
            if record._fields.get("company_id") and record.company_id:
                values["company_id"] = record.company_id.id
            created = Account.create(values)
            by_plan[plan.id][_normalize(record.name)] = created
            record.cost_id = created
            report["creadas"].append("%s %s -> %s" % (model, record.name, created.display_name))
    return report
