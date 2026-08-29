# -*- coding: utf-8 -*-
{
    "name": "Steps - Tesorería: pagos por lotes",
    "summary": "Accesos a pagos por lotes dentro del menú Tesorería",
    "description": """Puente opcional. `account_batch_payment` no está instalado en
todos los ambientes, así que los accesos a pagos por lotes viven aquí y no en el
núcleo de Tesorería, que debe poder instalarse siempre.""",
    "version": "18.0.1.0.0",
    "category": "Accounting/Accounting",
    "author": "Steps Consulting",
    "license": "LGPL-3",
    "depends": ["step_account_treasury", "account_batch_payment"],
    "data": ["views/batch_menus.xml"],
    "auto_install": True,
    "installable": True,
}
