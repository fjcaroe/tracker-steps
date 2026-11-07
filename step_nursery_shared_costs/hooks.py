from datetime import timedelta

from odoo import Command

from .masters import last_closed_week

MODULE = "step_nursery_shared_costs"


def seed_example(env):
    if env.cr.dbname != "ECOPLANTAS" and not env.cr.dbname.startswith("ECOPLANTAS_GH_QA_"):
        return
    company = env.ref("base.main_company")
    if company.name != "ECOPLANTAS" or env.ref(f"{MODULE}.demo_run", raise_if_not_found=False):
        return
    plan = env.ref("analytic.analytic_plan_projects")
    week = last_closed_week(env["step.nursery.cost.run"].with_context(tz="America/Santiago"))

    def create(key, model, values):
        record = env[model].with_company(company).create(values)
        env["ir.model.data"].create({
            "module": MODULE, "name": "demo_" + key, "model": model,
            "res_id": record.id, "noupdate": True,
        })
        return record

    costs = [
        ("riego", "Riego compartido", "Superficie atendida", "uom.uom_square_meter", 120000, (300, 100)),
        ("sanidad", "Sanidad compartida", "Horas de labor", "uom.product_uom_hour", 80000, (2, 6)),
    ]
    drivers = []
    for key, labor_name, driver_name, unit, amount, quantities in costs:
        labor = create(key, "product.template", {"name": labor_name + " [DEMO]", "type": "service",
                                               "company_id": company.id, "sale_ok": False})
        driver = create(key + "_driver", "step.sawmill.costing.driver", {
            "name": driver_name + " [DEMO]", "company_id": company.id, "uom_id": env.ref(unit).id,
        })
        drivers.append((key, labor, driver, amount, quantities))
    accounts = {"company_id": company.id, "plan_id": plan.id}
    parent = create("parent", "account.analytic.account", {
        **accounts, "name": "Servicios compartidos del vivero [DEMO]", "step_cost_pool": True,
        "step_cost_rule_ids": [Command.create({"labor_id": labor.id, "driver_id": driver.id})
                               for _key, labor, driver, _amount, _quantities in drivers],
    })
    children = [
        create(key, "account.analytic.account", {
            **accounts, "name": name + " [DEMO]", "step_cost_parent_id": parent.id,
        })
        for key, name in (("north", "Propagación Norte"), ("south", "Propagación Sur"))
    ]
    for key, labor, driver, amount, quantities in drivers:
        for child, quantity in zip(children, quantities):
            create(f"{key}_{child.id}_measure", "step.nursery.cost.measure", {
                "center_id": child.id, "driver_id": driver.id, "company_id": company.id,
                "week_start": week, "quantity": quantity,
            })
        create(key + "_charge", "account.analytic.line", {
            "name": labor.name, "date": week + timedelta(days=3), "company_id": company.id,
            plan._column_name(): parent.id, "amount": -amount,
            "product_id": labor.product_variant_id.id, "step_cost_labor_id": labor.id,
        })
    create("run", "step.nursery.cost.run", {"parent_id": parent.id, "week_start": week})
