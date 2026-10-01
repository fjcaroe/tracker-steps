from odoo import api, fields, models


class HrExpenseSheet(models.Model):
    _inherit = "hr.expense.sheet"
    _rec_names_search = ["name", "folio"]

    folio = fields.Char(string="Folio", readonly=True, copy=False, index=True, default="Nuevo")
    step_notes = fields.Text(string="Notas")
    step_comment = fields.Text(string="Comentario")
    use_vehicle = fields.Boolean(string="Incluye uso de vehículo")
    vehicle_mode = fields.Selection(related="company_id.step_expense_vehicle_mode")
    show_vehicle = fields.Boolean(compute="_compute_show_vehicle")
    vehicle_line_ids = fields.One2many("step.expense.vehicle.line", "sheet_id", string="Uso de vehículo")

    @api.depends("use_vehicle", "company_id.step_expense_vehicle_mode", "vehicle_line_ids")
    def _compute_show_vehicle(self):
        for sheet in self:
            mode = sheet.company_id.step_expense_vehicle_mode or "optional"
            sheet.show_vehicle = mode == "always" or (
                mode == "optional" and (sheet.use_vehicle or bool(sheet.vehicle_line_ids))
            )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get("folio") or vals["folio"] == "Nuevo":
                vals["folio"] = self.env["ir.sequence"].next_by_code("step.expense.sheet.folio") or "Nuevo"
        return super().create(vals_list)

    def _report_currency_totals(self):
        self.ensure_one()
        totals = {}
        for line in self.expense_line_ids:
            totals[line.currency_id] = totals.get(line.currency_id, 0.0) + line.total_amount_currency
        return list(totals.items())

    def _report_rate(self, expense):
        if expense.total_amount_currency:
            return expense.total_amount / expense.total_amount_currency
        return 1.0

    def _get_expense_account_destination(self):
        self.ensure_one()
        if self.payment_mode == "own_account" and self.journal_id.default_account_id:
            return self.journal_id.default_account_id.id
        return super()._get_expense_account_destination()
