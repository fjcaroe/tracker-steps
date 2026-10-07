# -*- coding: utf-8 -*-
{
    "name": "Steps - Packing Fruta: traslado de lotes",
    "summary": "Traslado de lotes en Packing nativo, preservando la navegación histórica.",
    "description": """
Integra transferencias por lotes con Packing nativo y conserva los menús
anteriores bajo el historial administrativo definido por la política Steps.
Se instala automáticamente solo cuando sus dependencias ya están presentes.
""",
    "version": "18.0.1.0.1",
    "category": "Agriculture",
    "author": "Steps Consulting",
    "license": "LGPL-3",
    "depends": ["step_packing", "stock_picking_batch", "step_packing_operations", "step_environment_policy"],
    "data": ["views/menu.xml"],
    "auto_install": True,
    "installable": True,
}
