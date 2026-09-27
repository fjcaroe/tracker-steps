{
    "name": "Steps - Experiencia de soporte",
    "summary": "Identidad visual de Helpdesk y URL canónica de soporte",
    "version": "18.0.1.0.0",
    "author": "Steps Consulting",
    "website": "https://stepsapp.cl",
    "category": "Services/Helpdesk",
    "license": "LGPL-3",
    "depends": ["helpdesk", "web", "portal"],
    "data": [
        "views/helpdesk_branding.xml",
        "views/portal_templates.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "step_helpdesk_brand/static/src/js/helpdesk_scope.js",
            "step_helpdesk_brand/static/src/xml/helpdesk_dashboard.xml",
            "step_helpdesk_brand/static/src/scss/helpdesk_backend.scss",
        ],
        "web.assets_frontend": [
            "step_helpdesk_brand/static/src/scss/helpdesk_portal.scss",
        ],
    },
    "application": False,
    "installable": True,
}
