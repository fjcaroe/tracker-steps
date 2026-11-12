{
    "name": "Steps - Operación de vivero",
    "summary": "Planificación de siembra, ocupación y trazabilidad de lotes",
    "version": "18.0.1.0.0",
    "license": "LGPL-3",
    "author": "Steps Consulting",
    "category": "Operations/Agriculture",
    "depends": ["sale_stock", "mrp", "product_expiry", "step_agriculture_catalogs"],
    "data": [
        "security/nursery_rules.xml",
        "security/ir.model.access.csv",
        "views/nursery_views.xml",
    ],
    "application": True,
    "installable": True,
}
