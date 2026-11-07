{
    'name': 'Steps - Anticipos de fruta a productores',
    'version': '18.0.1.0.2',
    'license': 'LGPL-3',
    'depends': ['step_packing_fruit_proforma', 'step_producer_daily_estimate', 'step_hr'],
    'data': ['security.xml', 'ir.model.access.csv', 'sequence.xml',
             'pricelist_views.xml', 'report.xml', 'views.xml'],
    'installable': True,
}
