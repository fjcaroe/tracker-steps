def migrate(cr, version):
    cr.execute("""
        UPDATE purchase_order SET step_advance_basis = 'processed'
        WHERE step_advance_proforma AND step_advance_basis IS NULL
    """)
