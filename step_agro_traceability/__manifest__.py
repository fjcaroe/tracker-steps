{
    "name": "Steps - Trazabilidad Fitosanitaria",
    "summary": "Carencia y reingreso por cuartel: control efectivo entre aplicación y cosecha",
    "description": """
        Convierte los datos fitosanitarios que hoy solo se registran (días de
        carencia, horas de reingreso, producto aplicado, cuartel intervenido)
        en una restricción operativa consultable y accionable.

        - Calcula por cuartel la fecha mínima de cosecha y la hora de reingreso
          seguro a partir de las aplicaciones registradas en BPA.
        - Muestra el estado fitosanitario en el registro de cosecha.
        - Advierte o bloquea la aprobación de una cosecha dentro de carencia,
          según la política configurada por empresa.
        - Entrega un tablero de restricciones vigentes por fundo y cuartel.
    """,
    "author": "Steps Consulting",
    "category": "Operations/Agriculture",
    "version": "18.0.1.0.0",
    "license": "LGPL-3",
    "depends": [
        "base",
        "mail",
        "web",
        "product",
        "step_hr",
        "step_cosecha",
        "step_bpa_irrigation",
        "step_agricultural_access",
    ],
    "data": [
        "security/ir.model.access.csv",
        "security/phyto_security.xml",
        "data/ir_cron.xml",
        "views/phyto_restriction_views.xml",
        "views/step_cosecha_registry_views.xml",
        "views/res_company_views.xml",
        "views/menu_views.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "step_agro_traceability/static/src/scss/phyto.scss",
        ],
    },
    "post_init_hook": "post_init_hook",
    "installable": True,
    "application": False,
}
