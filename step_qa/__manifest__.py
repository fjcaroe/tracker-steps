{
    "name": "Steps QA - Inspecciones",
    "summary": "Centro operativo y analítico para calidad e inspecciones agrícolas",
    "description": """
        Moderniza QA-Inspecciones con un tablero ejecutivo, navegación guiada,
        vistas operativas para controles y alertas, e interfaces renovadas para
        inspecciones internas y asesorías externas.
    """,
    "author": "Steps Consulting",
    "category": "Operations/Quality",
    "version": "18.0.1.0.1",
    "license": "LGPL-3",
    "depends": [
        "base",
        "mail",
        "web",
        "quality_control",
        "step_hr",
    ],
    "data": [
        "views/step_qa_dashboard_views.xml",
        "views/quality_views.xml",
        "views/studio_inspection_views.xml",
        "views/menu_views.xml",
        "views/translations.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "step_qa/static/src/js/qa_dashboard.js",
            "step_qa/static/src/xml/qa_dashboard.xml",
            "step_qa/static/src/scss/qa_dashboard.scss",
        ],
    },
    "application": True,
    "installable": True,
}
