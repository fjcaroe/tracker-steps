from odoo import models


class CategoryIdentifiers(models.Model):
    _inherit = 'ir.model.data'

    def _step_retained_aliases(self):
        names = (
            'field_step_packing_process_type__step_category',
            'selection__step_packing_process_type__step_category__selection',
            'selection__step_packing_process_type__step_category__packing',
            'selection__step_packing_process_type__step_category__correction',
        )
        return [*super()._step_retained_aliases(), ('step_packing_operations', 'step_packing_process_category', names)]
