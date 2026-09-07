# -*- coding: utf-8 -*-
{
    'name': "Step Cosecha",
    'summary': "Gestión integral de cosecha propia y contratista",
    'description': """
        Registra, controla y costea la cosecha propia y de contratistas.
        Incluye una portada ejecutiva, recepción, contabilización, historial
        y accesos guiados a los maestros operacionales.
    """,

    'author': "jamie.escalante7@gmail.com",
    'website': "",
    'category': 'Operations/Agriculture',
    'version': '18.0.1.6.0',
    'license': 'LGPL-3',

    'depends': ['base',
                'hr_holidays_gantt',
                'hr_work_entry_holidays',
                'account',
                'mail',
                'web',
                'stock',
                'purchase',
                'step_hr',
                'hr_payroll',
                'hr_work_entry_contract_enterprise',
                'sale',
                'sale_management',
                'fleet'],
    'data': [
        'security/history_security.xml',
        'security/cosecha_security.xml',
        'security/ir.model.access.csv',
        'data/ir_sequence.xml',
        'views/step_cosecha_dashboard_views.xml',
        'views/step_cosecha_views.xml',
        'views/product_pricelist_views.xml',
        'views/step_cosecha_registry_views.xml',
        'views/step_cosecha_recepcion_views.xml',
        'views/step_cosecha_proceso_views.xml',
        'views/step_history_cosecha_views.xml',
        'views/menu_views.xml',
    ],
    'demo': [],
    'assets': {
        'web.assets_backend': [
            'step_cosecha/static/src/js/cosecha_dashboard.js',
            'step_cosecha/static/src/xml/cosecha_dashboard.xml',
            'step_cosecha/static/src/scss/cosecha_dashboard.scss',
        ],
    },
    'application': True,
}
