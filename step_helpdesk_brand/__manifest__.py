{
    "name": "Steps - Experiencia de soporte",
    "summary": "Identidad visual de Helpdesk y URL canónica de soporte",
    "version": "18.0.1.1.1",
    "author": "Steps Consulting",
    "website": "https://stepsapp.cl",
    "category": "Services/Helpdesk",
    "license": "LGPL-3",
    "depends": ["helpdesk", "web", "portal", "website_helpdesk"],
    "data": [
        "views/helpdesk_branding.xml",
        "views/ticket_views.xml",
        "views/portal_templates.xml",
        "views/support_public_templates.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "step_helpdesk_brand/static/src/js/helpdesk_scope.js",
            "step_helpdesk_brand/static/src/xml/helpdesk_dashboard.xml",
            "step_helpdesk_brand/static/src/scss/helpdesk_backend.scss",
        ],
        "web.assets_frontend": [
            "step_helpdesk_brand/static/src/js/public_form.js",
            "step_helpdesk_brand/static/src/scss/helpdesk_portal.scss",
            "step_helpdesk_brand/static/src/scss/helpdesk_public.scss",
        ],
    },
    "application": False,
    "installable": True,
}
