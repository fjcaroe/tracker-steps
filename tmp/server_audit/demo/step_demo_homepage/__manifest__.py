{
    "name": "Steps - Portada Demo",
    "summary": "Identidad comercial y portada de producto para Steps Agro",
    "version": "18.0.1.0.3",
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
        ],
    },
    "post_init_hook": "post_init_hook",
    "application": False,
    "installable": True,
}
