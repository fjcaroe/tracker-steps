# -*- coding: utf-8 -*-
{
    "name": "Step - Remove Database Expiration Message",
    "version": "18.0.1.0.1",
    "summary": "Remueve el panel que muestra que la base de datos expirará",
    "description": "Oculta o elimina el div #database_expiration_panel en la pantalla de login y home menu para no mostrar el aviso de expiración de base de datos.",
    "category": "Hidden",
    "author": "Steps Consulting",
    "license": "LGPL-3",
    "depends": [
        "web",
        "web_enterprise"
    ],
    "data": [
        # No view templates to avoid xpath/parse errors; assets are declared below
    ],
    "assets": {
        "web.assets_frontend": [
            "step_expire_database/static/src/scss/hide_expiration.scss"
        ],
        "web.assets_backend": [
            "step_expire_database/static/src/scss/hide_expiration.scss"
        ]
    },
    "installable": True,
    "application": False,
    "auto_install": False,
}
