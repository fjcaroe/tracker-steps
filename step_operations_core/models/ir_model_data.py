from odoo import models

from ..hooks import CORE, LEGACY, _owned


class ExternalIdentifiers(models.Model):
    _inherit = 'ir.model.data'

    def _step_transferred_names(self, legacy, owner, owns):
        # Select only writable originals. Odoo already retains noupdate rows.
        self.env.cr.execute("""
            SELECT source.id
              FROM ir_model_data source
              JOIN ir_model_data adopted ON adopted.module=%s AND adopted.name=source.name
             WHERE source.module=%s AND NOT source.noupdate
             ORDER BY source.id
        """, (owner, legacy))
        originals = self.browse([row[0] for row in self.env.cr.fetchall()])
        return tuple(record.name for record in originals if owns(record))

    def _step_retained_aliases(self):
        names = self._step_transferred_names(LEGACY, CORE, _owned)
        return [*super()._step_retained_aliases(), (LEGACY, CORE, names)]
