{
    "name": "Steps - Flujo de fruta de Productores",
    "summary": "Saldo, recepción y preliquidación de productores",
    "version": "18.0.1.2.1",
    "category": "Agriculture",
    "author": "Steps Consulting",
    "license": "LGPL-3",
    "depends": ["step_producers", "step_inventory_packing"],
    "data": [
        "security/ir.model.access.csv",
        "security/rules.xml",
        "views/preliquidation_views.xml",
        "views/estimate_progress_views.xml",
        "views/producer_flow_menus.xml",
    ],
    "installable": True,
    "application": False,
}
