# -*- coding: utf-8 -*-
{
    "name": "Steps - Tesorería agrícola",
    "summary": "Agrega el fundo al flujo de caja donde exista el stack agrícola",
    "description": """Puente opcional. `step.fundo` sólo existe donde está instalado
`step_hr`; el núcleo de Tesorería no puede depender de él.""",
    "version": "18.0.1.0.0",
    "category": "Accounting/Accounting",
    "author": "Steps Consulting",
    "license": "LGPL-3",
    "depends": ["step_account_treasury", "step_hr"],
    "data": ["views/cashflow_agro_views.xml"],
    "auto_install": True,
    "installable": True,
}
