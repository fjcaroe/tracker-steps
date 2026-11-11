def migrate(cr, version):
    cr.execute("""
        ALTER TABLE stock_picking
        DROP CONSTRAINT IF EXISTS stock_picking_external_reception_folio_unique
    """)
