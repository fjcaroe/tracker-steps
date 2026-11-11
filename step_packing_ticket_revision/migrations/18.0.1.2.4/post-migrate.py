from odoo.addons.step_packing_ticket_revision.hooks import assign_dispatch_type_companies


def migrate(cr, version):
    cr.execute("""
        ALTER TABLE stock_picking
        DROP CONSTRAINT IF EXISTS stock_picking_external_reception_folio_unique
    """)
    assign_dispatch_type_companies(cr)
