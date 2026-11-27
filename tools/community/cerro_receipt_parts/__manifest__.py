{
    'name': 'Cerro El Plomo - Recepción de fruta a proceso',
    'version': '18.0.1.0.0',
    'license': 'AGPL-3',
    'depends': ['step_cerro_pack_reports', 'step_cerro_catalog_contracts', 'step_producers', 'step_cosecha_planning'],
    'pre_init_hook': 'adopt_originals',
    'assets': {'web.assets_backend': ['step_cerro_receipt_flow/static/src/scale_capture.js',
                                     'step_cerro_receipt_flow/static/src/scale_capture.xml']},
    'installable': True,
}
