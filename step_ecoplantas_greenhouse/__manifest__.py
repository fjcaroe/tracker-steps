{
    "name": "Steps - Invernadero",
    "summary": "Portada operativa y recorrido de demostración de ECOPLANTAS",
    "version": "18.0.1.0.0",
    "category": "Operations/Agriculture",
    "author": "Steps Consulting",
    "website": "https://stepsapp.cl",
    "license": "LGPL-3",
    "depends": ["web", "stock", "mrp", "quality_mrp", "project", "maintenance"],
    "data": ["views/greenhouse_views.xml"],
    "assets": {
        "web.assets_backend": [
            "step_ecoplantas_greenhouse/static/src/greenhouse.js",
            "step_ecoplantas_greenhouse/static/src/greenhouse.xml",
            "step_ecoplantas_greenhouse/static/src/greenhouse.scss",
        ],
    },
    "post_init_hook": "post_init_hook",
    "application": True,
    "installable": True,
}
