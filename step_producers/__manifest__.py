{
    "name": "Steps - Productores",
    "summary": "Productores, fundos, estimaciones, tarifas y liquidaciones",
    "version": "18.0.1.0.0",
    "category": "Agriculture",
    "author": "Steps Consulting",
    "license": "LGPL-3",
    "depends": ["step_export"],
    "data": [
        "security/producer_rules.xml",
        "views/producer_dashboard.xml",
        "views/producer_partner_views.xml",
        "views/menu.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "step_producers/static/src/js/dashboard.js",
            "step_producers/static/src/xml/dashboard.xml",
        ],
    },
    "application": True,
    "installable": True,
}
