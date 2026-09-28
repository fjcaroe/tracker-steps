{
    "name": "Steps - Guías de despacho",
    "summary": "Guías internas de despacho y enlace con Inventario y Fletes",
    "version": "18.0.1.0.0",
    "category": "Inventory/Inventory",
    "author": "Steps Consulting",
    "license": "LGPL-3",
    "depends": ["stock", "step_operations_ui"],
    "data": [
        "security/ir.model.access.csv",
        "data/ir_sequence.xml",
        "views/res_config_settings_views.xml",
        "views/dispatch_guide_views.xml",
        "views/stock_picking_views.xml",
        "views/freight_order_views.xml",
        "report/dispatch_guide_report.xml",
    ],
    "installable": True,
    "application": True,
}

