{
    "name": "Steps - Flujo de fruta de Productores",
    "summary": "Saldo de estimación y recepciones de productores",
    "version": "18.0.1.0.0",
    "category": "Agriculture",
    "author": "Steps Consulting",
    "license": "LGPL-3",
    "depends": ["step_producers", "step_inventory_packing"],
    "data": [
        "security/ir.model.access.csv",
        "security/rules.xml",
        "views/estimate_progress_views.xml",
        "views/producer_flow_menus.xml",
    ],
    "installable": True,
    "application": False,
}
