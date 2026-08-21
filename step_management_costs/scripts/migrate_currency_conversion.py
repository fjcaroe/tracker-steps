"""Initialize currency conversion on an existing Gestión y Costos database."""

from odoo import fields


def migrate_currency_conversion(env):
    today = fields.Date.context_today(env["step.management.exchange.rate"])
    company = env.company
    usd = env.ref("base.USD", raise_if_not_found=False)
    if not usd:
        raise RuntimeError("No se encontró la moneda USD de Odoo.")

    Rate = env["step.management.exchange.rate"]
    rate = Rate.search([
        ("company_id", "=", company.id),
        ("currency_id", "=", usd.id),
        ("year", "=", today.year),
        ("month", "=", "%02d" % today.month),
    ], limit=1)
    if not rate:
        company_value = usd._convert(
            1.0, company.currency_id, company, today, round=False,
        )
        rate = Rate.create({
            "company_id": company.id,
            "currency_id": usd.id,
            "year": today.year,
            "month": "%02d" % today.month,
            "company_value_per_unit": company_value,
            "source": "odoo",
            "notes": (
                "Estimación inicial copiada desde la tasa real Odoo. "
                "Debe ajustarse según el supuesto presupuestario del negocio."
            ),
        })

    templates = env["step.management.budget.template"].search([
        ("company_id", "=", company.id), ("conversion_currency_id", "=", False),
    ])
    templates.write({
        "conversion_currency_id": usd.id,
        "conversion_date": today,
        "conversion_rate_type": "estimated",
    })
    budgets = env["step.management.operational.budget"].search([
        ("company_id", "=", company.id), ("conversion_currency_id", "=", False),
    ])
    budgets.write({
        "conversion_currency_id": usd.id,
        "conversion_rate_type": "estimated",
    })
    costs = env["step.management.historical.cost"].search([
        ("company_id", "=", company.id), ("conversion_currency_id", "=", False),
    ])
    costs.write({
        "conversion_currency_id": usd.id,
        "conversion_rate_type": "actual",
    })

    env.cr.commit()
    result = {
        "estimated_rate": rate.display_name,
        "company_value_per_usd": rate.company_value_per_unit,
        "templates_updated": len(templates),
        "budgets_updated": len(budgets),
        "historical_costs_updated": len(costs),
    }
    print("CURRENCY_MIGRATION_RESULT", result)
    return result
