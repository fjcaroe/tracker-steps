"""Make native model XML IDs portable from databases that used Studio first."""


def migrate(cr, version):
    # Odoo cannot safely unlink old selection values after the field has been
    # promoted to a relational agricultural master. Remove only that obsolete
    # metadata before the registry changes the field type; business records
    # remain untouched.
    cr.execute(
        """
        DELETE FROM ir_model_data
         WHERE model = 'ir.model.fields.selection'
           AND res_id IN (
               SELECT selection.id
                 FROM ir_model_fields_selection selection
                 JOIN ir_model_fields field ON field.id = selection.field_id
                WHERE field.model = 'x_riego_y_fertilizacio'
                  AND field.name = 'x_studio_tipo_de_aplicacin'
           )
        """
    )
    cr.execute(
        """
        DELETE FROM ir_model_fields_selection
         WHERE field_id IN (
             SELECT id
               FROM ir_model_fields
              WHERE model = 'x_riego_y_fertilizacio'
                AND name = 'x_studio_tipo_de_aplicacin'
         )
        """
    )

    model_names = (
        "x_riego_y_fertilizacio",
        "x_aplicacion_foliar",
        "x_monitoreo_agricola",
        "x_sector_de_riego",
        "x_tipo_de_aplicaciones",
        "x_objetivo_o_plaga",
        "x_estado_fenologico",
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
                "step_bpa_irrigation",
                f"model_{model_name}",
                model_name,
                "step_bpa_irrigation",
                f"model_{model_name}",
            ),
        )
