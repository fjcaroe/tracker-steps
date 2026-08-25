{
    "name": "Steps - Protección Laboral",
    "summary": "Prevención, Ley Karin, EPP, capacitación y accidentes laborales",
    "version": "18.0.1.0.2",
    "author": "Steps Consulting",
    "category": "Operations/Health and Safety",
    "license": "LGPL-3",
    "depends": ["base", "mail", "web", "hr", "step_hr"],
    "data": [
        "security/labor_security.xml",
        "security/ir.model.access.csv",
        "data/labor_sequence.xml",
        "views/labor_protocol_views.xml",
        "views/labor_karin_case_views.xml",
        "views/labor_dashboard_views.xml",
        "views/menu_views.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "step_labor_protection/static/src/js/labor_dashboard.js",
            "step_labor_protection/static/src/xml/labor_dashboard.xml",
            "step_labor_protection/static/src/scss/labor_dashboard.scss",
        ],
    },
    "application": True,
    "installable": True,
}
