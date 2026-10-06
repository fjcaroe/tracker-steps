{
    'name': 'Steps - Soporte por WhatsApp',
    'version': '18.0.1.0.0',
    'license': 'LGPL-3',
    'author': 'Steps Consulting',
    'depends': ['helpdesk', 'mail', 'phone_validation'],
    'data': ['security/ir.model.access.csv', 'security/rules.xml', 'views/whatsapp.xml', 'data/cron.xml'],
    'installable': True,
    'application': False,
}
