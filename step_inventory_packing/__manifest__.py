{
    "name": "Steps - Inventario de fruta para Packing",
    "summary": "Recepciones diferenciadas, tarjas C/E/N y pesaje de fruta",
    "version": "18.0.1.0.0",
    "category": "Inventory/Inventory",
    "author": "Steps Consulting",
    "license": "LGPL-3",
    "depends": ["step_packing", "step_inventory_fruit_tag", "step_producers"],
    "data": [
        "security/ir.model.access.csv",
        "views/settings_views.xml",
        "views/fruit_package_views.xml",
        "views/fruit_reception_views.xml",
        "views/harvest_container_views.xml",
        "wizard/fruit_reception_import_views.xml",
    ],
    "installable": True,
    "application": False,
}
