{
    "name": "Steps - Costos compartidos de vivero",
    "summary": "Centros padres, drivers semanales y redistribución analítica",
    "version": "18.0.1.1.0",
    "license": "LGPL-3",
    "depends": ["account", "step_costing_driver", "step_ecoplantas_greenhouse"],
    "data": [
        "security/cost_rules.xml",
        "security/ir.model.access.csv",
        "views/cost_views.xml",
    ],
    "assets": {
        "web.assets_backend": ["step_nursery_shared_costs/static/src/cost_card.xml"],
    },
    "post_init_hook": "seed_example",
    "installable": True,
}
