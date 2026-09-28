# -*- coding: utf-8 -*-
{
    "name": "Steps - Packing Fruta: traslado de lotes",
    "summary": "Agrega Traslado lotes (transferencias por lotes) a la app Packing Fruta.",
    "description": """
Puente entre step_packing y stock_picking_batch (ticket 34).

En Studio, la app Packing Fruta tenia el menu Operaciones > Traslado lotes.
Se deja en un modulo aparte que se instala solo cuando ambos modulos estan
presentes, para que step_packing no obligue a instalar stock_picking_batch
en instancias que no lo usan.
""",
    "version": "18.0.1.0.0",
    "category": "Agriculture",
    "author": "Steps Consulting",
    "license": "LGPL-3",
    "depends": ["step_packing", "stock_picking_batch"],
    "data": ["views/menu.xml"],
    "auto_install": True,
    "installable": True,
}
