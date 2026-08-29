# -*- coding: utf-8 -*-
{
    'name': "Movilización",
    'summary': "Transporte de personal: recorridos, tarifas, viajes, contratos, "
               "prevención de riesgos y seguimiento GPS",
    'description': """
        Aplicación independiente de transporte de personal (buses/furgones de
        trabajadores), separada del módulo de Actividades agrícolas. Incluye
        maestros de transportistas/choferes/vehículos, recorridos y tarifas,
        registro de viajes y pasajeros, costeo y contabilización, contratos de
        prestación de servicio, Derecho a Saber, entrega de EPP, control
        documental, inspecciones de vehículos, y una API móvil versionada para
        el chofer (marcación de pasajeros y seguimiento GPS).
    """,
    'author': "Steps Consulting",
    'category': 'Operations/Fleet',
    'version': '18.0.1.0.1',
    'license': 'LGPL-3',
    'depends': ['base', 'mail', 'web', 'hr', 'contacts', 'fleet', 'product', 'account', 'analytic'],
    'data': [
        'security/step_mobilization_security.xml',
        'security/ir.model.access.csv',
        'security/ir_rule.xml',
        'data/step_mobilization_document_type_data.xml',
        'data/step_mobilization_inspection_template_data.xml',
        'data/step_mobilization_right_to_know_data.xml',
        'data/step_mobilization_contract_template_data.xml',
        'views/step_mobilization_registry_views.xml',
        'views/step_mobilization_registry_line_views.xml',
        'views/step_mobilization_cost_views.xml',
        'views/hr_route_views.xml',
        'views/product_pricelist_views.xml',
        'views/step_mobilization_contract_views.xml',
        'views/step_mobilization_right_to_know_views.xml',
        'views/step_mobilization_epp_delivery_views.xml',
        'views/step_mobilization_document_views.xml',
        'views/step_mobilization_inspection_views.xml',
        'views/step_mobilization_driver_device_views.xml',
        'views/product_template_views.xml',
        'views/hr_employee_views.xml',
        'views/res_partner_views.xml',
        'views/fleet_vehicle_views.xml',
        'views/account_move_views.xml',
        'views/res_config_settings_views.xml',
        'views/step_mobilization_dashboard_views.xml',
        'views/step_mobilization_reports_views.xml',
        'views/menu_views.xml',
        'report/step_mobilization_contract_report.xml',
        'report/step_mobilization_contract_template.xml',
    ],
    'demo': [],
    'assets': {
        'web.assets_backend': [
            'step_mobilization/static/src/js/mobilization_dashboard.js',
            'step_mobilization/static/src/xml/mobilization_dashboard.xml',
            'step_mobilization/static/src/scss/mobilization_dashboard.scss',
        ],
    },
    'application': True,
    'post_init_hook': 'post_init_hook',
}
