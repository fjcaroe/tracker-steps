"""Repeatable smoke test for the multi-center template budget engine.

Run from an Odoo shell after ``migrate_steps_qa_data.py``::

    exec(open('/path/validate_template_budget.py').read())
    validate(env)
"""


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
    if probe.line_ids.quantity_per_ha != 5.0 or probe.line_ids.cost_per_ha != 500.0:
        raise AssertionError("La normalización de plantillas con base mayor a 1 ha falló.")

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
        "base_2ha_quantity_per_ha": probe.line_ids.quantity_per_ha,
    }
    env.cr.commit()
    print("VALIDATION_RESULT", result)
    return result
