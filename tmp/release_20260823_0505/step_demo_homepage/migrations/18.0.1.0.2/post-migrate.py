def migrate(cr, version):
    cr.execute(
        """
        UPDATE ir_ui_view AS target
           SET active = TRUE,
               name = source.name,
               arch_db = source.arch_db
          FROM ir_ui_view AS source
          JOIN ir_model_data AS data
            ON data.model = 'ir.ui.view'
           AND data.res_id = source.id
         WHERE data.module = 'website'
           AND data.name = 'homepage'
           AND target.key = 'website.homepage'
           AND target.id != source.id
        """
    )
