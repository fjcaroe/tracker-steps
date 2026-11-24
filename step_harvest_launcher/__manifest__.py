{
    'name': 'Steps Harvest',
    'summary': 'Acceso a la aplicación independiente de cosecha en terreno',
    'description': 'Publica Steps Harvest como aplicación independiente en Odoo. Abre la app web instalada en este servidor.',
    'version': '18.0.1.4.0',
    'category': 'Operations/Agriculture',
    'author': 'Steps Consulting',
    'license': 'LGPL-3',
    'depends': ['base', 'step_cosecha', 'hr_attendance'],
    'data': ['views/menu.xml', 'views/mobile_lifecycle.xml', 'views/crew_attendance.xml'],
    'application': True,
    'installable': True,
}
