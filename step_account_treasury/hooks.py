# -*- coding: utf-8 -*-
"""Migración del prototipo Studio de Tesorería al módulo propio.

Es idempotente y tolerante: si el prototipo no existe (Demo, Demo-SyS) no hace
nada. Nunca borra los modelos, tablas, vistas ni registros Studio: sólo copia,
deja una referencia de legado y —una vez comprobada la paridad— archiva los
lanzadores Studio específicos de Tesorería.
"""

import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)

#: Modelos del prototipo Studio.
STUDIO_CONCEPT = "x_concepto_flujo_caja"
STUDIO_FLOW = "x_flujo_de_caja"
STUDIO_STAGE = "x_flujo_de_caja_stage"

#: El código Studio codifica el signo: 01 saldo inicial, 1x ingreso, 2x egreso.
def _flow_type_from_code(code):
    code = (code or "").strip()
    if code == "01":
        return "opening"
    if code.startswith("2"):
        return "outflow"
    return "inflow"


#: Etapa Studio -> estado del modelo propio.
STAGE_TO_STATE = {
    "nuevo": "draft",
    "en progreso": "in_progress",
    "listo": "approved",
}

#: Lanzadores Studio que se archivan al terminar (por nombre, sin IDs fijos).
STUDIO_MENU_NAMES = ("tesorería", "tesoreria", "flujo de caja",
                     "concepto flujo caja", "flujo de caja stages")


def migrate_studio_treasury(env):
    """Copia conceptos y flujos Studio al módulo propio. Devuelve un informe."""
    report = {
        "conceptos_studio": 0, "conceptos_creados": 0, "conceptos_existentes": 0,
        "flujos_studio": 0, "flujos_creados": 0, "flujos_existentes": 0,
        "cuentas_migradas": 0, "menus_archivados": [],
    }
    Concept = env["step.treasury.concept"].sudo()
    Flow = env["step.cashflow"].sudo()

    # --- conceptos ------------------------------------------------------
    if STUDIO_CONCEPT in env:
        studio_concepts = env[STUDIO_CONCEPT].sudo().with_context(active_test=False).search([])
        report["conceptos_studio"] = len(studio_concepts)
        company = env["res.company"].sudo().search([], order="id", limit=1)
        for source in studio_concepts:
            code = (getattr(source, "x_studio_cdigo_flujo", False) or "").strip()
            if not code:
                continue
            existing = Concept.with_context(active_test=False).search([
                ("legacy_studio_id", "=", source.id)], limit=1)
            if not existing:
                existing = Concept.with_context(active_test=False).search([
                    ("code", "=", code), ("company_id", "=", company.id)], limit=1)
            account_ids = []
            raw_account = getattr(source, "x_studio_cuentas_posibles", False)
            account_id = raw_account.id if hasattr(raw_account, "id") else raw_account
            if account_id:
                account = env["account.account"].sudo().browse(account_id).exists()
                if account and company in account.company_ids:
                    account_ids = [(4, account.id)]
                    report["cuentas_migradas"] += 1
            values = {
                "name": source.x_name or code,
                "code": code,
                "flow_type": _flow_type_from_code(code),
                "sequence": getattr(source, "x_studio_sequence", 10) or 10,
                "active": bool(getattr(source, "x_active", True)),
                "company_id": company.id,
                "legacy_studio_id": source.id,
            }
            if existing:
                existing.write(values)
                if account_ids and not existing.account_ids:
                    existing.write({"account_ids": account_ids})
                report["conceptos_existentes"] += 1
            else:
                Concept.create(dict(values, account_ids=account_ids))
                report["conceptos_creados"] += 1

    # --- flujos ---------------------------------------------------------
    if STUDIO_FLOW in env:
        studio_flows = env[STUDIO_FLOW].sudo().with_context(active_test=False).search([])
        report["flujos_studio"] = len(studio_flows)
        for source in studio_flows:
            existing = Flow.search([("legacy_studio_id", "=", source.id)], limit=1)
            if existing:
                report["flujos_existentes"] += 1
                continue
            company = source.x_studio_empresa or env["res.company"].sudo().search(
                [], order="id", limit=1)
            currency = source.x_studio_moneda_del_flujo or company.currency_id
            stage_name = ""
            stage = getattr(source, "x_studio_stage_id", False)
            if stage:
                stage_name = (stage.x_name or "").strip().lower()
            values = {
                "name": source.x_name or "Flujo Studio %s" % source.id,
                "date": source.x_studio_fecha or source.create_date,
                "company_id": company.id,
                "start_date": source.x_studio_periodo_flujo or (
                    source.x_studio_date_start and source.x_studio_date_start.date()),
                "responsible_id": source.x_studio_responsable.id or False,
                "approver_id": source.x_studio_aprueba.id or False,
                "currency_id": currency.id,
                "aux_currency_id": company.operational_currency_id.id or False,
                "state": STAGE_TO_STATE.get(stage_name, "draft"),
                "legacy_studio_id": source.id,
            }
            rate = getattr(source, "x_studio_tipo_de_cambio", 0.0) or 0.0
            if rate and values["aux_currency_id"]:
                values.update({
                    "rate_policy": "manual",
                    "manual_rate": rate,
                    "manual_rate_reason": "Migrado del prototipo Studio",
                })
            Flow.with_context(treasury_bypass_lock=True).create(values)
            report["flujos_creados"] += 1

    _logger.info("Tesorería: migración Studio %s", report)
    return report


def archive_studio_menus(env, report=None):
    """Archiva los lanzadores Studio de Tesorería, sin borrar nada."""
    report = report if report is not None else {"menus_archivados": []}
    Menu = env["ir.ui.menu"].sudo().with_context(**{"ir.ui.menu.full_list": True})
    data = env["ir.model.data"].sudo().search([
        ("model", "=", "ir.ui.menu"), ("module", "=", "studio_customization")])
    emptied_parents = set()
    for entry in data:
        menu = Menu.browse(entry.res_id).exists()
        if not menu or not menu.active:
            continue
        # No asumir que es_CL está cargado (una base limpia puede tener sólo
        # en_US). El nombre fuente del menú ya está en español.
        label = (menu.name or "").strip().lower()
        # No basta el nombre: otra app Studio puede tener legítimamente un
        # menú "Flujo de Caja". Se exige además que el XMLID identifique el
        # prototipo de Contabilidad/Tesorería o que la acción abra uno de sus
        # modelos conocidos.
        xml_name = (entry.name or "").lower()
        action_model = getattr(menu.action, "res_model", False) if menu.action else False
        is_treasury_prototype = (
            action_model in (STUDIO_CONCEPT, STUDIO_FLOW, STUDIO_STAGE)
            or (
                label in ("tesorería", "tesoreria")
                and "contabilidad" in xml_name
                and "tesorer" in xml_name
            )
            or (
                label in STUDIO_MENU_NAMES
                and "contabilidad" in xml_name
                and "flujo" in xml_name
            )
        )
        if label in STUDIO_MENU_NAMES and is_treasury_prototype:
            if menu.parent_id:
                emptied_parents.add(menu.parent_id.id)
            menu.write({"active": False})
            report.setdefault("menus_archivados", []).append("%s (#%s)" % (menu.name, menu.id))

    # Sólo los contenedores que ESTA pasada dejó vacíos: no se tocan menús
    # Studio ajenos a Tesorería.
    for parent in emptied_parents:
        parent = Menu.browse(parent).exists()
        if not parent or not parent.active or not parent.parent_id or parent.action:
            continue
        if Menu.search_count([("parent_id", "=", parent.id)]):
            continue
        parent.write({"active": False})
        report.setdefault("menus_archivados", []).append(
            "%s (#%s, contenedor vacío)" % (parent.name, parent.id))

    _logger.info("Tesorería: menús Studio archivados %s", report.get("menus_archivados"))
    return report


def grant_initial_groups(env):
    """Perfil inicial: quien ya administra Contabilidad gestiona Tesorería.

    Es sólo un punto de partida razonable para que la app sea alcanzable tras
    instalar; el reparto fino de los cuatro perfiles queda en manos del cliente.
    """
    manager = env.ref("step_account_treasury.group_treasury_manager", raise_if_not_found=False)
    reader = env.ref("step_account_treasury.group_treasury_reader", raise_if_not_found=False)
    granted = {"manager": 0, "reader": 0}
    if manager:
        accountants = env.ref("account.group_account_manager", raise_if_not_found=False)
        if accountants:
            users = accountants.users.filtered(lambda u: not u.share)
            if users:
                users.write({"groups_id": [(4, manager.id)]})
                granted["manager"] = len(users)
    if reader:
        billing = env.ref("account.group_account_invoice", raise_if_not_found=False)
        if billing:
            users = billing.users.filtered(
                lambda u: not u.share and manager not in u.groups_id)
            if users:
                users.write({"groups_id": [(4, reader.id)]})
                granted["reader"] = len(users)
    _logger.info("Tesorería: perfiles iniciales asignados %s", granted)
    return granted


def post_init_treasury(env):
    if not isinstance(env, api.Environment):  # compatibilidad de firmas
        env = api.Environment(env, SUPERUSER_ID, {})
    report = migrate_studio_treasury(env)
    archive_studio_menus(env, report)
    grant_initial_groups(env)
