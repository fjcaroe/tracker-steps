# -*- coding: utf-8 -*-
{
    'name': "Step Task",
    'summary': "App móvil y consola de registro de labores (Steps Task)",
    'description': """
        Steps Task es la capa móvil + consola para el registro de labores de
        campo (propias y de contratista) sobre el módulo de Actividades
        (``step.tarja``).

        Aporta:
          * Campos de sincronización móvil en ``step.tarja`` / ``step.tarja.registry``.
          * Un controlador same-origin ``/api/task/*`` para la PWA publicada en
            ``/task/`` (equivalente a ``/api/harvest/*`` de Steps Harvest).
          * Consola: menú Task, tablero, estados de OT, consolidación y
            transmisión a Actividades, y alertas de validación diaria.
    """,
    'author': "Steps Consulting",
    'website': "https://stepsapp.cl",
    'category': 'Operations/Agriculture',
    'version': '18.0.1.3.0',
    'license': 'LGPL-3',
    'depends': [
        'base',
        'web',
        'mail',
        'hr',
        'hr_attendance',
        'account',
        'step_hr',
    ],
    'data': [
        'security/ir.model.access.csv',
        'data/ir_sequence.xml',
        'views/task_dashboard_views.xml',
        'views/step_tarja_task_views.xml',
        'views/menu_views.xml',
        'wizard/task_report_wizards.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'step_task/static/src/js/task_dashboard.js',
            'step_task/static/src/xml/task_dashboard.xml',
            'step_task/static/src/scss/task_dashboard.scss',
        ],
    },
    'application': True,
}
