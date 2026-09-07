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
          * (fases siguientes) menús de consola, tablero OWL, aprobación y
            transmisión a Actividades, e informes.
    """,
    'author': "Steps Consulting",
    'website': "https://stepsapp.cl",
    'category': 'Operations/Agriculture',
    'version': '18.0.1.0.0',
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
        'data/ir_sequence.xml',
    ],
    'assets': {},
    'application': True,
}
