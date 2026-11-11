{
    "name": "Steps - Guías de despacho",
    "summary": "Guías de despacho con proveedor DTE tercero: traslado, transporte, flete, "
               "facturación de guías y libro de guías",
    "description": """
Módulo de guías de despacho (diseño 2.10 y complemento "versión sin CAF", ticket 25).

* Proveedor DTE por empresa: Tercero (folio emitido en otro sistema; la guía de
  Odoo es de uso interno) u Odoo (DTE 52 con CAF, aún no habilitado).
* Formulario del Anexo 1: destinatario, razón del traslado (códigos SII), tipo
  de despacho con regla de flete, fechas de salida y llegada, transportista y
  chofer desde Contactos, patentes desde Flota, detalle con empaque, lote,
  impuestos y distribución analítica, subtotal, exento, IVA y total.
* Paga flete: genera la OT de flete con el tramo indicado.
* Facturación de guías de venta, una o varias guías del mismo cliente por factura.
* Informes: estado de guías y libro de guías con el formato del SII.
* Se crea desde Inventario (entregas y traslados internos), desde Fletes y
  desde el propio módulo; Cosecha se integra con step_dispatch_guide_cosecha.
""",
    "version": "18.0.2.0.4",
    "category": "Inventory/Inventory",
    "author": "Steps Consulting",
    "license": "LGPL-3",
    "depends": ["stock", "account", "fleet", "step_operations_ui"],
    "data": [
        "security/ir.model.access.csv",
        "data/ir_sequence.xml",
        "data/transfer_reason_data.xml",
        "views/res_config_settings_views.xml",
        "views/dispatch_guide_views.xml",
        "views/stock_picking_views.xml",
        "views/freight_order_views.xml",
        "report/dispatch_guide_report.xml",
    ],
    "installable": True,
    "application": True,
}
