{
    "name": "Steps - Experiencia Maquinaria y Fletes",
    "summary": "Portadas y estilo agrícola para Maquinaria y Fletes",
    "version": "18.0.1.1.0",
    "category": "Operations/Agriculture",
    "author": "Steps Consulting",
    "license": "LGPL-3",
    "depends": ["web", "step_agricultural_access", "step_machinery"],
    "data": [
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
