{
    "name": "Steps - Experiencia Maquinaria y Fletes",
    "summary": "Portadas y estilo agrícola para Maquinaria y Fletes",
    "version": "18.0.2.1.0",
    "category": "Operations/Agriculture",
    "author": "Steps Consulting",
    "license": "LGPL-3",
    "depends": ["base", "mail", "web", "hr", "account", "fleet", "step_hr", "step_machinery"],
    "data": [
        "security/ir.model.access.csv",
        "data/freight_dispatch_type_data.xml",
        "views/freight_views.xml",
        "views/app_icons.xml",
        "views/dashboard_actions.xml",
        "views/machinery_views.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "step_operations_ui/static/src/js/operations_dashboards.js",
            "step_operations_ui/static/src/xml/operations_dashboards.xml",
            "step_operations_ui/static/src/scss/operations_ui.scss",
        ],
    },
    "installable": True,
    "application": False,
}
