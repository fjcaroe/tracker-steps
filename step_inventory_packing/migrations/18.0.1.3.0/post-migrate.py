"""Move the recorded header variety to existing receipt rows without rewriting history."""


def migrate(cr, version):
    cr.execute("""
        UPDATE step_packing_picking_tag_line l
           SET variety_id=COALESCE(p.fruit_variety_id,
               (SELECT q.variedad_id FROM stock_quant_package q WHERE q.id=l.package_id))
          FROM stock_picking p
         WHERE p.id=l.picking_id AND p.step_fruit_reception_kind IN ('process','packed')
           AND l.variety_id IS NULL
           AND COALESCE(p.fruit_variety_id,
               (SELECT q.variedad_id FROM stock_quant_package q WHERE q.id=l.package_id)) IS NOT NULL
    """)
