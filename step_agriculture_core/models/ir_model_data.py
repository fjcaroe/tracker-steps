from odoo import models
from odoo.exceptions import ValidationError

from ..hooks import _owned


class ExternalIdentifiers(models.Model):
    _inherit = 'ir.model.data'

    def _step_retained_aliases(self):
        # A None name set denotes the identities the two namespaces already
        # share. A nonempty tuple narrows this to named, versioned records.
        return [('step_hr', 'step_agriculture_core', None)]

    def _process_end(self, modules):
        for legacy, owner, names in self._step_retained_aliases():
            if legacy not in (modules or ()):
                continue
            names = list(names) if names is not None else None
            self.env.cr.execute("""
                SELECT original.id, original.name, original.model, original.res_id, adopted.model, adopted.res_id
                  FROM ir_model_data AS original
                  JOIN ir_model_data AS adopted ON adopted.module=%s AND adopted.name=original.name
                 WHERE original.module=%s AND NOT original.noupdate
                   AND (%s::text[] IS NULL OR original.name=ANY(%s::text[]))
            """, (owner, legacy, names, names))
            for source_id, name, model, record_id, adopted_model, adopted_id in self.env.cr.fetchall():
                if (names is None and legacy == 'step_hr' and owner == 'step_agriculture_core'
                        and not _owned(self.browse(source_id))):
                    # The standalone core also defines distinct menus with names in common.
                    continue
                if (model, record_id) != (adopted_model, adopted_id):
                    raise ValidationError('El identificador original cambió de registro: ' + legacy + '.' + name)
                # Odoo's normal cleanup keeps declared XML IDs. This retains
                # the old name without modifying the original noupdate flag.
                self.pool.loaded_xmlids.add(legacy + '.' + name)
        return super()._process_end(modules)
