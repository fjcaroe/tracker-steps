{
    "name": "Steps - Maestros y reportes de recepción de fruta",
    "summary": "Configuración de fruta y reportes a proceso y embalada en Productores e Inventario",
    "version": "18.0.1.0.0",
    "license": "LGPL-3",
    "depends": ["step_producer_fruit_flow", "step_export_client_revision", "step_agriculture_catalogs"],
    "data": ["security/ir.model.access.csv", "security/rules.xml", "views/catalogs.xml", "views/reports.xml"],
    "installable": True,
}
