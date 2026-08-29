{
    "name": "Steps Contabilidad Multimoneda",
    "summary": "Captura contable multimoneda y balances en monedas de presentación",
    "version": "18.0.2.0.1",
    "category": "Accounting/Accounting",
    "author": "Steps Consulting",
    "license": "LGPL-3",
    "depends": ["account", "account_reports"],
    "data": [
        "views/account_move_views.xml",
        "views/account_payment_views.xml",
        "views/res_config_settings_views.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "step_accounting_multicurrency/static/src/js/report_filters.js",
            "step_accounting_multicurrency/static/src/xml/report_filters.xml",
            "step_accounting_multicurrency/static/src/scss/report_filters.scss",
        ],
    },
    "installable": True,
    "application": False,
}
