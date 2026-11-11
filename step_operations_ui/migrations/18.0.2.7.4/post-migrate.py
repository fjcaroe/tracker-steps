def migrate(cr, version):
    cr.execute("""
        INSERT INTO step_freight_dispatch_type_company_rel (dispatch_type_id, company_id)
        SELECT t.id, t.company_id
          FROM step_freight_dispatch_type t
         WHERE NOT EXISTS (
             SELECT 1 FROM ir_model_data d
              WHERE d.module = 'step_operations_ui' AND d.model = 'step.freight.dispatch.type'
                AND d.name IN ('freight_dispatch_type_retira_cliente', 'freight_dispatch_type_despacho_cliente',
                               'freight_dispatch_type_despacho_tercero') AND d.res_id = t.id
         )
        ON CONFLICT DO NOTHING
    """)
    cr.execute("SELECT to_regclass('step_dispatch_guide')")
    if cr.fetchone()[0]:
        cr.execute("""
            INSERT INTO step_freight_dispatch_type_company_rel (dispatch_type_id, company_id)
            SELECT DISTINCT g.dispatch_type_id, g.company_id
              FROM step_dispatch_guide g
             WHERE g.company_id IS NOT NULL AND g.dispatch_type_id IN (
                 SELECT dispatch_type_id FROM step_freight_dispatch_type_company_rel
             )
            ON CONFLICT DO NOTHING
        """)
