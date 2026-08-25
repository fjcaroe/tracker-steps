"""Make native freight model XML IDs portable from Studio databases."""


def migrate(cr, version):
    model_names = (
        "x_orden_de_flete",
        "x_contabilizacion_de_f",
        "x_tarifa_de_fletes",
        "x_rastreo_camiones",
        "x_tramo_de_flete",
        "x_modalidad_de_frio",
    )
    for model_name in model_names:
        cr.execute(
            """
            INSERT INTO ir_model_data (module, name, model, res_id, noupdate)
            SELECT %s, %s, 'ir.model', id, TRUE
              FROM ir_model
             WHERE model = %s
               AND NOT EXISTS (
                   SELECT 1
                     FROM ir_model_data
                    WHERE module = %s AND name = %s
               )
            """,
            (
                "step_operations_ui",
                f"model_{model_name}",
                model_name,
                "step_operations_ui",
                f"model_{model_name}",
            ),
        )
