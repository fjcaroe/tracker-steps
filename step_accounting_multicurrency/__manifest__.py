{
    "name": "Steps Contabilidad Multimoneda",
    "summary": "Puente opcional de la multimoneda Steps con informes Enterprise",
    "version": "18.0.2.1.0",
    "category": "Accounting/Accounting",
    "author": "Steps Consulting",
    "license": "LGPL-3",
    "depends": ["step_accounting_multicurrency_core", "account_reports"],
    "data": [],
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
