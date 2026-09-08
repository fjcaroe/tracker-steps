{
    "name": "Steps - Portada de producto",
    "summary": "Ecosistema Steps: campo, personas, logística y finanzas",
    "version": "18.0.2.1.0",
    "author": "Steps Consulting",
    "category": "Website",
    "license": "LGPL-3",
    "depends": ["website"],
    "data": [
        "views/homepage.xml",
    ],
    "assets": {
        "web.assets_frontend": [
            "step_demo_homepage/static/src/scss/homepage.scss",
            "step_demo_homepage/static/src/js/homepage.js",
        ],
    },
    "post_init_hook": "post_init_hook",
    "application": False,
    "installable": True,
}
