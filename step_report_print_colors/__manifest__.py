{
    "name": "Steps — Colores de impresión",
    "summary": "Conserva los tonos del texto en los documentos comerciales históricos.",
    "version": "18.0.1.0.0",
    "author": "Steps",
    "license": "LGPL-3",
    "depends": ["web"],
    "assets": {
        "web.report_assets_common": [
            ("prepend", "step_report_print_colors/static/src/scss/print_colors.scss"),
        ],
    },
    "installable": True,
}
