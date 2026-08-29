# -*- coding: utf-8 -*-
{
    "name": "Steps - Tesorería",
    "summary": "Planificación de caja a cinco semanas integrada con Contabilidad",
    "description": """Tesorería sobre la contabilidad de Odoo: maestro de conceptos
de flujo, flujos de caja con horizonte de cinco semanas, siete hojas de detalle y
resumen acumulado, todo derivado de un único dataset canónico y auditable.""",
    "version": "18.0.1.0.1",
    "category": "Accounting/Accounting",
    "author": "Steps Consulting",
    "website": "https://stepsapp.cl",
    "license": "LGPL-3",
    # Sólo motores presentes en los tres ambientes autorizados. `account_batch_payment`
    # no está instalado en Demo-SyS y va en el puente step_account_treasury_batch;
    # `step_hr` tampoco, y el fundo va en step_account_treasury_agro.
    "depends": [
        "base",
        "mail",
        "web",
        "account",
        "account_reports",
        "sale",
        "purchase",
        "step_accounting_multicurrency",
    ],
    "data": [
        "security/treasury_groups.xml",
        "security/ir.model.access.csv",
        "security/treasury_rules.xml",
        "data/ir_sequence.xml",
        "views/treasury_concept_views.xml",
        "views/vendor_proforma_views.xml",
        "views/cashflow_views.xml",
        "views/sale_purchase_views.xml",
        "views/treasury_menus.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "step_account_treasury/static/src/scss/treasury.scss",
        ],
    },
    "post_init_hook": "post_init_treasury",
    "application": False,
    "installable": True,
}
