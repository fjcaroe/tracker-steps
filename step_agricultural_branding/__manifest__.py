{
    "name": "Steps - Identidad de aplicaciones agrícolas",
    "summary": "Contraste común de portadas, iconografía y limpieza del Home",
    "version": "18.0.1.0.0",
    "category": "Operations/Agriculture",
    "author": "Steps Consulting",
    "website": "https://stepsapp.cl",
    "license": "LGPL-3",
    "depends": ["web", "hr_work_entry_contract_enterprise"],
    "data": [
        "views/app_branding.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "step_agricultural_branding/static/src/scss/app_branding.scss",
        ],
    },
    "post_init_hook": "post_init_hook",
    "installable": True,
    "application": False,
}

