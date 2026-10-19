"""Preserve legacy related master values when SAG becomes independent of one OT."""
def migrate(cr, version):
    cr.execute('''UPDATE step_packing_inspection i
        SET sag_species_id=p.fruit_species_id, sag_packing_id=p.packing_partner_id
        FROM step_packing_production p WHERE i.production_id=p.id
        AND i.sag_species_id IS NULL AND i.sag_packing_id IS NULL''')
