{
    "name": "Steps - Maestros agrícolas multiempresa",
    "version": "18.0.1.0.5",
    "license": "LGPL-3",
    "depends": ["step_fruit_category_unification", "step_producer_fruit_reports", "step_packing_operations", "step_packing_ticket_revision", "step_export_shipping_design"],
    "data": ["security/rules.xml", "security/producer_access.xml", "views/masters.xml", "views/calibers.xml"],
    "post_init_hook": "post_init_hook",
    "uninstall_hook": "uninstall_hook",
    "installable": True,
}
