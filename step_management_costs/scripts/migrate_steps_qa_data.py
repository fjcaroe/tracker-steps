"""One-time, idempotent migration of useful Gestión y Costos data from steps_qa.

Run from an Odoo shell connected to the target database:
    exec(open('/path/step_management_costs/scripts/migrate_steps_qa_data.py').read())
    migrate(env)

The addon itself does not depend on these records and remains portable.
"""


def migrate(env):
    company = env.company
    Group = env["step.management.budget.group"]
    Center = env["step.management.cost.center"]
    Template = env["step.management.budget.template"]

    group_values = [
        ("01", "Mano de obra", None), ("02", "Insumos agrícolas", None),
        ("03", "Maquinarias", None), ("04", "Gastos y servicios", None),
        ("06", "Materiales de embalaje", None), ("0101", "Personal propio", "01"),
        ("0102", "Contratista", "01"), ("0103", "Movilización", "01"),
        ("0201", "Fertilizantes", "02"), ("0202", "Herbicidas", "02"),
        ("0203", "Pesticidas", "02"), ("0204", "Insecticidas", "02"),
        ("0205", "Otros agroquímicos", "02"), ("0301", "Combustibles", "03"),
        ("0302", "Mantención y repuestos", "03"), ("0104", "EPP", "01"),
        ("0401", "Artículos de ferretería", "04"), ("0402", "Herramientas", "04"),
        ("0403", "Maderas", "04"), ("0404", "Envases", "04"),
        ("05", "Plantas frutales", None), ("0405", "Otros gastos", "04"),
        ("0406", "Otros servicios", "04"), ("0303", "Arriendo maquinarias", "03"),
    ]
    groups = {}
    for code, name, _parent in group_values:
        group = Group.search([("code", "=", code), ("company_id", "=", company.id)], limit=1)
        if not group:
            group = Group.create({"code": code, "name": name, "company_id": company.id})
        groups[code] = group
    for code, _name, parent_code in group_values:
        if parent_code and groups[code].parent_id != groups[parent_code]:
            groups[code].parent_id = groups[parent_code]

    center_values = [
        ("01012018", "Ara Brigitta 2018", "crop", 6.0, "C33 Brigitta 2 ha", "Arándanos", "Brigitta"),
        ("01777001", "Administración", "administrative", 0.0, "", "", ""),
        ("01999005", "Tractor 5", "machinery", 0.0, "", "", ""),
        ("01750001", "BPA", "operational", 0.0, "", "", ""),
        ("011010", "Packing Cerezas", "operational", 0.0, "", "", ""),
        ("01011635", "Arándano Crunch 2016", "crop", 10.0, "", "Arándanos", "Crunch"),
        ("01999001", "Tractor Ford", "machinery", 0.0, "", "", ""),
        ("21140517", "Thompson 2017 8 has.", "crop", 8.0, "", "Uva de mesa", "Thompson"),
    ]
    centers = {}
    for code, name, cost_type, hectares, plot, species, variety in center_values:
        center = Center.search([("code", "=", code), ("company_id", "=", company.id)], limit=1)
        values = {"name": name, "cost_type": cost_type, "hectares": hectares,
                  "plot": plot, "species": species, "variety": variety}
        if center:
            center.write(values)
        else:
            values.update({"code": code, "company_id": company.id})
            center = Center.create(values)
        centers[code] = center

    template = Template.search([
        ("name", "=", "Plantilla Ara MBO T2526"), ("company_id", "=", company.id)
    ], limit=1)
    if not template:
        jornada = env["uom.uom"].search([("name", "ilike", "Jornada")], limit=1)
        liter = env["uom.uom"].search([("name", "in", ["L", "Litro", "Litros"])], limit=1)
        unit = env.ref("uom.product_uom_unit", raise_if_not_found=False)
        lines = [
            ("labor", "01", "Poda", "Poda", jornada, 25, 40000, {"jun": 25}),
            ("labor", "01", "Ralear frutos", "Labores en verde", jornada, 5, 38000, {"oct": 5}),
            ("labor", "01", "Amarrar guías", "Poda", jornada, 10, 38000, {"jun": 10}),
            ("labor", "01", "Cosecha para proceso", "Cosecha", jornada, 200, 41000, {"nov": 100, "dec": 100}),
            ("input", "02", "Glifospec 48%", "Control de malezas", liter, 4.6, 15000, {}),
            ("machinery", "03", "Labor pasar rana", "Aplicaciones", unit, 3, 7000, {"jul": 3}),
            ("service", "04", "Flete campo planta", "Cosecha", unit, 4, 40000, {"dec": 4}),
        ]
        line_commands = []
        for sequence, (category, group_code, indicator, activity, uom, qty, price, months) in enumerate(lines, 10):
            values = {"sequence": sequence, "category": category, "group_id": groups[group_code].id,
                      "indicator": indicator, "activity": activity, "uom_id": uom.id,
                      "base_quantity": qty if not months else 0.0, "unit_price": price}
            values.update(months)
            line_commands.append((0, 0, values))
        template = Template.create({
            "name": "Plantilla Ara MBO T2526", "version": "1", "company_id": company.id,
            "currency_id": company.currency_id.id, "base_hectares": 1.0,
            "species": "Arándanos", "expected_yield_kg_ha": 12000,
            "notes": "Migrada desde steps_qa. Cantidades y tarifas expresadas por hectárea.",
            "line_ids": line_commands, "state": "active",
        })

    Plan = env["step.management.plan"]
    if not Plan.search([("description", "=", "Plan Arándanos Sept 25"), ("company_id", "=", company.id)]):
        Plan.create({
            "description": "Plan Arándanos Sept 25", "company_id": company.id,
            "responsible_id": env.user.id, "date_start": "2025-09-01", "date_end": "2025-09-30",
            "week_reference": "W37", "center_ids": [(6, 0, [centers["01012018"].id])],
            "state": "planned", "notes": "Migrado desde steps_qa.",
        })

    Historical = env["step.management.historical.cost"]
    for date in ("2025-06-30", "2025-07-30"):
        if not Historical.search([("date", "=", date), ("center_id", "=", centers["01012018"].id)], limit=1):
            Historical.create({
                "name": "Poda - histórico steps_qa", "company_id": company.id, "date": date,
                "center_id": centers["01012018"].id, "group_id": groups["01"].id,
                "indicator": "Poda", "quantity": 1.0, "currency_id": company.currency_id.id,
                "actual_amount": 1000.0, "budget_amount": 1200.0,
            })

    env.cr.commit()
    print({
        "groups": len(groups), "centers": len(centers), "template": template.display_name,
        "template_lines": len(template.line_ids),
    })
