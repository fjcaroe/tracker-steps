def migrate(cr, version):
    cr.execute(
        """
        UPDATE ir_ui_view
           SET active = FALSE
         WHERE key = 'website.homepage'
           AND id != (
               SELECT res_id
                 FROM ir_model_data
                WHERE module = 'website'
                  AND name = 'homepage'
                  AND model = 'ir.ui.view'
                LIMIT 1
           )
        """
    )
