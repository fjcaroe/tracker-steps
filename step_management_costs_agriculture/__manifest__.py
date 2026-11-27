{
    "name": "Steps - Gestión y Costos (puente agrícola)",
    "summary": "Enlaza Gestión y Costos con los maestros agrícolas Community",
    "version": "18.0.2.2.1",
    "author": "Steps Consulting",
    "category": "Operations/Planning",
    "license": "LGPL-3",
    "depends": ["step_management_costs", "step_agriculture_core", "step_agriculture_catalogs"],
    "auto_install": True,
    "pre_init_hook": "adopt_cost_center_bindings",
    "data": ["views/estimation_catalog_views.xml", "views/cost_center_views.xml", "views/menu_views.xml"],
    "installable": True,
    "application": False,
}
