"""Initialize the new editable default without relabeling historical stock."""


def migrate(cr, version):
    cr.execute("""
        UPDATE step_packing_production
           SET step_output_lot_name = name
         WHERE state IN ('created', 'validated')
           AND (step_output_lot_name IS NULL OR step_output_lot_name = '')
    """)
