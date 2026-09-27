# -*- coding: utf-8 -*-
{
    "name": "Steps - Tesorería: pagos por lotes",
    "summary": "Lotes de pago generados desde el flujo de caja de Tesorería",
    "description": """Puente opcional. `account_batch_payment` no está instalado en
todos los ambientes, así que los accesos a pagos por lotes viven aquí y no en el
núcleo de Tesorería, que debe poder instalarse siempre.

Incluye el proceso que genera un lote de pago a partir de la planificación:
toma los egresos vencidos y de la semana 1 del flujo, deja elegir qué documentos
se pagan, crea un pago por factura con `account.payment.register` y los agrupa en
un único lote saliente.""",
    "version": "18.0.1.2.0",
    "category": "Accounting/Accounting",
    "author": "Steps Consulting",
    "license": "LGPL-3",
    "depends": ["step_account_treasury", "account_batch_payment"],
    "data": [
        "security/ir.model.access.csv",
        "wizard/cashflow_batch_wizard_views.xml",
        "views/batch_menus.xml",
        "views/batch_payment_views.xml",
        "views/cashflow_batch_views.xml",
    ],
    "auto_install": True,
    "installable": True,
}
