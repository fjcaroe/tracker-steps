{
    'name': 'Steps - Proforma mensual de fruta',
    'version': '18.0.1.2.1',
    'license': 'LGPL-3',
    'depends': ['step_packing_operations', 'step_packing_holding_contract',
                'purchase_stock', 'l10n_cl'],
    'data': ['security.xml', 'ir.model.access.csv', 'sequence.xml',
             'report.xml', 'views.xml', 'migration_views.xml', 'precision_views.xml', 'purchase_workflow_views.xml'],
    'installable': True,
}
