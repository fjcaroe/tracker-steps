from odoo import models

from ..hooks import FIELD_XMLID


SHARED_WIZARDS = {'hr.input.step.wizard', 'hr.entry.xls.wizard', 'success.message'}


def belongs_to_shared_wizard(alias):
    # Harvest and the native HR application both registered these transient
    # model identities before they moved into the payroll wizard provider.
    if alias.model in ('ir.model', 'ir.model.fields'):
        item = alias.env[alias.model].browse(alias.res_id).exists()
        return bool(item and item.model in SHARED_WIZARDS)
    if alias.model == 'ir.model.fields.selection':
        item = alias.env[alias.model].browse(alias.res_id).exists()
        return bool(item and item.field_id.model in SHARED_WIZARDS)
    return False


class HarvestIdentifiers(models.Model):
    _inherit = 'ir.model.data'

    def _step_retained_aliases(self):
        names = ('model_stock_picking', FIELD_XMLID)
        shared = self._step_transferred_names('step_cosecha', 'step_hr', belongs_to_shared_wizard)
        return [*super()._step_retained_aliases(), ('step_hr', 'step_cosecha', names),
                ('step_cosecha', 'step_hr', shared)]
