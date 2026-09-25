{
    "name": "Steps - Tarja de Fruta e Inventario",
    "summary": "Bodegas reales, tarja de fruta de exportación (paquetes) y campos OP/OT en Inventario",
    "description": """
        Implementa la porción autocontenida del ticket 22 (T22 Mejoras del
        módulo de Inventario) que no depende de módulos inexistentes
        (Guías de Despacho) ni de decisiones de arquitectura todavía
        pendientes (variantes de producto de fruta, marcado explícitamente
        "(pendiente)" en el documento de diseño del cliente):

        - Bodegas reales confirmadas por el cliente: se siembran Bodega
          Insumos y Bodega Fruta (las 2 que faltaban); Bodega BPA y Bodega
          Máquina ya existen con otro nombre técnico vía los módulos
          puente de los tickets 23/24 -- ver data/stock_location_data.xml.
        - Adapta el paquete nativo de Inventario (stock.quant.package) al
          concepto de "tarja de fruta de exportación": variantes
          (especie, variedad, calibre, calidad, categoría, clase, tipo de
          fruta, etiqueta) y datos de producción (tipo de proceso, línea,
          folio OP, OT, certificado, packing, cajas, kilos).
        - Reporte imprimible de la tarja con código QR.
        - Campos "Número OP" / "Número OT" en el formulario de Operaciones
          de Inventario (stock.picking).
    """,
    "version": "18.0.1.1.0",
    "author": "Steps Consulting",
    "category": "Inventory/Inventory",
    "license": "LGPL-3",
    "depends": ["stock", "step_hr", "step_management_costs"],
    "data": [
        "security/ir.model.access.csv",
        "data/stock_location_data.xml",
        "data/fruit_quality_data.xml",
        "views/stock_quant_package_views.xml",
        "views/stock_picking_views.xml",
        "views/fruit_quality_views.xml",
        "report/fruit_tag_report.xml",
    ],
    "installable": True,
    "application": False,
}
