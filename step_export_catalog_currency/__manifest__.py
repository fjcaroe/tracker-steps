{
    'name': 'Steps - Catálogos y monedas de Exportaciones',
    'version': '18.0.1.0.0', 'license': 'LGPL-3',
    'depends': ['step_export_client_revision', 'step_producer_daily_estimate', 'l10n_cl_edi_exports'],
    'data': ['views/catalogs.xml', 'views/programs.xml'],
    'assets': {'web.assets_backend': ['step_export_catalog_currency/static/src/amount.js']},
    'installable': True,
}
