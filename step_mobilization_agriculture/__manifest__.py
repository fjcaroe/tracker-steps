# -*- coding: utf-8 -*-
{
    'name': "Movilización — Adaptador Agrícola",
    'summary': "Distribución de costos de movilización por fundo, temporada y tarja",
    'description': """
        Conecta el núcleo de Movilización (step_mobilization) con el dominio
        agrícola de step_hr: asigna fundo, resuelve centro de costo/labor por
        tarja y temporada, y aplica esa distribución al costeo/contabilización
        de viajes sin que el núcleo dependa de step_hr.
    """,
    'author': "Steps Consulting",
    'category': 'Operations/Fleet',
    'version': '18.0.1.0.0',
    'license': 'LGPL-3',
    'depends': ['step_mobilization', 'step_hr'],
    'data': [
        'views/step_mobilization_registry_views.xml',
    ],
    'installable': True,
    'application': False,
    'post_init_hook': 'post_init_hook',
}
