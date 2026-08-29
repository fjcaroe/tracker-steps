{
    "name": "Steps - BPA y Riego",
    "summary": "Centro operativo moderno para BPA, monitoreo y fertirriego",
    "version": "18.0.2.3.1",
    "author": "Steps Consulting",
    "category": "Operations",
    "license": "LGPL-3",
    "depends": ["base", "mail", "web", "hr", "fleet", "step_hr", "step_machinery"],
    "data": [
        "security/ir.model.access.csv",
        "views/bpa_dashboard_views.xml",
        "views/bpa_studio_layout_views.xml",
        "views/bpa_report_views.xml",
        "views/bpa_machinery_views.xml",
        "views/menu_views.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "step_bpa_irrigation/static/src/js/bpa_dashboard.js",
            "step_bpa_irrigation/static/src/xml/bpa_dashboard.xml",
            "step_bpa_irrigation/static/src/scss/bpa_dashboard.scss",
        ],
    },
    "application": True,
    "installable": True,
}
