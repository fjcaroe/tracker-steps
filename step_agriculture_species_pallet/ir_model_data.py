from odoo import models


class SpeciesIdentifiers(models.Model):
    _inherit = 'ir.model.data'

    def _step_retained_aliases(self):
        names = (
            'field_step_especie__sag_code',
            'field_step_especie__base_boxes_per_pallet',
            'constraint_step_especie_base_boxes_per_pallet_nonnegative',
        )
        return [*super()._step_retained_aliases(), ('step_producer_fruit_reports', 'step_agriculture_species_pallet', names)]
