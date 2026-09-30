# -*- coding: utf-8 -*-
{
    "name": "Steps - Gastos y rendiciones",
    "version": "18.0.1.0.0",
    "summary": "Rendición de gastos con folio, datos de documento, uso de vehículo e informe imprimible",
    "description": "Extiende el módulo estándar de Gastos (hr_expense): folio FC-000001 por rendición, "
                   "tipo y número de documento por gasto, tabla de uso de vehículo (opcional según "
                   "configuración de la compañía o decisión del usuario) e informe PDF con el formato "
                   "de rendición de gastos con firmas de trabajador y aprobador.",
    "category": "Human Resources/Expenses",
    "author": "Steps Consulting",
    "license": "LGPL-3",
    "depends": ["hr_expense"],
    "data": [
        "security/ir.model.access.csv",
        "security/ir_rule.xml",
        "data/ir_sequence_data.xml",
        "views/hr_expense_views.xml",
        "views/hr_expense_sheet_views.xml",
        "views/res_company_views.xml",
        "report/expense_sheet_report.xml",
    ],
    "installable": True,
    "application": False,
    "auto_install": False,
}
