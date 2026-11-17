{
    "name": "Steps - BPA / Inventario",
    "summary": "Genera el movimiento de Inventario por consumo de productos al costear una OT-BPA de Aplicación foliar",
    "version": "18.0.1.0.2",
    "author": "Steps Consulting",
    "category": "Operations",
    "license": "LGPL-3",
    "depends": ["step_bpa_irrigation", "stock_account"],
    "data": [
        "security/ir.model.access.csv",
        "security/company_rules.xml",
        "data/stock_data.xml",
        "views/x_aplicacion_foliar_views.xml",
    ],
    "installable": True,
    "application": False,
}
