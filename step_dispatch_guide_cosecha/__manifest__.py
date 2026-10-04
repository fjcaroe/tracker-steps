{
    "name": "Steps - Guías de despacho desde Cosecha",
    "summary": "Crea la guía de traslado de fruta (campo a packing) desde la recepción de Cosecha",
    "description": """
Puente entre step_dispatch_guide y step_cosecha (ticket 25). El cliente pidió
priorizar la guía de traslado de fruta desde el campo al packing. Se instala
solo cuando ambos módulos están presentes.
""",
    "version": "18.0.1.0.0",
    "category": "Inventory/Inventory",
    "author": "Steps Consulting",
    "license": "LGPL-3",
    "depends": ["step_dispatch_guide", "step_cosecha"],
    "data": ["views/step_cosecha_recepcion_views.xml"],
    "auto_install": True,
    "installable": True,
}
