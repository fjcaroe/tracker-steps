{
    "name": "Steps - Gestión y Costos (puente de maquinaria)",
    "summary": "Enlaza Gestión y Costos con el costeo real de maquinaria de step_machinery",
    "version": "18.0.1.0.0",
    "author": "Steps Consulting",
    "category": "Operations/Planning",
    "license": "LGPL-3",
    "depends": ["step_management_costs", "step_machinery"],
    "auto_install": True,
    "data": [
        "security/ir.model.access.csv",
        "views/machinery_budget_line_views.xml",
    ],
    "installable": True,
    "application": False,
}
