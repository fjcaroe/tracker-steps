"""Compatibility with the installed core's overly strict end-date validation."""
from collections import Counter
from odoo import api, models
from odoo.addons.step_hr_previred.tools import previred


class PreviredExtractor(models.AbstractModel):
    _inherit = 'step.previred.extractor'

    @api.model
    def build_dataset(self, *args, **kwargs):
        dataset = super().build_dataset(*args, **kwargs)
        return self._allow_open_ended_movements(dataset)

    def _allow_open_ended_movements(self, dataset):
        # The native form and supplier already permit an empty end date. Keep
        # the raw movement and exported row untouched, correcting only the
        # installed validator's false requirement for official codes 1 and 8.
        # No global monkey patch or temporary validator replacement is needed.
        obsolete = Counter()
        for record in dataset.records:
            label = 'RUT %s-%s' % (record.rut, record.dv)
            for row in record.annexes:
                if (len(row) != previred.FIELD_COUNT
                        or str(row[14] or '').strip().lstrip('0') not in ('1', '8')
                        or str(row[16] or '').strip() not in previred.NULL_DATE_TOKENS):
                    continue
                for issue in previred.validate_annex_conditions(
                        row, label, record.department_label):
                    if issue.code == 'movement_date_to_required':
                        obsolete[(issue.code, issue.message, issue.department)] += 1
        kept = []
        for issue in dataset.issues:
            key = (issue.code, issue.message, issue.department)
            if obsolete[key]:
                obsolete[key] -= 1
            else:
                kept.append(issue)
        dataset.issues = kept
        return dataset
