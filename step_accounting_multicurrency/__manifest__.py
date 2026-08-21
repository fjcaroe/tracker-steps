{
    "name": "Steps Contabilidad Multimoneda",
    "summary": "Captura contable multimoneda y balances en monedas de presentación",
    "version": "18.0.1.0.0",
    "category": "Accounting/Accounting",
    "author": "Steps Consulting",
    "license": "LGPL-3",
    "depends": ["account", "account_reports"],
    "data": [
        "views/account_move_views.xml",
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
