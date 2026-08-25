import logging
from collections import defaultdict
from datetime import timedelta

from odoo import fields


_logger = logging.getLogger(__name__)


def _field(record, name, default=False):
    return record[name] if name in record._fields else default


def _mark_legacy_masters(env):
    Product = env["product.template"].sudo()
    if "x_studio_es_colacin" in Product._fields:
        Product.search([("x_studio_es_colacin", "=", True)]).write({"is_meal": True})

    Employee = env["hr.employee"].sudo()
    legacy_flags = [name for name in ("x_studio_tiene_colacin", "x_studio_tiene_colacin_1") if name in Employee._fields]
    if legacy_flags:
        domain = []
        for index, field_name in enumerate(legacy_flags):
            if index:
                domain.insert(0, "|")
            domain.append((field_name, "=", True))
        Employee.search(domain).write({"meal_eligible": True})


def _legacy_suppliers(env):
    supplier_ids = set()
    for model_name, field_name in (
        ("x_tarifa_colaciones", "x_studio_proveedor"),
        ("x_plan_colaciones", "x_studio_proveedor"),
        ("x_registro_colaciones", "x_studio_proveedor_colacin"),
    ):
        Model = env.get(model_name)
        if Model is None or field_name not in Model._fields:
            continue
        supplier_ids.update(Model.sudo().search([]).mapped(field_name).ids)
    if supplier_ids:
        env["res.partner"].sudo().browse(supplier_ids).write({"is_meal_supplier": True})


def _migrate_tariffs(env):
    Legacy = env.get("x_tarifa_colaciones")
    LegacyLine = env.get("x_tarifa_colaciones_line_606ce")
    if Legacy is None or LegacyLine is None:
        return
    Tariff = env["step.colacion.tariff"].sudo()
    for legacy in Legacy.sudo().search([]):
        supplier = _field(legacy, "x_studio_proveedor")
        if not supplier:
            continue
        company = _field(legacy, "x_studio_company_id") or env.company
        lines = LegacyLine.sudo().search([("x_tarifa_colaciones_id", "=", legacy.id)])
        by_currency = defaultdict(lambda: env["x_tarifa_colaciones_line_606ce"])
        for line in lines:
            product = _field(line, "x_studio_producto")
            if not product:
                continue
            product.write({"is_meal": True})
            currency = _field(line, "x_studio_moneda") or company.currency_id
            by_currency[currency.id] |= line
        for currency_id, currency_lines in by_currency.items():
            legacy_ref = "x_tarifa_colaciones,%s,%s" % (legacy.id, currency_id)
            if Tariff.search_count([("legacy_ref", "=", legacy_ref)]):
                continue
            valid_from = _field(legacy, "x_studio_date") or fields.Date.to_date(legacy.create_date) or fields.Date.context_today(legacy)
            valid_to = _field(legacy, "x_studio_vigencia") or False
            tariff = Tariff.create({
                "name": legacy.display_name,
                "supplier_id": supplier.id,
                "company_id": company.id,
                "currency_id": currency_id,
                "valid_from": valid_from,
                "valid_to": valid_to,
                "legacy_ref": legacy_ref,
                "line_ids": [(0, 0, {
                    "sequence": _field(line, "x_studio_sequence", 10),
                    "product_tmpl_id": line.x_studio_producto.id,
                    "price": _field(line, "x_studio_precio_colacin", 0.0),
                }) for line in currency_lines],
            })
            if _field(legacy, "x_active", True):
                try:
                    with env.cr.savepoint():
                        tariff.action_activate()
                except Exception as exc:
                    _logger.warning("Tarifa Studio %s migrada como borrador: %s", legacy.id, exc)


def _migrate_registrations(env):
    Legacy = env.get("x_registro_colaciones")
    LegacyLine = env.get("x_registro_colaciones_line_b71e5")
    if Legacy is None or LegacyLine is None:
        return
    Registration = env["step.colacion.registration"].sudo()
    for header in Legacy.sudo().search([]):
        supplier = _field(header, "x_studio_proveedor_colacin")
        if not supplier:
            continue
        legacy_state = _field(header, "x_studio_selection_field_9lm_1k0icduec", "status1")
        for line in LegacyLine.sudo().search([("x_registro_colaciones_id", "=", header.id)]):
            employee = _field(line, "x_studio_trabajador")
            product = _field(line, "x_studio_producto_colacin")
            event_datetime = _field(line, "x_studio_fecha_hora")
            if not employee or not product or not event_datetime:
                continue
            legacy_ref = "x_registro_colaciones_line_b71e5,%s" % line.id
            if Registration.search_count([("legacy_ref", "=", legacy_ref)]):
                continue
            product.write({"is_meal": True})
            employee.write({"meal_eligible": True})
            values = {
                "event_datetime": event_datetime,
                "employee_id": employee.id,
                "employee_name_snapshot": employee.name,
                "department_id": employee.department_id.id,
                "product_tmpl_id": product.id,
                "supplier_id": supplier.id,
                "quantity": 1,
                "source": "manual",
                "company_id": employee.company_id.id,
                "legacy_ref": legacy_ref,
            }
            if legacy_state in ("status2", "status3"):
                price = _field(line, "x_studio_tarifa_colacin", 0.0)
                values.update({
                    "state": "validated",
                    "currency_id": employee.company_id.currency_id.id,
                    "unit_cost": price,
                    "total_cost": price,
                })
            try:
                with env.cr.savepoint():
                    Registration.create(values)
            except Exception as exc:
                _logger.warning("Registro Studio %s no migrado: %s", line.id, exc)


def _migrate_plans(env):
    Legacy = env.get("x_plan_colaciones")
    LegacyLine = env.get("x_plan_colaciones_line_b555c")
    if Legacy is None or LegacyLine is None:
        return
    Plan = env["step.colacion.plan"].sudo()
    for legacy in Legacy.sudo().search([]):
        supplier = _field(legacy, "x_studio_proveedor")
        department = _field(legacy, "x_studio_departamento_1")
        week_start = _field(legacy, "x_studio_fecha")
        if not supplier or not department or not week_start:
            continue
        week_start = fields.Date.to_date(week_start)
        week_start -= timedelta(days=week_start.weekday())
        legacy_ref = "x_plan_colaciones,%s" % legacy.id
        if Plan.search_count([("legacy_ref", "=", legacy_ref)]):
            continue
        company = _field(legacy, "x_studio_company_id") or env.company
        plan_lines = []
        for line in LegacyLine.sudo().search([("x_plan_colaciones_id", "=", legacy.id)]):
            product = _field(line, "x_studio_producto_colacin")
            if not product:
                continue
            product.write({"is_meal": True})
            plan_lines.append((0, 0, {
                "sequence": _field(line, "x_studio_sequence", 10),
                "product_tmpl_id": product.id,
                "monday": _field(line, "x_studio_lunes_1", 0),
                "tuesday": _field(line, "x_studio_martes_1", 0),
                "wednesday": _field(line, "x_studio_mircoles_1", 0),
                "thursday": _field(line, "x_studio_jueves_1", 0),
                "friday": _field(line, "x_studio_viernes_1", 0),
                "saturday": _field(line, "x_studio_sbado_1", 0),
                "sunday": _field(line, "x_studio_domingo_1", 0),
                "unit_cost": _field(line, "x_studio_tarifa", 0.0),
            }))
        try:
            with env.cr.savepoint():
                Plan.create({
                    "name": legacy.display_name,
                    "week_start": week_start,
                    "department_id": department.id,
                    "supplier_id": supplier.id,
                    "company_id": company.id,
                    "legacy_ref": legacy_ref,
                    "line_ids": plan_lines,
                })
        except Exception as exc:
            _logger.warning("Plan Studio %s no migrado: %s", legacy.id, exc)


def _hide_legacy_app_menu(env):
    native_root = env.ref("step_colaciones.menu_colaciones_root", raise_if_not_found=False)
    if not native_root:
        return
    candidates = env["ir.ui.menu"].sudo().search([("name", "=", "Colaciones"), ("parent_id", "=", False)])
    for menu in candidates - native_root:
        xmlid = menu.get_external_id().get(menu.id, "")
        if xmlid.startswith("studio_customization."):
            menu.active = False


def _grant_admin_access(env):
    """Make the application immediately available to the database administrator."""
    admin = env.ref("base.user_admin", raise_if_not_found=False)
    manager_group = env.ref("step_colaciones.group_colaciones_manager", raise_if_not_found=False)
    if admin and manager_group:
        admin.sudo().write({"groups_id": [(4, manager_group.id)]})


def post_init_hook(env):
    _mark_legacy_masters(env)
    _legacy_suppliers(env)
    _migrate_tariffs(env)
    _migrate_registrations(env)
    _migrate_plans(env)
    _hide_legacy_app_menu(env)
    _grant_admin_access(env)
