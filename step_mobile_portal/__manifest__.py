{
    "name": "Steps App — portal móvil",
    "summary": "Personas, accesos, empresas, módulos y dispositivos de la aplicación Steps",
    "description": """
Núcleo de administración de la aplicación móvil unificada Steps. Separa identidad
(quién inició sesión), membresía/autorización (en qué empresas y con qué roles) y
dispositivo (desde dónde opera). Odoo entrega catálogo y autorizaciones; el código
de los módulos viaja en la aplicación.
""",
    "version": "18.0.1.0.0",
    "category": "Operations",
    "author": "Steps Consulting",
    "license": "LGPL-3",
    "depends": ["base", "mail"],
    "data": [
        "security/security.xml",
        "security/ir.model.access.csv",
        "security/ir_rule.xml",
        "views/person_views.xml",
        "views/membership_views.xml",
        "views/catalog_views.xml",
        "views/res_company_views.xml",
        "views/menus.xml",
    ],
    "application": True,
    "installable": True,
}
