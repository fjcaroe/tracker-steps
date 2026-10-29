"""Apply original type defaults only through explicit, prevalidated onchanges."""
from odoo import _, api, models
from odoo.exceptions import UserError


class Contract(models.Model):
    _inherit = "hr.contract"

    def _step_check_original_structure_type_policy(self):
        kinds = self.structure_type_id
        if kinds and not hasattr(kinds, "_step_check_original_type_policy"):
            raise UserError(_("Load the original payroll type adapter before selecting a structure type."))
        if kinds:
            kinds._step_check_original_type_policy()

    @api.onchange("structure_type_id")
    def _onchange_structure_type_id(self):
        # Guard before official Community can propose a different calendar.
        self._step_check_original_structure_type_policy()
        return super()._onchange_structure_type_id()

    @api.onchange("structure_type_id")
    def _onchange_simpledigital_structure_type(self):
        # Guard before StepBase assigns the actual default structure. No type
        # default is copied when reading a contract or closed payroll history.
        self._step_check_original_structure_type_policy()
        result = super()._onchange_simpledigital_structure_type()
        for contract in self.filtered("structure_type_id"):
            if contract.structure_type_id.default_schedule_pay:
                contract.schedule_pay = contract.structure_type_id.default_schedule_pay
            contract.wage_type = contract.structure_type_id.wage_type
        return result
