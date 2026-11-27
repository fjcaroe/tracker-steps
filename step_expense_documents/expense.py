from odoo import _, fields, models


class Expense(models.Model):
    _inherit = "hr.expense"

    document_count = fields.Integer(string="Documentos", compute="_compute_document_count")

    def _compute_document_count(self):
        expenses = self._origin.filtered("id")
        expenses.check_access("read")
        # The original count includes every linked document. The action itself keeps the reader's file permissions.
        grouped = self.env["documents.document"].sudo()._read_group(
            [("res_model", "=", self._name), ("res_id", "in", expenses.ids)], ["res_id"], ["__count"]
        )
        counts = dict(grouped)
        for expense in self:
            expense.document_count = counts.get(expense._origin.id, 0)

    def action_open_attachments(self):
        self.ensure_one()
        self.check_access("read")
        return {
            "name": _("Documentos"),
            "type": "ir.actions.act_window",
            "res_model": "documents.document",
            "domain": [("res_model", "=", self._name), ("res_id", "=", self.id)],
            "view_mode": "list,form",
            "views": [(self.env.ref("step_document_library.library_list").id, "list"),
                      (self.env.ref("step_document_library.library_form").id, "form")],
        }
