{
    'name': 'Steps - Trazabilidad por pallet',
    'version': '18.0.1.0.0',
    'license': 'LGPL-3',
    'depends': ['step_packing_sag', 'step_packing_dispatch', 'quality_control'],
    'data': ['views/traceability.xml'],
    'assets': {'web.assets_backend': ['step_export_traceability/static/src/traceability.scss']},
    'installable': True,
}
