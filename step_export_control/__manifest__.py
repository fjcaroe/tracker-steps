{
    'name': 'Steps Control de documentos y naves', 'version': '18.0.1.0.1',
    'depends': ['step_export_document_revision', 'step_export_shipping_design'],
    'license': 'LGPL-3', 'installable': True, 'application': True,
    'data': ['security/ir.model.access.csv', 'security/rules.xml', 'data/document_types.xml', 'views/control.xml'],
    'assets': {'web.assets_backend': ['step_export_control/static/src/control.js',
        'step_export_control/static/src/control.xml', 'step_export_control/static/src/control.scss']},
}
