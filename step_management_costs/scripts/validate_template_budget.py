"""Repeatable smoke test for the multi-center template budget engine.

Run from an Odoo shell after ``migrate_steps_qa_data.py``::

    exec(open('/path/validate_template_budget.py').read())
    validate(env)
"""

from datetime import date


def validate(env):
    Template = env["step.management.budget.template"]
    Center = env["step.management.cost.center"]
    Budget = env["step.management.operational.budget"]

    template = Template.search([("name", "=", "Plantilla Ara MBO T2526")], limit=1)
    centers = Center.search([("hectares", ">", 0)], order="hectares asc", limit=2)
    if not template or len(centers) != 2:
        raise RuntimeError("Se requiere la plantilla migrada y dos centros con hectáreas.")

    budget = Budget.search([
        ("description", "=", "Demostración plantilla multi-centro"),
    ], limit=1)
    allocation_commands = [
        (0, 0, {"center_id": center.id, "hectares": center.hectares})
        for center in centers
    ]
    if not budget:
        budget = Budget.create({
            "description": "Demostración plantilla multi-centro",
            "season": "2026/2027",
            "template_id": template.id,
            "allocation_ids": allocation_commands,
        })
    else:
        if budget.state not in ("draft", "calculated"):
            budget.action_set_draft()
        budget.allocation_ids.unlink()
        budget.write({
            "template_id": template.id,
            "allocation_ids": allocation_commands,
        })

    budget.action_generate_lines()
    expected = round(template.total_per_ha * budget.total_hectares, 2)
    actual = round(budget.total_amount, 2)
    if actual != expected:
        raise AssertionError(
            "Escalamiento incorrecto: esperado %s, obtenido %s" % (expected, actual)
        )

    dashboard = Budget.get_management_dashboard(days=0)
    root_menu = env.ref("step_management_costs.menu_management_root")
    child_names = set(root_menu.child_id.mapped("name"))
    excluded = {"Cultivos", "Informes"} & child_names
    if excluded:
        raise AssertionError("Se encontraron menús excluidos: %s" % sorted(excluded))
    if dashboard["budgets"]["total"] < 1 or dashboard["templates"] < 1:
        raise AssertionError("El tablero no está recuperando los datos migrados.")

    probe = Template.new({
        "name": "Validación en memoria",
        "base_hectares": 2.0,
        "line_ids": [(0, 0, {
            "category": "labor",
            "group_id": template.line_ids[0].group_id.id,
            "indicator": "Indicador de prueba",
            "base_quantity": 10.0,
            "unit_price": 100.0,
        })],
    })
    probe.line_ids._compute_amounts()
    probe_quantity_per_ha = probe.line_ids.quantity_per_ha
    if probe_quantity_per_ha != 5.0 or probe.line_ids.cost_per_ha != 500.0:
        raise AssertionError("La normalización de plantillas con base mayor a 1 ha falló.")

    Rate = env["step.management.exchange.rate"]
    usd = env.ref("base.USD")
    estimated_usd = Rate.search([
        ("company_id", "=", env.company.id),
        ("currency_id", "=", usd.id),
        ("year", "=", budget.date.year),
        ("month", "=", "%02d" % budget.date.month),
    ], limit=1)
    if not estimated_usd:
        raise AssertionError("Falta el tipo de cambio USD estimado del mes del presupuesto.")
    expected_usd = budget.total_amount / estimated_usd.company_value_per_unit
    if not budget.conversion_available or abs(budget.total_amount_converted - expected_usd) > 0.01:
        raise AssertionError("La conversión presupuestaria a USD estimado es incorrecta.")

    actual_result = Rate.get_conversion(
        budget.total_amount, budget.currency_id, usd, env.company, budget.date, "actual",
    )
    if not actual_result["available"] or actual_result["amount"] <= 0:
        raise AssertionError("La conversión con tasa real Odoo no está disponible.")

    eur = env.ref("base.EUR")
    probe_rate = Rate.create({
        "company_id": env.company.id,
        "currency_id": eur.id,
        "year": 2040,
        "month": "01",
        "company_value_per_unit": 1100.0,
        "notes": "Registro temporal de validación; se elimina inmediatamente.",
    })
    eur_result = Rate.get_conversion(
        1100000.0, env.company.currency_id, eur, env.company, date(2040, 1, 15), "estimated",
    )
    probe_rate.unlink()
    if not eur_result["available"] or abs(eur_result["amount"] - 1000.0) > 0.01:
        raise AssertionError("La conversión estimada genérica para otras monedas falló.")

    probe_month = env["step.management.budget.month"].new({
        "budget_line_id": budget.line_ids[0].id,
        "month": "jan",
    })
    probe_month._compute_conversion_date()
    if probe_month.conversion_date != date(2027, 1, 1):
        raise AssertionError("La distribución mensual no interpretó correctamente la temporada 2026/2027.")

    env.ref("step_management_costs.menu_exchange_rate")

    result = {
        "budget_id": budget.id,
        "folio": budget.name,
        "centers": len(budget.allocation_ids),
        "hectares": budget.total_hectares,
        "lines": budget.line_count,
        "cost_per_ha": budget.cost_per_ha,
        "expected": expected,
        "actual": actual,
        "scaling_ok": True,
        "dashboard_budgets": dashboard["budgets"]["total"],
        "dashboard_templates": dashboard["templates"],
        "excluded_menus": sorted(excluded),
        "base_2ha_quantity_per_ha": probe_quantity_per_ha,
        "estimated_usd_value": estimated_usd.company_value_per_unit,
        "budget_usd_estimated": budget.total_amount_converted,
        "budget_usd_actual": actual_result["amount"],
        "generic_eur_ok": True,
        "january_conversion_month": str(probe_month.conversion_date),
    }
    env.cr.commit()
    print("VALIDATION_RESULT", result)
    return result
