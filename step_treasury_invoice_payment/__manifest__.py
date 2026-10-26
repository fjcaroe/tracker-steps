{
    'name': 'Steps - Facturas en pagos de Tesorería',
    'version': '18.0.1.0.0',
    'license': 'LGPL-3',
    'depends': ['step_account_treasury', 'account_payment'],
    'data': ['security/ir.model.access.csv', 'security/rules.xml', 'views/payment.xml'],
    'installable': True,
}
